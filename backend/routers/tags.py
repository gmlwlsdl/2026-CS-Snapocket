from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from models.tag import Tag
from models.document_tag import DocumentTag

router = APIRouter(tags=["tags"])


@router.get("/tags")
def get_tags(db: Session = Depends(get_db)):
    tags = db.query(Tag).all()
    return tags


@router.get("/documents/{document_id}/tags")
def get_document_tags(document_id: int, db: Session = Depends(get_db)):
    tags = (
        db.query(Tag)
        .join(DocumentTag, Tag.id == DocumentTag.tag_id)
        .filter(DocumentTag.document_id == document_id)
        .all()
    )
    return tags
