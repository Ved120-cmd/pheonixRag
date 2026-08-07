from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Query
from fastapi import status
from typing import List

from app.api.dependencies.auth import get_current_user
from app.api.dependencies.services import get_document_service
from app.application.services.document_service import DocumentService
from app.domain.entities.user import User
from app.schemas.document import DocumentResponse, UploadResponse, ListDocumentsResponse

router = APIRouter()


@router.post("", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    document_service: DocumentService = Depends(get_document_service),
):
    # Basic validation: content-type and size checked in service
    if file.content_type not in ("application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "text/plain", "text/markdown"):
        raise HTTPException(status_code=400, detail="unsupported file type")

    content = await file.read()
    import io

    stream = io.BytesIO(content)
    doc = await document_service.register_upload(
        file_stream=stream,
        filename=file.filename,
        mime_type=file.content_type,
        owner_id=user.id,
        size=len(content),
    )
    return UploadResponse(id=doc.id, status=doc.status)


@router.get("", response_model=ListDocumentsResponse)
async def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    document_service: DocumentService = Depends(get_document_service),
):
    items = await document_service.list(skip=skip, limit=limit)
    return ListDocumentsResponse(items=[DocumentResponse(**d.__dict__) for d in items], total=len(items))


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str, document_service: DocumentService = Depends(get_document_service)):
    from uuid import UUID

    try:
        did = UUID(document_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid id")
    doc = await document_service.get(did)
    if not doc:
        raise HTTPException(status_code=404, detail="not found")
    return DocumentResponse(**doc.__dict__)


@router.delete("/{document_id}")
async def delete_document(document_id: str, document_service: DocumentService = Depends(get_document_service)):
    from uuid import UUID

    try:
        did = UUID(document_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid id")
    await document_service.soft_delete(did)
    return {"message": "deleted"}


@router.post("/{document_id}/restore")
async def restore_document(document_id: str, document_service: DocumentService = Depends(get_document_service)):
    from uuid import UUID

    try:
        did = UUID(document_id)
    except Exception:
        raise HTTPException(status_code=400, detail="invalid id")
    await document_service.restore(did)
    return {"message": "restored"}
