"""Tests covering LocalFileBackend operations."""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from f9_file_backend import (
    AlreadyExistsError,
    InvalidOperationError,
    LocalFileBackend,
    NotFoundError,
)


@pytest.fixture
def backend(tmp_path: Path) -> LocalFileBackend:
    """Provide a backend instance scoped to a temporary directory."""
    return LocalFileBackend(root=tmp_path)


def test_create_file(backend: LocalFileBackend) -> None:
    """Ensure file creation writes data and metadata correctly."""
    info = backend.create("foo.txt", data="hello world")
    assert info.path.name == "foo.txt"
    assert not info.is_dir
    assert backend.read("foo.txt", binary=False) == "hello world"

    payload = backend.create("foo.bin", data=io.BytesIO(b"bytes payload"))
    assert backend.read("foo.bin") == b"bytes payload"
    as_dict = payload.as_dict()
    assert as_dict["path"].endswith("foo.bin")
    assert as_dict["is_dir"] is False


def test_create_directory(backend: LocalFileBackend) -> None:
    """Ensure directory creation returns directory info and metadata."""
    info = backend.create("data", is_directory=True)
    assert info.is_dir
    assert info.path.name == "data"
    assert backend.info("data").is_dir


def test_create_existing_without_overwrite(backend: LocalFileBackend) -> None:
    """Verify creating an existing file without overwrite raises."""
    backend.create("foo.txt", data="original")
    with pytest.raises(AlreadyExistsError):
        backend.create("foo.txt", data="new")


def test_create_overwrite_file(backend: LocalFileBackend) -> None:
    """Confirm creating with overwrite replaces prior content."""
    backend.create("foo.txt", data="original")
    backend.create("foo.txt", data="new", overwrite=True)
    assert backend.read("foo.txt", binary=False) == "new"


def test_read_directory_raises(backend: LocalFileBackend) -> None:
    """Reading a directory should raise an error."""
    backend.create("data", is_directory=True)
    with pytest.raises(InvalidOperationError):
        backend.read("data")


def test_update_file_overwrite_and_append(backend: LocalFileBackend) -> None:
    """Verify update supports overwriting and appending file data."""
    backend.create("foo.txt", data="start")
    backend.update("foo.txt", data=" replaced")
    assert backend.read("foo.txt", binary=False) == " replaced"
    backend.update("foo.txt", data=" plus", append=True)
    assert backend.read("foo.txt", binary=False) == " replaced plus"


def test_update_missing_file_raises(backend: LocalFileBackend) -> None:
    """Updating a missing file must raise a not found error."""
    with pytest.raises(NotFoundError):
        backend.update("missing.txt", data="data")


def test_update_directory_raises(backend: LocalFileBackend) -> None:
    """Updating a directory should raise an invalid operation error."""
    backend.create("dir", is_directory=True)
    with pytest.raises(InvalidOperationError):
        backend.update("dir", data="nope")


def test_delete_file_and_directory(backend: LocalFileBackend) -> None:
    """Exercise deletion for both files and directories."""
    backend.create("foo.txt", data="hello")
    backend.delete("foo.txt")
    with pytest.raises(NotFoundError):
        backend.info("foo.txt")

    backend.create("dir", is_directory=True)
    backend.create("dir/a.txt", data="value")
    with pytest.raises(InvalidOperationError):
        backend.delete("dir")

    # Ensure recursive deletion clears nested content
    backend.delete("dir", recursive=True)
    with pytest.raises(NotFoundError):
        backend.info("dir")


def test_info_not_found(backend: LocalFileBackend) -> None:
    """Requesting info on a missing path should raise."""
    with pytest.raises(NotFoundError):
        backend.info("missing.txt")


def test_path_escape_prevented(backend: LocalFileBackend) -> None:
    """Ensure unsafe paths outside the root are rejected."""
    with pytest.raises(InvalidOperationError):
        backend.create("../outside.txt", data="bad")
    with pytest.raises(InvalidOperationError):
        backend.read("../outside.txt")
