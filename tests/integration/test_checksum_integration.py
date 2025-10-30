"""Integration tests for checksum functionality across backends."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from f9_file_backend import (
    GitSyncFileBackend,
    LocalFileBackend,
)


@pytest.fixture
def local_backend(tmp_path: Path) -> LocalFileBackend:
    """Provide a local backend instance."""
    return LocalFileBackend(root=tmp_path / "local")


class TestChecksumIntegration:
    """Integration tests for checksum operations."""

    def test_local_checksum_with_streaming(
        self,
        local_backend: LocalFileBackend,
    ) -> None:
        """Verify checksum consistency with streamed content."""
        # Write via streaming
        def content_stream():
            yield b"Hello, "
            yield b"World!"

        local_backend.stream_write("stream.txt", chunk_source=content_stream())
        checksum = local_backend.checksum("stream.txt")
        assert isinstance(checksum, str)
        assert len(checksum) == 64

    def test_local_checksum_round_trip(
        self,
        local_backend: LocalFileBackend,
    ) -> None:
        """Verify checksum is consistent across read/write operations."""
        original_content = "test content for round trip"
        local_backend.create("test.txt", data=original_content)
        checksum1 = local_backend.checksum("test.txt")

        # Read and write back
        content = local_backend.read("test.txt", binary=False)
        assert content == original_content

        checksum2 = local_backend.checksum("test.txt")
        assert checksum1 == checksum2

    def test_checksum_many_mixed_valid_invalid(
        self,
        local_backend: LocalFileBackend,
    ) -> None:
        """Verify checksum_many handles mixed valid and invalid paths."""
        local_backend.create("valid1.txt", data="content1")
        local_backend.create("valid2.txt", data="content2")
        local_backend.create("dir", is_directory=True)

        paths = [
            "valid1.txt",
            "nonexistent.txt",
            "valid2.txt",
            "dir",
            "../escape.txt",  # Invalid path
        ]

        result = local_backend.checksum_many(paths)

        # Should only have the two valid files
        assert len(result) == 2
        assert "valid1.txt" in result
        assert "valid2.txt" in result

    def test_git_backend_checksum_delegation(tmp_path: Path) -> None:
        """Verify Git backend correctly delegates to local backend."""
        pytest.importorskip("git")

        git_dir = tmp_path / "git_repo"
        local_dir = tmp_path / "local"
        local_dir.mkdir()

        # Initialize a local backend and git repo
        local_backend = LocalFileBackend(root=local_dir)
        local_backend.create("test.txt", data="git test content")
        local_backend.create("file2.txt", data="another file")

        # Initialize git repo
        import shutil
        import subprocess

        git_dir.mkdir()
        git_path = shutil.which("git")
        if not git_path:
            pytest.skip("git not found in PATH")

        subprocess.run(
            [git_path, "init"],
            cwd=git_dir,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            [git_path, "config", "user.email", "test@example.com"],
            cwd=git_dir,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            [git_path, "config", "user.name", "Test User"],
            cwd=git_dir,
            capture_output=True,
            check=True,
        )

        # Create git backend pointing to this repo
        git_backend = GitSyncFileBackend(
            {
                "remote_url": str(git_dir),
                "path": str(git_dir / "work"),
                "branch": "main",
            },
        )

        # Create test file in git backend
        git_backend.create("git_file.txt", data="git content")

        # Verify checksum works
        checksum = git_backend.checksum("git_file.txt")
        assert isinstance(checksum, str)
        assert len(checksum) == 64

        # Verify checksum_many works
        result = git_backend.checksum_many(["git_file.txt"])
        assert "git_file.txt" in result

    def test_checksum_with_special_characters(
        self,
        local_backend: LocalFileBackend,
    ) -> None:
        """Verify checksum handles filenames with special characters."""
        local_backend.create("file-with-dashes.txt", data="content")
        local_backend.create("file_with_underscores.txt", data="content")
        local_backend.create("file.multiple.dots.txt", data="content")

        checksums = local_backend.checksum_many([
            "file-with-dashes.txt",
            "file_with_underscores.txt",
            "file.multiple.dots.txt",
        ])

        assert len(checksums) == 3

    def test_checksum_performance_many_files(
        self,
        local_backend: LocalFileBackend,
    ) -> None:
        """Verify checksum_many performs efficiently with many files."""
        num_files = 50
        file_paths = []

        # Create many files
        for i in range(num_files):
            path = f"file_{i:03d}.txt"
            local_backend.create(path, data=f"content {i}")
            file_paths.append(path)

        # Compute all checksums at once
        result = local_backend.checksum_many(file_paths)

        # Verify all files are included
        assert len(result) == num_files
        assert all(path in result for path in file_paths)

        # Verify all checksums are unique (with high probability)
        hashes = list(result.values())
        assert len(hashes) == len(set(hashes))

    def test_checksum_algorithms_consistency(
        self,
        local_backend: LocalFileBackend,
    ) -> None:
        """Verify different algorithms produce different outputs for same content."""
        local_backend.create("test.txt", data="test content")

        md5_hash = local_backend.checksum("test.txt", algorithm="md5")
        sha256_hash = local_backend.checksum("test.txt", algorithm="sha256")
        sha512_hash = local_backend.checksum("test.txt", algorithm="sha512")

        # All should be different
        assert md5_hash != sha256_hash
        assert sha256_hash != sha512_hash
        assert md5_hash != sha512_hash

        # Verify hash lengths
        assert len(md5_hash) == 32
        assert len(sha256_hash) == 64
        assert len(sha512_hash) == 128

    def test_checksum_binary_vs_text_mode(
        self,
        local_backend: LocalFileBackend,
    ) -> None:
        """Verify checksum is based on actual bytes, not text mode."""
        # Create the same content via different methods
        content = "hello world"
        local_backend.create("text.txt", data=content)
        local_backend.create("binary.txt", data=content.encode("utf-8"))

        hash1 = local_backend.checksum("text.txt")
        hash2 = local_backend.checksum("binary.txt")

        # Should be identical (both are same bytes)
        assert hash1 == hash2
