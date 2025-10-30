"""Comprehensive tests for validation helpers.

This module tests the validation functions and LocalPathEntry adapter to ensure:
1. All validation functions raise correct exceptions
2. LocalPathEntry correctly adapts Path objects to the PathEntry protocol
3. Validation logic works with both real and mocked entries
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from f9_file_backend.interfaces import (
    AlreadyExistsError,
    InvalidOperationError,
    NotFoundError,
)
from f9_file_backend.validation import (
    LocalPathEntry,
    validate_entry_exists,
    validate_entry_not_exists,
    validate_is_file,
    validate_not_overwriting_directory_with_file,
    validate_not_overwriting_file_with_directory,
)


class MockEntry:
    """Mock PathEntry for testing validation functions."""

    def __init__(self, is_dir: bool) -> None:
        """Initialize with is_dir property."""
        self._is_dir = is_dir

    @property
    def is_dir(self) -> bool:
        """Return the is_dir flag."""
        return self._is_dir


class TestLocalPathEntry:
    """Tests for LocalPathEntry adapter."""

    def test_from_path_returns_entry_when_exists(self) -> None:
        """LocalPathEntry.from_path returns entry for existing path."""
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            test_file = tmp_path / "test.txt"
            test_file.write_text("hello")

            entry = LocalPathEntry.from_path(test_file)

            assert entry is not None
            assert isinstance(entry, LocalPathEntry)

    def test_from_path_returns_none_when_not_exists(self) -> None:
        """LocalPathEntry.from_path returns None for non-existent path."""
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            test_file = tmp_path / "nonexistent.txt"

            entry = LocalPathEntry.from_path(test_file)

            assert entry is None

    def test_is_dir_property_for_file(self) -> None:
        """LocalPathEntry.is_dir returns False for files."""
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            test_file = tmp_path / "test.txt"
            test_file.write_text("hello")

            entry = LocalPathEntry(test_file)

            assert entry.is_dir is False

    def test_is_dir_property_for_directory(self) -> None:
        """LocalPathEntry.is_dir returns True for directories."""
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            test_dir = tmp_path / "subdir"
            test_dir.mkdir()

            entry = LocalPathEntry(test_dir)

            assert entry.is_dir is True


class TestValidateEntryExists:
    """Tests for validate_entry_exists function."""

    def test_passes_when_entry_exists(self) -> None:
        """validate_entry_exists passes when entry is not None."""
        entry = MockEntry(is_dir=False)

        result = validate_entry_exists(entry, "test.txt")

        assert result is entry

    def test_raises_not_found_when_entry_none(self) -> None:
        """validate_entry_exists raises NotFoundError when entry is None."""
        with pytest.raises(NotFoundError) as exc_info:
            validate_entry_exists(None, "test.txt")

        assert "test.txt" in str(exc_info.value.path)

    def test_raises_with_path_object(self) -> None:
        """validate_entry_exists works with Path objects in error message."""
        path = Path("some/path.txt")
        with pytest.raises(NotFoundError):
            validate_entry_exists(None, path)


class TestValidateEntryNotExists:
    """Tests for validate_entry_not_exists function."""

    def test_passes_when_entry_none(self) -> None:
        """validate_entry_not_exists passes when entry is None."""
        validate_entry_not_exists(None, "test.txt")  # Should not raise

    def test_passes_when_entry_exists_and_overwrite_true(self) -> None:
        """validate_entry_not_exists passes when overwrite=True."""
        entry = MockEntry(is_dir=False)

        validate_entry_not_exists(entry, "test.txt", overwrite=True)  # Should not raise

    def test_raises_when_entry_exists_and_overwrite_false(self) -> None:
        """validate_entry_not_exists raises AlreadyExistsError when entry exists."""
        entry = MockEntry(is_dir=False)

        with pytest.raises(AlreadyExistsError) as exc_info:
            validate_entry_not_exists(entry, "test.txt", overwrite=False)

        assert "test.txt" in str(exc_info.value.path)

    def test_raises_by_default_when_entry_exists(self) -> None:
        """validate_entry_not_exists raises AlreadyExistsError by default."""
        entry = MockEntry(is_dir=False)

        with pytest.raises(AlreadyExistsError):
            validate_entry_not_exists(entry, "test.txt")


class TestValidateIsFile:
    """Tests for validate_is_file function."""

    def test_passes_when_entry_is_file(self) -> None:
        """validate_is_file passes when entry.is_dir is False."""
        entry = MockEntry(is_dir=False)

        validate_is_file(entry, "test.txt")  # Should not raise

    def test_raises_when_entry_is_directory(self) -> None:
        """validate_is_file raises InvalidOperationError when entry.is_dir is True."""
        entry = MockEntry(is_dir=True)

        with pytest.raises(InvalidOperationError) as exc_info:
            validate_is_file(entry, "some/dir")

        assert "Cannot read directory" in str(exc_info.value)
        assert "some/dir" in str(exc_info.value.path)


class TestValidateNotOverwritingDirectoryWithFile:
    """Tests for validate_not_overwriting_directory_with_file function."""

    def test_passes_when_entry_none(self) -> None:
        """Function passes when entry is None (creating new file)."""
        # Should not raise
        validate_not_overwriting_directory_with_file(None, "test.txt")

    def test_passes_when_entry_is_file(self) -> None:
        """Function passes when entry is a file (overwriting file with file is ok)."""
        entry = MockEntry(is_dir=False)

        # Should not raise
        validate_not_overwriting_directory_with_file(entry, "test.txt")

    def test_raises_when_entry_is_directory(self) -> None:
        """Function raises InvalidOperationError when trying to overwrite directory."""
        entry = MockEntry(is_dir=True)

        with pytest.raises(InvalidOperationError) as exc_info:
            validate_not_overwriting_directory_with_file(entry, "some/dir")

        assert "Cannot overwrite directory with file" in str(exc_info.value)
        assert "some/dir" in str(exc_info.value.path)


class TestValidateNotOverwritingFileWithDirectory:
    """Tests for validate_not_overwriting_file_with_directory function."""

    def test_passes_when_entry_none(self) -> None:
        """Function passes when entry is None (creating new directory)."""
        # Should not raise
        validate_not_overwriting_file_with_directory(None, "newdir")

    def test_passes_when_entry_is_directory(self) -> None:
        """Function passes when entry is a directory (no conflict)."""
        entry = MockEntry(is_dir=True)

        # Should not raise
        validate_not_overwriting_file_with_directory(entry, "some/dir")

    def test_raises_when_entry_is_file(self) -> None:
        """Function raises InvalidOperationError when trying to overwrite file."""
        entry = MockEntry(is_dir=False)

        with pytest.raises(InvalidOperationError) as exc_info:
            validate_not_overwriting_file_with_directory(entry, "test.txt")

        assert "Cannot overwrite file with directory" in str(exc_info.value)
        assert "test.txt" in str(exc_info.value.path)


class TestValidationIntegration:
    """Integration tests for validation functions with real files."""

    def test_read_file_validation_flow(self) -> None:
        """Test validation flow for reading files."""
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            test_file = tmp_path / "test.txt"
            test_file.write_text("hello")

            entry = LocalPathEntry.from_path(test_file)
            validate_entry_exists(entry, test_file)
            validate_is_file(entry, test_file)
            # Should complete without errors

    def test_read_nonexistent_file_validation_flow(self) -> None:
        """Test validation flow for reading non-existent files."""
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            test_file = tmp_path / "nonexistent.txt"

            entry = LocalPathEntry.from_path(test_file)
            with pytest.raises(NotFoundError):
                validate_entry_exists(entry, test_file)

    def test_read_directory_validation_flow(self) -> None:
        """Test validation flow for attempting to read a directory."""
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            test_dir = tmp_path / "subdir"
            test_dir.mkdir()

            entry = LocalPathEntry.from_path(test_dir)
            validate_entry_exists(entry, test_dir)
            with pytest.raises(InvalidOperationError):
                validate_is_file(entry, test_dir)

    def test_create_file_validation_flow(self) -> None:
        """Test validation flow for creating files."""
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            test_file = tmp_path / "new.txt"

            entry = LocalPathEntry.from_path(test_file)
            validate_not_overwriting_directory_with_file(entry, test_file)
            validate_entry_not_exists(entry, test_file)
            # Should complete without errors

    def test_create_existing_file_no_overwrite_validation(self) -> None:
        """Test validation flow for creating existing file without overwrite."""
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            test_file = tmp_path / "existing.txt"
            test_file.write_text("original")

            entry = LocalPathEntry.from_path(test_file)
            validate_not_overwriting_directory_with_file(entry, test_file)
            with pytest.raises(AlreadyExistsError):
                validate_entry_not_exists(entry, test_file, overwrite=False)

    def test_create_existing_file_with_overwrite_validation(self) -> None:
        """Test validation flow for creating existing file with overwrite."""
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            test_file = tmp_path / "existing.txt"
            test_file.write_text("original")

            entry = LocalPathEntry.from_path(test_file)
            validate_not_overwriting_directory_with_file(entry, test_file)
            validate_entry_not_exists(entry, test_file, overwrite=True)
            # Should complete without errors

    def test_create_directory_validation_flow(self) -> None:
        """Test validation flow for creating directories."""
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            test_dir = tmp_path / "newdir"

            entry = LocalPathEntry.from_path(test_dir)
            validate_not_overwriting_file_with_directory(entry, test_dir)
            # Should complete without errors

    def test_create_directory_over_file_validation(self) -> None:
        """Test validation flow for attempting to create directory over file."""
        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            test_file = tmp_path / "test.txt"
            test_file.write_text("content")

            entry = LocalPathEntry.from_path(test_file)
            with pytest.raises(InvalidOperationError):
                validate_not_overwriting_file_with_directory(entry, test_file)


class TestValidationErrorMessages:
    """Tests for validation error messages."""

    def test_not_found_error_includes_path(self) -> None:
        """NotFoundError includes the path in the error message."""
        path = "missing/file.txt"
        with pytest.raises(NotFoundError) as exc_info:
            validate_entry_exists(None, path)

        error_str = str(exc_info.value)
        assert "not found" in error_str.lower() or "missing" in error_str.lower()

    def test_already_exists_error_includes_path(self) -> None:
        """AlreadyExistsError includes the path in the error message."""
        entry = MockEntry(is_dir=False)
        path = "existing/file.txt"
        with pytest.raises(AlreadyExistsError) as exc_info:
            validate_entry_not_exists(entry, path)

        error_str = str(exc_info.value)
        assert "already exists" in error_str.lower() or path in error_str

    def test_invalid_operation_error_includes_path(self) -> None:
        """InvalidOperationError includes the path in the error message."""
        entry = MockEntry(is_dir=True)
        path = "some/directory"
        with pytest.raises(InvalidOperationError) as exc_info:
            validate_is_file(entry, path)

        error_str = str(exc_info.value)
        assert path in error_str


class TestValidationEdgeCases:
    """Tests for edge cases in validation."""

    def test_validate_with_empty_string_path(self) -> None:
        """Validation works with empty string paths."""
        entry = MockEntry(is_dir=False)
        # Should not crash with empty path
        validate_is_file(entry, "")

    def test_validate_with_path_object(self) -> None:
        """Validation works with Path objects."""
        entry = MockEntry(is_dir=False)
        path = Path("test.txt")
        # Should not crash with Path object
        validate_is_file(entry, path)

    def test_validate_with_none_entry_and_path_object(self) -> None:
        """validate_entry_exists works with None entry and Path object."""
        path = Path("missing.txt")
        with pytest.raises(NotFoundError):
            validate_entry_exists(None, path)
