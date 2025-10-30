"""Validation helpers for file operations.

This module provides reusable validation functions that work with entries
(files/directories) from different backend implementations. The PathEntry
protocol allows validation logic to be backend-agnostic while supporting
type-safe validation.

Example:
    >>> from pathlib import Path
    >>> entry = LocalPathEntry.from_path(Path("file.txt"))
    >>> validate_entry_exists(entry, "file.txt")  # Raises if doesn't exist
    >>> validate_is_file(entry, "file.txt")  # Raises if is a directory

"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

from .interfaces import (
    AlreadyExistsError,
    InvalidOperationError,
    NotFoundError,
)

if TYPE_CHECKING:
    pass


class PathEntry(Protocol):
    """Protocol for path entry objects used in validation.

    Any object with an `is_dir` property can be used with the validation
    functions, including Path objects (via LocalPathEntry adapter) and
    _RemoteEntry objects from the OpenAI backend.
    """

    @property
    def is_dir(self) -> bool:
        """Whether the entry is a directory."""
        ...


class LocalPathEntry:
    """Adapter to make Path objects compatible with PathEntry protocol.

    This wrapper allows Path objects to be used with the validation functions
    by providing the required `is_dir` property interface.

    Example:

        >>> from pathlib import Path
        >>> entry = LocalPathEntry(Path("file.txt"))
        >>> entry.is_dir
        False

    """

    def __init__(self, path: Any) -> None:
        """Initialize the adapter with a Path object."""
        self._path = path

    @property
    def is_dir(self) -> bool:
        """Return True if the path is a directory."""
        return self._path.is_dir()

    @classmethod
    def from_path(cls, path: Any) -> LocalPathEntry | None:
        """Create entry if path exists, else return None.

        Args:
            path: Path object to check

        Returns:
            LocalPathEntry instance if path exists, None otherwise.

        """
        return cls(path) if path.exists() else None


def validate_entry_exists(
    entry: PathEntry | None,
    path: Any,
) -> PathEntry:
    """Validate that an entry exists.

    Args:
        entry: Entry to validate (None if doesn't exist)
        path: Path representation for error messages

    Returns:
        The entry if it exists.

    Raises:
        NotFoundError: If entry is None.

    """
    if entry is None:
        raise NotFoundError(path)
    return entry


def validate_entry_not_exists(
    entry: PathEntry | None,
    path: Any,
    overwrite: bool = False,
) -> None:
    """Validate that an entry does not exist (or overwrite is allowed).

    Args:
        entry: Entry to validate (None if doesn't exist)
        path: Path representation for error messages
        overwrite: If True, allow existing entries

    Raises:
        AlreadyExistsError: If entry exists and overwrite is False.

    """
    if entry is not None and not overwrite:
        raise AlreadyExistsError(path)


def validate_is_file(entry: PathEntry, path: Any) -> None:
    """Validate that an entry is a file, not a directory.

    Args:
        entry: Entry to validate (must not be None)
        path: Path representation for error messages

    Raises:
        InvalidOperationError: If entry is a directory.

    """
    if entry.is_dir:
        raise InvalidOperationError.cannot_read_directory(path)


def validate_not_overwriting_directory_with_file(
    entry: PathEntry | None,
    path: Any,
) -> None:
    """Validate that we're not trying to overwrite a directory with a file.

    Args:
        entry: Entry to validate (None if doesn't exist)
        path: Path representation for error messages

    Raises:
        InvalidOperationError: If entry exists and is a directory.

    """
    if entry is not None and entry.is_dir:
        raise InvalidOperationError.cannot_overwrite_directory_with_file(path)


def validate_not_overwriting_file_with_directory(
    entry: PathEntry | None,
    path: Any,
) -> None:
    """Validate that we're not trying to overwrite a file with a directory.

    Args:
        entry: Entry to validate (None if doesn't exist)
        path: Path representation for error messages

    Raises:
        InvalidOperationError: If entry exists and is a file.

    """
    if entry is not None and not entry.is_dir:
        raise InvalidOperationError.cannot_overwrite_file_with_directory(path)
