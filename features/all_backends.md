# Feature Request: Multiple sync backends

The library now supports multiple backend implementations and a sync-capable
interface. Below is the current status of the ongoing rollout.

## Completed

- Implemented `SyncFileBackend` with push/pull/conflict resolution contracts.
- Delivered the Git-backed implementation (`GitSyncFileBackend`) including tests,
  configuration handling (remote URL, branch, identity), and documentation.

## Remaining

- Implement the OpenAI Vector Store backend (API key + vector store ID driven)
  and document usage.
- Add additional backends: S3, MongoDB, DynamoDB, SQL.
