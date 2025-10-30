# File Backend Library

`f9_file_backend` provides a consistent interface for working with different file storage providers. The initial release includes a local filesystem backend; additional implementations can plug into the same API.

## Installation

Install into your environment (`pip install -e .` for editable development installs). Then import the backend you need:

```python
from f9_file_backend import LocalFileBackend
```

## Usage

```python
from f9_file_backend import LocalFileBackend

backend = LocalFileBackend(root="data")

# Create a file
backend.create("example.txt", data="hello world")

# Inspect a file
info = backend.info("example.txt")
print(info.as_dict())

# Read content (text or bytes)
text = backend.read("example.txt", binary=False)

# Update a file
backend.update("example.txt", data="\nnew line", append=True)

# Manage directories
backend.create("reports", is_directory=True)
backend.delete("reports", recursive=True)

# Remove a file
backend.delete("example.txt")
```

Each backend must support the `FileBackend` interface, so introducing new storage providers is as simple as adding another implementation.

## Synchronised Backends

For storage providers that support remote synchronisation, `f9_file_backend` exposes the `SyncFileBackend` interface. It extends `FileBackend` with:

- `push()` to publish local changes, optionally with a commit message
- `pull()` to fetch and merge remote updates
- `sync()` to perform a pull followed by a push
- `conflict_report()` to inspect outstanding merge conflicts
- `conflict_accept_local()`, `conflict_accept_remote()`, and `conflict_resolve()` to settle conflicts in favour of the local copy, the remote copy, or an entirely new version respectively

The synchronisation APIs raise `FileBackendError` subclasses when an operation cannot be completed (for example, attempting to push while conflicts are unresolved).

## Git Backend

The `GitSyncFileBackend` ships as the first `SyncFileBackend` implementation. It maintains a working tree backed by Git and synchronises against a remote repository over HTTPS or SSH.

```python
from f9_file_backend import GitSyncFileBackend

connection = {
    "remote_url": "git@github.com:example/private-repo.git",
    "path": "/tmp/private-repo",
    "branch": "main",
    "author_name": "Automation",
    "author_email": "automation@example.com",
    # Optional keys for private access:
    # "username": "ci-user",
    # "password": "s3cr3t",
    # "ssh_key_path": "/path/to/private_key",
    # "known_hosts": "/path/to/known_hosts",
}

backend = GitSyncFileBackend(connection)
backend.pull()  # ensure local copy is up-to-date
backend.create("reports/today.txt", data="up-to-date summary")
backend.push(message="Add daily summary")
```

When Git reports conflicts during a pull, inspect and resolve them:

```python
conflicts = backend.conflict_report()
for conflict in conflicts:
    if conflict.path.name == "summary.txt":
backend.conflict_resolve(conflict.path, data="merged content")
backend.push(message="Resolve conflicts")
```

The backend keeps repository configuration self-contained; no environment variables are required. Supply everything in the connection dictionary so the backend can authenticate to the remote independently of the surrounding process.

## OpenAI Vector Store Backend

The `OpenAIVectorStoreFileBackend` lets you persist files directly to an OpenAI
vector store. Supply your API key and the target vector store identifier:

```python
from f9_file_backend import OpenAIVectorStoreFileBackend

backend = OpenAIVectorStoreFileBackend(
    {
        "api_key": "sk-your-api-key",
        "vector_store_id": "vs_123456789",
        # Optional: cache lookups for N seconds instead of re-listing every call.
        # "cache_ttl": 5,
    },
)

backend.create("documents/welcome.txt", data="hello world")
print(backend.read("documents/welcome.txt", binary=False))
backend.delete("documents", recursive=True)
```

By default the backend refreshes its index before each operation to capture
changes made by other processes. Provide a `cache_ttl` (in seconds) to reuse the
cached index for a short period when the workload benefits from fewer list calls.

For an end-to-end validation against live OpenAI services, run
`python scripts/live_sync_test.py`. The script will prompt for the required API
credentials (or read them from `OPENAI_API_KEY` / `OPENAI_STORAGE_VAULT_ID`),
mirror the public `aethermoor` repository into your vector store, and exercise
the full `SyncFileBackend` workflow using a temporary Git remote.

## Streaming Operations

Work with large files efficiently without loading them entirely into memory:

```python
from f9_file_backend import LocalFileBackend

backend = LocalFileBackend(root="data")

# Stream read with custom chunk size
for chunk in backend.stream_read("large_file.bin", chunk_size=1024 * 64):
    process(chunk)

# Stream write from an iterator or file-like object
def content_generator():
    for i in range(1000):
        yield f"Line {i}\n"

backend.stream_write("generated.txt", chunk_source=content_generator())
```

Streaming is supported across all backends (local, Git, and OpenAI vector store).

## Checksum & Integrity Verification

Verify file integrity using checksums with multiple algorithms:

```python
from f9_file_backend import LocalFileBackend

backend = LocalFileBackend(root="data")

# Compute a file checksum (default: SHA256)
sha256_hash = backend.checksum("documents/data.json")

# Use alternative algorithms
md5_hash = backend.checksum("documents/data.json", algorithm="md5")
sha512_hash = backend.checksum("documents/data.json", algorithm="sha512")

# For BLAKE3 (requires: pip install f9-file-backend[checksum])
blake3_hash = backend.checksum("documents/data.json", algorithm="blake3")

# Batch compute checksums for multiple files
hashes = backend.checksum_many(
    ["file1.txt", "file2.txt", "file3.txt"],
    algorithm="sha256",
)
# Missing files are silently skipped
# Returns: {"file1.txt": "abc123...", "file2.txt": "def456...", ...}
```

Supported algorithms: `md5`, `sha256` (default), `sha512`, `blake3`

**Note:** BLAKE3 requires an additional dependency. Install it with:

```bash
pip install f9-file-backend[checksum]
```

All backends support checksum operations with consistent results across local filesystem, Git repositories, and OpenAI vector stores.
