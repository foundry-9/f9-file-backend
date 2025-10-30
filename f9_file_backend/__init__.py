"""File backend abstraction library for multi-backend file storage.

This package provides a unified interface for file storage operations across
multiple storage backends (local filesystem, Git repositories, OpenAI vector stores).

Core Components:
    - FileBackend: Abstract interface all backends must implement
    - LocalFileBackend: Direct filesystem storage
    - GitSyncFileBackend: Version-controlled storage with Git integration
    - OpenAIVectorStoreFileBackend: Remote storage via OpenAI API

Quick Start:

    >>> from f9_file_backend import LocalFileBackend
    >>> from pathlib import Path
    >>> backend = LocalFileBackend(root=Path("/data"))
    >>> backend.create("document.txt", data=b"Hello, world!")
    >>> content = backend.read("document.txt")
    >>> content
    b'Hello, world!'

    >>> # Switch to Git-backed storage with just one line
    >>> from f9_file_backend import GitSyncFileBackend
    >>> backend = GitSyncFileBackend(root="/data/repo")
    >>> backend.create("file.txt", data=b"Content")  # Auto-committed

Exception Handling:

    >>> from f9_file_backend import NotFoundError
    >>> try:
    ...     backend.read("nonexistent.txt")
    ... except NotFoundError:
    ...     print("File not found")

Supported Operations:
    - create() - Create new files
    - read() - Read file contents
    - update() - Modify existing files
    - stream_read() - Stream large files
    - stream_write() - Write from streams
    - delete() - Remove files
    - exists() - Check file existence
    - list() - List directory contents
    - checksum() - Compute file checksums
    - info() - Get file metadata
    - mkdir() - Create directories
    - rmdir() - Remove directories

See Also:
    - ARCHITECTURE.md: Design patterns and architecture decisions
    - CONTRIBUTING.md: Guidelines for adding new backends

"""

from .async_git_backend import AsyncGitSyncFileBackend
from .async_interfaces import AsyncFileBackend, AsyncSyncFileBackend
from .async_local import AsyncLocalFileBackend
from .async_openai_backend import AsyncOpenAIVectorStoreFileBackend
from .git_backend import GitBackendError, GitSyncFileBackend
from .interfaces import (
    DEFAULT_CHUNK_SIZE,
    AlreadyExistsError,
    ChecksumAlgorithm,
    FileBackend,
    FileBackendError,
    FileInfo,
    InvalidOperationError,
    NotFoundError,
    PathLike,
    SupportsBackend,
    SyncConflict,
    SyncFileBackend,
)
from .local import LocalFileBackend
from .openai_backend import OpenAIBackendError, OpenAIVectorStoreFileBackend

__all__ = [
    "DEFAULT_CHUNK_SIZE",
    "AlreadyExistsError",
    "AsyncFileBackend",
    "AsyncGitSyncFileBackend",
    "AsyncLocalFileBackend",
    "AsyncOpenAIVectorStoreFileBackend",
    "AsyncSyncFileBackend",
    "ChecksumAlgorithm",
    "FileBackend",
    "FileBackendError",
    "FileInfo",
    "GitBackendError",
    "GitSyncFileBackend",
    "InvalidOperationError",
    "LocalFileBackend",
    "NotFoundError",
    "OpenAIBackendError",
    "OpenAIVectorStoreFileBackend",
    "PathLike",
    "SupportsBackend",
    "SyncConflict",
    "SyncFileBackend",
]
