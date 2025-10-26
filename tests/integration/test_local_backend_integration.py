"""Integration tests for LocalFileBackend using real filesystem operations."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from f9_file_backend import InvalidOperationError, LocalFileBackend

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def integration_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a dedicated temporary root directory for the backend."""
    return tmp_path_factory.mktemp("backend-integration")


@pytest.fixture
def backend(integration_root: Path) -> LocalFileBackend:
    """Provide a backend instance rooted at the integration directory."""
    return LocalFileBackend(root=integration_root)


def test_full_file_directory_workflow(
    backend: LocalFileBackend,
    integration_root: Path,
) -> None:
    """Exercise creation, updates, reads, and deletion within nested directories."""
    docs_info = backend.create("docs", is_directory=True)
    assert docs_info.is_dir

    backend.create("docs/report.txt", data="draft v1")
    backend.update("docs/report.txt", data="\nrevision", append=True)
    content = backend.read("docs/report.txt", binary=False)
    assert isinstance(content, str)
    assert content.endswith("revision")

    report_info = backend.info("docs/report.txt")
    assert report_info.path == integration_root / "docs" / "report.txt"
    assert report_info.size == len(content.encode("utf-8"))
    assert report_info.created_at is not None
    assert report_info.created_at.tzinfo is not None

    backend.delete("docs", recursive=True)
    assert not (integration_root / "docs").exists()


def test_respects_existing_root(tmp_path_factory: pytest.TempPathFactory) -> None:
    """Verify that create_root=False honours pre-existing directories and files."""
    root = tmp_path_factory.mktemp("existing-root")
    seed_file = root / "seed.txt"
    seed_file.write_text("seed", encoding="utf-8")

    backend = LocalFileBackend(root=root, create_root=False)
    assert backend.read("seed.txt", binary=False) == "seed"

    backend.update("seed.txt", data=" supplement", append=True)
    assert seed_file.read_text(encoding="utf-8") == "seed supplement"


def test_prevents_escape_and_preserves_external_files(
    backend: LocalFileBackend,
    integration_root: Path,
) -> None:
    """Ensure path traversal outside the backend root is blocked."""
    external_file = integration_root.parent / "outside.txt"
    external_file.write_text("external resource", encoding="utf-8")

    with pytest.raises(InvalidOperationError):
        backend.create("../outside.txt", data="intrusion attempt")

    assert external_file.read_text(encoding="utf-8") == "external resource"
