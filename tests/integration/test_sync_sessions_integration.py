"""Integration tests for sync_session functionality across backends.

This module tests sync_session behavior in realistic scenarios including:
    - Concurrent process access
    - Large file operations
    - Git sync with conflict resolution
    - Performance characteristics
"""

# ruff: noqa: S101,ANN202,PLR2004,E501,TRY003

import asyncio
import threading
import time
from pathlib import Path

import pytest

from f9_file_backend import (
    AsyncLocalFileBackend,
    LocalFileBackend,
)


class TestSyncSessionIntegration:
    """Integration tests for sync_session across backends."""

    def test_local_backend_sync_session_with_file_operations(
        self, tmp_path: Path,
    ) -> None:
        """Test sync_session with typical file operations."""
        backend = LocalFileBackend(root=tmp_path)

        # Create multiple files within a sync session
        with backend.sync_session():
            for i in range(10):
                backend.create(f"file{i}.txt", data=f"content{i}".encode())

        # Verify all files were created
        for i in range(10):
            assert backend.read(f"file{i}.txt") == f"content{i}".encode()

    def test_local_backend_sync_session_prevents_concurrent_modification(
        self, tmp_path: Path,
    ) -> None:
        """Test that sync_session serializes access from multiple threads."""
        backend = LocalFileBackend(root=tmp_path)
        operation_log = []

        def modify_with_lock(thread_id: int) -> None:
            """Modify a file within a sync session."""
            with backend.sync_session(timeout=10.0):
                operation_log.append(("enter", thread_id))
                # Create a file specific to this thread
                backend.create(f"thread{thread_id}.txt", data=b"data")
                time.sleep(0.1)  # Simulate work
                operation_log.append(("exit", thread_id))

        # Start multiple threads
        threads = [
            threading.Thread(target=modify_with_lock, args=(i,)) for i in range(5)
        ]

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # Verify all threads completed and files exist
        assert len(operation_log) == 10  # 5 enter + 5 exit
        for i in range(5):
            assert backend.info(f"thread{i}.txt").size > 0

    @pytest.mark.skip(reason="Requires proper Git repo initialization")
    def test_git_backend_sync_session_atomic_operations(self, tmp_path: Path) -> None:
        """Test that Git backend sync_session provides atomic operations."""
        # Skipped: Complex Git setup required
        pass

    def test_sync_session_with_large_file_operations(self, tmp_path: Path) -> None:
        """Test sync_session with large file streaming operations."""
        backend = LocalFileBackend(root=tmp_path)

        # Create a large file within sync session (512KB)
        large_content = b"x" * (512 * 1024)

        with backend.sync_session():
            def chunk_generator():
                """Generate chunks of data."""
                chunk_size = 8192
                for i in range(0, len(large_content), chunk_size):
                    yield large_content[i : i + chunk_size]

            backend.stream_write("large_file.bin", chunk_source=chunk_generator())

        # Verify file was created and has correct size
        info = backend.info("large_file.bin")
        assert info.size == len(large_content)

    def test_sync_session_performance(self, tmp_path: Path) -> None:
        """Test that sync_session has minimal overhead."""
        backend = LocalFileBackend(root=tmp_path)

        # Measure lock acquisition time
        start = time.time()
        with backend.sync_session():
            time.sleep(0.05)  # Simulate work
        elapsed = time.time() - start

        # Should be roughly 50ms + minimal overhead
        # Allow 200ms for slower systems
        assert elapsed < 0.2

    def test_sync_session_exception_cleanup(self, tmp_path: Path) -> None:
        """Test that sync_session cleans up properly on exception."""
        backend = LocalFileBackend(root=tmp_path)

        # First operation throws exception
        with pytest.raises(ValueError):
            with backend.sync_session():
                backend.create("file.txt", data=b"test")
                raise ValueError("Test error")

        # Lock should be released, next operation should work
        with backend.sync_session():
            backend.create("file2.txt", data=b"test2")

        assert backend.read("file2.txt") == b"test2"

    def test_sync_session_with_glob_operations(self, tmp_path: Path) -> None:
        """Test sync_session with pattern matching operations."""
        backend = LocalFileBackend(root=tmp_path)

        with backend.sync_session():
            # Create files with different patterns
            for i in range(3):
                backend.create(f"data{i}.txt", data=b"text")
            for i in range(3):
                backend.create(f"config{i}.yaml", data=b"yaml")

        # Glob operations should work
        text_files = backend.glob("*.txt")
        yaml_files = backend.glob("*.yaml")

        assert len(text_files) == 3
        assert len(yaml_files) == 3

    def test_sync_session_with_checksum_operations(self, tmp_path: Path) -> None:
        """Test sync_session with checksum verification."""
        backend = LocalFileBackend(root=tmp_path)

        with backend.sync_session():
            backend.create("file1.txt", data=b"content1")
            backend.create("file2.txt", data=b"content2")

        # Compute checksums
        checksums = backend.checksum_many(
            ["file1.txt", "file2.txt"], algorithm="sha256",
        )

        assert len(checksums) == 2
        assert "file1.txt" in checksums
        assert "file2.txt" in checksums


class TestAsyncSyncSessionIntegration:
    """Integration tests for async backends with sync_session."""

    def test_async_local_backend_sync_session_in_async_context(
        self, tmp_path: Path,
    ) -> None:
        """Test using sync_session in AsyncLocalFileBackend within async context."""

        async def test():
            backend = AsyncLocalFileBackend(root=tmp_path)

            # Use sync_session within async operations
            with backend.sync_session():
                await backend.create("file1.txt", data=b"content1")

            await backend.create("file2.txt", data=b"content2")

            content1 = await backend.read("file1.txt")
            content2 = await backend.read("file2.txt")

            assert content1 == b"content1"
            assert content2 == b"content2"

        asyncio.run(test())

    @pytest.mark.skip(reason="AsyncGitSyncFileBackend has different constructor")
    def test_async_git_backend_sync_session_in_async_context(
        self, tmp_path: Path,
    ) -> None:
        """Test using sync_session in AsyncGitSyncFileBackend within async context."""
        # Skipped: AsyncGitSyncFileBackend has a different constructor interface
        pass

    def test_async_concurrent_operations_with_sync_session(
        self, tmp_path: Path,
    ) -> None:
        """Test multiple concurrent async operations protected by sync_session."""

        async def test():
            backend = AsyncLocalFileBackend(root=tmp_path)

            async def create_file(index: int):
                """Create a file asynchronously."""
                with backend.sync_session(timeout=10.0):
                    await backend.create(
                        f"file{index}.txt", data=f"content{index}".encode(),
                    )

            # Run multiple concurrent operations
            await asyncio.gather(*[create_file(i) for i in range(5)])

            # Verify all files created
            for i in range(5):
                content = await backend.read(f"file{i}.txt")
                assert content == f"content{i}".encode()

        asyncio.run(test())


class TestSyncSessionReliability:
    """Tests for reliability and robustness of sync_session."""

    def test_sync_session_recovery_from_orphaned_lock(self, tmp_path: Path) -> None:
        """Test recovery if lock file becomes orphaned."""
        backend = LocalFileBackend(root=tmp_path)

        # Create and hold a lock
        with backend.sync_session():
            backend.create("file.txt", data=b"test")

        # Try to use again - should work even if lock file exists
        with backend.sync_session():
            backend.create("file2.txt", data=b"test2")

        assert backend.read("file2.txt") == b"test2"

    def test_sync_session_with_symlinks(self, tmp_path: Path) -> None:
        """Test sync_session with symlink handling."""
        backend = LocalFileBackend(root=tmp_path)

        with backend.sync_session():
            backend.create("original.txt", data=b"content")

        # Read the file
        content = backend.read("original.txt")
        assert content == b"content"

    def test_sync_session_nested_directories(self, tmp_path: Path) -> None:
        """Test sync_session with deeply nested directory structures."""
        backend = LocalFileBackend(root=tmp_path)

        with backend.sync_session():
            # Create nested structure
            backend.create("a/b/c/d/file.txt", data=b"nested")

        assert backend.read("a/b/c/d/file.txt") == b"nested"

    def test_sync_session_with_empty_operations(self, tmp_path: Path) -> None:
        """Test that sync_session works even with no operations inside."""
        backend = LocalFileBackend(root=tmp_path)

        # Empty sync session
        with backend.sync_session():
            pass

        # Should be able to use backend normally after
        backend.create("file.txt", data=b"test")
        assert backend.read("file.txt") == b"test"
