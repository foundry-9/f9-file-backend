"""Tests for GitSyncFileBackend auto-sync functionality."""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from f9_file_backend import GitSyncFileBackend


def _run_git(args: list[str], *, cwd: Path | None = None) -> str:
    """Run a git command."""
    git_executable = os.environ.get("GIT_EXECUTABLE")
    if not git_executable:
        git_executable = shutil.which("git")
    if not git_executable:
        message = "Unable to locate git executable for tests"
        raise RuntimeError(message)
    result = subprocess.run(  # noqa: S603 - tests invoke trusted git binary
        [git_executable, *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


@pytest.fixture
def git_remote(tmp_path: Path) -> Path:
    """Create a bare Git repository with an initial main branch."""
    remote = tmp_path / "remote.git"
    _run_git(["init", "--bare", str(remote)])

    seed = tmp_path / "seed"
    seed.mkdir()
    _run_git(["init"], cwd=seed)
    _run_git(["config", "user.name", "Seed User"], cwd=seed)
    _run_git(["config", "user.email", "seed@example.com"], cwd=seed)
    (seed / "README.md").write_text("seed\n", encoding="utf-8")
    _run_git(["add", "README.md"], cwd=seed)
    _run_git(["commit", "-m", "Initial commit"], cwd=seed)
    _run_git(["branch", "-M", "main"], cwd=seed)
    _run_git(["remote", "add", "origin", str(remote)], cwd=seed)
    _run_git(["push", "origin", "main"], cwd=seed)
    return remote


@pytest.fixture
def git_backend(tmp_path: Path, git_remote: Path):
    """Create a GitSyncFileBackend instance."""
    workdir = tmp_path / "work" / "clone"
    connection_info = {
        "remote_url": str(git_remote),
        "path": str(workdir),
        "branch": "main",
        "author_name": "Test User",
        "author_email": "test@example.com",
        "auto_pull": False,
        "auto_push": False,
    }
    return GitSyncFileBackend(connection_info)


class TestAutoPull:
    """Tests for auto-pull functionality."""

    def test_auto_pull_disabled_by_default(self, git_backend: Any) -> None:  # noqa: ANN001
        """Auto-pull should be disabled by default."""
        assert git_backend._auto_pull is False  # noqa: S101

    def test_auto_pull_on_read(self, tmp_path, git_remote):
        """Reading a file should trigger pull if auto_pull is enabled."""
        workdir = tmp_path / "clone_pull"
        backend = GitSyncFileBackend(
            connection_info={
                "remote_url": str(git_remote),
                "path": str(workdir),
                "branch": "main",
                "auto_pull": True,
                "auto_push": False,
                "author_name": "Test User",
                "author_email": "test@example.com",
            },
        )

        # Mock the pull method to track calls
        pull_calls = []

        def tracked_pull() -> None:  # noqa: ANN202
            pull_calls.append(True)

        backend.pull = tracked_pull

        # Reading a file should trigger pull
        try:
            backend.read("nonexistent.txt")
        except Exception:
            # File doesn't exist, but pull should have been called
            pass

        assert len(pull_calls) == 1  # noqa: S101

    def test_auto_pull_on_info(self, tmp_path, git_remote):
        """Getting info should trigger pull if auto_pull is enabled."""
        workdir = tmp_path / "clone_info"
        backend = GitSyncFileBackend(
            connection_info={
                "remote_url": str(git_remote),
                "path": str(workdir),
                "branch": "main",
                "auto_pull": True,
                "auto_push": False,
                "author_name": "Test User",
                "author_email": "test@example.com",
            },
        )

        # Mock the pull method
        pull_calls = []

        def tracked_pull() -> None:  # noqa: ANN202
            pull_calls.append(True)

        backend.pull = tracked_pull

        # Getting info should trigger pull
        try:
            backend.info("nonexistent.txt")
        except Exception:
            pass

        assert len(pull_calls) == 1  # noqa: S101

    def test_auto_pull_on_stream_read(self, tmp_path, git_remote):
        """Stream reading should trigger pull if auto_pull is enabled."""
        workdir = tmp_path / "clone_stream_read"
        backend = GitSyncFileBackend(
            connection_info={
                "remote_url": str(git_remote),
                "path": str(workdir),
                "branch": "main",
                "auto_pull": True,
                "auto_push": False,
                "author_name": "Test User",
                "author_email": "test@example.com",
            },
        )

        # Mock the pull method
        pull_calls = []

        def tracked_pull() -> None:  # noqa: ANN202
            pull_calls.append(True)

        backend.pull = tracked_pull

        # Stream reading should trigger pull
        try:
            list(backend.stream_read("nonexistent.txt"))
        except Exception:
            pass

        assert len(pull_calls) == 1  # noqa: S101

    def test_auto_pull_skipped_in_session(self, tmp_path, git_remote):
        """Auto-pull should not happen inside a sync_session."""
        workdir = tmp_path / "clone_session_pull"
        backend = GitSyncFileBackend(
            connection_info={
                "remote_url": str(git_remote),
                "path": str(workdir),
                "branch": "main",
                "auto_pull": True,
                "auto_push": False,
                "author_name": "Test User",
                "author_email": "test@example.com",
            },
        )

        # Mock the pull method
        pull_calls = []

        def tracked_pull() -> None:  # noqa: ANN202
            pull_calls.append(True)

        backend.pull = tracked_pull

        # Read inside a session should not trigger individual pulls
        with backend.sync_session():
            try:
                backend.read("file1.txt")
                backend.read("file2.txt")
            except Exception:
                pass

        # Only one pull at the start of the session
        assert len(pull_calls) == 1  # noqa: S101


class TestAutoPush:
    """Tests for auto-push functionality."""

    def test_auto_push_disabled_by_default(self, git_backend):
        """Auto-push should be disabled by default."""
        assert git_backend._auto_push is False  # noqa: S101

    def test_auto_push_on_create(self, tmp_path, git_remote):
        """Creating a file should trigger push if auto_push is enabled."""
        workdir = tmp_path / "clone_create"
        backend = GitSyncFileBackend(
            connection_info={
                "remote_url": str(git_remote),
                "path": str(workdir),
                "branch": "main",
                "auto_pull": False,
                "auto_push": True,
                "author_name": "Test User",
                "author_email": "test@example.com",
            },
        )

        # Mock the push method
        push_calls = []

        def tracked_push(message: str | None = None) -> None:  # noqa: ANN202
            push_calls.append(message or "")

        backend.push = tracked_push

        # Create should trigger push
        backend.create("test.txt", data=b"hello")

        assert len(push_calls) == 1  # noqa: S101
        assert "test.txt" in push_calls[0]  # noqa: S101

    def test_auto_push_on_update(self, tmp_path, git_remote):
        """Updating a file should trigger push if auto_push is enabled."""
        workdir = tmp_path / "clone_update"
        backend = GitSyncFileBackend(
            connection_info={
                "remote_url": str(git_remote),
                "path": str(workdir),
                "branch": "main",
                "auto_pull": False,
                "auto_push": True,
                "author_name": "Test User",
                "author_email": "test@example.com",
            },
        )

        # Create a file first
        backend._local_backend.create("test.txt", data=b"hello")

        # Mock the push method
        push_calls = []

        def tracked_push(message: str | None = None) -> None:  # noqa: ANN202
            push_calls.append(message or "")

        backend.push = tracked_push

        # Update should trigger push
        backend.update("test.txt", data=b"world")

        assert len(push_calls) == 1  # noqa: S101
        assert "test.txt" in push_calls[0]  # noqa: S101

    def test_auto_push_on_delete(self, tmp_path, git_remote):
        """Deleting a file should trigger push if auto_push is enabled."""
        workdir = tmp_path / "clone_delete"
        backend = GitSyncFileBackend(
            connection_info={
                "remote_url": str(git_remote),
                "path": str(workdir),
                "branch": "main",
                "auto_pull": False,
                "auto_push": True,
                "author_name": "Test User",
                "author_email": "test@example.com",
            },
        )

        # Create a file first
        backend._local_backend.create("test.txt", data=b"hello")

        # Mock the push method
        push_calls = []

        def tracked_push(message: str | None = None) -> None:  # noqa: ANN202
            push_calls.append(message or "")

        backend.push = tracked_push

        # Delete should trigger push
        backend.delete("test.txt")

        assert len(push_calls) == 1  # noqa: S101
        assert "test.txt" in push_calls[0]  # noqa: S101

    def test_auto_push_on_stream_write(self, tmp_path, git_remote):
        """Stream writing should trigger push if auto_push is enabled."""
        workdir = tmp_path / "clone_stream_write"
        backend = GitSyncFileBackend(
            connection_info={
                "remote_url": str(git_remote),
                "path": str(workdir),
                "branch": "main",
                "auto_pull": False,
                "auto_push": True,
                "author_name": "Test User",
                "author_email": "test@example.com",
            },
        )

        # Mock the push method
        push_calls = []

        def tracked_push(message: str | None = None) -> None:  # noqa: ANN202
            push_calls.append(message or "")

        backend.push = tracked_push

        # Stream write should trigger push
        def chunk_generator():  # noqa: ANN202
            yield b"hello"  # noqa: PYI053
            yield b" world"  # noqa: PYI053

        backend.stream_write("test.txt", chunk_source=chunk_generator())

        assert len(push_calls) == 1  # noqa: S101
        assert "test.txt" in push_calls[0]  # noqa: S101

    def test_auto_push_skipped_in_session(self, tmp_path, git_remote):
        """Auto-push should not happen inside a sync_session."""
        workdir = tmp_path / "clone_session_push"
        backend = GitSyncFileBackend(
            connection_info={
                "remote_url": str(git_remote),
                "path": str(workdir),
                "branch": "main",
                "auto_pull": False,
                "auto_push": True,
                "author_name": "Test User",
                "author_email": "test@example.com",
            },
        )

        # Mock the push method
        push_calls = []

        def tracked_push(message: str | None = None) -> None:  # noqa: ANN202
            push_calls.append(message or "")

        backend.push = tracked_push

        # Create inside a session should not trigger individual pushes
        with backend.sync_session():
            backend.create("file1.txt", data=b"hello")
            backend.create("file2.txt", data=b"world")

        # Only one push at the end of the session
        assert len(push_calls) == 1  # noqa: S101
        assert "Batch" in push_calls[0]  # noqa: S101


class TestSyncSession:
    """Tests for sync_session behavior with auto-sync."""

    def test_sync_session_batches_pulls(self, tmp_path, git_remote):
        """Sync session should batch pull operations."""
        workdir = tmp_path / "clone_batch_pull"
        backend = GitSyncFileBackend(
            connection_info={
                "remote_url": str(git_remote),
                "path": str(workdir),
                "branch": "main",
                "auto_pull": True,
                "auto_push": False,
                "author_name": "Test User",
                "author_email": "test@example.com",
            },
        )

        # Mock the pull method
        pull_calls = []

        def tracked_pull() -> None:  # noqa: ANN202
            pull_calls.append(True)

        backend.pull = tracked_pull

        # Multiple reads in a session should only pull once at the start
        with backend.sync_session():
            for i in range(5):
                try:
                    backend.read(f"file{i}.txt")
                except Exception:
                    pass

        # Only one pull at the start of the session
        assert len(pull_calls) == 1  # noqa: S101

    def test_sync_session_batches_pushes(self, tmp_path, git_remote):
        """Sync session should batch push operations."""
        workdir = tmp_path / "clone_batch_push"
        backend = GitSyncFileBackend(
            connection_info={
                "remote_url": str(git_remote),
                "path": str(workdir),
                "branch": "main",
                "auto_pull": False,
                "auto_push": True,
                "author_name": "Test User",
                "author_email": "test@example.com",
            },
        )

        # Mock the push method
        push_calls = []

        def tracked_push(message: str | None = None) -> None:  # noqa: ANN202
            push_calls.append(message or "")

        backend.push = tracked_push

        # Multiple creates in a session should only push once at the end
        with backend.sync_session():
            for i in range(5):
                backend.create(f"file{i}.txt", data=f"content{i}".encode())

        # Only one push at the end of the session
        assert len(push_calls) == 1  # noqa: S101
        assert "Batch" in push_calls[0]  # noqa: S101

    def test_sync_session_pulls_then_pushes(self, tmp_path, git_remote):
        """Sync session should pull at start and push at end."""
        workdir = tmp_path / "clone_pull_push"
        backend = GitSyncFileBackend(
            connection_info={
                "remote_url": str(git_remote),
                "path": str(workdir),
                "branch": "main",
                "auto_pull": True,
                "auto_push": True,
                "author_name": "Test User",
                "author_email": "test@example.com",
            },
        )

        # Track calls in order
        call_order = []

        def tracked_pull() -> None:  # noqa: ANN202
            call_order.append("pull")

        def tracked_push(message: str | None = None) -> None:  # noqa: ANN202
            call_order.append("push")

        backend.pull = tracked_pull
        backend.push = tracked_push

        # Session should pull first, then push
        with backend.sync_session():
            backend.create("test.txt", data=b"hello")

        assert call_order == ["pull", "push"]  # noqa: S101

    def test_sync_session_without_auto_sync(self, git_backend):
        """Sync session should work normally without auto-sync enabled."""
        # Mock the pull and push methods
        pull_calls = []
        push_calls = []

        def tracked_pull() -> None:  # noqa: ANN202
            pull_calls.append(True)

        def tracked_push(message: str | None = None) -> None:  # noqa: ANN202
            push_calls.append(True)

        git_backend.pull = tracked_pull
        git_backend.push = tracked_push

        # Session should not call pull or push
        with git_backend.sync_session():
            git_backend.create("test.txt", data=b"hello")

        assert len(pull_calls) == 0  # noqa: S101
        assert len(push_calls) == 0  # noqa: S101


class TestConfigurationOptions:
    """Tests for auto_pull and auto_push configuration."""

    def test_auto_pull_from_config(self, tmp_path, git_remote):
        """auto_pull should be configurable from connection_info."""
        workdir = tmp_path / "clone_config_pull"
        backend = GitSyncFileBackend(
            connection_info={
                "remote_url": str(git_remote),
                "path": str(workdir),
                "branch": "main",
                "auto_pull": True,
                "author_name": "Test User",
                "author_email": "test@example.com",
            },
        )
        assert backend._auto_pull is True  # noqa: S101

    def test_auto_push_from_config(self, tmp_path, git_remote):
        """auto_push should be configurable from connection_info."""
        workdir = tmp_path / "clone_config_push"
        backend = GitSyncFileBackend(
            connection_info={
                "remote_url": str(git_remote),
                "path": str(workdir),
                "branch": "main",
                "auto_push": True,
                "author_name": "Test User",
                "author_email": "test@example.com",
            },
        )
        assert backend._auto_push is True  # noqa: S101

    def test_both_auto_sync_options(self, tmp_path, git_remote):
        """Both auto_pull and auto_push can be enabled together."""
        workdir = tmp_path / "clone_config_both"
        backend = GitSyncFileBackend(
            connection_info={
                "remote_url": str(git_remote),
                "path": str(workdir),
                "branch": "main",
                "auto_pull": True,
                "auto_push": True,
                "author_name": "Test User",
                "author_email": "test@example.com",
            },
        )
        assert backend._auto_pull is True  # noqa: S101
        assert backend._auto_push is True  # noqa: S101

    def test_in_session_flag_initialized(self, git_backend):
        """_in_session flag should be initialized to False."""
        assert git_backend._in_session is False  # noqa: S101
