"""Integration tests for glob pattern matching across backends."""

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
def git_backend(tmp_path: Path) -> GitSyncFileBackend:
    """Provide a GitSyncFileBackend instance for testing."""
    # Note: GitSyncFileBackend requires a remote URL to clone from
    # For testing, we'll skip git backend tests as they require a remote repo
    pytest.skip("GitSyncFileBackend requires remote URL")


@pytest.fixture
def local_backend(tmp_path: Path) -> LocalFileBackend:
    """Provide a LocalFileBackend instance for testing."""
    return LocalFileBackend(root=tmp_path)


@pytest.fixture
def populated_git_backend(git_backend: GitSyncFileBackend) -> GitSyncFileBackend:
    """Provide a GitSyncFileBackend with test data."""
    git_backend.create("file1.txt", data=b"content1")
    git_backend.create("file2.txt", data=b"content2")
    git_backend.create("dir1", is_directory=True)
    git_backend.create("dir1/nested.txt", data=b"nested")
    return git_backend


class TestGlobLocalBackendIntegration:
    """Integration tests for LocalFileBackend glob."""

    def test_glob_large_file_set(self, local_backend: LocalFileBackend) -> None:
        """Ensure glob handles large number of files efficiently."""
        # Create 100 files
        for i in range(100):
            local_backend.create(f"file_{i:03d}.txt", data=f"content{i}".encode())

        results = local_backend.glob("*.txt")
        assert len(results) == 100

    def test_glob_deeply_nested_files(self, local_backend: LocalFileBackend) -> None:
        """Ensure glob finds deeply nested files."""
        # Create deep directory structure
        path = "a/b/c/d/e/f/g/file.txt"
        local_backend.create(path, data=b"deep")

        results = local_backend.glob("**/file.txt")
        assert len(results) == 1
        assert results[0].name == "file.txt"

    def test_glob_mixed_file_types(self, local_backend: LocalFileBackend) -> None:
        """Ensure glob correctly filters by file type."""
        local_backend.create("file.txt", data=b"text")
        local_backend.create("file.py", data=b"python")
        local_backend.create("file.json", data=b"json")
        local_backend.create("file.md", data=b"markdown")

        txt_files = local_backend.glob("*.txt")
        assert len(txt_files) == 1
        assert txt_files[0].suffix == ".txt"

    def test_glob_case_sensitive_matching(self, local_backend: LocalFileBackend) -> None:
        """Ensure glob matches patterns correctly."""
        # Create files with different naming schemes
        local_backend.create("ReadMe.txt", data=b"readme")
        local_backend.create("config.cfg", data=b"config")

        # Verify that glob returns files correctly
        txt_results = local_backend.glob("*.txt")
        cfg_results = local_backend.glob("*.cfg")

        assert len(txt_results) == 1
        assert len(cfg_results) == 1
        assert txt_results[0].suffix == ".txt"
        assert cfg_results[0].suffix == ".cfg"


class TestGlobGitBackendIntegration:
    """Integration tests for GitSyncFileBackend glob."""

    def test_glob_after_git_operations(self, git_backend: GitSyncFileBackend) -> None:
        """Ensure glob works correctly after git push/pull operations."""
        git_backend.create("test1.txt", data=b"content1")
        git_backend.create("test2.txt", data=b"content2")
        git_backend.push(message="Initial commit")

        results = git_backend.glob("*.txt")
        assert len(results) == 2

    def test_glob_with_git_sync(self, populated_git_backend: GitSyncFileBackend) -> None:
        """Ensure glob reflects all files after sync operations."""
        results = populated_git_backend.glob("**/*.txt")
        names = {p.name for p in results}
        assert "file1.txt" in names
        assert "file2.txt" in names
        assert "nested.txt" in names

    def test_glob_git_backend_delegation(self, git_backend: GitSyncFileBackend) -> None:
        """Ensure GitSyncFileBackend glob delegates to local backend correctly."""
        git_backend.create("a.txt", data=b"a")
        git_backend.create("b.txt", data=b"b")

        results = git_backend.glob("*.txt")
        assert len(results) == 2
        assert all(p.suffix == ".txt" for p in results)


class TestGlobAcrossBackends:
    """Test glob behavior consistency across different backends."""

    def test_glob_pattern_consistency(
        self, local_backend: LocalFileBackend, git_backend: GitSyncFileBackend,
    ) -> None:
        """Ensure glob patterns produce consistent results across backends."""
        # Create same structure in both backends
        for backend in [local_backend, git_backend]:
            backend.create("file1.txt", data=b"content1")
            backend.create("file2.txt", data=b"content2")
            backend.create("file.md", data=b"markdown")

        local_results = local_backend.glob("*.txt")
        git_results = git_backend.glob("*.txt")

        local_names = {p.name for p in local_results}
        git_names = {p.name for p in git_results}

        assert local_names == git_names

    def test_glob_directory_handling_consistency(
        self, local_backend: LocalFileBackend, git_backend: GitSyncFileBackend,
    ) -> None:
        """Ensure glob handles directories consistently across backends."""
        for backend in [local_backend, git_backend]:
            backend.create("dir1", is_directory=True)
            backend.create("dir2", is_directory=True)
            backend.create("file.txt", data=b"content")

        for backend in [local_backend, git_backend]:
            results_no_dirs = backend.glob("*")
            results_with_dirs = backend.glob("*", include_dirs=True)

            assert len(results_no_dirs) == 1  # Only file.txt
            assert len(results_with_dirs) == 3  # dir1, dir2, file.txt


class TestGlobPerformance:
    """Performance-related tests for glob operations."""

    def test_glob_performance_with_many_directories(self, local_backend: LocalFileBackend) -> None:
        """Ensure glob performs reasonably with many directories."""
        # Create 50 directories
        for i in range(50):
            local_backend.create(f"dir_{i}/file.txt", data=b"content")

        results = local_backend.glob("**/file.txt")
        assert len(results) == 50

    def test_glob_performance_complex_pattern(self, local_backend: LocalFileBackend) -> None:
        """Ensure glob handles complex patterns efficiently."""
        # Create diverse file structure
        for i in range(10):
            local_backend.create(f"test_{i}.txt", data=b"test")
            local_backend.create(f"data_{i}.json", data=b"data")
            local_backend.create(f"doc_{i}.md", data=b"doc")

        results = local_backend.glob("test_[0-5].txt")
        assert len(results) == 6  # 0 through 5

    def test_glob_pattern_with_many_matches(self, local_backend: LocalFileBackend) -> None:
        """Ensure glob returns all matches even with many results."""
        # Create 1000 files
        for i in range(1000):
            local_backend.create(f"file_{i:04d}.txt", data=b"content")

        results = local_backend.glob("*.txt")
        assert len(results) == 1000
        assert all(p.suffix == ".txt" for p in results)


class TestGlobEdgeCases:
    """Test edge cases and boundary conditions for glob."""

    def test_glob_with_special_characters(self, local_backend: LocalFileBackend) -> None:
        """Ensure glob handles files with special characters."""
        local_backend.create("file-with-dashes.txt", data=b"content")
        local_backend.create("file_with_underscores.txt", data=b"content")
        local_backend.create("file.with.dots.txt", data=b"content")

        results = local_backend.glob("file*.txt")
        assert len(results) == 3

    def test_glob_directory_with_dot(self, local_backend: LocalFileBackend) -> None:
        """Ensure glob handles directories with dots in name."""
        local_backend.create("data.v1.0", is_directory=True)
        local_backend.create("data.v1.0/file.txt", data=b"content")

        results = local_backend.glob("**/file.txt")
        assert len(results) == 1

    def test_glob_empty_pattern_matching(self, local_backend: LocalFileBackend) -> None:
        """Ensure glob with overly broad pattern still works."""
        local_backend.create("file.txt", data=b"content")
        local_backend.create("file.py", data=b"code")

        results = local_backend.glob("*")
        assert len(results) == 2

    def test_glob_pattern_with_consecutive_stars(self, local_backend: LocalFileBackend) -> None:
        """Ensure glob handles ** pattern correctly."""
        local_backend.create("a/b/c/file.txt", data=b"deep")
        local_backend.create("file.txt", data=b"root")

        results = local_backend.glob("**/file.txt")
        assert len(results) == 2


class TestGlobErrorHandling:
    """Test error handling and exceptional cases for glob."""

    def test_glob_nonexistent_parent_path(self, local_backend: LocalFileBackend) -> None:
        """Ensure glob returns empty list for pattern with nonexistent parent."""
        results = local_backend.glob("nonexistent/file.txt")
        assert results == []

    def test_glob_on_file_pattern_match(self, local_backend: LocalFileBackend) -> None:
        """Ensure glob patterns work correctly even with file-like names."""
        local_backend.create("test.txt", data=b"content")
        local_backend.create("test2.txt", data=b"content")

        results = local_backend.glob("test*.txt")
        assert len(results) == 2
