"""OpenAI vector store backed file backend implementation."""

from __future__ import annotations

import base64
import hashlib
import inspect
import io
import mimetypes
import time
from typing import TYPE_CHECKING, Any, BinaryIO

from .interfaces import (
    DEFAULT_CHUNK_SIZE,
    AlreadyExistsError,
    ChecksumAlgorithm,
    FileBackend,
    FileBackendError,
    FileInfo,
    InvalidOperationError,
    NotFoundError,
    PathLike,
)
from .utils import accumulate_chunks, coerce_to_bytes, compute_checksum_from_bytes

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping
else:
    from collections.abc import Mapping

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


@dataclass
class _RemoteEntry:
    """Internal representation of a vector store file entry."""

    path: str
    is_dir: bool
    size: int
    created_at: datetime | None
    modified_at: datetime | None
    file_id: str
    encoding: str | None = None


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

        try:
            create_params = inspect.signature(self._client.files.create).parameters
        except (TypeError, ValueError):
            create_params = {}
        self._files_create_supports_filename = "filename" in create_params
        self._files_create_supports_metadata = "metadata" in create_params
        self._vector_files_supports_attributes: bool | None = None

        self._allowed_upload_mimetypes: set[str] = {
            "application/csv",
            "application/json",
            "application/msword",
            "application/octet-stream",
            "application/pdf",
            "application/typescript",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/xml",
            "application/x-tar",
            "application/zip",
            "image/gif",
            "image/jpeg",
            "image/png",
            "image/webp",
            "text/css",
            "text/csv",
            "text/html",
            "text/javascript",
            "text/markdown",
            "text/plain",
            "text/x-c",
            "text/x-c++",
            "text/x-csharp",
            "text/x-java",
            "text/x-php",
            "text/x-python",
            "text/x-ruby",
            "text/x-script.python",
            "text/x-sh",
            "text/x-tex",
            "text/x-typescript",
            "text/xml",
        }

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

    def stream_read(
        self,
        path: PathLike,
        *,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        binary: bool = True,
    ) -> Iterator[bytes | str]:
        """Stream file contents in chunks from the vector store."""
        path_str = self._normalise_path(path)
        self._ensure_index()

        entry = self._index.get(path_str)
        if entry is None:
            raise NotFoundError(path_str)
        if entry.is_dir:
            raise InvalidOperationError.cannot_read_directory(path_str)

        payload = self._download_entry(entry)

        for i in range(0, len(payload), chunk_size):
            chunk = payload[i : i + chunk_size]
            if binary:
                yield chunk
            else:
                yield chunk.decode("utf-8")

    def stream_write(
        self,
        path: PathLike,
        *,
        chunk_source: Iterator[bytes | str] | BinaryIO,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overwrite: bool = False,
    ) -> FileInfo:
        """Write file from stream to the vector store."""
        path_str = self._normalise_path(path)
        self._ensure_index()

        existing = self._index.get(path_str)
        if existing:
            if existing.is_dir:
                raise InvalidOperationError.cannot_overwrite_directory_with_file(
                    path_str,
                )
            if not overwrite:
                raise AlreadyExistsError(path_str)
            self._remove_entry(existing)

        self._ensure_parent_directories(path_str)

        payload = accumulate_chunks(chunk_source, chunk_size)
        entry = self._persist_entry(path_str, payload, is_dir=False)
        return self._entry_to_info(entry)

    def checksum(
        self,
        path: PathLike,
        *,
        algorithm: ChecksumAlgorithm = "sha256",
    ) -> str:
        """Compute a file checksum using the specified algorithm."""
        self._ensure_index()
        path_str = self._normalise_path(path)

        entry = self._index.get(path_str)
        if not entry:
            raise NotFoundError(path_str)
        if entry.is_dir:
            raise InvalidOperationError.cannot_read_directory(path_str)

        # Download the file content and compute checksum
        payload = self._download_file_content(entry.file_id)
        return self._compute_checksum(payload, algorithm)

    def checksum_many(
        self,
        paths: list[PathLike],
        *,
        algorithm: ChecksumAlgorithm = "sha256",
    ) -> dict[str, str]:
        """Compute checksums for multiple files in batch."""
        self._ensure_index()
        result = {}

        for path in paths:
            try:
                path_str = self._normalise_path(path)
                entry = self._index.get(path_str)
                if entry and not entry.is_dir:
                    payload = self._download_file_content(entry.file_id)
                    result[str(path)] = self._compute_checksum(payload, algorithm)
            except (NotFoundError, InvalidOperationError):
                # Skip missing files and directories
                pass

        return result

    def _compute_checksum(
        self,
        payload: bytes,
        algorithm: ChecksumAlgorithm,
    ) -> str:
        """Compute the checksum of binary data using the specified algorithm."""
        return compute_checksum_from_bytes(payload, algorithm=algorithm)

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

    def _vector_store_files_resource(self) -> Any | None:
        """Return the vector store files resource, handling SDK variations."""
        latest = getattr(self._client, "vector_stores", None)
        files = getattr(latest, "files", None) if latest else None
        if files is not None:
            self._maybe_cache_vector_file_capabilities(files)
            return files

        beta = getattr(self._client, "beta", None)
        if beta is not None:
            vector = getattr(beta, "vector_stores", None)
            if vector is not None:
                files = getattr(vector, "files", None)
                if files is not None:
                    self._maybe_cache_vector_file_capabilities(files)
                    return files

        return None

    def _maybe_cache_vector_file_capabilities(self, files: Any) -> None:
        """Detect whether the SDK supports vector store file attributes."""
        if self._vector_files_supports_attributes is not None:
            return
        try:
            create_params = inspect.signature(files.create).parameters
        except (AttributeError, TypeError, ValueError):
            self._vector_files_supports_attributes = False
            return
        self._vector_files_supports_attributes = "attributes" in create_params

    def _refresh_index(self) -> None:
        """Synchronise the local index with the vector store."""
        entries: dict[str, _RemoteEntry] = {}
        try:
            files_resource = self._vector_store_files_resource()
            if files_resource is None:
                raise OpenAIBackendError.sync_failed()

            after: str | None = None
            while True:
                kwargs = {
                    "vector_store_id": self._vector_store_id,
                    # OpenAI REST currently caps vector store file pagination at 100.
                    "limit": 100,
                }
                if after is not None:
                    kwargs["after"] = after
                response = files_resource.list(**kwargs)
                for item in getattr(response, "data", []):
                    file_id = getattr(item, "file_id", None)
                    if not file_id:
                        file_id = getattr(item, "id", None)
                    if not file_id:
                        continue
                    try:
                        file_obj = self._client.files.retrieve(file_id)
                    except Exception as exc:
                        if _is_not_found_error(exc):
                            continue
                        raise
                    metadata = dict(getattr(file_obj, "metadata", {}) or {})
                    raw_attributes = getattr(item, "attributes", None) or {}
                    if isinstance(raw_attributes, Mapping):
                        attributes = dict(raw_attributes)
                    else:
                        attributes = {}

                    path_value = attributes.get("path") or metadata.get("path")
                    if not path_value:
                        continue
                    is_dir = _metadata_to_bool(attributes.get("is_dir"))
                    if "is_dir" not in attributes:
                        is_dir = _metadata_to_bool(metadata.get("is_dir"))
                    size_value = attributes.get("size")
                    size = _metadata_to_int(size_value)
                    if size is None:
                        size = _metadata_to_int(metadata.get("size"))
                    raw_size = getattr(file_obj, "bytes", 0) or 0
                    created_at = _timestamp_to_datetime(
                        getattr(file_obj, "created_at", None),
                    )
                    modified_value = attributes.get("modified_at")
                    if modified_value is None:
                        modified_value = metadata.get("modified_at")
                    modified_at = (
                        _timestamp_to_datetime(modified_value)
                        if modified_value is not None
                        else created_at
                    )
                    encoding_value = attributes.get("encoding")
                    if encoding_value is None:
                        encoding_value = metadata.get("encoding")
                    entry = _RemoteEntry(
                        path=path_value,
                        is_dir=is_dir,
                        size=0
                        if is_dir
                        else (size if size is not None else int(raw_size)),
                        created_at=created_at,
                        modified_at=modified_at,
                        file_id=file_id,
                        encoding=str(encoding_value)
                        if encoding_value is not None
                        else None,
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
        modified_timestamp = time.time()
        encoding = "raw"
        metadata = {
            "path": path,
            "is_dir": "true" if is_dir else "false",
            "size": str(0 if is_dir else len(payload)),
            "modified_at": str(modified_timestamp),
            "encoding": encoding,
        }
        attributes_payload = {
            "path": path,
            "is_dir": is_dir,
            "size": 0 if is_dir else len(payload),
            "modified_at": modified_timestamp,
            "encoding": encoding,
        }

        def _create_remote_file(data: bytes, name: str, meta: dict[str, str]) -> Any:
            upload_kwargs: dict[str, Any] = {
                "file": io.BytesIO(data),
                "purpose": self._purpose,
            }
            if self._files_create_supports_filename:
                upload_kwargs["filename"] = name
            if self._files_create_supports_metadata:
                upload_kwargs["metadata"] = meta
            try:
                return self._client.files.create(**upload_kwargs)
            except TypeError:
                upload_kwargs.pop("metadata", None)
                try:
                    return self._client.files.create(**upload_kwargs)
                except TypeError:
                    upload_kwargs.pop("filename", None)
                    return self._client.files.create(**upload_kwargs)

        upload_payload = payload if not is_dir else b"# directory placeholder\n"
        filename = self._upload_filename(path, upload_payload, is_dir=is_dir)

        try:
            file_obj = _create_remote_file(upload_payload, filename, metadata)
        except Exception as exc:
            if (
                not is_dir
                and encoding == "raw"
                and _is_invalid_mimetype_error(exc)
            ):
                encoding = "base64"
                metadata["encoding"] = encoding
                attributes_payload["encoding"] = encoding
                upload_payload = base64.b64encode(payload)
                filename = self._upload_filename(path, upload_payload, is_dir=is_dir)
                try:
                    file_obj = _create_remote_file(upload_payload, filename, metadata)
                except Exception as retry_exc:
                    raise OpenAIBackendError.upload_failed(path) from retry_exc
            else:
                raise OpenAIBackendError.upload_failed(path) from exc

        file_id = getattr(file_obj, "id", None) or getattr(file_obj, "file_id", None)
        if file_id is None:
            raise OpenAIBackendError.upload_failed(path)

        try:
            files_resource = self._vector_store_files_resource()
            if files_resource is None:
                raise OpenAIBackendError.attach_failed(path)
            attach_kwargs = {
                "vector_store_id": self._vector_store_id,
                "file_id": file_id,
            }
            if self._vector_files_supports_attributes:
                attach_kwargs["attributes"] = attributes_payload
            elif not self._files_create_supports_metadata:
                raise OpenAIBackendError.attach_failed(path)
            files_resource.create(**attach_kwargs)
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
            file_id=file_id,
            encoding=encoding,
        )
        self._index[path] = entry
        self._last_synced = time.time()
        return entry

    def _remove_entry(self, entry: _RemoteEntry) -> None:
        """Detach a vector store entry and delete the underlying file."""
        try:
            files_resource = self._vector_store_files_resource()
            if files_resource is None:
                raise OpenAIBackendError.detach_failed(entry.path)
            files_resource.delete(
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
            raw_bytes = payload.encode("utf-8")
        elif isinstance(payload, bytes):
            raw_bytes = payload
        elif isinstance(payload, bytearray):
            raw_bytes = bytes(payload)
        else:
            payload_type = type(payload).__name__
            raise OpenAIBackendError.download_failed(entry.path, payload_type)

        if entry.encoding == "base64" and not entry.is_dir:
            try:
                return base64.b64decode(raw_bytes, validate=True)
            except Exception as exc:
                raise OpenAIBackendError.download_failed(entry.path, "base64") from exc

        return raw_bytes

    def _upload_filename(self, path: str, payload: bytes, *, is_dir: bool) -> str:
        """Return a filename that yields an allowed MIME type for upload."""
        candidate = self._canonical_filename(path, is_dir=is_dir)
        if self._filename_mimetype_allowed(candidate):
            return candidate

        suffix = ".txt" if self._looks_like_text(payload) else ".bin"
        digest_bytes = hashlib.sha1(
            path.encode("utf-8"),
            usedforsecurity=False,
        ).hexdigest()
        digest = digest_bytes[:8]
        base = PurePosixPath(path).name or "root"
        fallback = f"{base}-{digest}{suffix}"
        if self._filename_mimetype_allowed(fallback):
            return fallback

        # As a last resort, use a generic safe name.
        safe_name = f"file-{digest}{suffix}"
        return safe_name

    def _canonical_filename(self, path: str, *, is_dir: bool) -> str:
        """Return the default filename derived from the logical path."""
        candidate = path.rsplit("/", 1)[-1] or "root"
        if is_dir:
            return f"{candidate}.dir"
        return candidate

    def _filename_mimetype_allowed(self, filename: str) -> bool:
        """Return True when the filename maps to an allowed MIME type."""
        mimetype, _ = mimetypes.guess_type(filename)
        return mimetype in self._allowed_upload_mimetypes if mimetype else False

    @staticmethod
    def _looks_like_text(payload: bytes) -> bool:
        """Best-effort detection for textual payloads."""
        if not payload:
            return True
        if b"\x00" in payload:
            return False
        try:
            payload.decode("utf-8")
        except UnicodeDecodeError:
            return False
        return True

    def _entry_to_info(self, entry: _RemoteEntry) -> FileInfo:
        """Convert an internal entry to public FileInfo."""
        return FileInfo(
            path=Path(entry.path),
            is_dir=entry.is_dir,
            size=entry.size,
            created_at=entry.created_at,
            modified_at=entry.modified_at,
        )

    _coerce_bytes = staticmethod(coerce_to_bytes)

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


def _is_invalid_mimetype_error(exc: Exception) -> bool:
    """Return True when the exception indicates an unsupported MIME type."""
    message = getattr(exc, "message", None)
    if not message:
        message = str(exc)
    return "Invalid file format" in message


def _is_not_found_error(exc: Exception) -> bool:
    """Return True when the exception indicates a missing remote file."""
    message = getattr(exc, "message", None)
    if not message:
        message = str(exc)
    return "No such File object" in message or "not found" in message.lower()
