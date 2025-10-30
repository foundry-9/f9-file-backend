"""File-based locking utilities for atomic operations and concurrency control.

This module provides cross-platform file locking mechanisms for synchronizing
access to backend resources. It uses platform-specific approaches:
    - Unix/Linux: fcntl module for advisory file locking
    - Windows: msvcrt module for file locking

Key Features:
    - File-based locking (persists across processes)
    - Timeout support with proper cleanup
    - Re-entrant lock support (same process can acquire multiple times)
    - Cross-platform compatibility (Unix and Windows)
    - Context manager interface for safe lock management

Example:

    >>> from f9_file_backend.locking import FileLock
    >>> from pathlib import Path
    >>>
    >>> lock_path = Path("/data/.backend.lock")
    >>> lock = FileLock(lock_path)
    >>>
    >>> with lock.acquire(timeout=5.0):
    ...     # Perform atomic operations
    ...     backend.pull()
    ...     backend.create("file.txt", data=b"content")
    ...     backend.push()

See Also:

    - GitSyncFileBackend: Uses FileLock for atomic sync sessions
    - LocalFileBackend: Provides sync_session() context manager

"""

from __future__ import annotations

import os
import platform
import time
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator


class LockError(IOError):
    """Raised when file locking operations fail."""

    def __init__(self, message: str, *, lock_path: Path | None = None) -> None:
        """Initialize lock error with optional path context."""
        if lock_path:
            detail = f"{message}: {lock_path}"
        else:
            detail = message
        super().__init__(detail)
        self.message = message
        self.lock_path = lock_path


class FileLock:
    """Cross-platform file-based locking mechanism.

    Uses advisory file locking on Unix/Linux (fcntl) and file locking on
    Windows (msvcrt). Supports timeout and re-entrant locking.
    """

    def __init__(self, lock_path: Path) -> None:
        """Initialize the file lock.

        Args:
            lock_path: Path to the lock file (will be created if needed).

        """
        self.lock_path = Path(lock_path)
        self._lock_file = None
        self._lock_count = 0  # For re-entrant lock support
        self._owner_pid = None  # Track which process owns the lock

    @contextmanager
    def acquire(self, timeout: float | None = None) -> Iterator[None]:
        """Acquire the file lock with optional timeout.

        Args:
            timeout: Timeout in seconds. If None, wait indefinitely.

        Yields:
            None while lock is held.

        Raises:
            TimeoutError: If lock cannot be acquired within timeout.
            LockError: If lock acquisition fails for other reasons.

        Example:

            >>> with lock.acquire(timeout=5.0):
            ...     # Critical section protected by lock
            ...     perform_operations()

        """
        acquired = False
        try:
            acquired = self._acquire_lock(timeout)
            if not acquired:
                message = (
                    f"Could not acquire lock within {timeout} seconds: "
                    f"{self.lock_path}"
                )
                raise TimeoutError(message)
            yield
        finally:
            if acquired:
                self._release_lock()

    def _acquire_lock(self, timeout: float | None = None) -> bool:
        """Attempt to acquire the lock.

        Returns:
            True if lock was acquired, False if timeout occurred.

        Raises:
            LockError: If lock acquisition fails.

        """
        # Support re-entrant locking within same process
        current_pid = os.getpid()
        if self._owner_pid == current_pid:
            self._lock_count += 1
            return True

        start_time = time.time()
        while True:
            try:
                # Create lock file if it doesn't exist
                self.lock_path.parent.mkdir(parents=True, exist_ok=True)

                # Open file in append mode (creates if needed)
                self._lock_file = open(self.lock_path, "a", encoding="utf-8")

                # Try to lock the file
                self._apply_lock(self._lock_file)

                # Successfully acquired lock
                self._owner_pid = current_pid
                self._lock_count = 1
                return True

            except OSError as e:
                # Lock failed, check if timeout exceeded
                if self._lock_file is not None:
                    try:
                        self._lock_file.close()
                    except OSError:
                        pass
                    self._lock_file = None

                if timeout is not None:
                    elapsed = time.time() - start_time
                    if elapsed >= timeout:
                        return False
                    # Brief sleep before retry
                    time.sleep(min(0.1, timeout / 10))
                else:
                    # No timeout, raise error
                    message = f"Failed to acquire lock: {e}"
                    raise LockError(message, lock_path=self.lock_path) from e

    def _release_lock(self) -> None:
        """Release the file lock."""
        if self._lock_count > 1:
            # Re-entrant: just decrement count
            self._lock_count -= 1
            return

        try:
            if self._lock_file is not None:
                try:
                    self._unlock_file(self._lock_file)
                except ValueError:
                    # File already closed, ignore
                    pass
                try:
                    self._lock_file.close()
                except OSError:
                    # Already closed, ignore
                    pass
                self._lock_file = None
        except OSError as e:
            message = f"Failed to release lock: {e}"
            raise LockError(message, lock_path=self.lock_path) from e
        finally:
            self._lock_count = 0
            self._owner_pid = None

    @staticmethod
    def _apply_lock(file_obj) -> None:
        """Apply platform-specific file lock.

        Args:
            file_obj: Opened file object to lock.

        Raises:
            OSError: If lock cannot be acquired.

        """
        if platform.system() == "Windows":
            # Windows file locking
            import msvcrt

            try:
                # Lock the first byte of the file (non-blocking)
                msvcrt.locking(file_obj.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as e:
                message = f"Windows lock failed: {e}"
                raise OSError(message) from e
        else:
            # Unix/Linux file locking
            import fcntl

            try:
                # Exclusive lock, non-blocking
                fcntl.flock(file_obj.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as e:
                message = f"Unix lock failed: {e}"
                raise OSError(message) from e

    @staticmethod
    def _unlock_file(file_obj) -> None:
        """Remove platform-specific file lock.

        Args:
            file_obj: Opened file object to unlock.

        """
        if platform.system() == "Windows":
            # Windows file unlocking
            import msvcrt

            try:
                # Unlock the first byte
                msvcrt.locking(file_obj.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass  # Ignore unlock errors
        else:
            # Unix/Linux file unlocking
            import fcntl

            try:
                fcntl.flock(file_obj.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass  # Ignore unlock errors
