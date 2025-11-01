# F9 File Backend Library Issues

## Summary

This document tracks design incompatibilities and API mismatches with the `f9-file-backend` library
(version 1.0.0). These are not necessarily "bugs" but rather API design choices that require workarounds
in downstream code.

**Status:** These workarounds are currently active in our code. Consider re-evaluating if the library
is updated or if an alternative approach becomes available.

---

## Issue 1: Async wrapper mismatch with sync backend API

**Severity:** Critical - Makes async wrappers unusable without workarounds

**Description:**
The async wrapper classes (`AsyncGitSyncFileBackend`, `AsyncOpenAIVectorStoreFileBackend`) have a
different API design from their sync counterparts. The async wrappers are initialized with keyword
arguments (e.g., `root=...`, `vector_store_id=...`), but the sync backends they wrap only accept
a `connection_info` dictionary as the first positional parameter.

**Locations:**

- `AsyncGitSyncFileBackend`: `/async_git_backend.py`, line 88
- `AsyncOpenAIVectorStoreFileBackend`: `/async_openai_backend.py`, line 83
- Sync counterparts: `GitSyncFileBackend`, `OpenAIVectorStoreFileBackend`

**Observed Errors:**

```
TypeError: GitSyncFileBackend.__init__() got an unexpected keyword argument 'root'
TypeError: OpenAIVectorStoreFileBackend.__init__() got an unexpected keyword argument 'vector_store_id'
```

**Root Cause:**
The async wrappers accept keyword arguments in their `__init__` signatures but pass them directly
to the sync backends, which expect a single `connection_info` dict. This is a design mismatch
between the async wrapper API and the sync backend API.

**Expected Behavior (Option A - Fix the async wrappers):**
The async wrappers should construct a proper `connection_info` dict from the keyword arguments
before passing it to the sync backends, similar to how the `BackendFactory` does it.

**Our Solution (Option B - Wrap the sync backend directly):**

We bypass the broken async wrappers entirely by:

1. Manually constructing the `connection_info` dict with the required parameters
2. Instantiating the sync backend directly with the `connection_info`
3. Wrapping it in a custom async wrapper (`_AsyncGitBackendWrapper`, `_AsyncOpenAIBackendWrapper`)
   that provides async operations via `asyncio.to_thread()`

This approach is more reliable because:

- We have explicit control over the `connection_info` construction
- We can document exactly what parameters are expected
- We avoid relying on the async wrapper implementations
- The pattern is consistent across all backends

**Related Files:**

- `server/backends/f9_git.py` - Git backend wrapper and workaround
- `server/backends/f9_openai.py` - OpenAI backend wrapper and workaround

---

## Issue 2: Path validation rejects absolute paths unnecessarily

**Severity:** High - Breaks normal path usage patterns

**Description:**
The `LocalFileBackend` (and by extension `GitSyncFileBackend`) validates paths using `_ensure_within_root()` which rejects paths starting with `/` as "escaping the root", even when they're just absolute paths relative to the repository root.

**Location:**

- Library: `f9_file_backend` version 1.0.0
- File: `/local.py`, line 399 (in `_ensure_within_root()`)

**Error:**

```
InvalidOperationError: Path escapes backend root: /README.md
```

**Root Cause:**
The path validation logic treats leading slashes as path traversal attempts, but standard practice in MCP and other protocols is to use paths like `/file.txt` to represent root-relative files.

**Expected Behavior:**
Paths like `/file.txt` should be treated as relative to the backend root (i.e., equivalent to `file.txt`), not as absolute filesystem paths that escape the root.

**Workaround:**
Currently working around this by stripping leading slashes from all paths before passing them to the backend:

```python
path_str = str(path).lstrip("/")
```

**Related Files:**

- `server/backends/f9_git.py` - Multiple path handling fixes required

---

## Recommendation

These issues should be fixed in the f9_file_backend library:

1. **Fix AsyncGitSyncFileBackend**: Update `__init__()` to properly construct `connection_info` before passing to `GitSyncFileBackend`
2. **Fix path validation**: Update `_ensure_within_root()` to accept leading slashes as valid root-relative paths

This will make the library more usable and eliminate the need for workarounds in downstream code.

## Implementation Status

### Git Backend (server/backends/f9_git.py)

Status: **Workaround Implemented**

Workarounds applied:

1. **For Issue 1**: Manually construct `connection_info` dict and create `GitSyncFileBackend` directly,
   then wrap in a custom `_AsyncGitBackendWrapper` that provides async operations via `asyncio.to_thread()`

2. **For Issue 2**: Strip leading slashes from all paths before passing to backend methods using `.lstrip("/")`

### OpenAI Backend (server/backends/f9_openai.py)

Status: **Workaround Implemented**

Workarounds applied:

1. **For Issue 1**: Manually construct `connection_info` dict and create `OpenAIVectorStoreFileBackend`
   directly, then wrap in a custom `_AsyncOpenAIBackendWrapper` that provides async operations via
   `asyncio.to_thread()`

Tests: All 18 unit tests passing with mocked f9 backend ✓

### Migration Path

These workarounds should be re-evaluated if:

- The f9-file-backend library fixes the async wrapper API mismatch
- A compatible async-first backend library becomes available
- The library provides async-native versions of these backends
