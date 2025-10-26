"""Tests covering the Git-backed synchronised file backend."""

from __future__ import annotations

import os
import shutil
import subprocess
from typing import TYPE_CHECKING

import pytest

from f9_file_backend import GitBackendError, GitSyncFileBackend, SyncConflict

if TYPE_CHECKING:
    from pathlib import Path


def _run_git(args: list[str], *, cwd: Path | None = None) -> str:
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
def git_backend(tmp_path: Path, git_remote: Path) -> GitSyncFileBackend:
    """Provide a Git backend instance pointing at the remote repository."""
    workdir = tmp_path / "work" / "clone"
    connection_info = {
        "remote_url": str(git_remote),
        "path": str(workdir),
        "branch": "main",
        "author_name": "Test User",
        "author_email": "test@example.com",
    }
    return GitSyncFileBackend(connection_info)


def test_git_backend_push_creates_remote_commit(
    git_backend: GitSyncFileBackend,
    git_remote: Path,
) -> None:
    """Ensure pushing propagates content to the remote repository."""
    git_backend.create("notes.txt", data="hello world\n")
    git_backend.push(message="Add notes")

    content = _run_git(
        ["--git-dir", str(git_remote), "show", "main:notes.txt"],
    )
    assert content == "hello world"


def test_git_backend_conflict_report_and_resolution(
    tmp_path: Path,
    git_backend: GitSyncFileBackend,
    git_remote: Path,
) -> None:
    """Exercise merge conflict reporting and resolution."""
    git_backend.create("shared.txt", data="local base\n")
    git_backend.push(message="Base commit")

    # Apply a conflicting change via a secondary clone.
    other_clone = tmp_path / "other"
    _run_git(["clone", str(git_remote), str(other_clone)])
    _run_git(["config", "user.name", "Remote User"], cwd=other_clone)
    _run_git(["config", "user.email", "remote@example.com"], cwd=other_clone)
    (other_clone / "shared.txt").write_text("remote change\n", encoding="utf-8")
    _run_git(["commit", "-am", "Remote change"], cwd=other_clone)
    _run_git(["push", "origin", "main"], cwd=other_clone)

    git_backend.update("shared.txt", data="local change\n")
    with pytest.raises(GitBackendError):
        git_backend.push(message="Local change")

    with pytest.raises(GitBackendError):
        git_backend.pull()

    conflicts = git_backend.conflict_report()
    assert conflicts
    assert all(isinstance(conflict, SyncConflict) for conflict in conflicts)
    conflict_paths = {conflict.path.name for conflict in conflicts}
    assert "shared.txt" in conflict_paths

    git_backend.conflict_resolve("shared.txt", data="resolved value\n")
    assert not git_backend.conflict_report()

    git_backend.push(message="Resolve conflict")

    content = _run_git(
        ["--git-dir", str(git_remote), "show", "main:shared.txt"],
    )
    assert content == "resolved value"
