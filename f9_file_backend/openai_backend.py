"""OpenAI vector store backed file backend implementation."""

from __future__ import annotations

import io
import time
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

from .interfaces import (
    AlreadyExistsError,
    FileBackend,
    FileBackendError,
    FileInfo,
    InvalidOperationError,
    NotFoundError,
    PathLike,
)


@dataclass
class _RemoteEntry:
    """Internal representation of a vector store file entry."""

    path: str
    is_dir: bool
    size: int
    created_at: datetime | None
    modified_at: datetime | None
    file_id: str


class OpenAIBackendError(FileBackendError):
    """Error raised when OpenAI API operations fail."""

    @classmethod
    def missing_dependency(cls) -> OpenAIBackendError:
        """Return an error indicating the openai package is unavailable."""
        return cls("Install the 'openai' package to use OpenAIVectorStoreFileBackend")

    @classmethod
    def sync_failed(cls) -> OpenAIBackendError:
        """Return an error indicating a synchronisation issue."""
        return cls("Failed to synchronise vector store state")

    @classmethod
    def upload_failed(cls, path: str) -> OpenAIBackendError:
        """Return an error describing an upload failure for a path."""
        return cls(f"Failed to upload {path} to OpenAI")

    @classmethod
    def attach_failed(cls, path: str) -> OpenAIBackendError:
        """Return an error describing a vector store attachment failure."""
        return cls(f"Failed to attach {path} to vector store")

    @classmethod
    def detach_failed(cls, path: str) -> OpenAIBackendError:
        """Return an error describing a detachment failure."""
        return cls(f"Failed to detach {path} from vector store")

    @classmethod
    def delete_failed(cls, path: str) -> OpenAIBackendError:
        """Return an error describing a delete failure."""
        return cls(f"Failed to delete {path} from OpenAI files")

    @classmethod
    def download_failed(
        cls,
        path: str,
        payload_type: str | None = None,
    ) -> OpenAIBackendError:
        """Return an error describing a download failure."""
        if payload_type:
            return cls(f"Unexpected content type for {path}: {payload_type}")
        return cls(f"Failed to download {path} from OpenAI")


class OpenAIVectorStoreFileBackend(FileBackend):
    """File backend backed by an OpenAI vector store."""

    def __init__(
        self,
        connection_info: Mapping[str, Any],
        *,
        client: Any | None = None,
    ) -> None:
        """Initialise the backend using OpenAI connection parameters."""
        if not isinstance(connection_info, Mapping):
            message = "connection_info must be a mapping"
            raise TypeError(message)
        if "vector_store_id" not in connection_info:
            message = "Missing 'vector_store_id' in connection_info"
            raise ValueError(message)

        self._vector_store_id = str(connection_info["vector_store_id"])
        self._purpose = str(connection_info.get("purpose", "assistants"))
        self._sync_interval = float(connection_info.get("cache_ttl", 0.0))
        self._index: dict[str, _RemoteEntry] = {}
        self._last_synced: float | None = None

        if client is not None:
            self._client = client
        else:
            api_key = connection_info.get("api_key")
            if api_key is None:
                message = "Missing 'api_key' in connection_info"
                raise ValueError(message)
            try:
                from openai import OpenAI  # type: ignore import-not-found
            except ImportError as exc:  # pragma: no cover
                raise OpenAIBackendError.missing_dependency() from exc
            self._client = OpenAI(api_key=str(api_key))

    def create(
        self,
        path: PathLike,
        *,
        data: bytes | str | BinaryIO | None = None,
        is_directory: bool = False,
        overwrite: bool = False,
    ) -> FileInfo:
        """Create a file or directory within the vector store."""
        path_str = self._normalise_path(path)
        self._ensure_index()

        if is_directory:
            return self._create_directory(path_str)

        payload = self._coerce_bytes(data) if data is not None else b""
        self._ensure_parent_directories(path_str)

        existing = self._index.get(path_str)
        if existing:
            if existing.is_dir:
                raise InvalidOperationError.cannot_overwrite_directory_with_file(
                    path_str,
                )
            if not overwrite:
                raise AlreadyExistsError(path_str)
            self._remove_entry(existing)

        entry = self._persist_entry(path_str, payload, is_dir=False)
        return self._entry_to_info(entry)

    def read(
        self,
        path: PathLike,
        *,
        binary: bool = True,
    ) -> bytes | str:
        """Retrieve file contents from the vector store."""
        path_str = self._normalise_path(path)
        self._ensure_index()

        entry = self._index.get(path_str)
        if entry is None:
            raise NotFoundError(path_str)
        if entry.is_dir:
            raise InvalidOperationError.cannot_read_directory(path_str)

        payload = self._download_entry(entry)
        if binary:
            return payload
        return payload.decode("utf-8")

    def update(
        self,
        path: PathLike,
        *,
        data: bytes | str | BinaryIO,
        append: bool = False,
    ) -> FileInfo:
        """Update an existing file, optionally appending to the content."""
        path_str = self._normalise_path(path)
        self._ensure_index()

        entry = self._index.get(path_str)
        if entry is None:
            raise NotFoundError(path_str)
        if entry.is_dir:
            raise InvalidOperationError.cannot_update_directory(path_str)

        incoming = self._coerce_bytes(data)
        if append:
            current = self._download_entry(entry)
            payload = current + incoming
        else:
            payload = incoming

        self._remove_entry(entry)
        new_entry = self._persist_entry(path_str, payload, is_dir=False)
        return self._entry_to_info(new_entry)

    def delete(self, path: PathLike, *, recursive: bool = False) -> None:
        """Delete a file or directory from the vector store."""
        path_str = self._normalise_path(path)
        self._ensure_index()

        entry = self._index.get(path_str)
        if entry is None:
            raise NotFoundError(path_str)

        if entry.is_dir:
            descendants = self._descendant_entries(path_str)
            if descendants and not recursive:
                raise InvalidOperationError.directory_not_empty(path_str)
            for descendant in descendants:
                self._remove_entry(descendant)
            self._remove_entry(entry)
            return

        self._remove_entry(entry)

    def info(self, path: PathLike) -> FileInfo:
        """Return metadata about a stored file or directory."""
        path_str = self._normalise_path(path)
        self._ensure_index()

        entry = self._index.get(path_str)
        if entry is None:
            raise NotFoundError(path_str)
        return self._entry_to_info(entry)

    def _create_directory(self, path: str) -> FileInfo:
        """Create or return an existing directory placeholder."""
        self._ensure_parent_directories(path)
        existing = self._index.get(path)
        if existing:
            if not existing.is_dir:
                raise InvalidOperationError.cannot_overwrite_file_with_directory(path)
            return self._entry_to_info(existing)

        entry = self._persist_entry(path, b"", is_dir=True)
        return self._entry_to_info(entry)

    def _ensure_parent_directories(self, path: str) -> None:
        """Ensure directory placeholders exist for all parent paths."""
        pure = PurePosixPath(path)
        parents: list[str] = []
        current = pure.parent
        while current not in {PurePosixPath(""), PurePosixPath(".")}:
            parents.append(current.as_posix())
            current = current.parent
        for directory in reversed(parents):
            existing = self._index.get(directory)
            if existing:
                if not existing.is_dir:
                    raise InvalidOperationError.parent_path_not_directory(directory)
                continue
            self._persist_entry(directory, b"", is_dir=True)

    def _descendant_entries(self, path: str) -> list[_RemoteEntry]:
        """Return entries whose paths reside under the provided directory."""
        prefix = f"{path}/"
        entries = [
            entry
            for candidate, entry in self._index.items()
            if candidate.startswith(prefix)
        ]
        entries.sort(key=lambda item: item.path.count("/"), reverse=True)
        return entries

    def _ensure_index(self) -> None:
        """Refresh the local index when stale or caching disabled."""
        if self._sync_interval <= 0:
            self._refresh_index()
            return
        now = time.time()
        if self._last_synced is None or now - self._last_synced >= self._sync_interval:
            self._refresh_index()

    def _refresh_index(self) -> None:
        """Synchronise the local index with the vector store."""
        entries: dict[str, _RemoteEntry] = {}
        try:
            after: str | None = None
            while True:
                response = self._client.beta.vector_stores.files.list(
                    vector_store_id=self._vector_store_id,
                    limit=200,
                    after=after,
                )
                for item in getattr(response, "data", []):
                    file_id = getattr(item, "file_id", None)
                    if not file_id:
                        continue
                    file_obj = self._client.files.retrieve(file_id)
                    metadata = dict(getattr(file_obj, "metadata", {}) or {})
                    path_value = metadata.get("path")
                    if not path_value:
                        continue
                    is_dir = _metadata_to_bool(metadata.get("is_dir"))
                    size = _metadata_to_int(metadata.get("size"))
                    raw_size = getattr(file_obj, "bytes", 0) or 0
                    created_at = _timestamp_to_datetime(
                        getattr(file_obj, "created_at", None),
                    )
                    modified = metadata.get("modified_at")
                    entry = _RemoteEntry(
                        path=path_value,
                        is_dir=is_dir,
                        size=0
                        if is_dir
                        else (size if size is not None else int(raw_size)),
                        created_at=created_at,
                        modified_at=_timestamp_to_datetime(modified)
                        if modified
                        else created_at,
                        file_id=file_id,
                    )
                    entries[path_value] = entry

                if not getattr(response, "has_more", False):
                    break
                after = getattr(response, "last_id", None) or getattr(
                    getattr(response, "data", [])[-1],
                    "id",
                    None,
                )
                if after is None:
                    break
        except Exception as exc:  # pragma: no cover - defensive wrapper
            raise OpenAIBackendError.sync_failed() from exc

        self._index = entries
        self._last_synced = time.time()

    def _persist_entry(
        self,
        path: str,
        payload: bytes,
        *,
        is_dir: bool,
    ) -> _RemoteEntry:
        """Upload content and attach it to the vector store."""
        metadata = {
            "path": path,
            "is_dir": "true" if is_dir else "false",
            "size": str(0 if is_dir else len(payload)),
            "modified_at": str(time.time()),
        }
        filename = self._filename_for_path(path, is_dir=is_dir)
        try:
            file_obj = self._client.files.create(
                file=io.BytesIO(payload),
                purpose=self._purpose,
                filename=filename,
                metadata=metadata,
            )
        except TypeError:
            file_obj = self._client.files.create(
                file=io.BytesIO(payload),
                purpose=self._purpose,
                metadata=metadata,
            )
        except Exception as exc:
            raise OpenAIBackendError.upload_failed(path) from exc

        try:
            self._client.beta.vector_stores.files.create(
                vector_store_id=self._vector_store_id,
                file_id=file_obj.id,
            )
        except Exception as exc:
            raise OpenAIBackendError.attach_failed(path) from exc

        created_at = _timestamp_to_datetime(getattr(file_obj, "created_at", None))
        modified_at = _timestamp_to_datetime(metadata["modified_at"])
        entry = _RemoteEntry(
            path=path,
            is_dir=is_dir,
            size=0 if is_dir else len(payload),
            created_at=created_at,
            modified_at=modified_at,
            file_id=file_obj.id,
        )
        self._index[path] = entry
        self._last_synced = time.time()
        return entry

    def _remove_entry(self, entry: _RemoteEntry) -> None:
        """Detach a vector store entry and delete the underlying file."""
        try:
            self._client.beta.vector_stores.files.delete(
                vector_store_id=self._vector_store_id,
                file_id=entry.file_id,
            )
        except Exception as exc:
            raise OpenAIBackendError.detach_failed(entry.path) from exc

        try:
            self._client.files.delete(entry.file_id)
        except Exception as exc:
            raise OpenAIBackendError.delete_failed(entry.path) from exc

        existing = self._index.get(entry.path)
        if existing and existing.file_id == entry.file_id:
            self._index.pop(entry.path, None)
        self._last_synced = time.time()

    def _download_entry(self, entry: _RemoteEntry) -> bytes:
        """Retrieve raw bytes for the provided entry."""
        try:
            response = self._client.files.content(entry.file_id)
        except Exception as exc:
            raise OpenAIBackendError.download_failed(entry.path) from exc

        if hasattr(response, "read"):
            payload = response.read()
        else:
            payload = response
        if isinstance(payload, str):
            return payload.encode("utf-8")
        if isinstance(payload, bytes):
            return payload
        if isinstance(payload, bytearray):
            return bytes(payload)
        payload_type = type(payload).__name__
        raise OpenAIBackendError.download_failed(entry.path, payload_type)

    @staticmethod
    def _filename_for_path(path: str, *, is_dir: bool) -> str:
        """Construct a filename for uploads based on the logical path."""
        candidate = path.rsplit("/", 1)[-1] or "root"
        if is_dir:
            return f"{candidate}.dir"
        return candidate

    def _entry_to_info(self, entry: _RemoteEntry) -> FileInfo:
        """Convert an internal entry to public FileInfo."""
        return FileInfo(
            path=Path(entry.path),
            is_dir=entry.is_dir,
            size=entry.size,
            created_at=entry.created_at,
            modified_at=entry.modified_at,
        )

    @staticmethod
    def _coerce_bytes(data: bytes | str | BinaryIO) -> bytes:
        """Coerce supported input types to raw bytes."""
        if isinstance(data, bytes):
            return data
        if isinstance(data, str):
            return data.encode("utf-8")
        if isinstance(data, io.BufferedIOBase):
            return data.read()
        if isinstance(data, io.RawIOBase):
            return data.read()
        if hasattr(data, "read"):
            return data.read()
        message = f"Unsupported data type: {type(data).__name__}"
        raise TypeError(message)

    @staticmethod
    def _normalise_path(path: PathLike) -> str:
        """Normalise user-provided paths to POSIX-encoded relative paths."""
        path_str = str(path).replace("\\", "/")
        if not path_str or path_str.strip() == "":
            raise InvalidOperationError.empty_path_not_allowed(path)
        pure = PurePosixPath(path_str)
        if pure.is_absolute() or any(part == ".." for part in pure.parts):
            raise InvalidOperationError.path_outside_root(path_str)
        normalised = pure.as_posix()
        if normalised == ".":
            raise InvalidOperationError.root_path_not_allowed(path)
        return normalised


def _metadata_to_bool(value: Any) -> bool:
    """Return metadata values coerced to boolean with a safe default."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == "true"
    return False


def _metadata_to_int(value: Any) -> int | None:
    """Convert metadata values to integers when possible."""
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _timestamp_to_datetime(value: Any) -> datetime | None:
    """Convert timestamps (float/int/str) to timezone aware datetimes."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(numeric, tz=timezone.utc)
