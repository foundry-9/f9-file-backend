# Feature Requests for f9_file_backend Library

**Date**: 2025-10-30
**Submitted by**: Lore_MCP Project (Obsidian MCP Server)
**Target Library**: `f9-file-backend` (`git@github.com:foundry-9/f9-file-backend.git`)

## Overview

This document outlines feature requests to enhance the f9_file_backend library based on real-world usage in the Lore_MCP project. These features would improve the library's suitability for large-scale file backend abstraction, particularly for documentation and knowledge management systems that require advanced file operations.

---

## Feature 1: Streaming/Chunked I/O Operations

### Problem Statement

The current `read()` and `write()` methods load entire files into memory. This approach fails for large files and causes memory bloat in systems that:

- Process large markdown/document files (>100MB)
- Build full-text search indexes
- Generate semantic embeddings for thousands of files
- Stream files over network protocols

### Proposed Solution

Add streaming methods to the `FileBackend` interface:

```python
from typing import Iterator, BinaryIO

class FileBackend(ABC):
    @abstractmethod
    def stream_read(
        self,
        path: PathLike,
        *,
        chunk_size: int = 8192,
        binary: bool = True,
    ) -> Iterator[bytes | str]:
        """Stream file contents in chunks.

        Args:
            path: File path relative to backend root
            chunk_size: Size of each chunk (default 8KB)
            binary: Return bytes if True, str if False

        Yields:
            Chunk of file content

        Raises:
            NotFoundError: File does not exist
            InvalidOperationError: Path is a directory
        """

    @abstractmethod
    def stream_write(
        self,
        path: PathLike,
        *,
        chunk_source: Iterator[bytes | str] | BinaryIO,
        chunk_size: int = 8192,
        overwrite: bool = False,
    ) -> FileInfo:
        """Write file contents from a stream.

        Args:
            path: File path relative to backend root
            chunk_source: Iterator or file object providing chunks
            chunk_size: Expected chunk size (informational)
            overwrite: Replace existing file if True

        Returns:
            FileInfo describing the written file

        Raises:
            AlreadyExistsError: File exists and overwrite=False
            InvalidOperationError: Cannot write to directory
        """
```

### Use Cases

1. **Large Document Processing**: Index 500MB documentation files without loading into memory
2. **Search Indexing**: Stream files while building full-text search indexes
3. **Embedding Generation**: Process files for ML embeddings with constant memory usage
4. **Network Efficiency**: Stream files over HTTP/gRPC with chunked transfer encoding
5. **Tape Backup**: Stream to/from sequential media efficiently

### Implementation Notes

- Local backend: Use `open()` context manager with `read(chunk_size)` loop
- Git backend: Delegate to local backend (already materialized)
- OpenAI backend: Implement chunked uploads/downloads with API calls

### Priority: HIGH

**Rationale**: Without streaming, large vaults become unworkable; many ML/search operations require this capability.

---

## Feature 2: Checksum & Integrity Verification

### Problem Statement

The library provides no way to:

- Verify file integrity after transfer
- Detect file changes efficiently
- Deduplicate content
- Implement content-based caching
- Validate synchronization completeness

### Proposed Solution

Add checksum methods to the `FileBackend` interface:

```python
from typing import Literal

ChecksumAlgorithm = Literal["md5", "sha256", "sha512", "blake3"]

class FileBackend(ABC):
    @abstractmethod
    def checksum(
        self,
        path: PathLike,
        *,
        algorithm: ChecksumAlgorithm = "sha256",
    ) -> str:
        """Compute checksum of a file.

        Args:
            path: File path relative to backend root
            algorithm: Hash algorithm (md5, sha256, sha512, blake3)

        Returns:
            Hex-encoded checksum string

        Raises:
            NotFoundError: File does not exist
            InvalidOperationError: Path is a directory
            ValueError: Unsupported algorithm
        """

    @abstractmethod
    def checksum_many(
        self,
        paths: list[PathLike],
        *,
        algorithm: ChecksumAlgorithm = "sha256",
    ) -> dict[str, str]:
        """Compute checksums for multiple files.

        Args:
            paths: List of file paths relative to backend root
            algorithm: Hash algorithm to use

        Returns:
            Mapping of path → checksum (skips non-existent files)

        Raises:
            ValueError: Unsupported algorithm
        """
```

### Use Cases

1. **Change Detection**: Compare checksums to detect modified files without reading content
2. **Deduplication**: Identify duplicate files by content hash
3. **Backup Verification**: Ensure files were transferred correctly
4. **Cache Invalidation**: Invalidate caches when checksum changes
5. **Content Addressing**: Implement content-addressable storage schemes
6. **Integrity Monitoring**: Regular integrity checks across vaults

### Implementation Notes

- Support at least SHA256 (industry standard) and Blake3 (modern, fast)
- Optional support for MD5 and SHA512
- `checksum_many()` should batch-optimize for backends that support it
- For streaming backends (Git), compute incrementally during materialization
- Cache checksums in metadata where applicable

### Priority: HIGH

**Rationale**: Critical for search indexing, caching, and vault health monitoring. Used frequently (multiple times per search operation).

---

## Feature 3: Asynchronous Operations

### Problem Statement

All I/O is currently synchronous, blocking the event loop in async applications. This causes:

- Slowdowns in event-driven MCP servers
- Serial processing instead of concurrent operations
- Inability to parallelize multi-file operations
- Poor performance in I/O-bound workloads

### Proposed Solution

Add async variants of all I/O operations:

```python
class AsyncFileBackend(ABC):
    """Async variant of FileBackend with async/await support."""

    @abstractmethod
    async def create(
        self,
        path: PathLike,
        *,
        data: bytes | str | BinaryIO | None = None,
        is_directory: bool = False,
        overwrite: bool = False,
    ) -> FileInfo:
        """Async version of FileBackend.create()."""

    @abstractmethod
    async def read(
        self,
        path: PathLike,
        *,
        binary: bool = True,
    ) -> bytes | str:
        """Async version of FileBackend.read()."""

    @abstractmethod
    async def update(
        self,
        path: PathLike,
        *,
        data: bytes | str | BinaryIO,
        append: bool = False,
    ) -> FileInfo:
        """Async version of FileBackend.update()."""

    @abstractmethod
    async def delete(self, path: PathLike, *, recursive: bool = False) -> None:
        """Async version of FileBackend.delete()."""

    @abstractmethod
    async def info(self, path: PathLike) -> FileInfo:
        """Async version of FileBackend.info()."""

    @abstractmethod
    async def checksum(
        self,
        path: PathLike,
        *,
        algorithm: ChecksumAlgorithm = "sha256",
    ) -> str:
        """Async version of checksum()."""

    @abstractmethod
    async def stream_read(
        self,
        path: PathLike,
        *,
        chunk_size: int = 8192,
        binary: bool = True,
    ) -> AsyncIterator[bytes | str]:
        """Async version of stream_read()."""

    # ... etc for all methods
```

Additionally, add async variants for `SyncFileBackend`:

```python
class AsyncSyncFileBackend(AsyncFileBackend):
    """Async variant of SyncFileBackend."""

    @abstractmethod
    async def push(self, *, message: str | None = None) -> None:
        """Async version of push()."""

    @abstractmethod
    async def pull(self) -> None:
        """Async version of pull()."""

    @abstractmethod
    async def conflict_report(self) -> list[SyncConflict]:
        """Async version of conflict_report()."""

    # ... etc for sync methods
```

Provide implementations:

```python
class AsyncLocalFileBackend(AsyncFileBackend):
    """Async local filesystem backend using asyncio.to_thread()."""

class AsyncGitSyncFileBackend(AsyncSyncFileBackend):
    """Async Git backend using asyncio.to_thread() for subprocess calls."""

class AsyncOpenAIVectorStoreFileBackend(AsyncFileBackend):
    """Async OpenAI backend using async HTTP client."""
```

### Use Cases

1. **Parallel File Operations**: Process 1000s of files concurrently
2. **Non-blocking MCP Servers**: Event-driven architecture without blocking
3. **High-throughput Indexing**: Build search indexes 3-5x faster
4. **Concurrent Embeddings**: Generate ML embeddings in parallel
5. **Responsive UIs**: Prevent UI freezes during file operations

### Implementation Notes

- Use `asyncio.to_thread()` for blocking local/git operations
- Use async HTTP client (aiohttp, httpx) for OpenAI operations
- Maintain same interface/behavior as sync variants
- Ensure thread-safe access to shared resources
- Keep sync variants for backward compatibility

### Priority: HIGH

**Rationale**: Essential for modern async Python applications (MCP, FastAPI, etc.). Can improve vault operations performance 3-5x.

---

## Feature 4: Pattern Matching (Glob & Recursive Glob)

### Problem Statement

The library provides no way to discover files by pattern, requiring manual iteration through directory trees. This is needed for:

- Finding all markdown files in vault
- Discovering configuration files
- Pattern-based file selection
- Exclusion patterns (ignore rules)

### Proposed Solution

Add glob methods to the `FileBackend` interface:

```python
class FileBackend(ABC):
    @abstractmethod
    def glob(
        self,
        pattern: str,
        *,
        include_dirs: bool = False,
    ) -> list[Path]:
        """Find files matching a glob pattern.

        Args:
            pattern: Glob pattern (e.g., "*.md", "docs/**/*.txt")
            include_dirs: Include directories in results

        Returns:
            List of matching paths relative to backend root

        Examples:
            backend.glob("*.md")  # All markdown in root
            backend.glob("**/*.md")  # All markdown recursively
            backend.glob("src/**/*.py", include_dirs=True)
        """

    @abstractmethod
    def glob_files(
        self,
        pattern: str,
    ) -> list[Path]:
        """Find files matching glob pattern (directories excluded).

        Shorthand for glob(pattern, include_dirs=False).
        """

    @abstractmethod
    def glob_dirs(
        self,
        pattern: str,
    ) -> list[Path]:
        """Find directories matching glob pattern (files excluded)."""
```

### Use Cases

1. **Vault Discovery**: Find all markdown files: `backend.glob("**/*.md")`
2. **Selective Operations**: Find recently modified: `backend.glob("**/*.md", modified_after=...)`
3. **Configuration Loading**: Find config files: `backend.glob("**/.obsidian/*.json")`
4. **Exclusion Patterns**: Find non-ignored files using filter
5. **File Type Operations**: Migrate all PDFs: `backend.glob("**/*.pdf")`

### Implementation Notes

- Use pathlib's `glob()` under the hood for local backend
- For Git backend, glob the materialized working tree
- For OpenAI backend, filter results from `list_dir()` traversal
- Support standard glob patterns: `*`, `?`, `[...]`, `**`
- Return paths relative to backend root

### Priority: MEDIUM

**Rationale**: Enables file discovery; can be worked around with manual iteration but pattern matching is standard in Python.

---

## Feature 5: Atomic Operations (Sync Sessions)

### Problem Statement

Multi-file operations lack atomicity guarantees:

- No way to prevent concurrent modifications during bulk operations
- Race conditions possible when synchronizing multiple files
- No bracketed context for related operations
- Git operations may conflict with concurrent access

### Proposed Solution

Add sync session support to `SyncFileBackend`:

```python
from contextlib import asynccontextmanager, contextmanager

class SyncFileBackend(FileBackend):
    @contextmanager
    def sync_session(self) -> Iterator[None]:
        """Context manager for atomic multi-file operations.

        Acquires locks to prevent concurrent modifications during the session.

        Usage:
            with backend.sync_session():
                backend.create("file1.txt", data="content1")
                backend.create("file2.txt", data="content2")
                backend.push(message="Atomic update")

        Raises:
            FileBackendError: Cannot acquire lock (timeout, conflict, etc)
        """

class AsyncSyncFileBackend(AsyncFileBackend):
    @asynccontextmanager
    async def sync_session(self) -> AsyncIterator[None]:
        """Async variant of sync_session()."""
```

Behavior requirements:

```python
class SyncSession(Protocol):
    """Protocol for sync sessions."""

    def __enter__(self) -> "SyncSession": ...
    def __exit__(self, *args) -> None: ...

    def acquire_lock(self, timeout: float = 30.0) -> bool:
        """Try to acquire exclusive operation lock."""

    def release_lock(self) -> None:
        """Release the exclusive operation lock."""
```

### Use Cases

1. **Bulk Metadata Updates**: Update 100 files atomically
2. **Related Files**: Create note + update index atomically
3. **Conflict Avoidance**: Prevent concurrent changes during sensitive operations
4. **Git Transactions**: Multiple changes pushed as single commit
5. **Snapshot Consistency**: Ensure operations see consistent view of vault

### Implementation Notes

- Local backend: File-based lock (e.g., `.backend.lock`)
- Git backend: Lock during pull/push cycle
- OpenAI backend: No-op (single-threaded access assumed)
- Optional timeout parameter (default 30s)
- Implement using context managers
- Lock should be re-entrant (same thread can acquire multiple times)

### Priority: MEDIUM

**Rationale**: Prevents race conditions in concurrent scenarios. Many operations could benefit from atomicity guarantees.

---

## Feature 6: URI-Based Backend Factory/Resolution

### Problem Statement

Backends must be instantiated explicitly with specific configuration. This makes it difficult to:

- Switch backends without code changes
- Store vault configurations as URIs
- Support multiple backends in one application
- Dynamically resolve backends from configuration

### Proposed Solution

Add a backend factory that parses URIs and returns configured backend instances:

```python
from typing import Protocol

class BackendFactory(Protocol):
    """Factory for creating backends from URIs."""

    def resolve(self, uri: str) -> FileBackend | SyncFileBackend:
        """Create a backend from a URI.

        Args:
            uri: Backend URI (scheme://path?params)

        Returns:
            Configured backend instance

        Raises:
            ValueError: Invalid URI format
            FileBackendError: Backend initialization failed

        URI Schemes:
            file://path/to/root
            file:///absolute/path/to/root
            git://github.com/user/repo@main?ssh_key=/path/to/key
            git+https://github.com/user/repo@main?username=user&password=pwd
            git+ssh://github.com/user/repo@main?ssh_key_path=/path
            openai+vector://vs_123456?api_key=sk_xxx&cache_ttl=5
        """

    def register(
        self,
        scheme: str,
        factory_func: Callable[[str, dict[str, str]], FileBackend],
    ) -> None:
        """Register a custom backend factory for a URI scheme."""

    def parse_uri(self, uri: str) -> tuple[str, str, dict[str, str]]:
        """Parse URI into (scheme, path, params).

        Examples:
            "file:///home/user/vault"
            → ("file", "/home/user/vault", {})

            "git+ssh://github.com/user/repo@main?ssh_key=/path/key"
            → ("git+ssh", "github.com/user/repo",
               {"branch": "main", "ssh_key": "/path/key"})
        """
```

Standard implementations:

```python
class DefaultBackendFactory(BackendFactory):
    """Default factory supporting file://, git://, openai+vector:// schemes."""

    def resolve(self, uri: str) -> FileBackend | SyncFileBackend:
        scheme, path, params = self.parse_uri(uri)

        if scheme in ("file", ""):
            return LocalFileBackend(root=path, **params)
        elif scheme in ("git", "git+https", "git+ssh"):
            return GitSyncFileBackend({
                "path": path,
                "remote_url": params.get("remote_url"),
                "branch": params.get("branch", "main"),
                # ... other git params
            })
        elif scheme in ("openai+vector", "openai-vector"):
            return OpenAIVectorStoreFileBackend({
                "api_key": params.get("api_key"),
                "vector_store_id": params.get("vector_store_id"),
                # ... other openai params
            })
        else:
            raise ValueError(f"Unknown backend scheme: {scheme}")

    def register(self, scheme: str, factory_func: Callable) -> None:
        """Register custom backend factory."""
        self._factories[scheme] = factory_func
```

Module-level convenience:

```python
# Global factory instance
_default_factory = DefaultBackendFactory()

def resolve_backend(uri: str) -> FileBackend | SyncFileBackend:
    """Resolve a backend from a URI using the default factory."""
    return _default_factory.resolve(uri)

def register_backend_factory(
    scheme: str,
    factory_func: Callable[[str, dict[str, str]], FileBackend],
) -> None:
    """Register a custom backend factory."""
    _default_factory.register(scheme, factory_func)
```

### Use Cases

1. **Configuration Files**: Store vault URIs in config
2. **Environment Variables**: Backend URI from env: `VAULT_URI=git+ssh://...`
3. **Runtime Switching**: Change backends without code changes
4. **Testing**: Use different backends in test vs production
5. **Multi-Backend Apps**: Support multiple vault types in one app

### Example Usage

```python
from f9_file_backend import resolve_backend

# From URI string
vault_uri = "git+ssh://github.com/user/docs@main?ssh_key=/home/user/.ssh/id_rsa"
backend = resolve_backend(vault_uri)

# Or explicit
backend = resolve_backend("file:///home/user/vault")

# Custom registration
def my_s3_backend_factory(path: str, params: dict) -> FileBackend:
    return S3Backend(bucket=path, **params)

register_backend_factory("s3", my_s3_backend_factory)
backend = resolve_backend("s3://my-bucket/vault?region=us-west-2")
```

### Priority: MEDIUM

**Rationale**: Enables flexible configuration and multi-backend support. Nice-to-have but makes library more composable.

---

## Feature 7: Multi-Instance Management & Context

### Problem Statement

Applications need to work with multiple vaults simultaneously, but F9 has no built-in support for:

- Managing multiple backend instances
- Switching between vaults
- Per-vault metadata/options
- Context-aware operations

### Proposed Solution

Add context management for vault operations:

```python
from typing import Any

class VaultRegistry:
    """Registry for managing multiple vault backends."""

    def __init__(self):
        """Initialize an empty vault registry."""

    def register(
        self,
        name: str,
        backend: FileBackend | SyncFileBackend,
        *,
        options: dict[str, Any] | None = None,
    ) -> None:
        """Register a vault backend.

        Args:
            name: Vault identifier
            backend: Configured backend instance
            options: Optional metadata (ignored_folders, link_style, etc)
        """

    def unregister(self, name: str) -> None:
        """Unregister a vault."""

    def get(self, name: str) -> FileBackend | SyncFileBackend:
        """Get backend by name.

        Raises:
            KeyError: Vault not registered
        """

    def list(self) -> list[str]:
        """List registered vault names."""

    def get_options(self, name: str) -> dict[str, Any]:
        """Get metadata/options for a vault."""


class VaultContext:
    """Context manager for vault operations."""

    def __init__(self, registry: VaultRegistry):
        """Initialize with a registry."""

    def with_vault(self, name: str) -> "VaultContext":
        """Set active vault.

        Usage:
            ctx = VaultContext(registry)
            with ctx.with_vault("main"):
                # Operations use "main" vault backend
                content = ctx.read("file.md")
        """

    def read(self, path: PathLike, *, binary: bool = True) -> bytes | str:
        """Read from active vault."""

    def write(self, path: PathLike, data: bytes | str) -> FileInfo:
        """Write to active vault."""

    # ... delegate all operations to active vault backend
```

Module-level convenience:

```python
from contextlib import contextmanager

# Global registry
_global_registry = VaultRegistry()
_active_vault: str | None = None

@contextmanager
def vault_context(name: str) -> Iterator[VaultContext]:
    """Context manager for vault operations."""
    global _active_vault
    old = _active_vault
    _active_vault = name
    try:
        yield VaultContext(_global_registry)
    finally:
        _active_vault = old

def register_vault(
    name: str,
    backend: FileBackend | SyncFileBackend,
    **options,
) -> None:
    """Register a vault globally."""
    _global_registry.register(name, backend, options=options)

def get_active_vault() -> str | None:
    """Get name of currently active vault."""
    return _active_vault
```

### Use Cases

1. **Multi-Vault Apps**: Work with personal + team vaults
2. **Vault Switching**: Switch between vaults in operations
3. **Backup Systems**: Replicate across multiple vaults
4. **Testing**: Separate test vaults from production
5. **Vault Metadata**: Store ignore rules, search options per vault

### Priority: LOW

**Rationale**: Not essential; can be implemented at application layer if needed.

---

## Feature 8: Implicit Auto-Sync for Git Backends

### Problem Statement

Git backends require explicit `pull()` before reads and `push()` after writes. This is error-prone:

- Developers forget to pull, reading stale data
- Developers forget to push, losing changes
- Manual sync clutters application code
- Not idiomatic for file backend abstraction

### Proposed Solution

Add optional auto-sync behavior to `GitSyncFileBackend`:

```python
class GitSyncFileBackend(SyncFileBackend):
    def __init__(
        self,
        connection_info: Mapping[str, Any],
        *,
        auto_pull: bool = False,
        auto_push: bool = False,
    ) -> None:
        """Initialize Git backend with optional auto-sync.

        Args:
            connection_info: Connection configuration
            auto_pull: Automatically pull before read operations
            auto_push: Automatically push after write operations

        Note:
            Auto-pull/push add latency but ensure data consistency.
            Disable for performance-critical scenarios.
        """
```

When enabled:

```python
# With auto_pull=True
content = backend.read("file.md")  # Implicitly pulls first

# With auto_push=True
backend.create("file.md", data="content")  # Implicitly pushes after

# Combined
with backend.sync_session():
    backend.create("file1.md", data="a")
    backend.create("file2.md", data="b")
    # Single pull at start, single push at end (not per-operation)
```

Implementation notes:

```python
class GitSyncFileBackend(SyncFileBackend):
    def __init__(self, ..., auto_pull=False, auto_push=False):
        self._auto_pull = auto_pull
        self._auto_push = auto_push
        self._in_session = False

    def read(self, path, *, binary=True):
        if self._auto_pull and not self._in_session:
            self.pull()
        return self._local_backend.read(path, binary=binary)

    def create(self, path, *, data=None, is_directory=False, overwrite=False):
        result = self._local_backend.create(
            path, data=data, is_directory=is_directory, overwrite=overwrite
        )
        if self._auto_push and not self._in_session:
            self.push()
        return result

    def sync_session(self):
        @contextmanager
        def _session():
            old_in_session = self._in_session
            self._in_session = True
            try:
                if self._auto_pull:
                    self.pull()
                yield
                if self._auto_push:
                    self.push()
            finally:
                self._in_session = old_in_session
        return _session()
```

### Use Cases

1. **Simpler Applications**: No manual sync bookkeeping needed
2. **Transparent Sync**: Backend sync feels like local operations
3. **Always-Fresh Data**: Auto-pull ensures latest data
4. **Write-Through Cache**: Auto-push ensures durability
5. **Reduced Errors**: Harder to forget sync operations

### Trade-offs

- **Pros**: Simpler API, fewer bugs, more transparent
- **Cons**: Additional latency per operation (pulls/pushes happen automatically)

### Implementation Notes

- Sync sessions should batch operations (pull once, push once)
- Add metrics/logging to track auto-sync overhead
- Make auto-pull/push independent toggles
- Document performance implications

### Priority: LOW

**Rationale**: Convenience feature; manual sync is explicit and clear. Can be implemented in wrapper layer if needed.

---

## Feature 9: File Metadata Completeness

### Problem Statement

Current `FileInfo` metadata is minimal. Enhanced metadata enables:

- Efficient change detection
- Smart caching strategies
- File type detection
- Permissions-based access control
- Backup scheduling

### Proposed Solution

Enhance `FileInfo` dataclass:

```python
from typing import Optional
from enum import Enum

class FileType(Enum):
    """File type classification."""
    FILE = "file"
    DIRECTORY = "directory"
    SYMLINK = "symlink"
    UNKNOWN = "unknown"

@dataclass(frozen=True)
class FileInfo:
    """Extended file metadata."""

    path: Path
    is_dir: bool
    size: int
    created_at: datetime | None
    modified_at: datetime | None

    # NEW FIELDS (optional for backward compatibility)
    accessed_at: datetime | None = None
    file_type: FileType = FileType.FILE
    permissions: int | None = None  # Unix permissions (e.g., 0o644)
    owner_uid: int | None = None  # Unix UID
    owner_gid: int | None = None  # Unix GID
    checksum: str | None = None  # SHA256 hex string
    encoding: str | None = None  # Text encoding (e.g., "utf-8")

    def is_text_file(self) -> bool:
        """Heuristic: is this likely a text file?"""
        # Check by extension, encoding, content

    def is_binary_file(self) -> bool:
        """Heuristic: is this likely a binary file?"""

    def is_readable(self, uid: int | None = None) -> bool:
        """Check if file is readable by user."""
        if self.permissions is None:
            return True  # Unknown, assume readable
        # Check permission bits

    def is_modified_since(self, timestamp: datetime) -> bool:
        """Check if modified after timestamp."""
        if self.modified_at is None:
            return False
        return self.modified_at > timestamp
```

### Use Cases

1. **Smart Caching**: Invalidate cache only if mtime changed
2. **Binary/Text Detection**: Handle different file types appropriately
3. **Permissions**: Enforce access control on vault files
4. **Efficient Indexing**: Skip unchanged files
5. **Backup Scheduling**: Prioritize recent changes

### Implementation Notes

- New fields should be optional (None if not available)
- Compute checksum only if requested (expensive operation)
- For backends without full metadata (OpenAI), populate what's available
- Provide helper methods for common checks

### Priority: LOW

**Rationale**: Nice-to-have enhancements. Can be deferred or implemented incrementally.

---

## Feature 10: Exception Translation/Mapping

### Problem Statement

F9 uses custom exception hierarchy different from Python's built-in `OSError` family. This causes:

- Incompatibility with code expecting standard exceptions
- Need for adapter layers
- Lost exception context when translating
- Difficulty mixing F9 with standard file operations

### Proposed Solution

Add exception mapping utilities:

```python
import errno
from builtins import FileExistsError, FileNotFoundError, IsADirectoryError

def translate_backend_exception(exc: FileBackendError) -> OSError:
    """Convert F9 exception to standard Python OSError.

    Args:
        exc: F9 FileBackendError or subclass

    Returns:
        Appropriate OSError subclass

    Mapping:
        NotFoundError → FileNotFoundError (errno.ENOENT)
        AlreadyExistsError → FileExistsError (errno.EEXIST)
        InvalidOperationError (cannot_read_directory) → IsADirectoryError
        InvalidOperationError (cannot_update_directory) → IsADirectoryError
        InvalidOperationError → OSError (general)
        FileBackendError → OSError (fallback)
    """
    if isinstance(exc, NotFoundError):
        return FileNotFoundError(
            errno.ENOENT,
            os.strerror(errno.ENOENT),
            str(exc.path) if exc.path else None,
        )
    elif isinstance(exc, AlreadyExistsError):
        return FileExistsError(
            errno.EEXIST,
            os.strerror(errno.EEXIST),
            str(exc.path) if exc.path else None,
        )
    elif isinstance(exc, InvalidOperationError):
        if "directory" in exc.message.lower():
            return IsADirectoryError(
                errno.EISDIR,
                os.strerror(errno.EISDIR),
                str(exc.path) if exc.path else None,
            )
        return OSError(str(exc))
    else:
        return OSError(str(exc))


@contextmanager
def translate_exceptions():
    """Context manager that translates F9 exceptions to standard OSError.

    Usage:
        with translate_exceptions():
            backend.read("file.txt")  # NotFoundError becomes FileNotFoundError
    """
    try:
        yield
    except FileBackendError as exc:
        raise translate_backend_exception(exc) from exc
```

Optional wrapper class:

```python
class CompatibleFileBackend(FileBackend):
    """Wrapper that translates exceptions to standard OSError."""

    def __init__(self, backend: FileBackend):
        self._backend = backend

    def read(self, path, *, binary=True):
        with translate_exceptions():
            return self._backend.read(path, binary=binary)

    # ... wrap all methods
```

### Use Cases

1. **Drop-in Replacement**: Use F9 where pathlib/os are expected
2. **Exception Handling**: Catch `FileNotFoundError` as usual
3. **Mixed Code**: Combine F9 with standard library code
4. **Migration**: Easier to swap out backends in existing code
5. **Error Handling**: Standard exception handling patterns work

### Priority: LOW

**Rationale**: Nice-to-have for compatibility; doesn't impact core functionality.

---

## Implementation Roadmap

### Phase 1: High-Priority (Recommended for v2.0)

1. ✅ Streaming I/O (Feature 1)
2. ✅ Checksums (Feature 2)
3. ✅ Async Support (Feature 3)

**Estimated effort**: 40-60 hours
**Impact**: 3-5x performance improvement, enables large-scale use cases

### Phase 2: Medium-Priority (For v2.1)

4. ✅ Pattern Matching (Feature 4)
5. ✅ Sync Sessions (Feature 5)
6. ✅ URI Factory (Feature 6)

**Estimated effort**: 30-40 hours
**Impact**: Better usability, configuration flexibility

### Phase 3: Low-Priority (For v2.2+)

7. ✅ Multi-Vault Context (Feature 7)
8. ✅ Auto-Sync (Feature 8)
9. ✅ Enhanced Metadata (Feature 9)
10. ✅ Exception Translation (Feature 10)

**Estimated effort**: 20-30 hours
**Impact**: Polish, convenience, compatibility

---

## Summary & Recommendations

### Why These Features Matter

The current F9 library is excellent for basic file operations but lacks features needed for production systems that:

- Process large files (streaming needed)
- Build search indexes (checksums + async needed)
- Support multiple backends simultaneously (URI factory + context needed)
- Require atomicity guarantees (sync sessions needed)

### Which Features Are Most Critical

**For Lore_MCP specifically**:

1. **Streaming I/O** - Required for large markdown/embedding operations
2. **Checksums** - Required for search indexing and caching
3. **Async Support** - Required for event-driven MCP architecture
4. **Pattern Matching** - Required for vault file discovery

**For general-purpose file backend library**:
All 10 features would strengthen F9 and expand its use cases.

### Implementation Priorities

- **Must Have** (Phase 1): Streaming, Checksums, Async
- **Should Have** (Phase 2): Pattern Matching, Sync Sessions, URI Factory
- **Nice to Have** (Phase 3): Multi-Vault, Auto-Sync, Metadata, Exception Translation

### Backward Compatibility

All proposed features should be:

- Optional/additive (don't break existing code)
- Implemented as new methods/parameters
- Available in both sync and async variants
- Tested against existing backends

---

## Contact & Discussion

These features are requested for use in the Lore_MCP project (Obsidian MCP Server). We're happy to:

- Discuss implementation approaches
- Contribute code/PRs
- Provide test cases
- Collaborate on design

**Submitted**: 2025-10-30
**For**: f9-file-backend library
**By**: Lore_MCP team
