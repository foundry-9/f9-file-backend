"""Integration tests for async backend implementations.

Tests cover:
- Real-world async usage patterns
- Performance characteristics
- Integration between async and sync operations
- Stress testing with concurrent operations

"""

from __future__ import annotations

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pytest

from f9_file_backend import (
    AsyncLocalFileBackend,
    NotFoundError,
)


class TestAsyncIntegration:
    """Integration tests for async backends."""

    @pytest.fixture
    def temp_root(self) -> Any:
        """Provide a temporary directory as backend root."""
        with TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.mark.asyncio
    async def test_mixed_read_write_operations(
        self,
        temp_root: Path,
    ) -> None:
        """Test interleaved read and write operations."""
        backend = AsyncLocalFileBackend(root=temp_root)

        # Create initial files
        await asyncio.gather(
            backend.create("file1.txt", data=b"Initial 1"),
            backend.create("file2.txt", data=b"Initial 2"),
        )

        # Read and write concurrently
        async def read_and_update(filename: str) -> None:
            content = await backend.read(filename)
            updated = content + b" updated"
            await backend.update(filename, data=updated)

        await asyncio.gather(
            read_and_update("file1.txt"),
            read_and_update("file2.txt"),
        )

        results = await asyncio.gather(
            backend.read("file1.txt"),
            backend.read("file2.txt"),
        )

        assert results == [b"Initial 1 updated", b"Initial 2 updated"]

    @pytest.mark.asyncio
    async def test_stream_and_checksum_concurrently(
        self,
        temp_root: Path,
    ) -> None:
        """Test streaming and checksumming simultaneously."""
        backend = AsyncLocalFileBackend(root=temp_root)

        # Create test files
        files = []
        for i in range(5):
            await backend.create(f"file{i}.txt", data=f"Content {i}".encode())
            files.append(f"file{i}.txt")

        # Stream and checksum concurrently
        async def stream_file(path: str) -> int:
            total = 0
            async for chunk in await backend.stream_read(path):
                total += len(chunk)
            return total

        async def checksum_file(path: str) -> str:
            return await backend.checksum(path)

        stream_results = await asyncio.gather(
            *[stream_file(f) for f in files],
        )

        checksum_results = await asyncio.gather(
            *[checksum_file(f) for f in files],
        )

        assert len(stream_results) == 5
        assert len(checksum_results) == 5
        assert all(isinstance(c, str) for c in checksum_results)

    @pytest.mark.asyncio
    async def test_high_concurrency_operations(
        self,
        temp_root: Path,
    ) -> None:
        """Test handling many concurrent operations."""
        backend = AsyncLocalFileBackend(root=temp_root)
        num_operations = 20

        # Create many files concurrently
        create_tasks = [
            backend.create(f"file{i}.txt", data=f"Content {i}".encode())
            for i in range(num_operations)
        ]
        await asyncio.gather(*create_tasks)

        # Read all files concurrently
        read_tasks = [
            backend.read(f"file{i}.txt")
            for i in range(num_operations)
        ]
        results = await asyncio.gather(*read_tasks)

        assert len(results) == num_operations
        assert all(isinstance(r, bytes) for r in results)

    @pytest.mark.asyncio
    async def test_checksum_many_vs_concurrent(
        self,
        temp_root: Path,
    ) -> None:
        """Compare batch checksum vs concurrent individual checksums."""
        backend = AsyncLocalFileBackend(root=temp_root)

        files = []
        for i in range(10):
            await backend.create(f"file{i}.txt", data=f"Data {i}".encode())
            files.append(f"file{i}.txt")

        # Batch checksum
        batch_results = await backend.checksum_many(files)

        # Concurrent individual checksums
        individual_tasks = [
            backend.checksum(f)
            for f in files
        ]
        individual_results = await asyncio.gather(*individual_tasks)

        assert len(batch_results) == len(files)
        for i, path in enumerate(files):
            assert batch_results[path] == individual_results[i]

    @pytest.mark.asyncio
    async def test_directory_tree_operations(
        self,
        temp_root: Path,
    ) -> None:
        """Test creating and managing directory trees."""
        backend = AsyncLocalFileBackend(root=temp_root)

        # Create directory structure
        dirs = [
            "project/src",
            "project/tests",
            "project/docs",
        ]

        create_dirs = [
            backend.create(d, is_directory=True)
            for d in dirs
        ]
        await asyncio.gather(*create_dirs)

        # Create files in directories
        files = [
            backend.create("project/src/main.py", data=b"# Main"),
            backend.create("project/tests/test.py", data=b"# Test"),
            backend.create("project/docs/README.md", data=b"# Docs"),
        ]
        await asyncio.gather(*files)

        # Verify all files exist
        results = await asyncio.gather(
            backend.read("project/src/main.py"),
            backend.read("project/tests/test.py"),
            backend.read("project/docs/README.md"),
        )

        assert results == [b"# Main", b"# Test", b"# Docs"]

    @pytest.mark.asyncio
    async def test_streaming_large_files(
        self,
        temp_root: Path,
    ) -> None:
        """Test streaming operations with large files."""
        backend = AsyncLocalFileBackend(root=temp_root)

        # Create large file (10MB)
        large_data = b"x" * (10 * 1024 * 1024)
        await backend.create("large.bin", data=large_data)

        # Stream and collect chunks
        chunks = []
        chunk_size = 1024 * 1024
        stream = await backend.stream_read("large.bin", chunk_size=chunk_size)
        async for chunk in stream:
            chunks.append(chunk)
            # Simulate processing
            await asyncio.sleep(0)

        reconstructed = b"".join(chunks)
        assert len(reconstructed) == len(large_data)

    @pytest.mark.asyncio
    async def test_error_recovery(
        self,
        temp_root: Path,
    ) -> None:
        """Test graceful error handling in concurrent operations."""
        backend = AsyncLocalFileBackend(root=temp_root)

        # Create some files
        await backend.create("exists.txt", data=b"Exists")

        # Try mixed valid and invalid operations
        async def safe_operation(path: str, exists: bool = True) -> tuple[str, bool]:
            try:
                await backend.read(path)
                return (path, True)
            except Exception:
                return (path, False)

        results = await asyncio.gather(
            safe_operation("exists.txt", exists=True),
            safe_operation("missing.txt", exists=False),
            safe_operation("also_missing.txt", exists=False),
        )

        results_dict = {path: found for path, found in results}
        assert results_dict["exists.txt"] is True
        assert results_dict["missing.txt"] is False
        assert results_dict["also_missing.txt"] is False

    @pytest.mark.asyncio
    async def test_stress_test_many_small_files(
        self,
        temp_root: Path,
    ) -> None:
        """Stress test with many small files."""
        backend = AsyncLocalFileBackend(root=temp_root)

        num_files = 50
        create_tasks = [
            backend.create(f"file{i:03d}.txt", data=f"Content {i}".encode())
            for i in range(num_files)
        ]

        await asyncio.gather(*create_tasks)

        # Verify all files
        read_tasks = [
            backend.read(f"file{i:03d}.txt")
            for i in range(num_files)
        ]

        results = await asyncio.gather(*read_tasks)
        assert len(results) == num_files

    @pytest.mark.asyncio
    async def test_delete_many_files_concurrently(
        self,
        temp_root: Path,
    ) -> None:
        """Test deleting many files concurrently."""
        backend = AsyncLocalFileBackend(root=temp_root)

        # Create files
        num_files = 20
        for i in range(num_files):
            await backend.create(f"file{i}.txt", data=b"Content")

        # Delete concurrently
        delete_tasks = [
            backend.delete(f"file{i}.txt")
            for i in range(num_files)
        ]

        await asyncio.gather(*delete_tasks)

        # Verify all deleted
        for i in range(num_files):
            with pytest.raises(NotFoundError):
                await backend.info(f"file{i}.txt")

    @pytest.mark.asyncio
    async def test_timeout_handling(
        self,
        temp_root: Path,
    ) -> None:
        """Test handling of timeout scenarios."""
        backend = AsyncLocalFileBackend(root=temp_root)

        # Create files
        await backend.create("file1.txt", data=b"Content 1")
        await backend.create("file2.txt", data=b"Content 2")

        # Use timeout protection
        try:
            results = await asyncio.wait_for(
                asyncio.gather(
                    backend.read("file1.txt"),
                    backend.read("file2.txt"),
                ),
                timeout=5.0,
            )
            assert len(results) == 2
        except asyncio.TimeoutError:
            pytest.fail("Operations should complete within timeout")

    @pytest.mark.asyncio
    async def test_contextual_streaming(
        self,
        temp_root: Path,
    ) -> None:
        """Test streaming in context of other operations."""
        backend = AsyncLocalFileBackend(root=temp_root)

        # Create multiple files
        for i in range(3):
            await backend.create(
                f"file{i}.txt",
                data=b"x" * 1000,
            )

        # Stream multiple files concurrently
        async def stream_and_count(path: str) -> tuple[str, int]:
            count = 0
            async for _chunk in await backend.stream_read(path):
                count += 1
            return (path, count)

        results = await asyncio.gather(
            stream_and_count("file0.txt"),
            stream_and_count("file1.txt"),
            stream_and_count("file2.txt"),
        )

        assert len(results) == 3
        assert all(count > 0 for _, count in results)
