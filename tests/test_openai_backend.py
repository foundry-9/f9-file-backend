"""Unit tests covering the OpenAI vector store file backend."""

from __future__ import annotations

import pytest

from f9_file_backend import (
    AlreadyExistsError,
    InvalidOperationError,
    NotFoundError,
    OpenAIVectorStoreFileBackend,
)
from tests.fakes import FakeOpenAIClient


@pytest.fixture
def fake_client() -> FakeOpenAIClient:
    """Expose a fresh fake OpenAI client per test."""
    return FakeOpenAIClient()


@pytest.fixture
def backend(fake_client: FakeOpenAIClient) -> OpenAIVectorStoreFileBackend:
    """Provide a backend instance bound to the fake client."""
    return OpenAIVectorStoreFileBackend(
        {"vector_store_id": "vs_test"},
        client=fake_client,
    )


def test_create_and_read_file(backend: OpenAIVectorStoreFileBackend) -> None:
    """Creating a file should persist and return readable content."""
    info = backend.create("docs/readme.txt", data="hello world")
    assert info.path.as_posix() == "docs/readme.txt"
    assert info.size == len("hello world")
    assert not info.is_dir

    content = backend.read("docs/readme.txt", binary=False)
    assert content == "hello world"


def test_create_existing_requires_overwrite(
    backend: OpenAIVectorStoreFileBackend,
) -> None:
    """Creating an existing file without overwrite should raise."""
    backend.create("notes.txt", data="initial")
    with pytest.raises(AlreadyExistsError):
        backend.create("notes.txt", data="other")

    backend.create("notes.txt", data="replacement", overwrite=True)
    assert backend.read("notes.txt", binary=False) == "replacement"


def test_create_directory_and_nested_file(
    backend: OpenAIVectorStoreFileBackend,
) -> None:
    """Explicit directory creation should succeed and allow nested files."""
    directory_info = backend.create("reports", is_directory=True)
    assert directory_info.is_dir
    assert directory_info.path.as_posix() == "reports"

    nested_info = backend.create("reports/daily.txt", data="payload")
    assert not nested_info.is_dir
    assert nested_info.path.as_posix() == "reports/daily.txt"
    assert backend.info("reports").is_dir


def test_read_directory_raises(backend: OpenAIVectorStoreFileBackend) -> None:
    """Attempting to read a directory should raise an invalid operation error."""
    backend.create("data", is_directory=True)
    with pytest.raises(InvalidOperationError):
        backend.read("data")


def test_update_file_overwrite_and_append(
    backend: OpenAIVectorStoreFileBackend,
) -> None:
    """Updating a file should support overwrite and append modes."""
    backend.create("data.txt", data="start")
    backend.update("data.txt", data="replace")
    assert backend.read("data.txt", binary=False) == "replace"

    backend.update("data.txt", data=" plus", append=True)
    assert backend.read("data.txt", binary=False) == "replace plus"


def test_update_missing_file_raises(
    backend: OpenAIVectorStoreFileBackend,
) -> None:
    """Updating a missing path should raise a not found error."""
    with pytest.raises(NotFoundError):
        backend.update("missing.txt", data="payload")


def test_delete_directory_requires_recursive(
    backend: OpenAIVectorStoreFileBackend,
) -> None:
    """Deleting a populated directory without recursive flag should raise."""
    backend.create("nested/data.txt", data="value")
    with pytest.raises(InvalidOperationError):
        backend.delete("nested")


def test_recursive_delete_directory(
    backend: OpenAIVectorStoreFileBackend,
) -> None:
    """Recursive deletion should remove directories and their contents."""
    backend.create("nested/data.txt", data="value")
    backend.create("nested/deeper/more.txt", data="value")
    backend.delete("nested", recursive=True)

    with pytest.raises(NotFoundError):
        backend.info("nested")


def test_path_escape_is_blocked(backend: OpenAIVectorStoreFileBackend) -> None:
    """Ensure attempts to escape the logical root are rejected."""
    with pytest.raises(InvalidOperationError):
        backend.create("../outside.txt", data="bad")
    with pytest.raises(InvalidOperationError):
        backend.create("dir/../../escape.txt", data="bad")
