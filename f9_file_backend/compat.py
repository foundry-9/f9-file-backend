"""Exception translation/mapping for standard Python compatibility.

This module provides utilities for translating f9_file_backend exceptions into
standard Python OSError subclasses, making the library compatible with code
expecting standard Python file operation exceptions.
"""

from __future__ import annotations

import functools
from contextlib import contextmanager
from typing import TYPE_CHECKING, TypeVar

from f9_file_backend.interfaces import (
    AlreadyExistsError,
    FileBackendError,
    InvalidOperationError,
    NotFoundError,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from f9_file_backend.interfaces import FileBackend

T = TypeVar("T")


def translate_backend_exception(exc: FileBackendError) -> OSError:
    """Convert a FileBackendError to a standard Python OSError.

    Maps:
    - NotFoundError → FileNotFoundError
    - AlreadyExistsError → FileExistsError
    - InvalidOperationError (cannot read directory) → IsADirectoryError
    - InvalidOperationError (other) → OSError
    - FileBackendError → OSError

    Args:
        exc: The FileBackendError to translate.

    Returns:
        A standard Python OSError or subclass.

    """
    # Preserve the original exception message
    message = str(exc)

    if isinstance(exc, NotFoundError):
        return FileNotFoundError(message)

    if isinstance(exc, AlreadyExistsError):
        return FileExistsError(message)

    if isinstance(exc, InvalidOperationError):
        # Check for specific InvalidOperationError cases
        if "Cannot read directory" in exc.message:
            return IsADirectoryError(message)
        if "Cannot update directory" in exc.message:
            return IsADirectoryError(message)
        if "not a directory" in exc.message.lower():
            return NotADirectoryError(message)
        # Generic invalid operation becomes OSError
        return OSError(message)

    # Generic FileBackendError
    return OSError(message)


@contextmanager
def translate_exceptions() -> Iterator[None]:
    """Context manager for exception translation.

    Catches any FileBackendError exceptions and translates them to standard
    Python OSError exceptions.

    Example:
        ```python
        with translate_exceptions():
            backend.read("nonexistent.txt")  # Raises FileNotFoundError
        ```

    Yields:
        None

    Raises:
        OSError: Any FileBackendError wrapped as appropriate OSError subclass.

    """
    try:
        yield
    except FileBackendError as exc:
        raise translate_backend_exception(exc) from exc


def translate_method(method: Callable[..., T]) -> Callable[..., T]:
    """Decorator for translating exceptions from a method.

    Wraps a method call with exception translation, converting any
    FileBackendError to standard Python OSError exceptions.

    This handles both regular methods and generators by wrapping the result
    if it's an iterator.

    Args:
        method: The method to wrap with exception translation.

    Returns:
        A wrapped version of the method that translates exceptions.

    Example:
        ```python
        @translate_method
        def some_backend_operation(self):
            return self.backend.read("file.txt")
        ```

    """

    @functools.wraps(method)
    def wrapper(*args: object, **kwargs: object) -> T:
        with translate_exceptions():
            result = method(*args, **kwargs)  # type: ignore[assignment]

            # If the result is an iterator, wrap it to translate exceptions
            # from generator iteration
            if hasattr(result, "__iter__") and hasattr(result, "__next__"):
                return _wrap_iterator(result)  # type: ignore[return-value]

            return result  # type: ignore[return-value]

    return wrapper


def _wrap_iterator(iterator: object) -> object:
    """Wrap an iterator to translate exceptions during iteration.

    Args:
        iterator: The iterator to wrap.

    Yields:
        Items from the wrapped iterator with exception translation.

    Raises:
        OSError: Any FileBackendError translated to appropriate OSError.

    """
    try:
        while True:
            with translate_exceptions():
                try:
                    yield next(iterator)  # type: ignore[arg-type]
                except StopIteration:
                    break
    except FileBackendError as exc:
        raise translate_backend_exception(exc) from exc


class CompatibleFileBackend:
    """Wrapper backend that translates exceptions to standard Python OSError.

    This class wraps any FileBackend implementation and translates all
    FileBackendError exceptions to standard Python OSError exceptions.
    This makes the backend compatible with code expecting standard Python
    file operation exceptions.

    Example:
        ```python
        from f9_file_backend import LocalFileBackend, CompatibleFileBackend
        from pathlib import Path

        # Create a compatible wrapper
        base_backend = LocalFileBackend(root=Path("/data"))
        backend = CompatibleFileBackend(base_backend)

        # Operations raise standard Python exceptions
        try:
            backend.read("nonexistent.txt")
        except FileNotFoundError:
            print("File not found!")

        try:
            backend.create("file.txt", data=b"hello")
            backend.create("file.txt", data=b"world")
        except FileExistsError:
            print("File already exists!")
        ```

    Attributes:
        _backend: The wrapped FileBackend instance.

    """

    def __init__(self, backend: FileBackend) -> None:
        """Initialize the compatible wrapper.

        Args:
            backend: The FileBackend instance to wrap.

        """
        self._backend = backend

    def __getattr__(self, name: str) -> object:
        """Delegate attribute access to the wrapped backend.

        This allows transparent access to backend methods with exception
        translation applied to FileBackendError exceptions.

        Args:
            name: The attribute name.

        Returns:
            The attribute from the wrapped backend, wrapped with exception
            translation if it's a callable method.

        Raises:
            AttributeError: If the attribute doesn't exist on the backend.

        """
        attr = getattr(self._backend, name)

        # If it's a callable method, wrap it with exception translation
        if callable(attr):
            return translate_method(attr)

        # Otherwise, return the attribute as-is
        return attr

    def __repr__(self) -> str:
        """Return string representation of the wrapper.

        Returns:
            String showing this is a compatible wrapper around the backend.

        """
        return f"CompatibleFileBackend({self._backend!r})"
