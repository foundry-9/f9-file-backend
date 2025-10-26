"""Local filesystem backend implementation."""

from __future__ import annotations

import io
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO

from .interfaces import (
    AlreadyExistsError,
    FileBackend,
    FileInfo,
    InvalidOperationError,
    NotFoundError,
    PathLike,
)


class LocalFileBackend(FileBackend):
    """Backend implementation backed by the local filesystem."""

    def __init__(
        self,
        root: PathLike | None = None,
        *,
        create_root: bool = True,
    ) -> None:
        """Initialise the backend rooted at the given filesystem path."""
        base = Path(root or Path.cwd()).expanduser()
        self._root = base.resolve(strict=False)
        if create_root:
            self._root.mkdir(parents=True, exist_ok=True)
        elif not self._root.exists():
            raise NotFoundError(self._root)

    @property
    def root(self) -> Path:
        """Absolute path used as the backend root."""
        return self._root

    def create(
        self,
        path: PathLike,
        *,
        data: bytes | str | BinaryIO | None = None,
        is_directory: bool = False,
        overwrite: bool = False,
    ) -> FileInfo:
        """Create a file or directory relative to the backend root."""
        target = self._ensure_within_root(path)
        if target.exists() and not overwrite:
            raise AlreadyExistsError(target)

        target.parent.mkdir(parents=True, exist_ok=True)

        if is_directory:
            if target.exists() and not target.is_dir():
                raise InvalidOperationError.cannot_overwrite_file_with_directory(target)
            target.mkdir(exist_ok=True)
        else:
            if target.exists() and target.is_dir():
                raise InvalidOperationError.cannot_overwrite_directory_with_file(
                    target,
                )
            payload = self._coerce_bytes(data) if data is not None else b""
            with target.open("wb") as fh:
                fh.write(payload)
        return self.info(target)

    def read(
        self,
        path: PathLike,
        *,
        binary: bool = True,
    ) -> bytes | str:
        """Return file contents as bytes or text."""
        target = self._ensure_within_root(path)
        if not target.exists():
            raise NotFoundError(target)
        if target.is_dir():
            raise InvalidOperationError.cannot_read_directory(target)

        mode = "rb" if binary else "r"
        with target.open(mode) as fh:
            return fh.read()

    def update(
        self,
        path: PathLike,
        *,
        data: bytes | str | BinaryIO,
        append: bool = False,
    ) -> FileInfo:
        """Write new data to an existing file."""
        target = self._ensure_within_root(path)
        if not target.exists():
            raise NotFoundError(target)
        if target.is_dir():
            raise InvalidOperationError.cannot_update_directory(target)

        payload = self._coerce_bytes(data)
        mode = "ab" if append else "wb"
        with target.open(mode) as fh:
            fh.write(payload)
        return self.info(target)

    def delete(self, path: PathLike, *, recursive: bool = False) -> None:
        """Delete the specified path, optionally recursing into directories."""
        target = self._ensure_within_root(path)
        if not target.exists():
            raise NotFoundError(target)

        if target.is_dir():
            if any(target.iterdir()) and not recursive:
                raise InvalidOperationError.directory_not_empty(target)
            shutil.rmtree(target)
        else:
            target.unlink()

    def info(self, path: PathLike) -> FileInfo:
        """Return metadata about a file or directory."""
        target = self._ensure_within_root(path)
        if not target.exists():
            raise NotFoundError(target)

        stat_result = target.stat()
        return FileInfo(
            path=target,
            is_dir=target.is_dir(),
            size=stat_result.st_size,
            created_at=_timestamp_to_datetime(stat_result.st_ctime),
            modified_at=_timestamp_to_datetime(stat_result.st_mtime),
        )

    def _ensure_within_root(self, path: PathLike) -> Path:
        candidate = (self._root / Path(path)).resolve(strict=False)
        try:
            candidate.relative_to(self._root)
        except ValueError as exc:
            raise InvalidOperationError.path_outside_root(candidate) from exc
        return candidate

    @staticmethod
    def _coerce_bytes(data: bytes | str | BinaryIO) -> bytes:
        if isinstance(data, bytes):
            return data
        if isinstance(data, str):
            return data.encode("utf-8")
        if isinstance(data, (io.BufferedIOBase, io.RawIOBase)):
            return data.read()
        data_type = type(data).__name__
        message = f"Unsupported data type: {data_type}"
        raise TypeError(message)


def _timestamp_to_datetime(timestamp: float) -> datetime:
    """Convert a POSIX timestamp to an aware datetime in UTC."""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)
