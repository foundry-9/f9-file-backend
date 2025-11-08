# Quick Reference: Sync/Async Interface Inconsistencies

## The One Critical Issue

### `sync_session()` Method in AsyncSyncFileBackend

**File:** `/f9_file_backend/async_interfaces.py`, line 359

**Problem:**
```python
# WRONG: Method is not async but return type claims async context manager
def sync_session(
    self,
    *,
    timeout: float | None = None,
) -> AbstractAsyncContextManager[None]:  # Claims async but method is sync!
```

**What the interface says you should do:**
```python
async with backend.sync_session():
    await backend.pull()
```

**What you actually have to do (breaks interface contract):**
```python
with backend.sync_session():  # Sync context manager, not async
    await backend.pull()
```

**Why it's wrong:**
1. All other async methods are `async def` - this breaks the pattern
2. Return type annotation says `AbstractAsyncContextManager` but implements `AbstractContextManager`
3. Users expecting the interface will write `async with` and get a type error

**Implementations acknowledge the issue:**
- `AsyncLocalFileBackend.sync_session()` (line 250) - explicitly documents "This method is NOT async"
- `AsyncGitSyncFileBackend.sync_session()` (line 320) - explicitly documents "This method is NOT async"

---

## All Other Methods - CONSISTENT ✓

### FileBackend Core Methods
```
create()          ✓ async in AsyncFileBackend
read()            ✓ async in AsyncFileBackend
update()          ✓ async in AsyncFileBackend
delete()          ✓ async in AsyncFileBackend
info()            ✓ async in AsyncFileBackend
stream_read()     ✓ async in AsyncFileBackend (uses AsyncIterator)
stream_write()    ✓ async in AsyncFileBackend (accepts AsyncIterator)
checksum()        ✓ async in AsyncFileBackend
checksum_many()   ✓ async in AsyncFileBackend
glob()            ✓ async in AsyncFileBackend
glob_files()      ✓ async in AsyncFileBackend (concrete, properly awaits)
glob_dirs()       ✓ async in AsyncFileBackend (concrete, properly awaits)
```

### SyncFileBackend Extended Methods
```
push()                      ✓ async in AsyncSyncFileBackend
pull()                      ✓ async in AsyncSyncFileBackend
sync()                      ✓ async in AsyncSyncFileBackend (concrete, properly awaits)
conflict_report()           ✓ async in AsyncSyncFileBackend
conflict_accept_local()     ✓ async in AsyncSyncFileBackend
conflict_accept_remote()    ✓ async in AsyncSyncFileBackend
conflict_resolve()          ✓ async in AsyncSyncFileBackend
sync_session()              ✗ NOT async in AsyncSyncFileBackend (BUG)
```

---

## Implementation Patterns - All CONSISTENT ✓

### Wrapper Pattern
All async implementations use the same pattern:
```python
class AsyncLocalFileBackend(AsyncFileBackend):
    def __init__(self, root=None, *, create_root=True):
        self._sync_backend = LocalFileBackend(root, create_root=create_root)
    
    async def create(self, path, *, data=None, is_directory=False, overwrite=False):
        return await asyncio.to_thread(
            self._sync_backend.create,
            path,
            data=data,
            is_directory=is_directory,
            overwrite=overwrite,
        )
```

---

## Type Consistency - CONSISTENT ✓

### Iterator Types
```
Sync:  Iterator[bytes | str]
Async: AsyncIterator[bytes | str]
✓ Correctly adapted for async
```

### Default Parameters
```
Sync interface: DEFAULT_CHUNK_SIZE = 8192
Async interface: chunk_size: int = 8192
✓ Both use 8192

Sync interface: algorithm: ChecksumAlgorithm = "sha256"
Async interface: algorithm: ChecksumAlgorithm = "sha256"
✓ Both use sha256
```

---

## Related Issues (Already Known)

These are documented in `/bugs/fixed/bug_report_from_lore_mcp_1.md`:

### Issue 1: AsyncGitSyncFileBackend Initialization
- **Problem:** Async wrappers accept kwargs but sync backends expect connection_info dict
- **Status:** Documented and has workarounds in downstream code

### Issue 2: Path Validation with Leading Slashes
- **Problem:** Paths like `/file.txt` rejected as "escaping root"
- **Status:** Documented and has workarounds in downstream code

---

## Fix Recommendations

### Option A: Make sync_session truly async (Preferred)
Update interface and implementations to:
```python
async def sync_session(
    self,
    *,
    timeout: float | None = None,
) -> AbstractAsyncContextManager[None]:
```

### Option B: Fix the return type annotation (Pragmatic)
Keep implementations as sync but fix interface:
```python
def sync_session(
    self,
    *,
    timeout: float | None = None,
) -> AbstractContextManager[None]:  # Match SyncFileBackend
```

**Recommendation:** Option B is more practical since context managers need to work
synchronously for proper locking across sync and async code. Just update the
type annotation and documentation to be clear about usage.

