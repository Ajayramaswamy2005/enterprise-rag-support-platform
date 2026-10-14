from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.models.schemas import (
    DocumentCreate,
    DocumentResponse,
    DocumentUpdate,
    DocumentList,
    IngestResponse,
)
from app.models.database import get_db
from app.services.knowledge_service import KnowledgeService

from app.core.auth import get_current_user

router = APIRouter(
    prefix="/knowledge",
    tags=["Knowledge Base"],
    dependencies=[Depends(get_current_user)],
)

@router.post("/documents", response_model=IngestResponse, status_code=201)
def create_document(payload: DocumentCreate, db: Session = Depends(get_db)):
    service = KnowledgeService()
    service.set_db(db)
    doc = service.create_document(payload)
    # Count chunks is approximate via Qdrant document_id filter would need additional query; using payload chunker
    chunk_count = len(service.chunker.split_text(payload.content))
    return IngestResponse(
        document_id=doc.id,
        chunks_indexed=chunk_count,
        message="Document indexed successfully.",
    )

@router.get("/documents", response_model=DocumentList)
def list_documents(skip: int = 0, limit: int = 50, db: Session = Depends(get_db)):
    service = KnowledgeService()
    service.set_db(db)
    items = service.list_documents(skip=skip, limit=limit)
    return DocumentList(items=items, total=len(items))

@router.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document(document_id: UUID, db: Session = Depends(get_db)):
    service = KnowledgeService()
    service.set_db(db)
    try:
        return service.get_document(document_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.put("/documents/{document_id}", response_model=DocumentResponse)
def update_document(document_id: UUID, payload: DocumentUpdate, db: Session = Depends(get_db)):
    service = KnowledgeService()
    service.set_db(db)
    try:
        return service.update_document(document_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/documents/{document_id}", status_code=204)
def delete_document(document_id: UUID, db: Session = Depends(get_db)):
    service = KnowledgeService()
    service.set_db(db)
    service.delete_document(document_id)
    return {"message": "Deleted"}

@router.post("/warm", status_code=200)
def warm_index(db: Session = Depends(get_db)):
    service = KnowledgeService()
    service.set_db(db)
    service.warm_retrieval_index()
    return {"message": "Index warmed"}
