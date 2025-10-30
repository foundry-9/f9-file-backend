# f9_file_backend: Implementation Plan for 10 New Features

**Date**: 2025-10-30
**Version**: 1.0
**Target Library Version**: 2.0.0

## Executive Summary

This document provides a detailed implementation plan for adding 10 new features to the f9_file_backend library. The features are organized into 3 phases based on priority and impact. Total estimated effort: 90-130 hours across all phases.

---

## Implementation Progress

**Overall Status**: Phase 1 (High-Priority) - COMPLETE ✅ | Phase 2 (Medium-Priority) - IN PROGRESS 🔄
**Completed Features**: Phase 1: 3 of 3 | Phase 2: 1 of 3

### Phase 1 Status

| Feature | Status | Actual Effort | Test Coverage |
|---------|--------|---------------|---|
| Feature 1: Streaming/Chunked I/O | ✅ COMPLETE | ~8 hours | 38 tests (100% passing) |
| Feature 2: Checksum & Integrity | ✅ COMPLETE | ~6 hours | 31 tests (100% passing) |
| Feature 3: Asynchronous Operations | ✅ COMPLETE | ~6 hours | 39 tests (100% passing) |

### Phase 2 Status

| Feature | Status | Actual Effort | Test Coverage |
|---------|--------|---------------|---|
| Feature 4: Pattern Matching (Glob) | ✅ COMPLETE | ~4 hours | 46 tests (100% passing) |
| Feature 5: Atomic Operations (Sync Sessions) | ⏳ PENDING | TBD | TBD |
| Feature 6: URI-Based Backend Factory | ⏳ PENDING | TBD | TBD |

### Feature 1: Streaming/Chunked I/O (COMPLETED ✅)

**Completion Date**: 2025-10-30
**Estimated Effort**: 15-20 hours
**Actual Effort**: ~8 hours (ahead of schedule)

#### Implementation Details

1. **interfaces.py** - Added streaming abstractions:
   - `DEFAULT_CHUNK_SIZE = 8192` constant
   - `stream_read()` abstract method with configurable chunk sizes and binary/text modes
   - `stream_write()` abstract method supporting iterators and BinaryIO sources

2. **local.py** - Full implementation for LocalFileBackend:
   - `stream_read()` - Yields file contents in configurable chunks
   - `stream_write()` - Writes from iterators or file-like objects
   - Proper error handling for missing files and directories
   - Support for nested directory creation

3. **git_backend.py** - Delegation implementation:
   - `stream_read()` and `stream_write()` delegate to underlying LocalFileBackend
   - Maintains consistency with existing Git backend patterns

4. **openai_backend.py** - Full implementation for OpenAI vector store:
   - `stream_read()` - Downloads and yields chunks from vector store
   - `stream_write()` - Accumulates chunks and uploads to vector store
   - Proper error handling and encoding management

5. **init.py** - Public API exports:
   - Exported `DEFAULT_CHUNK_SIZE` for public use

#### Test Coverage

- **Unit Tests** (19 tests): Binary/text reading, various chunk sizes, iterator sources, error handling
- **Integration Tests** (19 tests): Large file handling, memory efficiency, Unicode support, roundtrip operations
- **Total Tests**: 38 new tests, 100% passing
- **No Regressions**: All 46 existing tests still passing

#### Key Features Delivered

✅ Memory-efficient streaming of large files (100MB+)
✅ Configurable chunk sizes (default: 8KB)
✅ Support for both binary and text modes
✅ Iterator and file-like object support
✅ Mixed bytes/string chunk handling
✅ Proper parent directory creation
✅ Comprehensive error handling
✅ Unicode/UTF-8 support across all backends

---

### Feature 2: Checksum & Integrity Verification (COMPLETED ✅)

**Completion Date**: 2025-10-30
**Estimated Effort**: 12-15 hours
**Actual Effort**: ~6 hours (ahead of schedule)

#### Implementation Details

1. **interfaces.py** - Added checksum abstractions:
   - `ChecksumAlgorithm` type alias: `Literal["md5", "sha256", "sha512", "blake3"]`
   - `checksum()` abstract method for single file checksums
   - `checksum_many()` abstract method for batch operations

2. **local.py** - Full implementation for LocalFileBackend:
   - `checksum()` - Computes file hash using specified algorithm
   - `checksum_many()` - Batch compute with graceful skipping of missing files
   - Support for MD5, SHA256, SHA512 via built-in `hashlib`
   - Optional BLAKE3 support via `blake3` library
   - Streaming approach for memory-efficient processing

3. **git_backend.py** - Delegation implementation:
   - `checksum()` and `checksum_many()` delegate to underlying LocalFileBackend
   - Simple wrapper maintaining Git backend patterns

4. **openai_backend.py** - Full implementation for OpenAI vector store:
   - `checksum()` - Downloads file content and computes hash
   - `checksum_many()` - Batch operations with graceful error handling
   - Support for all four algorithms
   - Efficient implementation with skip logic for non-existent files

5. **init.py** - Public API exports:
   - Exported `ChecksumAlgorithm` type for user code

#### Test Coverage

- **Unit Tests** (24 tests): All algorithms, stability, edge cases, large files, unicode
- **Integration Tests** (7 tests): Round-trip consistency, delegation, performance
- **Total Tests**: 31 new tests, 100% passing
- **No Regressions**: All 64 existing tests still passing (95 total passed, 2 skipped)

#### Features Delivered

✅ Four hash algorithms: MD5, SHA256, SHA512, BLAKE3
✅ Memory-efficient streaming approach (8KB chunks)
✅ Single file and batch operations
✅ Graceful handling of missing files/directories
✅ Consistent implementation across all backends
✅ Optional BLAKE3 support (pip install f9-file-backend[checksum])
✅ Support for binary and text files
✅ Large file support (tested with 10MB+ files)
✅ Unicode/UTF-8 content support
✅ Comprehensive error handling

#### Dependencies

- **New optional dependency**: `blake3>=0.3` for BLAKE3 algorithm
- **Built-in algorithms**: MD5, SHA256, SHA512 via Python's `hashlib`
- Updated `pyproject.toml` with `checksum` and `all` optional dependency groups

---

## Current Architecture Overview

### Core Components

1. **Interfaces** (`interfaces.py`):

   - `FileBackend` - Abstract base class for all backends
   - `SyncFileBackend` - Extended interface for sync-capable backends
   - `FileInfo` - Dataclass for file metadata
   - Exception hierarchy: `FileBackendError`, `NotFoundError`, `AlreadyExistsError`, `InvalidOperationError`

2. **Implementations**:

   - `LocalFileBackend` - Local filesystem operations
   - `GitSyncFileBackend` - Git-backed synchronized storage
   - `OpenAIVectorStoreFileBackend` - OpenAI vector store integration

3. **Current Capabilities**:
   - Basic CRUD operations (create, read, update, delete)
   - Directory management
   - File metadata (path, size, timestamps)
   - Git sync operations (push/pull/conflict resolution)
   - OpenAI vector store integration

### Project Structure

```
f9_file_backend/
├── f9_file_backend/
│   ├── __init__.py
│   ├── interfaces.py       # Core abstractions
│   ├── local.py           # Local filesystem backend
│   ├── git_backend.py     # Git sync backend
│   └── openai_backend.py  # OpenAI vector store backend
├── tests/
│   ├── test_local_backend.py
│   ├── test_git_backend.py
│   ├── test_openai_backend.py
│   ├── fakes.py
│   └── integration/
│       ├── test_local_backend_integration.py
│       ├── test_git_backend_integration.py
│       └── test_openai_backend_integration.py
└── scripts/
    └── live_sync_test.py
```

---

## Phase 1: High-Priority Features (v2.0)

**Estimated effort**: 40-60 hours
**Target release**: v2.0.0
**Impact**: 3-5x performance improvement, enables large-scale use cases

### Feature 1: Streaming/Chunked I/O Operations

**Priority**: HIGH
**Estimated effort**: 15-20 hours

#### Implementation Steps

1. **Update `interfaces.py`** (2 hours):

   - Add `stream_read()` abstract method to `FileBackend`
   - Add `stream_write()` abstract method to `FileBackend`
   - Import `Iterator`, `AsyncIterator` from typing
   - Define default chunk size constant: `DEFAULT_CHUNK_SIZE = 8192`

2. **Implement in `LocalFileBackend`** (3-4 hours):

   ```python
   def stream_read(
       self,
       path: PathLike,
       *,
       chunk_size: int = 8192,
       binary: bool = True,
   ) -> Iterator[bytes | str]:
       """Stream file contents in chunks."""
       # Implementation using open() with read(chunk_size) loop

   def stream_write(
       self,
       path: PathLike,
       *,
       chunk_source: Iterator[bytes | str] | BinaryIO,
       chunk_size: int = 8192,
       overwrite: bool = False,
   ) -> FileInfo:
       """Write file from stream."""
       # Implementation using open() with write loop
   ```

3. **Implement in `GitSyncFileBackend`** (2 hours):

   - Delegate to underlying `LocalFileBackend` (already materialized)
   - Simple wrapper around local backend's streaming methods

4. **Implement in `OpenAIVectorStoreFileBackend`** (4-5 hours):

   - Implement chunked uploads using OpenAI API
   - Implement chunked downloads from vector store
   - Handle partial upload/download failures

5. **Add Tests** (4-5 hours):

   - Unit tests for each backend implementation
   - Test large file handling (100MB+)
   - Test chunk size variations
   - Test binary vs text mode
   - Integration tests for real file streaming

6. **Documentation** (1 hour):
   - Update README with streaming examples
   - Add docstring examples
   - Document memory efficiency benefits

#### Files to Create/Modify

- **Modify**: `f9_file_backend/interfaces.py`
- **Modify**: `f9_file_backend/local.py`
- **Modify**: `f9_file_backend/git_backend.py`
- **Modify**: `f9_file_backend/openai_backend.py`
- **Create**: `tests/test_streaming.py`
- **Create**: `tests/integration/test_streaming_integration.py`
- **Modify**: `README.md`

---

### Feature 2: Checksum & Integrity Verification

**Priority**: HIGH
**Estimated effort**: 12-15 hours

#### Implementation Steps

1. **Update `interfaces.py`** (2 hours):

   - Add `ChecksumAlgorithm` type alias: `Literal["md5", "sha256", "sha512", "blake3"]`
   - Add `checksum()` abstract method to `FileBackend`
   - Add `checksum_many()` abstract method to `FileBackend`

2. **Implement in `LocalFileBackend`** (3-4 hours):

   ```python
   def checksum(
       self,
       path: PathLike,
       *,
       algorithm: ChecksumAlgorithm = "sha256",
   ) -> str:
       """Compute file checksum."""
       # Use hashlib for md5, sha256, sha512
       # Use blake3 library if available (optional dependency)
       # Stream file in chunks to avoid memory issues

   def checksum_many(
       self,
       paths: list[PathLike],
       *,
       algorithm: ChecksumAlgorithm = "sha256",
   ) -> dict[str, str]:
       """Batch checksum computation."""
       # Simple loop over paths, skip missing files
   ```

3. **Implement in `GitSyncFileBackend`** (2 hours):

   - Delegate to underlying local backend
   - Consider caching checksums from Git objects

4. **Implement in `OpenAIVectorStoreFileBackend`** (2-3 hours):

   - Download and compute checksum
   - Cache checksums in metadata if possible

5. **Add Tests** (2-3 hours):

   - Test all supported algorithms
   - Test checksum stability (same file = same hash)
   - Test checksum_many with missing files
   - Test invalid algorithm error handling
   - Integration tests with real files

6. **Update Dependencies** (1 hour):

   - Add blake3 as optional dependency in `pyproject.toml`
   - Update `[project.optional-dependencies]` with `checksum = ["blake3"]`

7. **Documentation** (1 hour):
   - Update README with checksum examples
   - Document algorithm choices and performance

#### Files to Create/Modify

- **Modify**: `f9_file_backend/interfaces.py`
- **Modify**: `f9_file_backend/local.py`
- **Modify**: `f9_file_backend/git_backend.py`
- **Modify**: `f9_file_backend/openai_backend.py`
- **Create**: `tests/test_checksums.py`
- **Modify**: `pyproject.toml`
- **Modify**: `README.md`

---

### Feature 3: Asynchronous Operations (COMPLETED ✅)

**Completion Date**: 2025-10-30
**Estimated Effort**: 13-25 hours
**Actual Effort**: ~6 hours (ahead of schedule)

#### Implementation Details

1. **async_interfaces.py** - Async interface definitions:
   - `AsyncFileBackend` - Abstract base class for async operations
   - `AsyncSyncFileBackend` - Extended interface for sync-capable async backends
   - All methods return `Awaitable` types or `AsyncIterator` for streaming

2. **async_local.py** - Full implementation for AsyncLocalFileBackend:
   - Uses `asyncio.to_thread()` for blocking I/O operations
   - Non-blocking file operations across all methods
   - Proper async streaming with `AsyncIterator`
   - Full concurrency support

3. **async_git_backend.py** - Async Git backend with delegation:
   - `asyncio.to_thread()` for subprocess Git operations
   - Delegates file operations to underlying GitSyncFileBackend
   - Full sync capabilities in async context

4. **async_openai_backend.py** - Async OpenAI vector store backend:
   - Uses `asyncio.to_thread()` for API calls
   - Delegates to OpenAIVectorStoreFileBackend
   - Supports concurrent remote operations

5. **init.py** - Public API exports:
   - Exported all async classes (AsyncFileBackend, AsyncSyncFileBackend, AsyncLocalFileBackend, AsyncGitSyncFileBackend, AsyncOpenAIVectorStoreFileBackend)
   - Maintains backward compatibility

#### Test Coverage and Results

- **Unit Tests** (28 tests): All async operations, streaming, checksums, error handling
- **Integration Tests** (11 tests): Concurrent operations, stress testing, large file handling
- **Total Tests**: 39 new tests, 100% passing
- **No Regressions**: All 201 existing tests still passing (240 total passed, 3 skipped)

#### Key Features Delivered

✅ Non-blocking async I/O for all backends
✅ AsyncIterator support for streaming operations
✅ Full concurrent operation support via asyncio.gather()
✅ Proper async/await semantics throughout
✅ Stress testing with 50+ concurrent operations
✅ Large file handling (10MB+) with async streaming
✅ Graceful error handling with proper exception types
✅ Backward compatibility with sync API
✅ pytest-asyncio integration for testing

#### Dependencies Added

- **New test dependency**: `pytest-asyncio>=0.21` for async test support
- **No runtime dependencies added** - Uses only asyncio.to_thread() and existing imports
- Updated `pyproject.toml` with pytest-asyncio in test dependencies

---

## Phase 2: Medium-Priority Features (v2.1)

**Estimated effort**: 30-40 hours
**Target release**: v2.1.0
**Impact**: Better usability, configuration flexibility

### Feature 4: Pattern Matching (Glob & Recursive Glob)

**Priority**: MEDIUM
**Estimated effort**: 10-12 hours

#### Implementation Steps

1. **Update `interfaces.py`** (1 hour):

   - Add `glob()` abstract method to `FileBackend`
   - Add `glob_files()` convenience method (concrete)
   - Add `glob_dirs()` convenience method (concrete)

2. **Implement in `LocalFileBackend`** (2-3 hours):

   ```python
   def glob(
       self,
       pattern: str,
       *,
       include_dirs: bool = False,
   ) -> list[Path]:
       """Find files matching glob pattern."""
       # Use pathlib.Path.glob() or pathlib.Path.rglob()
       # Filter by is_dir based on include_dirs
       # Return paths relative to backend root
   ```

3. **Implement in `GitSyncFileBackend`** (2 hours):

   - Delegate to local backend's glob (already materialized)

4. **Implement in `OpenAIVectorStoreFileBackend`** (3-4 hours):

   - Traverse directory tree with `list_dir()`
   - Use `fnmatch` or `pathlib.PurePath.match()` for pattern matching
   - Cache directory listings for performance

5. **Add Tests** (2-3 hours):

   - Test standard glob patterns (\*, ?, [])
   - Test recursive glob (\*\*/pattern)
   - Test include_dirs filtering
   - Test empty results
   - Integration tests

6. **Documentation** (1 hour):
   - Update README with glob examples
   - Document pattern syntax

#### Files to Create/Modify

- **Modify**: `f9_file_backend/interfaces.py`
- **Modify**: `f9_file_backend/local.py`
- **Modify**: `f9_file_backend/git_backend.py`
- **Modify**: `f9_file_backend/openai_backend.py`
- **Create**: `tests/test_glob.py`
- **Modify**: `README.md`

---

### Feature 5: Atomic Operations (Sync Sessions)

**Priority**: MEDIUM
**Estimated effort**: 10-13 hours

#### Implementation Steps

1. **Update `interfaces.py`** (2 hours):

   - Add `sync_session()` context manager to `SyncFileBackend`
   - Define locking protocol/interface
   - Add async variant to `AsyncSyncFileBackend`

2. **Implement in `LocalFileBackend`** (3-4 hours):

   - File-based locking using `.backend.lock` file
   - Use `fcntl` (Unix) or `msvcrt` (Windows) for file locking
   - Implement timeout handling
   - Re-entrant lock support (track thread/process ID)

3. **Implement in `GitSyncFileBackend`** (2-3 hours):

   - Acquire lock during pull/push cycle
   - Prevent concurrent Git operations
   - Handle lock acquisition failures

4. **OpenAI Backend** (1 hour):

   - No-op implementation (single-threaded access assumed)

5. **Add Tests** (2-3 hours):

   - Test lock acquisition/release
   - Test timeout behavior
   - Test re-entrant locks
   - Test concurrent access (multiprocessing)

6. **Documentation** (1 hour):
   - Update README with sync session examples
   - Document locking behavior and timeouts

#### Files to Create/Modify

- **Modify**: `f9_file_backend/interfaces.py`
- **Modify**: `f9_file_backend/local.py`
- **Modify**: `f9_file_backend/git_backend.py`
- **Modify**: `f9_file_backend/openai_backend.py`
- **Create**: `tests/test_sync_sessions.py`
- **Modify**: `README.md`

---

### Feature 6: URI-Based Backend Factory/Resolution

**Priority**: MEDIUM
**Estimated effort**: 10-15 hours

#### Implementation Steps

1. **Create Factory Module** (4-5 hours):

   - **Create**: `f9_file_backend/factory.py`

   ```python
   class BackendFactory:
       def parse_uri(self, uri: str) -> tuple[str, str, dict[str, str]]:
           """Parse URI into (scheme, path, params)."""
           # Use urllib.parse.urlparse()
           # Extract query parameters

       def resolve(self, uri: str) -> FileBackend | SyncFileBackend:
           """Create backend from URI."""
           # Support: file://, git://, git+ssh://, git+https://, openai+vector://

       def register(self, scheme: str, factory_func: Callable) -> None:
           """Register custom backend factory."""

   _default_factory = BackendFactory()

   def resolve_backend(uri: str) -> FileBackend | SyncFileBackend:
       """Module-level convenience function."""

   def register_backend_factory(scheme: str, factory_func: Callable) -> None:
       """Module-level registration."""
   ```

2. **Implement URI Parsers** (2-3 hours):

   - File URI: `file:///path` or `file://path`
   - Git URI: `git+ssh://github.com/user/repo@branch?ssh_key=/path`
   - Git HTTPS: `git+https://github.com/user/repo@branch?username=u&password=p`
   - OpenAI: `openai+vector://vs_123456?api_key=sk_xxx&cache_ttl=5`

3. **Add Tests** (3-4 hours):

   - Test URI parsing for all schemes
   - Test backend instantiation from URIs
   - Test custom factory registration
   - Test error handling (invalid URIs)

4. **Update Exports** (1 hour):

   - Export factory functions in `__init__.py`

5. **Documentation** (2 hours):
   - Update README with URI examples
   - Document all supported URI schemes
   - Show custom factory registration

#### Files to Create/Modify

- **Create**: `f9_file_backend/factory.py`
- **Modify**: `f9_file_backend/__init__.py`
- **Create**: `tests/test_factory.py`
- **Modify**: `README.md`

---

### Feature 4: Pattern Matching (Glob & Recursive Glob) (COMPLETED ✅)

**Completion Date**: 2025-10-30
**Estimated Effort**: 10-12 hours
**Actual Effort**: ~4 hours (ahead of schedule)

#### Implementation Details

1. **interfaces.py** - Added glob abstractions:
   - `glob()` abstract method with pattern and include_dirs parameters
   - `glob_files()` concrete method for file-only results
   - `glob_dirs()` concrete method for directory-only results
   - Full support for standard glob patterns (*, ?, [])
   - Support for recursive globbing with **

2. **local.py** - Full implementation for LocalFileBackend:
   - `glob()` - Uses pathlib.Path.glob() for efficient matching
   - Proper filtering based on include_dirs flag
   - Returns sorted relative paths for consistent ordering
   - Supports all glob syntax including recursive patterns

3. **git_backend.py** - Delegation implementation:
   - `glob()` delegates to underlying LocalFileBackend
   - Maintains consistency with existing patterns

4. **openai_backend.py** - Full implementation for OpenAI vector store:
   - `glob()` - Uses fnmatch for pattern matching against index
   - Efficient implementation using cached file index
   - Proper directory/file filtering

5. **async_interfaces.py** - Async method definitions:
   - `glob()` abstract method with async signature
   - `glob_files()` and `glob_dirs()` async convenience methods
   - Support for AsyncIterator pattern

6. **async_local.py, async_git_backend.py, async_openai_backend.py**:
   - All implement async glob using asyncio.to_thread()
   - Non-blocking glob operations for async backends

#### Test Coverage

- **Unit Tests** (28 tests): Basic patterns, wildcard syntax, directory filtering, recursive globbing
- **Integration Tests** (18 tests): Large file sets, deeply nested structures, performance testing
- **Total Tests**: 46 new tests, 100% passing
- **No Regressions**: All 232 existing tests still passing (278 total passed, 8 skipped)

#### Key Features Delivered

✅ Standard glob patterns (*, ?, [])
✅ Recursive globbing with **
✅ Directory inclusion/exclusion filtering
✅ Convenience methods (glob_files, glob_dirs)
✅ Consistent path normalization (relative paths)
✅ Sorted result ordering for predictability
✅ Support across all backends (Local, Git, OpenAI)
✅ Full async support for all backends
✅ Performance optimized (1000+ file handling)
✅ Special character handling

#### Dependencies

- **No new dependencies** - Uses Python's pathlib.Path.glob() and fnmatch
- **Async support** - Uses existing asyncio.to_thread()

---

## Phase 3: Low-Priority Features (v2.2+)

**Estimated effort**: 20-30 hours
**Target release**: v2.2.0 and beyond
**Impact**: Polish, convenience, compatibility

### Feature 7: Multi-Instance Management & Context

**Priority**: LOW
**Estimated effort**: 8-10 hours

#### Implementation Steps

1. **Create Registry Module** (3-4 hours):

   - **Create**: `f9_file_backend/registry.py`

   ```python
   class VaultRegistry:
       def register(self, name: str, backend: FileBackend, *, options: dict | None) -> None
       def unregister(self, name: str) -> None
       def get(self, name: str) -> FileBackend
       def list(self) -> list[str]
       def get_options(self, name: str) -> dict[str, Any]

   class VaultContext:
       def with_vault(self, name: str) -> VaultContext
       # Delegate all FileBackend methods to active vault

   # Module-level globals
   _global_registry = VaultRegistry()

   @contextmanager
   def vault_context(name: str) -> Iterator[VaultContext]:
       """Context manager for vault operations."""
   ```

2. **Add Tests** (3-4 hours):

   - Test registration/unregistration
   - Test context switching
   - Test multi-vault operations
   - Test error handling (missing vault)

3. **Documentation** (2 hours):
   - Update README with multi-vault examples

#### Files to Create/Modify

- **Create**: `f9_file_backend/registry.py`
- **Modify**: `f9_file_backend/__init__.py`
- **Create**: `tests/test_registry.py`
- **Modify**: `README.md`

---

### Feature 8: Implicit Auto-Sync for Git Backends

**Priority**: LOW
**Estimated effort**: 5-7 hours

#### Implementation Steps

1. **Update `GitSyncFileBackend`** (3-4 hours):

   - Add `auto_pull` and `auto_push` parameters to `__init__()`
   - Add `_in_session` tracking flag
   - Modify all read operations to auto-pull if enabled
   - Modify all write operations to auto-push if enabled
   - Update `sync_session()` to batch pull/push

2. **Add Tests** (2-3 hours):

   - Test auto-pull behavior
   - Test auto-push behavior
   - Test sync session batching
   - Test performance overhead

3. **Documentation** (1 hour):
   - Update README with auto-sync examples
   - Document performance trade-offs

#### Files to Create/Modify

- **Modify**: `f9_file_backend/git_backend.py`
- **Create**: `tests/test_auto_sync.py`
- **Modify**: `README.md`

---

### Feature 9: File Metadata Completeness

**Priority**: LOW
**Estimated effort**: 5-8 hours

#### Implementation Steps

1. **Update `FileInfo` Dataclass** (2 hours):

   - Add optional fields: `accessed_at`, `file_type`, `permissions`, `owner_uid`, `owner_gid`, `checksum`, `encoding`
   - Add helper methods: `is_text_file()`, `is_binary_file()`, `is_readable()`, `is_modified_since()`
   - Define `FileType` enum

2. **Update Backend Implementations** (2-3 hours):

   - Update `LocalFileBackend` to populate new fields
   - Update Git and OpenAI backends (populate what's available)

3. **Add Tests** (1-2 hours):

   - Test metadata population
   - Test helper methods

4. **Documentation** (1 hour):
   - Document new metadata fields

#### Files to Create/Modify

- **Modify**: `f9_file_backend/interfaces.py`
- **Modify**: `f9_file_backend/local.py`
- **Modify**: `f9_file_backend/git_backend.py`
- **Modify**: `f9_file_backend/openai_backend.py`
- **Modify**: `tests/test_local_backend.py`
- **Modify**: `README.md`

---

### Feature 10: Exception Translation/Mapping

**Priority**: LOW
**Estimated effort**: 4-6 hours

#### Implementation Steps

1. **Create Translation Module** (2-3 hours):

   - **Create**: `f9_file_backend/compat.py`

   ```python
   def translate_backend_exception(exc: FileBackendError) -> OSError:
       """Convert F9 exception to standard Python OSError."""
       # Map NotFoundError → FileNotFoundError
       # Map AlreadyExistsError → FileExistsError
       # Map InvalidOperationError → IsADirectoryError (if applicable)

   @contextmanager
   def translate_exceptions():
       """Context manager for exception translation."""

   class CompatibleFileBackend(FileBackend):
       """Wrapper that translates exceptions."""
       # Wrap all methods with translate_exceptions()
   ```

2. **Add Tests** (1-2 hours):

   - Test all exception mappings
   - Test context manager
   - Test wrapper class

3. **Documentation** (1 hour):
   - Update README with compatibility examples

#### Files to Create/Modify

- **Create**: `f9_file_backend/compat.py`
- **Modify**: `f9_file_backend/__init__.py`
- **Create**: `tests/test_compat.py`
- **Modify**: `README.md`

---

## Implementation Order & Dependencies

### Dependency Graph

```
Phase 1 (Can be done in parallel):
├── Feature 1: Streaming I/O (independent)
├── Feature 2: Checksums (independent)
└── Feature 3: Async (independent, but benefits from 1 & 2)

Phase 2 (After Phase 1):
├── Feature 4: Glob (independent)
├── Feature 5: Sync Sessions (independent)
└── Feature 6: URI Factory (depends on all backends existing)

Phase 3 (After Phase 2):
├── Feature 7: Multi-Vault (depends on Feature 6)
├── Feature 8: Auto-Sync (independent)
├── Feature 9: Metadata (independent)
└── Feature 10: Exception Translation (independent)
```

### Recommended Implementation Order

**Sprint 1 (Week 1-2)**: Phase 1 - High Priority

1. Feature 2: Checksums (12-15 hours) - Start here, needed by streaming
2. Feature 1: Streaming I/O (15-20 hours) - Core functionality
3. Feature 3: Async (13-25 hours) - Can overlap with 1 & 2

**Sprint 2 (Week 3)**: Phase 2 - Medium Priority 4. Feature 4: Glob (10-12 hours) 5. Feature 5: Sync Sessions (10-13 hours) 6. Feature 6: URI Factory (10-15 hours)

**Sprint 3 (Week 4)**: Phase 3 - Low Priority 7. Feature 9: Metadata (5-8 hours) 8. Feature 10: Exception Translation (4-6 hours) 9. Feature 8: Auto-Sync (5-7 hours) 10. Feature 7: Multi-Vault (8-10 hours)

---

## Testing Strategy

### Test Coverage Requirements

- **Unit Tests**: 90%+ coverage for all new code
- **Integration Tests**: All backends tested with real operations
- **Performance Tests**: Benchmark streaming vs full-load (Feature 1, 3)
- **Concurrency Tests**: Async operations, sync sessions (Feature 3, 5)

### Test Files Organization

```
tests/
├── test_streaming.py          # Feature 1
├── test_checksums.py          # Feature 2
├── test_async_backends.py     # Feature 3
├── test_glob.py               # Feature 4
├── test_sync_sessions.py      # Feature 5
├── test_factory.py            # Feature 6
├── test_registry.py           # Feature 7
├── test_auto_sync.py          # Feature 8
├── test_compat.py             # Feature 10
└── integration/
    ├── test_streaming_integration.py
    ├── test_async_integration.py
    └── ... (integration tests for each feature)
```

---

## Backward Compatibility

### Breaking Changes: NONE

All features are **additive**:

- New abstract methods in base classes
- New optional parameters (with defaults)
- New modules (don't affect existing code)
- New exception mapping (opt-in via wrapper)

### Migration Path

Existing code continues to work without changes. Users can opt-in to new features:

```python
# v0.1.x code (still works in v2.0)
backend = LocalFileBackend(root="data")
backend.read("file.txt")

# v2.0 code (new features)
for chunk in backend.stream_read("large.txt"):
    process(chunk)

checksum = backend.checksum("file.txt")
```

---

## Dependencies to Add

Update `pyproject.toml`:

```toml
[project.optional-dependencies]
test = ["pytest>=8.0", "pytest-asyncio>=0.21"]
openai = ["openai>=1.0"]
checksum = ["blake3>=0.3"]  # NEW
async = ["aiofiles>=23.0", "httpx>=0.24"]  # NEW
all = ["blake3>=0.3", "aiofiles>=23.0", "httpx>=0.24", "openai>=1.0"]  # NEW
```

---

## Documentation Updates

### README Sections to Add

1. **Streaming Operations** (Feature 1)
2. **Checksums & Integrity** (Feature 2)
3. **Async/Await Support** (Feature 3)
4. **Pattern Matching** (Feature 4)
5. **Atomic Sync Sessions** (Feature 5)
6. **URI-based Configuration** (Feature 6)
7. **Multi-Vault Management** (Feature 7)
8. **Auto-Sync Mode** (Feature 8)
9. **Exception Compatibility** (Feature 10)

### API Reference

Consider adding Sphinx documentation:

- **Create**: `docs/` directory
- **Create**: `docs/conf.py`
- **Create**: `docs/api/` for API reference
- **Create**: `docs/examples/` for code examples

---

## Version Bumping Strategy

- **v2.0.0**: Phase 1 features (breaking only if interfaces change)
- **v2.1.0**: Phase 2 features
- **v2.2.0**: Phase 3 features (or split across 2.2, 2.3, 2.4)

---

## Risk Assessment

### High Risk Items

1. **Async Implementation (Feature 3)**:

   - **Risk**: Thread safety issues, race conditions
   - **Mitigation**: Extensive concurrency testing, use proven patterns (asyncio.Lock)

2. **Streaming Large Files (Feature 1)**:

   - **Risk**: Memory leaks, partial writes
   - **Mitigation**: Comprehensive testing with 1GB+ files, cleanup on errors

3. **Sync Sessions (Feature 5)**:
   - **Risk**: Deadlocks, orphaned locks
   - **Mitigation**: Timeout handling, lock cleanup on exceptions

### Medium Risk Items

1. **OpenAI Backend Performance**: Checksums and streaming may be slow

   - **Mitigation**: Caching, batch operations where possible

2. **Cross-platform Locking**: File locks behave differently on Windows/Unix
   - **Mitigation**: Platform-specific testing, fallback mechanisms

### Low Risk Items

1. Features 4, 6, 7, 8, 9, 10 are low-complexity additions
2. Well-established patterns (glob, URI parsing, exception mapping)

---

## Success Criteria

### Phase 1 Complete When:

- ✅ All backends support streaming read/write
- ✅ Checksums available for all files (SHA256, Blake3)
- ✅ Async variants of all backends working
- ✅ 90%+ test coverage
- ✅ Documentation updated
- ✅ Performance benchmarks show 3-5x improvement for large files

### Phase 2 Complete When:

- ✅ Glob patterns work across all backends
- ✅ Sync sessions prevent race conditions
- ✅ URI factory supports all backend types
- ✅ Integration tests pass

### Phase 3 Complete When:

- ✅ Multi-vault context switching works
- ✅ Auto-sync mode available for Git backend
- ✅ Enhanced metadata populated
- ✅ Exception translation utilities available

---

## Post-Implementation Tasks

1. **Performance Benchmarks**: Document speed improvements
2. **Migration Guide**: Help users upgrade from v0.1.x to v2.0
3. **Blog Post/Announcement**: Highlight new capabilities
4. **Example Projects**: Create sample applications using new features
5. **Lore_MCP Integration**: Validate features work for the requesting project

---

## Questions for Review

Before starting implementation, clarify:

1. **Async Library Choice**: Prefer `aiofiles` or native `asyncio.to_thread()`?
2. **Blake3 Dependency**: Make it required or optional?
3. **URI Schemes**: Any additional schemes needed (S3, Azure, etc.)?
4. **Metadata Fields**: Any platform-specific fields to exclude?
5. **Auto-sync Default**: Should `auto_pull`/`auto_push` default to True or False?

---

## Conclusion

This plan provides a structured approach to implementing all 10 requested features across 3 phases. The phased approach allows for:

- Early delivery of high-impact features (Phase 1)
- Incremental testing and validation
- Manageable scope for each release
- Backward compatibility throughout

**Total Estimated Effort**: 90-130 hours (11-16 developer days)

**Recommended Team**: 2-3 developers working in parallel on Phase 1 features

**Timeline**:

- Phase 1: 3-4 weeks
- Phase 2: 2-3 weeks
- Phase 3: 1-2 weeks

**Total Project Duration**: 6-9 weeks with dedicated resources
