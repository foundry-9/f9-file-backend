# Feature Request: Git Backend

## File support

This file backend should include everything necessary for the file backend interface support.

## Sync support

This should introduce a new interface "SyncFileBackend" based on the old one, with "push", "pull", and "sync" capabilities.

There should also probably be a way to report on sync conflicts and how to resolve them:

- conflict_report()
- conflict_accept_local()
- conflict_accept_remote()
- conflict_resolve()

The `conflict_resolve()` method should probably accept a new version of the file that supercedes both local and remote.

### Do _NOT_ use environment variables

- I want the constructor to be able to accept a dictionary with everything necessary to make a connection to a remote system (no matter what the backend is, this is generic)

## Git backend

I want an implementation of SyncFileBackend for Git syncing. It should include everything in its special specific dictionary necessary to make a connection to a private git repository (either HTTPS or SSH based).

## Documentation

We need full documentation of both the SyncFileBackend interface and the new Git backend.
