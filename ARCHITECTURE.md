# Architecture Guide

This document describes the architecture and design patterns used in the f9_file_backend library.

## Table of Contents

- [Backend Design Patterns](#backend-design-patterns)
- [Shared Utilities Philosophy](#shared-utilities-philosophy)
- [Path Validation Strategies](#path-validation-strategies)
- [Error Handling Standards](#error-handling-standards)
- [Testing Patterns](#testing-patterns)

---

## Backend Design Patterns

### Overview

The f9_file_backend library provides a unified interface for file storage operations across multiple storage backends. All backends implement the abstract `FileBackend` interface, allowing applications to switch between storage mechanisms without code changes.

### Interface Definition: FileBackend ABC

The `FileBackend` abstract base class defines the contract that all backends must fulfill:

**File:** [f9_file_backend/interfaces.py](f9_file_backend/interfaces.py)

```python
from abc import ABC, abstractmethod

class FileBackend(ABC):
    """Abstract base class for all file storage backends."""

    @abstractmethod
    def create(
        self,
        path: PathLike,
        *,
        data: bytes | str | BinaryIO | None = None,
        overwrite: bool = False,
    ) -> FileInfo:
        """Create a new file with optional initial content."""

    @abstractmethod
    def read(
        self,
        path: PathLike,
        *,
        binary: bool = True,
    ) -> bytes | str:
        """Read file contents."""

    @abstractmethod
    def update(
        self,
        path: PathLike,
        *,
        data: bytes | str | BinaryIO,
        overwrite_mode: OverwriteMode = "replace",
    ) -> FileInfo:
        """Update existing file."""

    @abstractmethod
    def stream_read(
        self,
        path: PathLike,
        *,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> Iterator[bytes]:
        """Stream file contents in chunks."""

    @abstractmethod
    def stream_write(
        self,
        path: PathLike,
        *,
        chunk_source: Iterator[bytes | str] | BinaryIO,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overwrite: bool = False,
    ) -> FileInfo:
        """Write file from streaming source."""

    @abstractmethod
    def delete(self, path: PathLike) -> None:
        """Delete a file."""

    @abstractmethod
    def exists(self, path: PathLike) -> bool:
        """Check if file exists."""

    @abstractmethod
    def list(self, path: PathLike) -> list[FileInfo]:
        """List files in directory."""

    @abstractmethod
    def checksum(
        self,
        path: PathLike,
        algorithm: ChecksumAlgorithm = "sha256",
    ) -> str:
        """Compute file checksum."""

    @abstractmethod
    def info(self, path: PathLike) -> FileInfo:
        """Get file metadata."""

    @abstractmethod
    def mkdir(self, path: PathLike) -> None:
        """Create directory."""

    @abstractmethod
    def rmdir(self, path: PathLike) -> None:
        """Remove directory."""
```

All concrete implementations must provide these methods with identical semantics.

### Current Implementations

#### LocalFileBackend

**File:** [f9_file_backend/local.py](f9_file_backend/local.py)

- **Use case:** Direct filesystem access
- **Storage mechanism:** Native filesystem operations on a local root directory
- **Path validation:** Uses filesystem-aware validation with symlink resolution
- **Performance:** Optimal for local file operations
- **Concurrency:** Limited by filesystem locks

**Example:**

```python
from f9_file_backend import LocalFileBackend
from pathlib import Path

backend = LocalFileBackend(root=Path("/data/files"))
backend.create("document.txt", data=b"Hello, world!")
content = backend.read("document.txt")
```

#### GitSyncFileBackend

**File:** [f9_file_backend/git_backend.py](f9_file_backend/git_backend.py)

- **Use case:** Version-controlled file storage with Git integration
- **Storage mechanism:** Composes with LocalFileBackend and manages Git operations
- **Path validation:** Uses relative path validation with Git compatibility
- **Performance:** Adds Git operation overhead (commit, push)
- **Concurrency:** Limited by Git lock mechanisms

**Design:** Uses composition pattern to wrap LocalFileBackend and add version control.

**Example:**

```python
from f9_file_backend import GitSyncFileBackend

backend = GitSyncFileBackend(
    root="/data/repo",
    git_config={"user.name": "Bot", "user.email": "bot@example.com"},
    auto_commit=True,
)
backend.create("README.md", data=b"# Project")
# File is automatically committed to Git
```

#### OpenAIVectorStoreFileBackend

**File:** [f9_file_backend/openai_backend.py](f9_file_backend/openai_backend.py)

- **Use case:** Remote file storage using OpenAI's vector store
- **Storage mechanism:** OpenAI API with vector embeddings and storage
- **Path validation:** Uses virtual path validation (no filesystem access)
- **Performance:** Depends on API latency
- **Concurrency:** Managed by OpenAI API

**Example:**

```python
from f9_file_backend import OpenAIVectorStoreFileBackend
import openai

backend = OpenAIVectorStoreFileBackend(
    client=openai.OpenAI(api_key="sk-..."),
    vector_store_id="vs_...",
)
backend.create("document.txt", data=b"Content")
content = backend.read("document.txt")
```

### Design Patterns

#### Pattern 1: Composition

**Used by:** GitSyncFileBackend

The composition pattern allows adding behavior to existing backends without modifying them:

```python
class GitSyncFileBackend(FileBackend):
    def __init__(self, root: PathLike, ...):
        self._local = LocalFileBackend(root)  # Delegate core operations

    def create(self, path: PathLike, *, data=None, overwrite=False) -> FileInfo:
        # Use composed backend
        result = self._local.create(path, data=data, overwrite=overwrite)
        # Add Git behavior
        self._commit(f"Create {path}")
        return result
```

**Benefits:**
- Reuses existing backend logic
- Adds new behavior without changing original
- Easy to remove or replace
- Clear separation of concerns

**When to use:**
- Adding simple operations to existing backends
- Wrapper/decorator patterns
- Logging, metrics, audit trails

#### Pattern 2: Pure Implementation

**Used by:** LocalFileBackend, OpenAIVectorStoreFileBackend

Direct implementation of the FileBackend interface optimized for specific storage mechanism:

```python
class LocalFileBackend(FileBackend):
    def create(self, path: PathLike, *, data=None, overwrite=False) -> FileInfo:
        # Direct implementation specific to filesystem
        target = self._ensure_within_root(path)
        # ... filesystem operations ...
        return self.info(target)
```

**Benefits:**
- Full control over operations
- Optimal performance for specific backend
- Clear implementation-specific logic
- Easy to test and debug

**When to use:**
- Fundamentally different storage mechanisms
- Significant performance optimization needed
- Backend-specific features required

---

## Shared Utilities Philosophy

The library extracts common functionality into reusable utilities to reduce duplication while maintaining backend-specific optimizations.

### What Should Be Shared

#### 1. Pure Functions (No Side Effects)

Functions that don't depend on backend state:

**File:** [f9_file_backend/utils.py](f9_file_backend/utils.py)

- `get_hasher(algorithm)` - Create hasher instances
- `coerce_to_bytes(data)` - Convert various types to bytes
- `accumulate_chunks(chunk_source)` - Collect streaming data
- `compute_checksum_from_file()` - Compute file checksums
- `compute_checksum_from_bytes()` - Compute data checksums

**Example:**

```python
from f9_file_backend.utils import compute_checksum_from_file
from pathlib import Path

checksum = compute_checksum_from_file(
    Path("data.txt"),
    algorithm="sha256"
)
```

#### 2. Path Validation Helpers

Common validation patterns extracted into reusable functions:

**File:** [f9_file_backend/path_utils.py](f9_file_backend/path_utils.py)

- `validate_not_empty(path)` - Ensure path is not empty
- `validate_not_root(path)` - Prevent operations on root
- `detect_path_traversal_posix(parts)` - Detect ".." attempts
- `normalize_windows_path(path_str)` - Normalize path separators

**Example:**

```python
from f9_file_backend.path_utils import detect_path_traversal_posix
from pathlib import PurePosixPath

pure_path = PurePosixPath("../../../etc/passwd")
if detect_path_traversal_posix(pure_path.parts):
    raise ValueError("Path traversal attempt detected")
```

#### 3. Validation Protocol

Protocol-based validation that works across backends:

**File:** [f9_file_backend/validation.py](f9_file_backend/validation.py)

- `PathEntry` Protocol - Define minimal interface for path entries
- `validate_entry_exists()` - Check path exists
- `validate_entry_not_exists()` - Check path doesn't exist
- `validate_is_file()` - Ensure entry is a file
- `validate_not_overwriting_directory_with_file()` - Prevent overwrite errors

**Example:**

```python
from f9_file_backend.validation import validate_entry_exists

def read_impl(self, path: PathLike):
    entry = self._get_entry(path)  # Backend-specific lookup
    validate_entry_exists(entry, path)  # Shared validation
    # ... rest of implementation ...
```

### What Should NOT Be Shared

#### 1. Backend-Specific Logic

Each backend has unique initialization, state management, and operations:

**LocalFileBackend specifics:**
- `_ensure_within_root()` - Filesystem path resolution
- `_load_index()` - (Not applicable)
- Direct `Path` operations

**OpenAIVectorStoreFileBackend specifics:**
- `_ensure_index()` - Load/cache OpenAI index
- `_normalise_path()` - Virtual path normalization
- OpenAI API calls

**GitSyncFileBackend specifics:**
- Git repository management
- Commit/push operations
- Git-specific path handling

#### 2. State-Dependent Operations

Operations that depend on backend state should remain in backend:

```python
# DON'T extract this - backend-specific
def _ensure_within_root(self, path: PathLike) -> Path:
    """Requires self._root and filesystem context."""
    candidate = (self._root / Path(path)).resolve(strict=False)
    try:
        candidate.relative_to(self._root)
    except ValueError as exc:
        raise InvalidOperationError.path_outside_root(candidate) from exc
    return candidate

# DO extract this - pure function
def validate_not_empty(path: Any) -> None:
    """No dependencies on backend state."""
    if not str(path).strip():
        raise InvalidOperationError.empty_path_not_allowed(path)
```

#### 3. Performance-Critical Code

Backends may need specialized implementations for performance:

```python
# OpenAI backend may cache checksums
def checksum(self, path: PathLike, algorithm: ChecksumAlgorithm = "sha256") -> str:
    if self._checksum_cache.get((path, algorithm)):
        return cached_value
    # ... compute and cache ...

# LocalFileBackend uses direct filesystem
def checksum(self, path: PathLike, algorithm: ChecksumAlgorithm = "sha256") -> str:
    return compute_checksum_from_file(target, algorithm)
```

### Guidelines for Adding New Utilities

When adding new shared utilities:

1. **Identify the pattern** - Look for duplication across 2+ backends
2. **Extract pure functions** - Remove backend-specific dependencies
3. **Add comprehensive tests** - Test all edge cases
4. **Document usage** - Show how backends should use it
5. **Measure impact** - Verify it reduces duplication

Example: Adding a new utility

```python
# 1. Identify the pattern (in 2+ backends)
# LocalFileBackend.read() and OpenAIVectorStoreFileBackend.read()
# both check if path is a file before reading

# 2. Extract as pure function using Protocol
def validate_is_file(entry: PathEntry, path: Any) -> None:
    """Validate entry is a file, not directory."""
    if entry.is_dir:
        raise InvalidOperationError.cannot_read_directory(path)

# 3. Add tests
def test_validate_is_file_with_directory():
    mock_entry = Mock(spec=PathEntry, is_dir=True)
    with pytest.raises(InvalidOperationError):
        validate_is_file(mock_entry, "dir_path")

# 4. Document in docstring with examples
# 5. Use in backends
entry = LocalPathEntry.from_path(target)
validate_is_file(entry, target)
```

---

## Path Validation Strategies

Different backends use different validation approaches depending on their storage mechanism.

### Strategy 1: Filesystem-Aware Validation

**Used by:** LocalFileBackend, GitSyncFileBackend

This strategy validates paths by resolving them against the filesystem:

```python
def _ensure_within_root(self, path: PathLike) -> Path:
    """File-based path resolution with traversal prevention."""
    candidate = (self._root / Path(path)).resolve(strict=False)
    try:
        candidate.relative_to(self._root)
    except ValueError as exc:
        raise InvalidOperationError.path_outside_root(candidate) from exc
    return candidate
```

**Characteristics:**
- Resolves symlinks and relative paths
- Works with actual filesystem
- Returns absolute `Path` objects
- Detects traversal attempts by checking relative_to()

**Security properties:**
- Symlink attacks prevented by `.resolve()`
- Traversal prevented by `relative_to()` check
- Works with complex path scenarios

**Example attacks prevented:**

```python
# Symlink to /etc/passwd - prevented by resolve()
backend._ensure_within_root("/data/../../../etc/passwd")
# Result: /data/etc/passwd (safely within root)

# Symlink escape - prevented by resolve()
symlink = Path("/data/link") -> "/etc"
backend._ensure_within_root("link/passwd")
# Result: raises ValueError (outside root)
```

### Strategy 2: Virtual Path Validation

**Used by:** OpenAIVectorStoreFileBackend

This strategy validates paths using pure path operations (no filesystem access):

```python
@staticmethod
def _normalise_path(path: PathLike) -> str:
    """POSIX string normalization with traversal prevention."""
    path_str = str(path).replace("\\", "/")
    if not path_str or path_str.strip() == "":
        raise InvalidOperationError.empty_path_not_allowed(path)
    pure = PurePosixPath(path_str)
    if pure.is_absolute() or any(part == ".." for part in pure.parts):
        raise InvalidOperationError.path_outside_root(path_str)
    normalised = pure.as_posix()
    if normalised == ".":
        raise InvalidOperationError.root_path_not_allowed(path)
    return normalised
```

**Characteristics:**
- No filesystem access required
- Works with virtual/remote paths
- Returns POSIX-normalized strings
- Detects traversal by checking path components

**Security properties:**
- No filesystem access (can't follow symlinks)
- Explicit ".." detection
- Absolute path rejection
- Works with any path format

**Example attacks prevented:**

```python
# Traversal attempt - prevented by ".." check
backend._normalise_path("../../etc/passwd")
# Result: raises InvalidOperationError

# Absolute path - prevented by is_absolute() check
backend._normalise_path("/etc/passwd")
# Result: raises InvalidOperationError

# Unicode/encoding tricks - normalized by PurePosixPath
backend._normalise_path("file\x00.txt")
# Result: raises or normalizes safely
```

### Choosing a Validation Strategy

| Requirement | Filesystem-Aware | Virtual Path |
|------------|------------------|--------------|
| Local filesystem | ✅ Preferred | ❌ Not needed |
| Remote storage | ❌ Not applicable | ✅ Preferred |
| Symlink handling | ✅ Resolves | ❌ N/A |
| Performance | ✅ Fast | ✅ Very fast |
| Complexity | Medium | Low |

---

## Error Handling Standards

### Exception Hierarchy

All backends raise exceptions from the standard hierarchy:

**File:** [f9_file_backend/exceptions.py](f9_file_backend/exceptions.py)

```
FileBackendException (base)
├── NotFoundError - Path doesn't exist
├── AlreadyExistsError - Path already exists
├── InvalidOperationError - Semantic constraint violation
│   ├── EmptyPathNotAllowed
│   ├── RootPathNotAllowed
│   ├── PathOutsideRoot
│   ├── CannotReadDirectory
│   ├── CannotWriteDirectory
│   ├── CannotOverwriteDirectoryWithFile
│   └── CannotOverwriteFileWithDirectory
└── GitOperationError - Git-specific failures (GitSyncFileBackend only)
```

### Exception Semantics

#### NotFoundError

**When to raise:**
- File/directory doesn't exist when expecting it to

**Example:**

```python
if not target.exists():
    raise NotFoundError(target)

if entry is None:
    raise NotFoundError(path)
```

#### AlreadyExistsError

**When to raise:**
- File/directory exists when expecting it to be new

**Example:**

```python
if target.exists() and not overwrite:
    raise AlreadyExistsError(target)

if entry is not None and not overwrite:
    raise AlreadyExistsError(path)
```

#### InvalidOperationError

**When to raise:**
- Semantic constraint violated (e.g., trying to read a directory as a file)

**Subtypes:**

- `EmptyPathNotAllowed` - Path string is empty or whitespace
- `RootPathNotAllowed` - Trying to operate on root directory
- `PathOutsideRoot` - Path escapes root directory
- `CannotReadDirectory` - Trying to read directory as file
- `CannotWriteDirectory` - Trying to write directory as file
- `CannotOverwriteDirectoryWithFile` - Overwriting directory with file
- `CannotOverwriteFileWithDirectory` - Overwriting file with directory

**Example:**

```python
if target.is_dir():
    raise InvalidOperationError.cannot_read_directory(target)

if entry.is_dir and not overwrite:
    raise InvalidOperationError.cannot_overwrite_file_with_directory(path)
```

### Error Messages

Error messages should be consistent across backends:

```python
# GOOD: Clear, includes path, suggests action
raise NotFoundError(f"File not found: {path}")

# GOOD: Explains why it failed
raise InvalidOperationError.cannot_read_directory(
    f"Cannot read directory as file: {path}"
)

# BAD: Vague message
raise InvalidOperationError("Error")

# BAD: No path information
raise AlreadyExistsError("Already exists")
```

---

## Testing Patterns

### Test Organization

Tests are organized by backend and functionality:

```
tests/
├── test_utils.py                    # Utility function tests
├── test_path_utils.py              # Path validation tests
├── test_validation.py              # Validation helper tests
├── test_local.py                   # LocalFileBackend tests
├── test_openai_backend.py          # OpenAIVectorStoreFileBackend tests
├── test_git_backend.py             # GitSyncFileBackend tests
├── test_shared_behavior.py         # Parameterized shared behavior
├── integration/
│   ├── test_streaming_integration.py
│   ├── test_local_backend_integration.py
│   └── test_openai_backend_integration.py
└── fakes.py                        # Test doubles
```

### Shared Behavior Tests

Use parameterized tests to ensure all backends behave consistently:

**Pattern:**

```python
import pytest
from f9_file_backend import LocalFileBackend, GitSyncFileBackend

@pytest.fixture(params=[
    "local",
    "git",
])
def backend(request, tmp_path):
    if request.param == "local":
        return LocalFileBackend(tmp_path)
    elif request.param == "git":
        return GitSyncFileBackend(tmp_path, git_config={...})

def test_create_and_read_file(backend):
    """All backends should support basic create/read."""
    backend.create("test.txt", data=b"Hello")
    assert backend.read("test.txt") == b"Hello"

def test_error_on_read_nonexistent(backend):
    """All backends should raise NotFoundError."""
    with pytest.raises(NotFoundError):
        backend.read("nonexistent.txt")
```

**Benefits:**
- Catches behavioral differences early
- Ensures API contract is satisfied
- Reduces test duplication

### Backend-Specific Tests

Each backend has unique features requiring specific tests:

**LocalFileBackend specifics:**
- Symlink handling
- Permission-based errors
- Large file handling

**OpenAIVectorStoreFileBackend specifics:**
- API error handling
- Rate limiting behavior
- Index synchronization

**GitSyncFileBackend specifics:**
- Git history tracking
- Merge conflict handling
- Push/pull operations

### Test Coverage Standards

- **Minimum coverage:** 90%
- **Utility modules:** 95%
- **Public APIs:** 100%
- **Error paths:** 100%

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=f9_file_backend --cov-report=html

# Run specific backend tests
pytest tests/test_local.py -v
pytest tests/test_openai_backend.py -v

# Run integration tests
pytest tests/integration/ -v

# Run performance benchmarks
pytest tests/ -v --benchmark-only
```

---

## Design Decisions

### Why Not Consolidate Path Validation?

**Question:** Could we merge LocalFileBackend and OpenAIVectorStoreFileBackend path validation?

**Decision:** No, keep backend-specific implementations.

**Rationale:**
1. **Different requirements** - One needs filesystem access, one doesn't
2. **Performance** - Consolidation would add unnecessary overhead
3. **Clarity** - Backend-specific code is easier to understand
4. **Security** - Easier to audit backend-specific validation

### Why Use Protocol-Based Validation?

**Question:** Could we just use duck typing for validation?

**Decision:** Use explicit Protocol with adapters.

**Rationale:**
1. **Type safety** - IDE can check contracts
2. **Documentation** - Protocol documents what validation expects
3. **Testability** - Clear interface for mocking
4. **Maintainability** - Changes caught early by type checker

### Why Defer Virtual Filesystem Layer?

**Question:** Could we implement a virtual filesystem abstraction now?

**Decision:** Defer to future Phase 5.

**Rationale:**
1. **Complexity** - High risk, unclear payoff
2. **Existing patterns work** - Composition is sufficient for most cases
3. **Evaluate need later** - See if maintaining current code becomes difficult
4. **Avoid over-engineering** - YAGNI principle

---

## Future Considerations

### Potential Phase 5: Virtual Filesystem Layer

Future refactoring could introduce an abstraction layer for remote storage:

```python
class VirtualFilesystem(Protocol):
    """Protocol for virtual filesystem implementations."""
    def read_bytes(self, path: str) -> bytes: ...
    def write_bytes(self, path: str, content: bytes) -> None: ...
    def exists(self, path: str) -> bool: ...
    def is_dir(self, path: str) -> bool: ...
```

This would allow OpenAI backend to delegate to a virtual filesystem implementation, reducing duplication.

### Additional Backends

With clear patterns established, new backends become easier:

- **S3Backend** - AWS S3 storage
- **AzureBlobBackend** - Azure Blob Storage
- **SFTPBackend** - Remote SFTP storage
- **MemoryBackend** - In-memory storage for testing

Each new backend should:
1. Inherit from `FileBackend`
2. Use shared utilities where applicable
3. Implement appropriate path validation
4. Include comprehensive tests
5. Update this document with architecture decisions

---

## Summary

The f9_file_backend library is designed with these core principles:

1. **Unified Interface** - All backends implement `FileBackend` contract
2. **Composition Over Inheritance** - Use composition for adding behavior
3. **Shared Utilities** - Extract pure functions, keep backend logic separate
4. **Consistent Validation** - Use protocols for backend-agnostic validation
5. **Clear Error Handling** - Standardized exception hierarchy and messages
6. **Comprehensive Testing** - Parameterized tests + backend-specific tests
7. **Incremental Optimization** - Only optimize when needed, document decisions

This architecture enables:
- Easy addition of new backends
- Reduced code duplication
- Consistent error handling
- Clear testing patterns
- Maintainable codebase

---

**Document Version:** 1.0
**Created:** 2025-10-30
**Last Updated:** 2025-10-30
