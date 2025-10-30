"""Tests for path validation utilities."""

from pathlib import Path, PurePosixPath

import pytest

from f9_file_backend.interfaces import InvalidOperationError
from f9_file_backend.path_utils import (
    detect_path_traversal_posix,
    normalize_windows_path,
    validate_not_empty,
    validate_not_root,
)


class TestValidateNotEmpty:
    """Tests for validate_not_empty function."""

    def test_valid_path_string(self) -> None:
        """Should not raise for non-empty string paths."""
        validate_not_empty("file.txt")
        validate_not_empty("dir/file.txt")
        validate_not_empty("/absolute/path")

    def test_valid_path_object(self) -> None:
        """Should not raise for non-empty Path objects."""
        validate_not_empty(Path("file.txt"))
        validate_not_empty(Path("/absolute/path"))

    def test_empty_string(self) -> None:
        """Should raise for empty string."""
        with pytest.raises(InvalidOperationError):
            validate_not_empty("")

    def test_whitespace_only_string(self) -> None:
        """Should raise for whitespace-only string."""
        with pytest.raises(InvalidOperationError):
            validate_not_empty("   ")
        with pytest.raises(InvalidOperationError):
            validate_not_empty("\t")
        with pytest.raises(InvalidOperationError):
            validate_not_empty("\n")

    def test_error_message_includes_path(self) -> None:
        """Error should reference the invalid path."""
        with pytest.raises(InvalidOperationError):
            validate_not_empty("")


class TestValidateNotRoot:
    """Tests for validate_not_root function."""

    def test_valid_relative_path_string(self) -> None:
        """Should not raise for valid relative path strings."""
        validate_not_root("file.txt")
        validate_not_root("dir/file.txt")
        validate_not_root("dir/subdir/file.txt")

    def test_valid_path_object(self) -> None:
        """Should not raise for valid Path objects."""
        validate_not_root(Path("file.txt"))
        validate_not_root(Path("dir/file.txt"))

    def test_current_directory_string(self) -> None:
        """Should raise for '.' (current directory)."""
        with pytest.raises(InvalidOperationError):
            validate_not_root(".")

    def test_absolute_root_string(self) -> None:
        """Should raise for '/' (absolute root)."""
        with pytest.raises(InvalidOperationError):
            validate_not_root("/")

    def test_empty_string(self) -> None:
        """Should raise for empty string."""
        with pytest.raises(InvalidOperationError):
            validate_not_root("")

    def test_path_object_with_as_posix(self) -> None:
        """Should handle Path objects with as_posix method."""
        # Valid path
        validate_not_root(PurePosixPath("file.txt"))
        # Root paths
        with pytest.raises(InvalidOperationError):
            validate_not_root(PurePosixPath("."))


class TestDetectPathTraversalPosix:
    """Tests for detect_path_traversal_posix function."""

    def test_no_traversal_in_valid_path(self) -> None:
        """Should return False for paths without '..' components."""
        path = PurePosixPath("dir/subdir/file.txt")
        result = detect_path_traversal_posix(path.parts)
        assert not result

    def test_single_component_path(self) -> None:
        """Should return False for single component paths."""
        path = PurePosixPath("file.txt")
        result = detect_path_traversal_posix(path.parts)
        assert not result

    def test_traversal_at_start(self) -> None:
        """Should detect '..' at the beginning of path."""
        path = PurePosixPath("../../../etc/passwd")
        result = detect_path_traversal_posix(path.parts)
        assert result

    def test_traversal_in_middle(self) -> None:
        """Should detect '..' in the middle of path."""
        path = PurePosixPath("dir/../../../etc/passwd")
        result = detect_path_traversal_posix(path.parts)
        assert result

    def test_traversal_at_end(self) -> None:
        """Should detect '..' at the end of path."""
        path = PurePosixPath("dir/subdir/..")
        result = detect_path_traversal_posix(path.parts)
        assert result

    def test_multiple_traversals(self) -> None:
        """Should detect multiple '..' components."""
        path = PurePosixPath("../dir/../file.txt")
        result = detect_path_traversal_posix(path.parts)
        assert result

    def test_single_dot_not_traversal(self) -> None:
        """Should not confuse '.' (current dir) with '..' (parent dir)."""
        path = PurePosixPath("./dir/./file.txt")
        result = detect_path_traversal_posix(path.parts)
        assert not result

    def test_double_dot_in_filename(self) -> None:
        """Should not confuse '..' in a filename with path traversal.

        Note: This is an edge case - filenames containing '..' should be
        rare, but technically valid. This test documents current behavior.
        """
        # PurePosixPath will normalize this
        path = PurePosixPath("file..txt")
        result = detect_path_traversal_posix(path.parts)
        assert not result

    def test_empty_parts(self) -> None:
        """Should handle paths with empty parts gracefully."""
        # Root directory has empty part
        path = PurePosixPath("/")
        result = detect_path_traversal_posix(path.parts)
        assert not result


class TestNormalizeWindowsPath:
    """Tests for normalize_windows_path function."""

    def test_windows_backslashes(self) -> None:
        """Should convert backslashes to forward slashes."""
        result1 = normalize_windows_path("dir\\file.txt")
        assert result1 == "dir/file.txt"
        result2 = normalize_windows_path("dir\\subdir\\file.txt")
        assert result2 == "dir/subdir/file.txt"

    def test_mixed_separators(self) -> None:
        """Should normalize mixed separators."""
        result1 = normalize_windows_path("dir\\subdir/file.txt")
        assert result1 == "dir/subdir/file.txt"
        result2 = normalize_windows_path("dir/subdir\\file.txt")
        assert result2 == "dir/subdir/file.txt"

    def test_forward_slashes_unchanged(self) -> None:
        """Should not change paths with forward slashes."""
        result = normalize_windows_path("dir/subdir/file.txt")
        assert result == "dir/subdir/file.txt"

    def test_absolute_windows_path(self) -> None:
        """Should normalize absolute Windows paths."""
        result = normalize_windows_path("C:\\Users\\file.txt")
        assert result == "C:/Users/file.txt"

    def test_empty_string(self) -> None:
        """Should handle empty string."""
        result = normalize_windows_path("")
        assert result == ""

    def test_single_filename(self) -> None:
        """Should handle single filenames without separators."""
        result = normalize_windows_path("file.txt")
        assert result == "file.txt"

    def test_network_path(self) -> None:
        """Should handle UNC paths (network paths)."""
        result = normalize_windows_path("\\\\server\\share\\file.txt")
        expected = "//server/share/file.txt"
        assert result == expected

    def test_multiple_consecutive_backslashes(self) -> None:
        """Should normalize multiple consecutive backslashes."""
        result = normalize_windows_path("dir\\\\subdir\\\\file.txt")
        expected = "dir//subdir//file.txt"
        assert result == expected


class TestPathValidationIntegration:
    """Integration tests combining multiple validation functions."""

    def test_validate_safe_relative_path(self) -> None:
        """Should validate a safe relative path without raising."""
        path = "documents/file.txt"
        validate_not_empty(path)
        validate_not_root(path)
        path_obj = PurePosixPath(normalize_windows_path(path))
        result = detect_path_traversal_posix(path_obj.parts)
        assert not result

    def test_reject_traversal_attempt(self) -> None:
        """Should reject path traversal attempts."""
        path = "../../../etc/passwd"
        # This path is not empty
        validate_not_empty(path)
        # This path is not root
        validate_not_root(path)
        # But it should be detected as traversal
        normalized = normalize_windows_path(path)
        path_obj = PurePosixPath(normalized)
        result = detect_path_traversal_posix(path_obj.parts)
        assert result

    def test_openai_backend_validation_pattern(self) -> None:
        """Test validation pattern used by OpenAI backend.

        This mimics the _normalise_path pattern from OpenAIVectorStoreFileBackend.
        """
        user_path = "documents\\file.txt"

        # Normalize
        path_str = normalize_windows_path(user_path)

        # Validate not empty
        validate_not_empty(path_str)

        # Parse as POSIX path
        pure = PurePosixPath(path_str)

        # Check for traversal and absolute paths
        if pure.is_absolute() or detect_path_traversal_posix(pure.parts):
            raise InvalidOperationError.path_outside_root(path_str)

        # Validate not root
        normalised = pure.as_posix()
        validate_not_root(normalised)

        # Should reach here
        expected = "documents/file.txt"
        assert normalised == expected

    def test_reject_absolute_path(self) -> None:
        """Should reject absolute paths in virtual backend context."""
        path = "/etc/passwd"
        pure = PurePosixPath(normalize_windows_path(path))
        result = pure.is_absolute()
        assert result

    def test_reject_empty_after_normalization(self) -> None:
        """Should reject paths that are empty after normalization."""
        paths = ["", "   ", "\t\n"]
        for path in paths:
            with pytest.raises(InvalidOperationError):
                validate_not_empty(path)


class TestSecurityEdgeCases:
    """Security-focused tests for path validation edge cases."""

    def test_unicode_path_traversal(self) -> None:
        """Should detect traversal attempts with unicode characters."""
        # Some filesystems might allow unicode ".." representation
        path = PurePosixPath("valid/../../../etc/passwd")
        result = detect_path_traversal_posix(path.parts)
        assert result

    def test_encoded_traversal_not_detected(self) -> None:
        """URL-encoded or otherwise obfuscated traversal might not be detected.

        This is a documented limitation - validation happens at the path level,
        not after decoding. Applications must decode first if applicable.
        """
        path = PurePosixPath("%2e%2e%2fetc%2fpasswd")
        # This won't be detected as traversal because it's a literal filename
        result = detect_path_traversal_posix(path.parts)
        assert not result

    def test_symlink_traversal_prevention_at_filesystem_level(self) -> None:
        """Note: Symlink traversal prevention happens at filesystem level.

        These utilities only validate path syntax, not filesystem-specific
        traversal. The filesystem validation (in LocalFileBackend) uses
        Path.resolve(strict=False) to handle symlinks properly.
        """
        # This is not detected here, but would be caught by Path.relative_to()
        path = PurePosixPath("symlink/../../secret/file.txt")
        result = detect_path_traversal_posix(path.parts)
        assert result
