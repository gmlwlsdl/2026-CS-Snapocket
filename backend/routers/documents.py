from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from models.document import Document

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("")
def read_documents(db: Session = Depends(get_db)):
    documents = db.query(Document).all()
    return documents


@router.get("/{document_id}")
def get_document(document_id: int, db: Session = Depends(get_db)):
    document = db.query(Document).filter(Document.id == document_id).first()

    if not document:
        return {"error": "Document not found"}

    return document