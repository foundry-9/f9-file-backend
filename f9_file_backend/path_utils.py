"""Path validation and normalization utilities.

This module provides common path validation functions used across multiple
backend implementations. These utilities help ensure consistent and secure
path handling while preventing path traversal attacks.

Key utilities:
- Empty/whitespace path validation
- Root directory detection
- Path traversal detection
- Windows path normalization
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .interfaces import InvalidOperationError

if TYPE_CHECKING:
    from pathlib import Path


def validate_not_empty(path: Any) -> None:
    """Validate that path is not empty or whitespace-only.

    Args:
        path: Path to validate

    Raises:
        InvalidOperationError: If path is empty or whitespace.

    """
    path_str = str(path)
    if not path_str or path_str.strip() == "":
        raise InvalidOperationError.empty_path_not_allowed(path)


def validate_not_root(path: str | Path) -> None:
    """Validate that path is not the root directory.

    Detects common root path representations:
    - "." (current directory)
    - "/" (absolute root)
    - "" (empty string)

    Args:
        path: Path to validate (as string or Path)

    Raises:
        InvalidOperationError: If path resolves to root.

    """
    if isinstance(path, str):
        path_str = path
    else:
        # Assume it's a Path-like object with as_posix method
        path_str = path.as_posix() if hasattr(path, "as_posix") else str(path)

    if path_str in (".", "/", ""):
        raise InvalidOperationError.root_path_not_allowed(path)


def detect_path_traversal_posix(path_parts: tuple[str, ...]) -> bool:
    """Detect path traversal attempts in path components.

    A path traversal attempt is detected when any component is "..",
    which would escape to a parent directory.

    Args:
        path_parts: Tuple of path components (from Path.parts or PurePosixPath.parts)

    Returns:
        True if traversal detected, False otherwise

    Example:

        >>> from pathlib import PurePosixPath
        >>> path = PurePosixPath("../../../etc/passwd")
        >>> detect_path_traversal_posix(path.parts)
        True
        >>> path = PurePosixPath("valid/relative/path")
        >>> detect_path_traversal_posix(path.parts)
        False

    """
    return any(part == ".." for part in path_parts)


def normalize_windows_path(path_str: str) -> str:
    """Normalize Windows backslashes to forward slashes.

    This is useful for creating consistent path strings across platforms,
    especially for virtual filesystem backends that need normalized paths.

    Args:
        path_str: Path string potentially containing backslashes

    Returns:
        Path string with forward slashes

    Example:

        >>> normalize_windows_path("dir\\subdir\\file.txt")
        'dir/subdir/file.txt'
        >>> normalize_windows_path("dir/subdir/file.txt")
        'dir/subdir/file.txt'

    """
    return path_str.replace("\\", "/")
