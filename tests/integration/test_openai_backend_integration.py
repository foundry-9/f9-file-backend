"""Integration tests for the OpenAI vector store backend."""

from __future__ import annotations

import pytest

from f9_file_backend import NotFoundError, OpenAIVectorStoreFileBackend
from tests.fakes import FakeOpenAIClient


@pytest.fixture
def fake_client() -> FakeOpenAIClient:
    """Provide a shared fake OpenAI client for integration tests."""
    return FakeOpenAIClient()


def test_openai_backend_shared_state(fake_client: FakeOpenAIClient) -> None:
    """Ensure multiple backend instances observe shared remote state."""
    backend_a = OpenAIVectorStoreFileBackend(
        {"vector_store_id": "vs_integration"},
        client=fake_client,
    )
    backend_b = OpenAIVectorStoreFileBackend(
        {"vector_store_id": "vs_integration"},
        client=fake_client,
    )

    backend_a.create("shared/data.txt", data="hello")
    assert backend_b.read("shared/data.txt", binary=False) == "hello"
    assert backend_b.info("shared").is_dir

    backend_b.update("shared/data.txt", data=" world", append=True)
    assert backend_a.read("shared/data.txt", binary=False) == "hello world"

    backend_b.create("shared/more/info.txt", data="value")
    backend_a.delete("shared", recursive=True)

    with pytest.raises(NotFoundError):
        backend_b.info("shared/data.txt")
