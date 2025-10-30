"""Tests for FileInfo metadata completeness.

This module tests the extended FileInfo dataclass and its metadata features:
- New metadata fields (accessed_at, file_type, permissions, owner_uid, owner_gid,
  checksum, encoding)
- Helper methods (is_text_file, is_binary_file, is_readable, is_modified_since)
- Backend implementations populating metadata across LocalFileBackend,
  GitSyncFileBackend, and OpenAIVectorStoreFileBackend
- Metadata serialization with as_dict()

Test coverage includes:
- Metadata population for files and directories
- Text vs binary file detection
- File type classification
- Permission and ownership metadata
- Timestamp-based comparison operations
- JSON serialization
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from f9_file_backend import FileInfo, FileType, LocalFileBackend

if TYPE_CHECKING:
    from collections.abc import Generator


class TestFileType:
    """Test FileType enum."""

    def test_file_type_values(self) -> None:
        """Test FileType enum values."""
        assert FileType.FILE.value == "file"
        assert FileType.DIRECTORY.value == "directory"
        assert FileType.SYMLINK.value == "symlink"
        assert FileType.OTHER.value == "other"


class TestFileInfoTextBinaryDetection:
    """Test file type detection methods."""

    def test_is_text_file_with_encoding(self) -> None:
        """Test is_text_file returns True when encoding is set."""
        info = FileInfo(
            path=Path("test.txt"),
            is_dir=False,
            size=100,
            created_at=None,
            modified_at=None,
            encoding="utf-8",
        )
        assert info.is_text_file() is True

    def test_is_text_file_without_encoding(self) -> None:
        """Test is_text_file returns False when encoding is None."""
        info = FileInfo(
            path=Path("test.bin"),
            is_dir=False,
            size=100,
            created_at=None,
            modified_at=None,
            encoding=None,
        )
        assert info.is_text_file() is False

    def test_is_binary_file_with_encoding(self) -> None:
        """Test is_binary_file returns False when encoding is set."""
        info = FileInfo(
            path=Path("test.txt"),
            is_dir=False,
            size=100,
            created_at=None,
            modified_at=None,
            encoding="utf-8",
        )
        assert info.is_binary_file() is False

    def test_is_binary_file_without_encoding(self) -> None:
        """Test is_binary_file returns True when encoding is None and not dir."""
        info = FileInfo(
            path=Path("test.bin"),
            is_dir=False,
            size=100,
            created_at=None,
            modified_at=None,
            encoding=None,
        )
        assert info.is_binary_file() is True

    def test_is_binary_file_for_directory(self) -> None:
        """Test is_binary_file returns False for directories."""
        info = FileInfo(
            path=Path("testdir"),
            is_dir=True,
            size=0,
            created_at=None,
            modified_at=None,
            encoding=None,
        )
        assert info.is_binary_file() is False


class TestFileInfoReadablePermissions:
    """Test file permission methods."""

    def test_is_readable_with_owner_read_permission(self) -> None:
        """Test is_readable returns True when owner has read permission."""
        # 0o644 = rw-r--r-- (owner read bit is set)
        info = FileInfo(
            path=Path("test.txt"),
            is_dir=False,
            size=100,
            created_at=None,
            modified_at=None,
            permissions=0o644,
        )
        assert info.is_readable() is True

    def test_is_readable_without_owner_read_permission(self) -> None:
        """Test is_readable returns False when owner doesn't have read permission."""
        # 0o244 = -w-r--r-- (owner read bit is not set)
        info = FileInfo(
            path=Path("test.txt"),
            is_dir=False,
            size=100,
            created_at=None,
            modified_at=None,
            permissions=0o244,
        )
        assert info.is_readable() is False

    def test_is_readable_with_no_permissions(self) -> None:
        """Test is_readable returns False when permissions is None."""
        info = FileInfo(
            path=Path("test.txt"),
            is_dir=False,
            size=100,
            created_at=None,
            modified_at=None,
            permissions=None,
        )
        assert info.is_readable() is False


class TestFileInfoModificationTime:
    """Test modification time comparison methods."""

    def test_is_modified_since_after_timestamp(self) -> None:
        """Test is_modified_since returns True when modified after timestamp."""
        now = datetime.now(tz=timezone.utc)
        past = now - timedelta(hours=1)

        info = FileInfo(
            path=Path("test.txt"),
            is_dir=False,
            size=100,
            created_at=None,
            modified_at=now,
        )
        assert info.is_modified_since(past) is True

    def test_is_modified_since_before_timestamp(self) -> None:
        """Test is_modified_since returns False when modified before timestamp."""
        now = datetime.now(tz=timezone.utc)
        future = now + timedelta(hours=1)

        info = FileInfo(
            path=Path("test.txt"),
            is_dir=False,
            size=100,
            created_at=None,
            modified_at=now,
        )
        assert info.is_modified_since(future) is False

    def test_is_modified_since_with_no_modified_at(self) -> None:
        """Test is_modified_since returns False when modified_at is None."""
        now = datetime.now(tz=timezone.utc)

        info = FileInfo(
            path=Path("test.txt"),
            is_dir=False,
            size=100,
            created_at=None,
            modified_at=None,
        )
        assert info.is_modified_since(now) is False

    def test_is_modified_since_at_exact_timestamp(self) -> None:
        """Test is_modified_since returns False when modified at exact timestamp."""
        now = datetime.now(tz=timezone.utc)

        info = FileInfo(
            path=Path("test.txt"),
            is_dir=False,
            size=100,
            created_at=None,
            modified_at=now,
        )
        assert info.is_modified_since(now) is False


class TestFileInfoSerialization:
    """Test FileInfo serialization methods."""

    def test_as_dict_with_all_fields(self) -> None:
        """Test as_dict includes all metadata fields."""
        now = datetime.now(tz=timezone.utc)
        info = FileInfo(
            path=Path("test.txt"),
            is_dir=False,
            size=1024,
            created_at=now,
            modified_at=now,
            accessed_at=now,
            file_type=FileType.FILE,
            permissions=0o644,
            owner_uid=1000,
            owner_gid=1000,
            checksum="abc123",
            encoding="utf-8",
        )

        result = info.as_dict()

        assert result["path"] == "test.txt"
        assert result["is_dir"] is False
        assert result["size"] == 1024
        assert result["created_at"] == now.isoformat()
        assert result["modified_at"] == now.isoformat()
        assert result["accessed_at"] == now.isoformat()
        assert result["file_type"] == "file"
        assert result["permissions"] == 0o644
        assert result["owner_uid"] == 1000
        assert result["owner_gid"] == 1000
        assert result["checksum"] == "abc123"
        assert result["encoding"] == "utf-8"

    def test_as_dict_with_none_fields(self) -> None:
        """Test as_dict handles None fields correctly."""
        info = FileInfo(
            path=Path("test.txt"),
            is_dir=False,
            size=100,
            created_at=None,
            modified_at=None,
            accessed_at=None,
            file_type=None,
            permissions=None,
            owner_uid=None,
            owner_gid=None,
            checksum=None,
            encoding=None,
        )

        result = info.as_dict()

        assert result["created_at"] is None
        assert result["modified_at"] is None
        assert result["accessed_at"] is None
        assert result["file_type"] is None
        assert result["permissions"] is None
        assert result["owner_uid"] is None
        assert result["owner_gid"] is None
        assert result["checksum"] is None
        assert result["encoding"] is None


class TestLocalFileBackendMetadata:
    """Test LocalFileBackend metadata population."""

    def test_file_info_populates_basic_fields(self, tmp_path: Path) -> None:
        """Test that file info populates basic metadata."""
        backend = LocalFileBackend(root=tmp_path)
        backend.create("test.txt", data=b"Hello, world!")

        info = backend.info("test.txt")

        assert info.path.name == "test.txt"
        assert info.is_dir is False
        assert info.size == 13
        assert info.created_at is not None
        assert info.modified_at is not None

    def test_file_info_populates_file_type(self, tmp_path: Path) -> None:
        """Test that file type is correctly identified."""
        backend = LocalFileBackend(root=tmp_path)
        backend.create("test.txt", data=b"Hello")

        info = backend.info("test.txt")

        assert info.file_type == FileType.FILE

    def test_file_info_populates_directory_type(self, tmp_path: Path) -> None:
        """Test that directory type is correctly identified."""
        backend = LocalFileBackend(root=tmp_path)
        backend.create("testdir", is_directory=True)

        info = backend.info("testdir")

        assert info.file_type == FileType.DIRECTORY
        assert info.is_dir is True

    def test_file_info_detects_text_encoding(self, tmp_path: Path) -> None:
        """Test that text file encoding is detected."""
        backend = LocalFileBackend(root=tmp_path)
        backend.create("test.txt", data=b"Hello, world!")

        info = backend.info("test.txt")

        assert info.encoding == "utf-8"
        assert info.is_text_file() is True

    def test_file_info_detects_binary_encoding(self, tmp_path: Path) -> None:
        """Test that binary file encoding is None."""
        backend = LocalFileBackend(root=tmp_path)
        # Create binary data that's not valid UTF-8
        binary_data = b"\x80\x81\x82\x83"
        backend.create("test.bin", data=binary_data)

        info = backend.info("test.bin")

        assert info.encoding is None
        assert info.is_binary_file() is True

    def test_file_info_populates_permissions(self, tmp_path: Path) -> None:
        """Test that file permissions are populated."""
        backend = LocalFileBackend(root=tmp_path)
        backend.create("test.txt", data=b"Hello")

        info = backend.info("test.txt")

        assert info.permissions is not None
        assert info.is_readable() is True

    def test_file_info_populates_timestamps(self, tmp_path: Path) -> None:
        """Test that all timestamps are populated."""
        backend = LocalFileBackend(root=tmp_path)
        backend.create("test.txt", data=b"Hello")

        info = backend.info("test.txt")

        assert info.created_at is not None
        assert info.modified_at is not None
        assert info.accessed_at is not None

    def test_file_info_directory_has_no_encoding(self, tmp_path: Path) -> None:
        """Test that directories have None encoding."""
        backend = LocalFileBackend(root=tmp_path)
        backend.create("testdir", is_directory=True)

        info = backend.info("testdir")

        assert info.encoding is None


class TestLocalFileBackendMetadataUpdate:
    """Test that metadata is updated correctly on file operations."""

    def test_metadata_after_create(self, tmp_path: Path) -> None:
        """Test metadata is set correctly after create."""
        backend = LocalFileBackend(root=tmp_path)
        hello_text = b"Hello"
        info = backend.create("test.txt", data=hello_text)

        assert info.file_type == FileType.FILE
        assert info.size == len(hello_text)  # noqa: PLR2004
        assert info.encoding == "utf-8"

    def test_metadata_after_update(self, tmp_path: Path) -> None:
        """Test metadata is updated correctly after update."""
        backend = LocalFileBackend(root=tmp_path)
        backend.create("test.txt", data=b"Hello")
        old_info = backend.info("test.txt")
        old_modified = old_info.modified_at

        # Wait a bit to ensure timestamp changes
        import time
        time.sleep(0.01)

        new_content = b"Hello, world!"
        updated_info = backend.update("test.txt", data=new_content)

        assert updated_info.size == len(new_content)
        assert updated_info.modified_at > old_modified

    def test_metadata_after_stream_write(self, tmp_path: Path) -> None:
        """Test metadata is correct after stream write."""
        backend = LocalFileBackend(root=tmp_path)

        def chunk_source() -> Generator[bytes, None, None]:
            yield b"Hello, "
            yield b"world!"

        info = backend.stream_write("test.txt", chunk_source=chunk_source())

        expected_size = len(b"Hello, ") + len(b"world!")
        assert info.file_type == FileType.FILE
        assert info.size == expected_size
        assert info.encoding == "utf-8"


class TestFileInfoFrozenDataclass:
    """Test FileInfo dataclass immutability."""

    def test_file_info_is_frozen(self) -> None:
        """Test that FileInfo instances are immutable."""
        info = FileInfo(
            path=Path("test.txt"),
            is_dir=False,
            size=100,
            created_at=None,
            modified_at=None,
        )

        with pytest.raises((AttributeError, TypeError)):
            info.size = 200  # type: ignore

    def test_file_info_is_hashable(self) -> None:
        """Test that FileInfo instances are hashable."""
        info = FileInfo(
            path=Path("test.txt"),
            is_dir=False,
            size=100,
            created_at=None,
            modified_at=None,
        )

        # Should be able to use in a set
        file_set = {info}
        assert info in file_set
