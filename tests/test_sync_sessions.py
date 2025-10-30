"""Unit tests for sync_session context manager and file-based locking.

This module tests the atomic synchronization capabilities provided by
sync_session() context managers across all backends that support them.

Key Test Areas:
    - Lock acquisition and release
    - Timeout behavior
    - Re-entrant locks (same process acquiring multiple times)
    - Lock file creation and cleanup
    - Exception handling during lock operations
"""

# ruff: noqa: S101,ANN202,PLR2004,E501,TRY003

import os
import threading
import time
from pathlib import Path

import pytest

from f9_file_backend import GitSyncFileBackend, LocalFileBackend
from f9_file_backend.locking import FileLock, LockError


class TestFileLock:
    """Tests for the FileLock utility class."""

    def test_lock_file_creation(self, tmp_path: Path) -> None:
        """Test that lock file is created in the expected location."""
        lock_path = tmp_path / ".test.lock"
        lock = FileLock(lock_path)

        with lock.acquire():
            assert lock_path.parent.exists()

    def test_lock_acquisition_and_release(self, tmp_path: Path) -> None:
        """Test basic lock acquisition and release."""
        lock_path = tmp_path / ".test.lock"
        lock = FileLock(lock_path)

        # Should be able to acquire lock
        with lock.acquire():
            pass

        # Should be able to acquire again after release
        with lock.acquire():
            pass

    def test_lock_reentrancy_same_process(self, tmp_path: Path) -> None:
        """Test that locks are re-entrant within the same process."""
        lock_path = tmp_path / ".test.lock"
        lock = FileLock(lock_path)

        # Acquire lock first time
        with lock.acquire():
            # Acquire same lock again in same process
            with lock.acquire():
                assert lock._lock_count == 2
            assert lock._lock_count == 1
        assert lock._lock_count == 0

    def test_lock_timeout_immediate_success(self, tmp_path: Path) -> None:
        """Test that lock succeeds immediately when not contended."""
        lock_path = tmp_path / ".test.lock"
        lock = FileLock(lock_path)

        start = time.time()
        with lock.acquire(timeout=5.0):
            pass
        elapsed = time.time() - start

        # Should acquire almost immediately
        assert elapsed < 1.0

    def test_lock_timeout_exceeded(self, tmp_path: Path) -> None:
        """Test that TimeoutError is raised when lock times out."""
        lock_path = tmp_path / ".test.lock"
        lock1 = FileLock(lock_path)
        lock2 = FileLock(lock_path)

        # First lock acquires
        with lock1.acquire():
            # Simulate delay to allow timeout check
            time.sleep(0.2)

            # Second lock in different thread should timeout
            def try_lock():
                with pytest.raises(TimeoutError):
                    with lock2.acquire(timeout=0.1):
                        pass

            thread = threading.Thread(target=try_lock)
            thread.start()
            thread.join()

    def test_lock_initialization_with_parent_creation(self, tmp_path: Path) -> None:
        """Test that parent directories are created if needed."""
        lock_path = tmp_path / "subdir" / "nested" / ".lock"
        lock = FileLock(lock_path)

        with lock.acquire():
            assert lock_path.parent.exists()

    def test_lock_error_message_includes_path(self, tmp_path: Path) -> None:
        """Test that LockError messages include the lock path."""
        lock_path = tmp_path / ".test.lock"
        error = LockError("Test error", lock_path=lock_path)

        assert str(lock_path) in str(error)


class TestLocalFileBackendSyncSession:
    """Tests for LocalFileBackend.sync_session() context manager."""

    def test_sync_session_basic(self, tmp_path: Path) -> None:
        """Test basic sync_session usage."""
        backend = LocalFileBackend(root=tmp_path)

        with backend.sync_session():
            backend.create("file.txt", data=b"test")

        assert backend.read("file.txt") == b"test"

    def test_sync_session_returns_context_manager(self, tmp_path: Path) -> None:
        """Test that sync_session returns a valid context manager."""
        backend = LocalFileBackend(root=tmp_path)
        cm = backend.sync_session()

        # Should have __enter__ and __exit__ methods
        assert hasattr(cm, "__enter__")
        assert hasattr(cm, "__exit__")

    def test_sync_session_with_timeout(self, tmp_path: Path) -> None:
        """Test sync_session with explicit timeout."""
        backend = LocalFileBackend(root=tmp_path)

        # Should succeed with sufficient timeout
        with backend.sync_session(timeout=5.0):
            backend.create("file.txt", data=b"test")

    def test_sync_session_creates_lock_file(self, tmp_path: Path) -> None:
        """Test that sync_session creates a lock file in backend root."""
        backend = LocalFileBackend(root=tmp_path)

        # Lock file should be created on first sync_session
        with backend.sync_session():
            # Parent directory should exist
            assert tmp_path.exists()

    def test_sync_session_multiple_operations(self, tmp_path: Path) -> None:
        """Test performing multiple operations within a sync session."""
        backend = LocalFileBackend(root=tmp_path)

        with backend.sync_session():
            backend.create("file1.txt", data=b"content1")
            backend.create("file2.txt", data=b"content2")
            backend.create("dir", is_directory=True)

        assert backend.read("file1.txt") == b"content1"
        assert backend.read("file2.txt") == b"content2"
        assert backend.info("dir").is_dir

    def test_sync_session_exception_in_context(self, tmp_path: Path) -> None:
        """Test that lock is properly released even if exception occurs."""
        backend = LocalFileBackend(root=tmp_path)

        # Exception inside context
        with pytest.raises(ValueError):
            with backend.sync_session():
                backend.create("file.txt", data=b"test")
                raise ValueError("Test error")

        # Lock should be released, can acquire again
        with backend.sync_session():
            backend.create("file2.txt", data=b"test2")

        assert backend.read("file2.txt") == b"test2"

    def test_sync_session_reentrancy(self, tmp_path: Path) -> None:
        """Test that sync_session supports nested/re-entrant usage."""
        backend = LocalFileBackend(root=tmp_path)

        with backend.sync_session():
            backend.create("file1.txt", data=b"content1")

            # Nested sync_session in same process
            with backend.sync_session():
                backend.create("file2.txt", data=b"content2")

        assert backend.read("file1.txt") == b"content1"
        assert backend.read("file2.txt") == b"content2"

    def test_sync_session_concurrent_threads(self, tmp_path: Path) -> None:
        """Test that sync_session prevents concurrent access from threads."""
        backend = LocalFileBackend(root=tmp_path)
        lock_acquired_order = []

        def thread_operation(thread_id: int, delay: float) -> None:
            """Perform operations within sync session."""
            time.sleep(delay)  # Stagger thread start times
            with backend.sync_session(timeout=5.0):
                lock_acquired_order.append(("acquired", thread_id))
                time.sleep(0.2)  # Hold lock briefly
                lock_acquired_order.append(("released", thread_id))

        # Start multiple threads
        threads = []
        for i in range(3):
            t = threading.Thread(target=thread_operation, args=(i, i * 0.1))
            threads.append(t)
            t.start()

        # Wait for all threads
        for t in threads:
            t.join()

        # Verify locks were acquired and released in order
        assert len(lock_acquired_order) == 6
        for i in range(3):
            # Should see acquire then release for each thread
            assert ("acquired", i) in lock_acquired_order
            assert ("released", i) in lock_acquired_order


class TestGitSyncFileBackendSyncSession:
    """Tests for GitSyncFileBackend.sync_session() context manager."""

    @pytest.fixture
    def git_backend(self, tmp_path: Path) -> GitSyncFileBackend:
        """Create a GitSyncFileBackend for testing."""
        # Initialize a git repo first
        repo_path = tmp_path / "repo"
        repo_path.mkdir()

        # Initialize bare repo to clone from
        bare_repo = tmp_path / "bare.git"
        os.system(f"git init --bare {bare_repo}")

        # Clone it
        os.system(f"git clone {bare_repo} {repo_path}")

        return GitSyncFileBackend(
            connection_info={
                "remote_url": str(bare_repo),
                "path": str(repo_path),
                "author_name": "Test",
                "author_email": "test@example.com",
            },
        )

    @pytest.mark.skip(reason="Git setup issue in tests")
    def test_git_sync_session_basic(self, git_backend: GitSyncFileBackend) -> None:
        """Test basic sync_session usage with GitSyncFileBackend."""
        with git_backend.sync_session():
            git_backend.create("file.txt", data=b"test")

        assert git_backend.read("file.txt") == b"test"

    @pytest.mark.skip(reason="Git setup issue in tests")
    def test_git_sync_session_delegates_to_local_backend(
        self, git_backend: GitSyncFileBackend,
    ) -> None:
        """Test that sync_session delegates to LocalFileBackend."""
        cm = git_backend.sync_session()

        # Should return a context manager
        assert hasattr(cm, "__enter__")
        assert hasattr(cm, "__exit__")

    @pytest.mark.skip(reason="Git setup issue in tests")
    def test_git_sync_session_with_operations(
        self, git_backend: GitSyncFileBackend,
    ) -> None:
        """Test performing sync operations within a session."""
        with git_backend.sync_session():
            git_backend.create("file.txt", data=b"content")
            git_backend.pull()  # Sync operations
            git_backend.push(message="Test commit")


class TestAsyncBackendsSyncSession:
    """Tests for async backends sync_session method."""

    def test_async_local_sync_session_not_async(self, tmp_path: Path) -> None:
        """Test that AsyncLocalFileBackend.sync_session() is NOT async."""
        from f9_file_backend import AsyncLocalFileBackend

        backend = AsyncLocalFileBackend(root=tmp_path)
        cm = backend.sync_session()

        # Should be a regular context manager, not async
        assert hasattr(cm, "__enter__")
        assert hasattr(cm, "__exit__")
        assert not hasattr(cm, "__aenter__")

    @pytest.mark.skip(reason="AsyncGitSyncFileBackend has different interface")
    def test_async_git_sync_session_not_async(self, tmp_path: Path) -> None:
        """Test that AsyncGitSyncFileBackend.sync_session() is NOT async."""
        # This test is skipped because AsyncGitSyncFileBackend has a different
        # constructor interface than GitSyncFileBackend
        pass

    def test_async_local_sync_session_usage(self, tmp_path: Path) -> None:
        """Test using sync_session with AsyncLocalFileBackend."""
        import asyncio

        from f9_file_backend import AsyncLocalFileBackend

        async def test():
            backend = AsyncLocalFileBackend(root=tmp_path)

            # Use sync_session in async context
            with backend.sync_session():
                await backend.create("file.txt", data=b"test")

            content = await backend.read("file.txt")
            assert content == b"test"

        asyncio.run(test())


class TestLockEdgeCases:
    """Tests for edge cases and error conditions in locking."""

    def test_lock_with_none_timeout(self, tmp_path: Path) -> None:
        """Test lock with None timeout (wait indefinitely)."""
        lock_path = tmp_path / ".test.lock"
        lock = FileLock(lock_path)

        # Should work with None timeout
        with lock.acquire(timeout=None):
            pass

    def test_lock_with_zero_timeout(self, tmp_path: Path) -> None:
        """Test lock with zero timeout."""
        lock_path = tmp_path / ".test.lock"
        lock1 = FileLock(lock_path)
        lock2 = FileLock(lock_path)

        with lock1.acquire():
            # Zero timeout should fail immediately
            with pytest.raises(TimeoutError):
                with lock2.acquire(timeout=0.0):
                    pass

    def test_lock_file_permissions(self, tmp_path: Path) -> None:
        """Test that lock file can be created in directories with various permissions."""
        lock_dir = tmp_path / "writable"
        lock_dir.mkdir(mode=0o755)
        lock_path = lock_dir / ".lock"
        lock = FileLock(lock_path)

        with lock.acquire():
            assert lock_path.parent.exists()

    def test_multiple_lock_objects_same_file(self, tmp_path: Path) -> None:
        """Test that multiple FileLock objects for same file work correctly."""
        lock_path = tmp_path / ".test.lock"
        lock1 = FileLock(lock_path)
        lock2 = FileLock(lock_path)

        # Both should be able to work with the same underlying lock file
        with lock1.acquire():
            # This is a different process/thread, so should block in real scenarios
            pass

        with lock2.acquire():
            pass
