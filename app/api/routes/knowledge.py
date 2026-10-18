from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.schemas import (
    DocumentCreate,
    DocumentResponse,
    DocumentUpdate,
    DocumentList,
    IngestResponse,
    KnowledgeStats,
)
from app.models.database import get_db
from app.services.knowledge_service import KnowledgeService

from app.core.auth import get_current_user

router = APIRouter(
    prefix="/knowledge",
    tags=["Knowledge Base"],
    dependencies=[Depends(get_current_user)],
)

def _service(db: Session) -> KnowledgeService:
    service = KnowledgeService()
    service.set_db(db)
    return service

@router.post("/documents", response_model=IngestResponse, status_code=201)
def create_document(payload: DocumentCreate, db: Session = Depends(get_db)):
    try:
        doc, chunk_count = _service(db).create_document(payload)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Indexing failed: {e}")
    return IngestResponse(
        document_id=doc.id,
        chunks_indexed=chunk_count,
        message="Document indexed successfully.",
    )

@router.get("/documents", response_model=DocumentList)
def list_documents(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    service = _service(db)
    items = service.list_documents(skip=skip, limit=limit)
    return DocumentList(items=items, total=service.count_documents())

@router.get("/stats", response_model=KnowledgeStats)
def knowledge_stats(db: Session = Depends(get_db)):
    return KnowledgeStats(**_service(db).stats())

@router.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(document_id: UUID, db: Session = Depends(get_db)):
    try:
        return _service(db).get_document(document_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.put("/documents/{document_id}", response_model=DocumentResponse)
def update_document(document_id: UUID, payload: DocumentUpdate, db: Session = Depends(get_db)):
    try:
        return _service(db).update_document(document_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Re-indexing failed: {e}")

@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: UUID, db: Session = Depends(get_db)):
    if not _service(db).delete_document(document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    # A 204 must not carry a body
    return Response(status_code=204)

@router.post("/warm", status_code=200)
def warm_index(db: Session = Depends(get_db)):
    chunks = _service(db).warm_retrieval_index()
    return {"message": "Index warmed", "chunks": chunks}
