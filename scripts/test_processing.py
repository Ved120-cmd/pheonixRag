"""Quick script to run processing for the first document in the DB.
Usage: python -m scripts.test_processing
"""
import asyncio

from app.infrastructure.database.session import AsyncSessionLocal
from app.infrastructure.database.repositories.document_repository import SQLAlchemyDocumentRepository
from app.infrastructure.database.repositories.processing_repository import SQLAlchemyProcessingRepository
from app.infrastructure.storage.document_store import DocumentStore
from app.application.parsers.text_parser import TextParser
from app.application.services.processing_service import ProcessingService


async def main():
    async with AsyncSessionLocal() as session:
        doc_repo = SQLAlchemyDocumentRepository(session)
        proc_repo = SQLAlchemyProcessingRepository(session)
        store = DocumentStore()
        parsers = {"text": TextParser()}
        svc = ProcessingService(proc_repo, doc_repo, store, parsers)

        docs = await doc_repo.list_all(0, 1)
        if not docs:
            print("No documents found. Upload one via the API first.")
            return
        doc = docs[0]
        print(f"Processing document: {doc.id} | {doc.filename}")
        job = await svc.process_document(doc.id)
        print(
            {
                "status": job.status,
                "parser": job.parser,
                "pages": job.pages,
                "char_count": job.char_count,
                "word_count": job.word_count,
                "last_error": job.last_error,
            }
        )


if __name__ == "__main__":
    asyncio.run(main())
