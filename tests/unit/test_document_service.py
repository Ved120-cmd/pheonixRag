import io
import pytest

from app.application.services.document_service import DocumentService


class DummyRepo:
    def __init__(self):
        self._store = {}

    async def find_by_checksum(self, checksum):
        return None

    async def create(self, document):
        self._store[document.id] = document
        return document

    async def update(self, document):
        self._store[document.id] = document
        return document


class DummyStore:
    def __init__(self):
        self.put_calls = []

    async def put(self, file_stream, key):
        self.put_calls.append(key)

    def key_for(self, filename):
        return f"dummy/{filename}"


@pytest.mark.asyncio
async def test_register_upload_creates_and_stores(tmp_path):
    repo = DummyRepo()
    store = DummyStore()
    svc = DocumentService(repo=repo, store=store)

    content = b"hello world"
    stream = io.BytesIO(content)
    doc = await svc.register_upload(file_stream=stream, filename="a.txt", mime_type="text/plain", owner_id=None, size=len(content))

    assert doc.filename == "a.txt"
    assert doc.status == "uploaded"
    assert store.put_calls
