"""Git-backed synchronised file backend implementation."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from shutil import which
from typing import TYPE_CHECKING, Any, BinaryIO
from urllib.parse import quote, urlparse, urlunparse

from .interfaces import (
    DEFAULT_CHUNK_SIZE,
    AlreadyExistsError,
    FileBackendError,
    FileInfo,
    InvalidOperationError,
    PathLike,
    SyncConflict,
    SyncFileBackend,
)
from .local import LocalFileBackend

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping


STATUS_LINE_MIN_LENGTH = 3


class GitBackendError(FileBackendError):
    """Error raised when Git operations fail."""


class GitSyncFileBackend(SyncFileBackend):
    """Synchronised backend implementation backed by a Git repository."""

    def __init__(self, connection_info: Mapping[str, Any]) -> None:
        """Initialise the backend using the provided connection configuration."""
        if "remote_url" not in connection_info:
            message = "Missing 'remote_url' in connection_info"
            raise ValueError(message)
        if "path" not in connection_info:
            message = "Missing 'path' in connection_info"
            raise ValueError(message)

        self._config = dict(connection_info)
        self._remote_url = self._construct_remote_url(self._config)
        self._branch = self._config.get("branch", "main")
        self._author_name = self._config.get("author_name", "f9-sync")
        self._author_email = self._config.get("author_email", "f9-sync@example.com")
        self._workdir = Path(self._config["path"]).expanduser()
        self._env = self._build_env()
        self._git_path = self._discover_git()

        if (self._workdir / ".git").exists():
            self._ensure_remote()
        elif self._workdir.exists() and any(self._workdir.iterdir()):
            raise AlreadyExistsError(
                self._workdir,
                reason="Working directory exists but is not a Git repository",
            )
        else:
            self._clone_repository()

        self._checkout_branch()
        self._configure_identity()

        self._local_backend = LocalFileBackend(root=self._workdir, create_root=True)
        self._root = self._workdir.resolve()

    def create(
        self,
        path: PathLike,
        *,
        data: bytes | str | BinaryIO | None = None,
        is_directory: bool = False,
        overwrite: bool = False,
    ) -> FileInfo:
        """Create a file or directory in the working tree."""
        return self._local_backend.create(
            path,
            data=data,
            is_directory=is_directory,
            overwrite=overwrite,
        )

    def read(
        self,
        path: PathLike,
        *,
        binary: bool = True,
    ) -> bytes | str:
        """Read a file from the working tree."""
        return self._local_backend.read(path, binary=binary)

    def update(
        self,
        path: PathLike,
        *,
        data: bytes | str | BinaryIO,
        append: bool = False,
    ) -> FileInfo:
        """Update the contents of an existing file."""
        return self._local_backend.update(path, data=data, append=append)

    def delete(self, path: PathLike, *, recursive: bool = False) -> None:
        """Delete a file or directory from the working tree."""
        self._local_backend.delete(path, recursive=recursive)

    def info(self, path: PathLike) -> FileInfo:
        """Return file metadata from the working tree."""
        return self._local_backend.info(path)

    def stream_read(
        self,
        path: PathLike,
        *,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        binary: bool = True,
    ) -> Iterator[bytes | str]:
        """Stream file contents in chunks from the working tree."""
        return self._local_backend.stream_read(
            path,
            chunk_size=chunk_size,
            binary=binary,
        )

    def stream_write(
        self,
        path: PathLike,
        *,
        chunk_source: Iterator[bytes | str] | BinaryIO,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overwrite: bool = False,
    ) -> FileInfo:
        """Write file from stream to the working tree."""
        return self._local_backend.stream_write(
            path,
            chunk_source=chunk_source,
            chunk_size=chunk_size,
            overwrite=overwrite,
        )

    def push(self, *, message: str | None = None) -> None:
        """Commit local changes (if any) and push to the remote repository."""
        self._ensure_no_conflicts()
        self._run_git(["add", "--all"])
        diff_result = self._run_git(["diff", "--cached", "--quiet"], check=False)
        has_changes = diff_result.returncode == 1
        if has_changes:
            commit_message = message or "Sync changes"
            commit = self._run_git(
                ["commit", "-m", commit_message],
                check=False,
            )
            if commit.returncode != 0:
                stderr = (commit.stderr or "").strip()
                if "nothing to commit" not in stderr.lower():
                    raise GitBackendError(stderr or "Unable to commit local changes")

        push = self._run_git(["push", "origin", self._branch], check=False)
        if push.returncode != 0:
            stderr = (push.stderr or "").strip()
            if "has no upstream branch" in stderr:
                push = self._run_git(
                    ["push", "--set-upstream", "origin", self._branch],
                    check=False,
                )
            if push.returncode != 0:
                stderr = (push.stderr or "").strip()
                raise GitBackendError(stderr or "Failed to push to remote")

    def pull(self) -> None:
        """Fetch and merge remote updates into the local repository."""
        self._ensure_no_conflicts()
        self._ensure_clean_working_tree()

        self._run_git(["fetch", "origin", self._branch])
        remote_ref = f"origin/{self._branch}"
        exists = self._run_git(["rev-parse", "--verify", remote_ref], check=False)
        if exists.returncode != 0:
            return

        merge = self._run_git(["merge", "--no-edit", remote_ref], check=False)
        if merge.returncode != 0:
            if self.conflict_report():
                message = "Pull resulted in merge conflicts"
                raise GitBackendError(message)
            stderr = (merge.stderr or "").strip()
            raise GitBackendError(stderr or "Failed to merge remote changes")

    def conflict_report(self) -> list[SyncConflict]:
        """Return the list of paths currently in conflict."""
        status_output = self._run_git(
            ["status", "--porcelain"],
        ).stdout.splitlines()
        conflicts: list[SyncConflict] = []
        for line in status_output:
            if len(line) < STATUS_LINE_MIN_LENGTH:
                continue
            code = line[:2]
            rel_path = line[3:]
            if "U" in code or code in {"AA", "DD"}:
                conflicts.append(
                    SyncConflict(
                        path=(self._root / rel_path),
                        status=code.strip(),
                    ),
                )
        return conflicts

    def conflict_accept_local(self, path: PathLike) -> None:
        """Resolve a conflict in favour of the local version."""
        rel_path = self._relative_path(path)
        self._assert_conflicted(rel_path)
        self._run_git(["checkout", "--ours", rel_path])
        self._run_git(["add", rel_path])

    def conflict_accept_remote(self, path: PathLike) -> None:
        """Resolve a conflict in favour of the remote version."""
        rel_path = self._relative_path(path)
        self._assert_conflicted(rel_path)
        self._run_git(["checkout", "--theirs", rel_path])
        self._run_git(["add", rel_path])

    def conflict_resolve(
        self,
        path: PathLike,
        *,
        data: bytes | str | BinaryIO,
    ) -> None:
        """Resolve a conflict by writing a new version of the file."""
        rel_path = self._relative_path(path)
        self._assert_conflicted(rel_path)
        self.update(rel_path, data=data)
        self._run_git(["add", rel_path])

    def _clone_repository(self) -> None:
        parent = self._workdir.parent
        parent.mkdir(parents=True, exist_ok=True)
        if self._workdir.exists():
            self._workdir.rmdir()
        clone = subprocess.run(  # noqa: S603 - commands are to the trusted git executable
            [
                self._git_path,
                "clone",
                "--branch",
                self._branch,
                "--single-branch",
                self._remote_url,
                str(self._workdir),
            ],
            check=False,
            env=self._env,
            capture_output=True,
            text=True,
        )
        if clone.returncode != 0:
            fallback = subprocess.run(  # noqa: S603 - fallback to trusted git executable
                [self._git_path, "clone", self._remote_url, str(self._workdir)],
                check=False,
                env=self._env,
                capture_output=True,
                text=True,
            )
            if fallback.returncode != 0:
                stderr = (fallback.stderr or clone.stderr or "").strip()
                raise GitBackendError(stderr or "Failed to clone remote repository")

    def _ensure_remote(self) -> None:
        remotes = self._run_git(["remote"], check=True).stdout.split()
        if "origin" in remotes:
            self._run_git(["remote", "set-url", "origin", self._remote_url])
        else:
            self._run_git(["remote", "add", "origin", self._remote_url])

    def _checkout_branch(self) -> None:
        current = (
            self._run_git(
                ["rev-parse", "--abbrev-ref", "HEAD"],
            ).stdout.strip()
        )
        if current == self._branch:
            return

        checkout = self._run_git(["checkout", self._branch], check=False)
        if checkout.returncode != 0:
            self._run_git(["checkout", "-b", self._branch])

    def _configure_identity(self) -> None:
        self._run_git(["config", "user.name", self._author_name])
        self._run_git(["config", "user.email", self._author_email])

    def _ensure_no_conflicts(self) -> None:
        if self.conflict_report():
            message = "Resolve outstanding conflicts before continuing"
            raise GitBackendError(message)

    def _ensure_clean_working_tree(self) -> None:
        status = self._run_git(["status", "--porcelain"]).stdout.strip()
        if status:
            message = "Working tree has pending changes; push or stash first"
            raise GitBackendError(message)

    def _assert_conflicted(self, rel_path: str) -> None:
        absolute = (self._root / rel_path).resolve()
        conflicts = {conflict.path.resolve() for conflict in self.conflict_report()}
        if absolute not in conflicts:
            message = f"{rel_path} is not currently conflicted"
            raise GitBackendError(message)

    def _relative_path(self, path: PathLike) -> str:
        path_obj = Path(path)
        candidate = path_obj if path_obj.is_absolute() else self._root / path_obj
        candidate = candidate.resolve(strict=False)
        try:
            relative = candidate.relative_to(self._root)
        except ValueError as exc:
            raise InvalidOperationError.path_outside_root(candidate) from exc
        return relative.as_posix()

    def _run_git(
        self,
        args: list[str],
        *,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(  # noqa: S603 - executing trusted git binary with controlled args
            [self._git_path, *args],
            cwd=self._workdir,
            env=self._env,
            check=False,
            capture_output=True,
            text=True,
        )
        if check and result.returncode != 0:
            stderr = (result.stderr or "").strip()
            raise GitBackendError(stderr or f"git {' '.join(args)} failed")
        return result

    def _build_env(self) -> dict[str, str]:
        env = os.environ.copy()
        ssh_key = self._config.get("ssh_key_path")
        if ssh_key:
            env["GIT_SSH_COMMAND"] = f"ssh -i {ssh_key} -o IdentitiesOnly=yes"
        known_hosts = self._config.get("known_hosts")
        if known_hosts:
            command = env.get("GIT_SSH_COMMAND", "ssh")
            command = f"{command} -o UserKnownHostsFile={known_hosts}"
            env["GIT_SSH_COMMAND"] = command
        return env

    def _discover_git(self) -> str:
        git_path = which("git")
        if not git_path:
            message = "Unable to locate git executable on PATH"
            raise GitBackendError(message)
        return git_path

    @staticmethod
    def _construct_remote_url(connection_info: Mapping[str, Any]) -> str:
        remote_url = str(connection_info["remote_url"])
        username = connection_info.get("username")
        password = connection_info.get("password")
        if (
            username
            and password
            and remote_url.startswith(("http://", "https://"))
        ):
            parsed = urlparse(remote_url)
            if parsed.username:
                return remote_url
            auth = f"{quote(str(username), safe='')}:{quote(str(password), safe='')}"
            netloc = parsed.hostname or ""
            if parsed.port:
                netloc = f"{netloc}:{parsed.port}"
            netloc = f"{auth}@{netloc}"
            parsed = parsed._replace(netloc=netloc)
            return urlunparse(parsed)
        return remote_url
