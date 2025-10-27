"""Live test harness for exercising SyncFileBackend behaviour with OpenAI storage.

This script performs the following steps:

1. Collects the OpenAI API key and storage vault (vector store) identifier from
   environment variables or via interactive prompts.
2. Clones the public `aethermoor` repository into a temporary workspace.
3. Seeds a local bare Git repository so the GitSyncFileBackend can interact with
   it safely without touching the upstream GitHub source.
4. Mirrors repository contents into the configured OpenAI vector store to
   double-check end-to-end connectivity.
5. Exercises the full SyncFileBackend contract (push, pull, sync, and conflict
   resolution) against the seeded repository.

The script is intentionally verbose and should only be executed in environments
where the caller is comfortable uploading repository data to the supplied
storage vault.
"""

from __future__ import annotations

import getpass
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterable
from pathlib import Path

from f9_file_backend import (
    GitBackendError,
    GitSyncFileBackend,
    OpenAIVectorStoreFileBackend,
    SyncFileBackend,
)

REPO_URL = "https://github.com/foundry-9/aethermoor.git"
DEFAULT_BRANCH = "main"
API_KEY_ENV = "OPENAI_API_KEY"
VAULT_ENV = "OPENAI_STORAGE_VAULT_ID"


class LiveSyncTestError(RuntimeError):
    """Raised when the live sync validation encounters an unexpected state."""

    @classmethod
    def remote_content_mismatch(cls) -> LiveSyncTestError:
        """Return an error when the remote repository contents differ."""
        return cls("Remote repository content mismatch after push")

    @classmethod
    def pull_content_mismatch(cls) -> LiveSyncTestError:
        """Return an error when a pull does not apply remote changes."""
        return cls("Pull did not apply remote change as expected")

    @classmethod
    def missing_conflict_entry(cls) -> LiveSyncTestError:
        """Return an error when the expected conflict is not reported."""
        return cls("Conflict report did not include expected file")

    @classmethod
    def unexpected_push_success(cls) -> LiveSyncTestError:
        """Return an error when a push succeeds despite conflicts."""
        return cls("Push succeeded unexpectedly despite conflict")

    @classmethod
    def unexpected_pull_success(cls) -> LiveSyncTestError:
        """Return an error when a pull succeeds despite conflicts."""
        return cls("Pull succeeded unexpectedly despite conflict")

    @classmethod
    def conflict_resolution_mismatch(cls) -> LiveSyncTestError:
        """Return an error when conflict resolution produces the wrong content."""
        return cls("Conflict resolution did not propagate expected content")


def _prompt_for_secret(env_name: str, prompt: str) -> str:
    """Return a secret value from the environment or interactive prompt."""
    value = os.environ.get(env_name)
    if value:
        return value.strip()
    return getpass.getpass(prompt)


def _run_git(args: Iterable[str], *, cwd: Path | None = None) -> str:
    """Run a git command and return stdout; raise when the command fails."""
    if not isinstance(args, Iterable):
        message = "args must be iterable"
        raise TypeError(message)
    git_executable = shutil.which("git")
    if git_executable is None:
        message = "git executable not found on PATH"
        raise RuntimeError(message)
    result = subprocess.run(  # noqa: S603 - controlled arguments to trusted binary
        [git_executable, *args],
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        message = f"git {' '.join(args)} failed"
        if stderr:
            message = f"{message}: {stderr}"
        raise RuntimeError(message)
    return result.stdout.strip()


def _mirror_directory_to_vector_store(
    backend: OpenAIVectorStoreFileBackend,
    source: Path,
) -> None:
    """Upload the contents of `source` into the provided vector store backend."""
    for entry in sorted(source.rglob("*")):
        if entry.name == ".git":
            continue
        relative = entry.relative_to(source).as_posix()
        if entry.is_dir():
            backend.create(relative, is_directory=True)
            continue
        data = entry.read_bytes()
        backend.create(relative, data=data, overwrite=True)


def _seed_local_remote(clone_dir: Path, remote_repo: Path) -> str:
    """Push the cloned repository into a bare remote and return the branch name."""
    _run_git(["init", "--bare", str(remote_repo)])
    branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=clone_dir)
    if branch == "HEAD":  # detached head; fall back to default
        branch = DEFAULT_BRANCH
    _run_git(["config", "user.name", "Live Sync Tester"], cwd=clone_dir)
    _run_git(["config", "user.email", "live-sync@example.com"], cwd=clone_dir)
    remote_name = "live-sync-remote"
    existing_remotes = _run_git(["remote"], cwd=clone_dir).splitlines()
    if remote_name in existing_remotes:
        _run_git(["remote", "remove", remote_name], cwd=clone_dir)
    _run_git(["remote", "add", remote_name, str(remote_repo)], cwd=clone_dir)
    _run_git(["push", remote_name, f"HEAD:{branch}"], cwd=clone_dir)
    return branch


def _exercise_sync_backend(
    backend: SyncFileBackend,
    *,
    remote_repo: Path,
    working_dir: Path,
    vector_backend: OpenAIVectorStoreFileBackend,
    branch: str,
) -> None:
    """Run a series of synchronisation scenarios against the backend."""
    print("Pulling latest changes from remote...")
    backend.pull()
    _mirror_directory_to_vector_store(vector_backend, working_dir)

    print("Creating and pushing a new file...")
    backend.create("live_sync_test.txt", data="initial content\n")
    backend.push(message="Add live sync test file")
    _mirror_directory_to_vector_store(vector_backend, working_dir)
    remote_content = _run_git(
        ["--git-dir", str(remote_repo), "show", f"{branch}:live_sync_test.txt"],
    )
    if remote_content != "initial content":
        raise LiveSyncTestError.remote_content_mismatch()
    print("Push validation succeeded.")

    print("Simulating remote update and pulling...")
    remote_clone = working_dir.parent / "remote_clone_for_pull"
    _run_git(["clone", str(remote_repo), str(remote_clone)])
    _run_git(["config", "user.name", "Remote Pull"], cwd=remote_clone)
    _run_git(["config", "user.email", "remote-pull@example.com"], cwd=remote_clone)
    (remote_clone / "live_sync_test.txt").write_text(
        "remote change\n",
        encoding="utf-8",
    )
    _run_git(["commit", "-am", "Remote change for pull"], cwd=remote_clone)
    _run_git(["push", "origin", branch], cwd=remote_clone)
    backend.pull()
    observed = backend.read("live_sync_test.txt", binary=False)
    if observed.strip() != "remote change":
        raise LiveSyncTestError.pull_content_mismatch()
    _mirror_directory_to_vector_store(vector_backend, working_dir)
    print("Pull validation succeeded.")

    print("Creating conflicting changes to exercise conflict resolution...")
    backend.update("live_sync_test.txt", data="local conflicting change\n")
    conflict_clone = working_dir.parent / "remote_conflict_clone"
    _run_git(["clone", str(remote_repo), str(conflict_clone)])
    _run_git(["config", "user.name", "Remote Conflict"], cwd=conflict_clone)
    _run_git(
        ["config", "user.email", "remote-conflict@example.com"],
        cwd=conflict_clone,
    )
    (conflict_clone / "live_sync_test.txt").write_text(
        "remote conflicting change\n",
        encoding="utf-8",
    )
    _run_git(["commit", "-am", "Remote conflicting change"], cwd=conflict_clone)
    _run_git(["push", "origin", branch], cwd=conflict_clone)

    try:
        backend.push(message="Attempt push with local conflict")
    except GitBackendError:
        print("Expected push failure detected (conflict).")
    else:
        raise LiveSyncTestError.unexpected_push_success()

    try:
        backend.pull()
    except GitBackendError:
        print("Expected pull failure detected (conflict).")
    else:
        raise LiveSyncTestError.unexpected_pull_success()

    conflicts = backend.conflict_report()
    conflict_paths = {conflict.path.name for conflict in conflicts}
    if "live_sync_test.txt" not in conflict_paths:
        raise LiveSyncTestError.missing_conflict_entry()

    backend.conflict_resolve(
        "live_sync_test.txt",
        data="resolved content from live script\n",
    )
    backend.push(message="Resolve conflict via live script")
    _mirror_directory_to_vector_store(vector_backend, working_dir)

    final_remote = _run_git(
        ["--git-dir", str(remote_repo), "show", f"{branch}:live_sync_test.txt"],
    )
    if final_remote.strip() != "resolved content from live script":
        raise LiveSyncTestError.conflict_resolution_mismatch()
    print("Conflict resolution workflow succeeded.")

    print("Triggering sync() convenience method...")
    backend.sync()
    print("All SyncFileBackend scenarios completed successfully.")


def main() -> int:
    """Entry point for the live sync test harness."""
    api_key = _prompt_for_secret(
        API_KEY_ENV,
        "OpenAI API key (stored as environment variable later): ",
    )
    vault_id = _prompt_for_secret(
        VAULT_ENV,
        "OpenAI storage vault (vector store) ID: ",
    )
    print("Initialising OpenAI vector store backend...")
    vector_backend = OpenAIVectorStoreFileBackend(
        {"api_key": api_key, "vector_store_id": vault_id, "cache_ttl": 5},
    )

    with tempfile.TemporaryDirectory(prefix="f9-live-sync-") as temp_dir:
        workspace = Path(temp_dir)
        clone_dir = workspace / "aethermoor"
        print(f"Cloning repository {REPO_URL}...")
        _run_git(["clone", REPO_URL, str(clone_dir)])

        print("Mirroring repository into OpenAI storage vault...")
        _mirror_directory_to_vector_store(vector_backend, clone_dir)

        remote_repo = workspace / "remote.git"
        branch = _seed_local_remote(clone_dir, remote_repo)
        print(f"Seeded local bare repository at {remote_repo} on branch {branch}.")

        workdir = workspace / "backend-workdir"
        backend = GitSyncFileBackend(
            {
                "remote_url": str(remote_repo),
                "path": str(workdir),
                "branch": branch,
                "author_name": "Live Sync Tester",
                "author_email": "live-sync@example.com",
            },
        )
        print(f"Initialised GitSyncFileBackend workdir at {workdir}.")

        _exercise_sync_backend(
            backend,
            remote_repo=remote_repo,
            working_dir=workdir,
            vector_backend=vector_backend,
            branch=branch,
        )

    print("Live sync test completed successfully.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nAborted by user.", file=sys.stderr)
        sys.exit(130)
