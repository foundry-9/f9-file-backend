"""Integration tests for GitSyncFileBackend synchronisation workflows."""

from __future__ import annotations

import os
import secrets
import shutil
import subprocess
from functools import lru_cache
from typing import TYPE_CHECKING

import pytest

from f9_file_backend import GitBackendError, GitSyncFileBackend

if TYPE_CHECKING:
    from pathlib import Path


@lru_cache(maxsize=1)
def _git_executable() -> str:
    env_override = os.environ.get("GIT_EXECUTABLE")
    if env_override:
        return env_override
    located = shutil.which("git")
    if not located:
        message = "Unable to locate git executable for integration tests"
        raise RuntimeError(message)
    return located


def _run_git(args: list[str], *, cwd: Path | None = None) -> str:
    executable = _git_executable()
    result = subprocess.run(  # noqa: S603 - tests execute trusted git binary with fixed args
        [executable, *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _create_random_files(base: Path, *, count: int = 3) -> list[Path]:
    """Populate the provided directory with randomly named text files."""
    relative_paths: list[Path] = []
    for index in range(count):
        subdir = base / f"dir_{index}"
        subdir.mkdir(parents=True, exist_ok=True)
        file_path = subdir / f"{secrets.token_hex(4)}.txt"
        file_path.write_text(secrets.token_hex(16), encoding="utf-8")
        relative_paths.append(file_path.relative_to(base))

    root_file = base / f"{secrets.token_hex(4)}.txt"
    root_file.write_text(secrets.token_hex(16), encoding="utf-8")
    relative_paths.append(root_file.relative_to(base))
    return relative_paths


def test_git_backend_end_to_end_sync(tmp_path: Path) -> None:
    """Verify sync, push, pull, and conflict resolution against a real repository."""
    seed_repo = tmp_path / "seed"
    seed_repo.mkdir()
    _run_git(["init"], cwd=seed_repo)
    _run_git(["config", "user.name", "Seed User"], cwd=seed_repo)
    _run_git(["config", "user.email", "seed@example.com"], cwd=seed_repo)
    _run_git(["config", "commit.gpgsign", "false"], cwd=seed_repo)

    relative_paths = _create_random_files(seed_repo)
    _run_git(["add", "."], cwd=seed_repo)
    _run_git(["commit", "-m", "Initial random files"], cwd=seed_repo)
    _run_git(["branch", "-M", "main"], cwd=seed_repo)

    remote_repo = tmp_path / "remote.git"
    _run_git(["init", "--bare", str(remote_repo)])
    _run_git(["remote", "add", "origin", str(remote_repo)], cwd=seed_repo)
    _run_git(["push", "origin", "main"], cwd=seed_repo)
    _run_git(["symbolic-ref", "HEAD", "refs/heads/main"], cwd=remote_repo)

    workdir = tmp_path / "backend"
    backend = GitSyncFileBackend(
        {
            "remote_url": str(remote_repo),
            "path": str(workdir),
            "branch": "main",
            "author_name": "Integration Tester",
            "author_email": "integration@example.com",
        },
    )

    for rel_path in relative_paths:
        expected = (seed_repo / rel_path).read_text(encoding="utf-8")
        observed = backend.read(rel_path.as_posix(), binary=False)
        assert observed == expected

    new_file = f"new_{secrets.token_hex(6)}.txt"
    new_content = f"fresh-content-{secrets.token_hex(8)}\n"
    backend.create(new_file, data=new_content)
    backend.push(message="Add integration test content")
    remote_new_content = _run_git(
        ["--git-dir", str(remote_repo), "show", f"main:{new_file}"],
    )
    assert remote_new_content == new_content.rstrip("\n")

    conflict_rel_path = relative_paths[0]
    local_update = f"local-update-{secrets.token_hex(6)}\n"
    backend.update(conflict_rel_path.as_posix(), data=local_update)
    backend.push(message="Local update before conflict")

    remote_clone = tmp_path / "remote_clone"
    _run_git(["clone", str(remote_repo), str(remote_clone)])
    _run_git(["config", "user.name", "Remote User"], cwd=remote_clone)
    _run_git(["config", "user.email", "remote@example.com"], cwd=remote_clone)
    _run_git(["config", "commit.gpgsign", "false"], cwd=remote_clone)
    remote_conflict_content = f"remote-change-{secrets.token_hex(6)}\n"
    (remote_clone / conflict_rel_path).write_text(
        remote_conflict_content,
        encoding="utf-8",
    )
    _run_git(["commit", "-am", "Remote conflicting change"], cwd=remote_clone)
    _run_git(["push", "origin", "main"], cwd=remote_clone)

    local_conflict_content = f"local-conflict-{secrets.token_hex(6)}\n"
    backend.update(conflict_rel_path.as_posix(), data=local_conflict_content)
    with pytest.raises(GitBackendError):
        backend.push(message="Attempt conflicting push")

    with pytest.raises(GitBackendError):
        backend.pull()

    conflicts = backend.conflict_report()
    assert conflicts
    conflict_paths = {conflict.path.name for conflict in conflicts}
    assert conflict_rel_path.name in conflict_paths

    resolved_content = f"resolved-{secrets.token_hex(6)}\n"
    backend.conflict_resolve(conflict_rel_path.as_posix(), data=resolved_content)
    assert not backend.conflict_report()
    backend.push(message="Resolve conflict with merged content")

    final_remote_content = _run_git(
        ["--git-dir", str(remote_repo), "show", f"main:{conflict_rel_path.as_posix()}"],
    )
    assert final_remote_content == resolved_content.rstrip("\n")

    backend.sync()
