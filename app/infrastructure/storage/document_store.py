from __future__ import annotations

import io
from typing import BinaryIO

from fastapi.concurrency import run_in_threadpool

from app.config.settings import get_settings
from app.infrastructure.storage.minio_client import get_minio_client

settings = get_settings()


class DocumentStore:
    def __init__(self, bucket: str | None = None) -> None:
        self._client = get_minio_client()
        self._bucket = bucket or settings.minio_bucket

    def key_for(self, filename: str, prefix: str | None = "documents") -> str:
        import uuid

        # simple namespaced key: documents/{uuid4}/{filename}
        return f"{prefix}/{uuid.uuid4()}/{filename}"

    async def put(self, file_stream: BinaryIO, key: str) -> None:
        # Minio client expects bytes-like or file-like and synchronous API.
        # We upload in a thread to avoid blocking the event loop.
        await run_in_threadpool(self._put_sync, file_stream, key)

    def _put_sync(self, file_stream: BinaryIO, key: str) -> None:
        client = self._client
        # ensure bucket exists
        try:
            if not client.bucket_exists(self._bucket):
                client.make_bucket(self._bucket)
        except Exception:
            # best-effort, avoid crash on concurrent create
            pass

        # If file_stream supports seek, get length; otherwise, buffer
        pos = None
        try:
            pos = file_stream.tell()
            file_stream.seek(0, io.SEEK_END)
            length = file_stream.tell()
            file_stream.seek(pos)
        except Exception:
            # fallback: read into memory (acceptable for modest files under configured limit)
            content = file_stream.read()
            length = len(content)
            file_stream = io.BytesIO(content)

        client.put_object(self._bucket, key, file_stream, length)

    async def get(self, key: str) -> bytes:
        return await run_in_threadpool(self._get_sync, key)

    def _get_sync(self, key: str) -> bytes:
        obj = self._client.get_object(self._bucket, key)
        try:
            return obj.read()
        finally:
            try:
                obj.close()
                obj.release_conn()
            except Exception:
                pass

    async def delete(self, key: str) -> None:
        await run_in_threadpool(self._client.remove_object, self._bucket, key)
