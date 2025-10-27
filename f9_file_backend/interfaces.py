"""Core interfaces and data structures for file backend implementations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, BinaryIO, Protocol, Union

if TYPE_CHECKING:
    from datetime import datetime

PathLike = Union[str, Path]


class FileBackendError(RuntimeError):
    """Base exception for backend operations."""

    def __init__(
        self,
        message: str,
        *,
        path: PathLike | None = None,
    ) -> None:
        """Initialise the base error with an optional filesystem path context."""
        path_obj = Path(path) if path is not None else None
        detail = message if path_obj is None else ": ".join((message, str(path_obj)))
        super().__init__(detail)
        self.message = message
        self.path = path_obj


class NotFoundError(FileBackendError):
    """Raised when an expected file or directory is missing."""

    def __init__(self, path: PathLike) -> None:
        """Create a not-found error for the provided path."""
        super().__init__("Path not found", path=path)


class AlreadyExistsError(FileBackendError):
    """Raised when attempting to create a resource that already exists."""

    def __init__(self, path: PathLike, *, reason: str | None = None) -> None:
        """Create an already-exists error with an optional reason."""
        super().__init__(reason or "Path already exists", path=path)


class InvalidOperationError(FileBackendError):
    """Raised when an operation is not allowed for the given path."""

    def __init__(self, message: str, *, path: PathLike | None = None) -> None:
        """Initialise an invalid operation error scoped to a path."""
        super().__init__(message, path=path)

    @classmethod
    def cannot_overwrite_file_with_directory(
        cls,
        path: PathLike,
    ) -> InvalidOperationError:
        """Return an error describing a file-to-directory overwrite attempt."""
        return cls("Cannot overwrite file with directory", path=path)

    @classmethod
    def cannot_overwrite_directory_with_file(
        cls,
        path: PathLike,
    ) -> InvalidOperationError:
        """Return an error describing a directory-to-file overwrite attempt."""
        return cls("Cannot overwrite directory with file", path=path)

    @classmethod
    def cannot_read_directory(cls, path: PathLike) -> InvalidOperationError:
        """Return an error indicating directories cannot be read as files."""
        return cls("Cannot read directory", path=path)

    @classmethod
    def cannot_update_directory(cls, path: PathLike) -> InvalidOperationError:
        """Return an error indicating directories cannot be updated as files."""
        return cls("Cannot update directory", path=path)

    @classmethod
    def directory_not_empty(cls, path: PathLike) -> InvalidOperationError:
        """Return an error indicating recursive deletion is required."""
        return cls("Directory not empty (use recursive=True)", path=path)

    @classmethod
    def path_outside_root(cls, path: PathLike) -> InvalidOperationError:
        """Return an error showing the path escapes the backend root."""
        return cls("Path escapes backend root", path=path)

    @classmethod
    def parent_path_not_directory(cls, path: PathLike) -> InvalidOperationError:
        """Return an error when a parent segment is not a directory."""
        return cls("Parent path is not a directory", path=path)

    @classmethod
    def empty_path_not_allowed(cls, path: PathLike) -> InvalidOperationError:
        """Return an error when an operation targets an empty path."""
        return cls("Path cannot be empty", path=path)

    @classmethod
    def root_path_not_allowed(cls, path: PathLike) -> InvalidOperationError:
        """Return an error when the backend root is targeted explicitly."""
        return cls("Path cannot refer to backend root", path=path)


@dataclass(frozen=True)
class FileInfo:
    """Snapshot of metadata for a backend resource."""

    path: Path
    is_dir: bool
    size: int
    created_at: datetime | None
    modified_at: datetime | None

    def as_dict(self) -> dict:
        """Return a JSON-serialisable representation."""
        return {
            "path": str(self.path),
            "is_dir": self.is_dir,
            "size": self.size,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "modified_at": self.modified_at.isoformat()
            if self.modified_at
            else None,
        }


class FileBackend(ABC):
    """Standardised interface for file-backed storage providers.

    Implementations must operate relative to an optional root directory and
    should avoid allowing traversal outside their configured scope.
    """

    @abstractmethod
    def create(
        self,
        path: PathLike,
        *,
        data: bytes | str | BinaryIO | None = None,
        is_directory: bool = False,
        overwrite: bool = False,
    ) -> FileInfo:
        """Create a new file or directory.

        Args:
            path: Target backend path relative to the backend root.
            data: Optional content for file creation. Ignored for directories.
            is_directory: Create a directory when True.
            overwrite: Replace existing files if True.

        Returns:
            FileInfo describing the newly created resource.

        """

    @abstractmethod
    def read(
        self,
        path: PathLike,
        *,
        binary: bool = True,
    ) -> bytes | str:
        """Retrieve file contents.

        Args:
            path: Target file path relative to the backend root.
            binary: When False, content should be decoded as UTF-8 text.

        """

    @abstractmethod
    def update(
        self,
        path: PathLike,
        *,
        data: bytes | str | BinaryIO,
        append: bool = False,
    ) -> FileInfo:
        """Modify an existing file.

        Args:
            path: Target file path relative to the backend root.
            data: New content to write.
            append: Append to the existing content when True.

        Returns:
            FileInfo describing the updated resource.

        """

    @abstractmethod
    def delete(self, path: PathLike, *, recursive: bool = False) -> None:
        """Remove a file or directory.

        Args:
            path: Target path relative to the backend root.
            recursive: Allow recursive deletion of non-empty directories.

        """

    @abstractmethod
    def info(self, path: PathLike) -> FileInfo:
        """Retrieve metadata about a path.

        Args:
            path: Target path relative to the backend root.

        """


class SupportsBackend(Protocol):
    """Convenience protocol for objects exposing a file backend."""

    backend: FileBackend


@dataclass(frozen=True)
class SyncConflict:
    """Details of an unresolved synchronisation conflict."""

    path: Path
    status: str

    def as_dict(self) -> dict:
        """Return a JSON-serialisable representation."""
        return {"path": str(self.path), "status": self.status}


class SyncFileBackend(FileBackend):
    """Extended backend interface supporting bidirectional synchronisation."""

    @abstractmethod
    def push(self, *, message: str | None = None) -> None:
        """Publish local changes to the remote data source."""

    @abstractmethod
    def pull(self) -> None:
        """Retrieve remote updates into the local workspace."""

    def sync(self) -> None:
        """Perform a pull followed by a push."""

        self.pull()
        self.push()

    @abstractmethod
    def conflict_report(self) -> list[SyncConflict]:
        """Return the set of outstanding synchronisation conflicts."""

    @abstractmethod
    def conflict_accept_local(self, path: PathLike) -> None:
        """Resolve a conflict by keeping the local version."""

    @abstractmethod
    def conflict_accept_remote(self, path: PathLike) -> None:
        """Resolve a conflict by keeping the remote version."""

    @abstractmethod
    def conflict_resolve(
        self,
        path: PathLike,
        *,
        data: bytes | str | BinaryIO,
    ) -> None:
        """Resolve a conflict by supplying a new version of the file."""
