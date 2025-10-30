"""Test doubles used across OpenAI backend tests."""

from __future__ import annotations

import io
import time
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

from f9_file_backend.utils import coerce_to_bytes


@dataclass
class _StoredFile:
    """In-memory representation of an uploaded OpenAI file."""

    id: str
    content: bytes
    created_at: float
    filename: str
    metadata: dict[str, Any]
    purpose: str


@dataclass
class _VectorAssociation:
    """Association between a vector store and a file."""

    id: str
    file_id: str
    created_at: float


class FakeOpenAIClient:
    """Minimal OpenAI client emulation suitable for backend tests."""

    def __init__(self) -> None:
        """Initialise in-memory collections that simulate OpenAI objects."""
        self._files: dict[str, _StoredFile] = {}
        self._vector_stores: dict[str, list[_VectorAssociation]] = {}
        self._counter = 0
        self.files = _FilesAPI(self)
        self.beta = SimpleNamespace(vector_stores=_VectorStoresAPI(self))

    def _next_id(self, prefix: str) -> str:
        """Return a monotonic identifier with the provided prefix."""
        self._counter += 1
        return f"{prefix}_{self._counter:06d}"


class _FilesAPI:
    """Subset of the OpenAI Files API used by the backend."""

    def __init__(self, client: FakeOpenAIClient) -> None:
        self._client = client

    def create(
        self,
        *,
        file: Any,
        purpose: str,
        filename: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SimpleNamespace:
        """Store an uploaded file and return a lightweight descriptor."""
        content = self._coerce_bytes(file)
        file_id = self._client._next_id("file")
        record = _StoredFile(
            id=file_id,
            content=content,
            created_at=time.time(),
            filename=filename or "upload",
            metadata=dict(metadata or {}),
            purpose=purpose,
        )
        self._client._files[file_id] = record
        return SimpleNamespace(
            id=file_id,
            bytes=len(content),
            created_at=record.created_at,
            filename=record.filename,
            metadata=dict(record.metadata),
        )

    def retrieve(self, file_id: str) -> SimpleNamespace:
        """Return metadata for a stored file."""
        record = self._client._files[file_id]
        return SimpleNamespace(
            id=file_id,
            bytes=len(record.content),
            created_at=record.created_at,
            filename=record.filename,
            metadata=dict(record.metadata),
        )

    def delete(self, file_id: str) -> SimpleNamespace:
        """Delete a stored file and detach it from all vector stores."""
        removed = file_id in self._client._files
        if removed:
            del self._client._files[file_id]
            for assoc_list in self._client._vector_stores.values():
                assoc_list[:] = [
                    association
                    for association in assoc_list
                    if association.file_id != file_id
                ]
        return SimpleNamespace(id=file_id, deleted=removed)

    def content(self, file_id: str) -> io.BytesIO:
        """Return the raw content for a stored file."""
        record = self._client._files[file_id]
        return io.BytesIO(record.content)

    _coerce_bytes = staticmethod(coerce_to_bytes)


class _VectorStoresAPI:
    """Subset of the vector store API used by the backend."""

    def __init__(self, client: FakeOpenAIClient) -> None:
        self.files = _VectorStoreFilesAPI(client)


class _VectorStoreFilesAPI:
    """Vector store file management API surface."""

    def __init__(self, client: FakeOpenAIClient) -> None:
        self._client = client

    def create(
        self,
        *,
        vector_store_id: str,
        file_id: str,
    ) -> SimpleNamespace:
        """Associate a file with a vector store."""
        if file_id not in self._client._files:
            message = f"Unknown file_id {file_id}"
            raise ValueError(message)
        association = _VectorAssociation(
            id=self._client._next_id("vsf"),
            file_id=file_id,
            created_at=time.time(),
        )
        store = self._client._vector_stores.setdefault(vector_store_id, [])
        store.append(association)
        return SimpleNamespace(
            id=association.id,
            object="vector_store.file",
            file_id=file_id,
            created_at=association.created_at,
            status="completed",
        )

    def list(
        self,
        *,
        vector_store_id: str,
        limit: int = 20,
        after: str | None = None,
    ) -> SimpleNamespace:
        """List files associated with a vector store."""
        associations = self._client._vector_stores.get(vector_store_id, [])
        start = 0
        if after:
            for index, association in enumerate(associations):
                if association.id == after:
                    start = index + 1
                    break
        slice_end = start + limit
        subset = associations[start:slice_end]
        data = [
            SimpleNamespace(
                id=association.id,
                object="vector_store.file",
                file_id=association.file_id,
                status="completed",
                created_at=association.created_at,
            )
            for association in subset
        ]
        has_more = slice_end < len(associations)
        last_id = data[-1].id if data else None
        return SimpleNamespace(
            object="list",
            data=data,
            has_more=has_more,
            last_id=last_id,
        )

    def delete(
        self,
        *,
        vector_store_id: str,
        file_id: str,
    ) -> SimpleNamespace:
        """Detach a file from the vector store."""
        associations = self._client._vector_stores.get(vector_store_id, [])
        removed = False
        retained: list[_VectorAssociation] = []
        for association in associations:
            if association.file_id == file_id:
                removed = True
                continue
            retained.append(association)
        if removed:
            self._client._vector_stores[vector_store_id] = retained
        return SimpleNamespace(id=file_id, deleted=removed)
