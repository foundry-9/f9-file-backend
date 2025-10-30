"""Tests covering glob pattern matching operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from f9_file_backend import (
    LocalFileBackend,
)


@pytest.fixture
def backend(tmp_path: Path) -> LocalFileBackend:
    """Provide a LocalFileBackend instance scoped to a temporary directory."""
    return LocalFileBackend(root=tmp_path)


@pytest.fixture
def populated_backend(backend: LocalFileBackend) -> LocalFileBackend:
    """Provide a backend with various test files and directories."""
    # Create test files and directories
    backend.create("file1.txt", data=b"content1")
    backend.create("file2.txt", data=b"content2")
    backend.create("file.md", data=b"markdown")
    backend.create("dir1", is_directory=True)
    backend.create("dir1/nested1.txt", data=b"nested content")
    backend.create("dir1/nested2.py", data=b"python code")
    backend.create("dir2", is_directory=True)
    backend.create("dir2/file3.txt", data=b"content3")
    backend.create("dir2/subdir", is_directory=True)
    backend.create("dir2/subdir/deep.txt", data=b"deep content")
    backend.create("README.md", data=b"readme")
    backend.create(".hidden", data=b"hidden")
    return backend


class TestGlobBasicPatterns:
    """Test basic glob pattern matching."""

    def test_glob_all_txt_files(self, populated_backend: LocalFileBackend) -> None:
        """Ensure glob matches all .txt files with * wildcard."""
        results = populated_backend.glob("*.txt")
        names = {p.name for p in results}
        assert "file1.txt" in names
        assert "file2.txt" in names
        assert "file.md" not in names
        assert len(results) == 2

    def test_glob_all_md_files(self, populated_backend: LocalFileBackend) -> None:
        """Ensure glob matches all .md files."""
        results = populated_backend.glob("*.md")
        names = {p.name for p in results}
        assert "file.md" in names
        assert "README.md" in names
        assert len(results) == 2

    def test_glob_question_mark_pattern(self, populated_backend: LocalFileBackend) -> None:
        """Ensure glob matches single character with ?."""
        results = populated_backend.glob("file?.txt")
        names = {p.name for p in results}
        assert "file1.txt" in names
        assert "file2.txt" in names
        assert len(results) == 2

    def test_glob_character_range(self, populated_backend: LocalFileBackend) -> None:
        """Ensure glob matches character ranges with [...]."""
        results = populated_backend.glob("file[12].txt")
        names = {p.name for p in results}
        assert "file1.txt" in names
        assert "file2.txt" in names
        assert len(results) == 2

    def test_glob_no_matches(self, populated_backend: LocalFileBackend) -> None:
        """Ensure glob returns empty list when no matches found."""
        results = populated_backend.glob("*.xyz")
        assert results == []

    def test_glob_hidden_files(self, populated_backend: LocalFileBackend) -> None:
        """Ensure glob can match hidden files starting with dot."""
        results = populated_backend.glob(".*")
        names = {p.name for p in results}
        assert ".hidden" in names


class TestGlobDirectoryFiltering:
    """Test directory inclusion/exclusion in glob results."""

    def test_glob_exclude_directories_default(self, populated_backend: LocalFileBackend) -> None:
        """Ensure glob excludes directories by default."""
        results = populated_backend.glob("*")
        # Check that dir1 and dir2 are not in results
        names = {p.name for p in results}
        assert "dir1" not in names
        assert "dir2" not in names
        # But txt files should be there
        assert "file1.txt" in names

    def test_glob_include_directories(self, populated_backend: LocalFileBackend) -> None:
        """Ensure glob includes directories when include_dirs=True."""
        results = populated_backend.glob("*", include_dirs=True)
        names = {p.name for p in results}
        assert "dir1" in names
        assert "dir2" in names
        assert "file1.txt" in names

    def test_glob_dirs_convenience_method(self, populated_backend: LocalFileBackend) -> None:
        """Ensure glob_dirs returns only directories."""
        results = populated_backend.glob_dirs("*")
        names = {p.name for p in results}
        assert "dir1" in names
        assert "dir2" in names
        assert "file1.txt" not in names
        assert "file2.txt" not in names

    def test_glob_files_convenience_method(self, populated_backend: LocalFileBackend) -> None:
        """Ensure glob_files returns only files."""
        results = populated_backend.glob_files("*")
        names = {p.name for p in results}
        assert "file1.txt" in names
        assert "file2.txt" in names
        assert "file.md" in names
        assert "dir1" not in names


class TestGlobRecursive:
    """Test recursive glob patterns with **."""

    def test_glob_recursive_all_txt_files(self, populated_backend: LocalFileBackend) -> None:
        """Ensure glob with ** finds txt files at all levels."""
        results = populated_backend.glob("**/*.txt")
        names = {p.name for p in results}
        assert "file1.txt" in names
        assert "file2.txt" in names
        assert "nested1.txt" in names
        assert "nested2.py" not in names
        assert "deep.txt" in names

    def test_glob_recursive_double_star(self, populated_backend: LocalFileBackend) -> None:
        """Ensure ** matches any depth of directories."""
        results = populated_backend.glob("**/nested*.txt")
        names = {p.name for p in results}
        assert "nested1.txt" in names
        assert "nested2.py" not in names

    def test_glob_recursive_with_include_dirs(self, populated_backend: LocalFileBackend) -> None:
        """Ensure recursive glob with include_dirs finds directories."""
        results = populated_backend.glob("**/sub*", include_dirs=True)
        names = {p.name for p in results}
        assert "subdir" in names

    def test_glob_recursive_deep_files(self, populated_backend: LocalFileBackend) -> None:
        """Ensure recursive glob finds deeply nested files."""
        results = populated_backend.glob("**/deep.txt")
        names = {p.name for p in results}
        assert "deep.txt" in names
        assert len(results) == 1


class TestGlobPathNormalization:
    """Test glob pattern path normalization and sorting."""

    def test_glob_returns_relative_paths(self, backend: LocalFileBackend) -> None:
        """Ensure glob returns paths relative to backend root."""
        backend.create("a.txt", data=b"a")
        backend.create("b.txt", data=b"b")
        results = backend.glob("*.txt")
        # Results should be relative paths, not absolute
        for path in results:
            assert not path.is_absolute()
            assert path.name in {"a.txt", "b.txt"}

    def test_glob_returns_sorted_results(self, backend: LocalFileBackend) -> None:
        """Ensure glob returns sorted results for consistent ordering."""
        backend.create("z.txt", data=b"z")
        backend.create("a.txt", data=b"a")
        backend.create("m.txt", data=b"m")
        results = backend.glob("*.txt")
        paths = [p.name for p in results]
        assert paths == sorted(paths)

    def test_glob_nested_relative_paths(self, populated_backend: LocalFileBackend) -> None:
        """Ensure nested glob results are relative paths."""
        results = populated_backend.glob("dir*/file*.txt")
        for path in results:
            assert not path.is_absolute()
            assert path.parts[0] in {"dir1", "dir2"}


class TestGlobEmptyBackend:
    """Test glob behavior with empty or minimal backends."""

    def test_glob_empty_backend(self, backend: LocalFileBackend) -> None:
        """Ensure glob on empty backend returns empty list."""
        results = backend.glob("*")
        assert results == []

    def test_glob_with_only_directories(self, backend: LocalFileBackend) -> None:
        """Ensure glob can find directories in otherwise empty backend."""
        backend.create("only_dir", is_directory=True)
        results = backend.glob("*", include_dirs=True)
        assert len(results) == 1
        assert results[0].name == "only_dir"

    def test_glob_nonexistent_pattern_in_empty_backend(self, backend: LocalFileBackend) -> None:
        """Ensure glob on nonexistent pattern returns empty."""
        results = backend.glob("*.txt")
        assert results == []


class TestGlobComplexPatterns:
    """Test complex and edge case glob patterns."""

    def test_glob_all_python_files_recursive(self, populated_backend: LocalFileBackend) -> None:
        """Ensure glob finds all Python files recursively."""
        results = populated_backend.glob("**/*.py")
        names = {p.name for p in results}
        assert "nested2.py" in names
        assert "file1.txt" not in names

    def test_glob_pattern_with_hyphens(self, backend: LocalFileBackend) -> None:
        """Ensure glob matches files with hyphens."""
        backend.create("test-file-1.txt", data=b"content")
        backend.create("test-file-2.txt", data=b"content")
        results = backend.glob("test-file-*.txt")
        assert len(results) == 2

    def test_glob_pattern_with_underscores(self, backend: LocalFileBackend) -> None:
        """Ensure glob matches files with underscores."""
        backend.create("test_file_1.txt", data=b"content")
        backend.create("test_file_2.txt", data=b"content")
        results = backend.glob("test_file_*.txt")
        assert len(results) == 2

    def test_glob_multiple_wildcard_levels(self, populated_backend: LocalFileBackend) -> None:
        """Ensure glob handles multiple wildcard levels."""
        results = populated_backend.glob("dir*/*.txt")
        names = {p.name for p in results}
        assert "nested1.txt" in names
        assert "nested2.py" not in names
        assert "file3.txt" in names


class TestGlobIntegration:
    """Test glob integration with other backend operations."""

    def test_glob_files_can_be_read(self, populated_backend: LocalFileBackend) -> None:
        """Ensure files found by glob can be read successfully."""
        results = populated_backend.glob("*.txt")
        for path in results:
            content = populated_backend.read(path)
            assert isinstance(content, bytes)
            assert len(content) > 0

    def test_glob_nested_files_can_be_read(self, populated_backend: LocalFileBackend) -> None:
        """Ensure nested files found by glob can be read."""
        results = populated_backend.glob("**/nested*.txt")
        for path in results:
            content = populated_backend.read(path)
            assert b"nested" in content

    def test_glob_after_delete(self, backend: LocalFileBackend) -> None:
        """Ensure glob reflects deletions."""
        backend.create("file1.txt", data=b"content1")
        backend.create("file2.txt", data=b"content2")
        assert len(backend.glob("*.txt")) == 2
        backend.delete("file1.txt")
        results = backend.glob("*.txt")
        assert len(results) == 1
        assert results[0].name == "file2.txt"

    def test_glob_after_create(self, backend: LocalFileBackend) -> None:
        """Ensure glob reflects new files."""
        assert backend.glob("*.txt") == []
        backend.create("newfile.txt", data=b"new")
        results = backend.glob("*.txt")
        assert len(results) == 1
        assert results[0].name == "newfile.txt"
