from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, ConfigDict
from collections import defaultdict
from sqlalchemy.sql import func
from sqlalchemy.orm import Session, joinedload
from datetime import datetime
from core.security import jwtAuth
from core.database import get_db
from models.user import User
from models.document import Document
from models.document_tag import DocumentTag
from models.tag import Tag
import uuid
from api.apiResponse import ApiResponse

router = APIRouter(prefix="/documents", tags=["documents"])

class UpdateDocuments(BaseModel):
    title: str | None = None
    category: str | None = None
    captureDate: datetime | None = None
    summary: str | None = None
    raw_text: str | None = None

class DocumentInfo(BaseModel):
    id: uuid.UUID
    doc_id: str | None = None
    title: str
    category: str
    status: str
    file_type: str
    capture_date: datetime | None = None
    created_at: datetime
    tags: list[str] = []

    model_config = ConfigDict(from_attributes=True)

class DetailedInfo(BaseModel):
    id: uuid.UUID
    doc_id: str | None = None
    title: str
    category: str
    summary: str | None = None
    raw_text: str | None = None
    status: str
    file_url: str
    file_type: str
    capture_date: datetime | None = None
    deadline: datetime | None = None
    created_at: datetime
    tags: list[str] = []

    model_config = ConfigDict(from_attributes=True)

class GetDocuments(BaseModel):
    items: list[DocumentInfo]
    pagination: dict


@router.get("", response_model=ApiResponse[GetDocuments])
def read_documents(jwtToken: dict = Depends(jwtAuth), db: Session = Depends(get_db)):

    userName = jwtToken.get("sub")
    userInfo = db.query(User).filter(User.email == userName).first()

    documents = (
        db.query(Document)
        .options(joinedload(Document.tag_objects)) 
        .filter(
            Document.user_id == userInfo.id, 
            Document.deleted_at.is_(None)
        )
        .all()
    )

    data = GetDocuments(
        items=documents,
        pagination={
            "page": 1,
            "size": len(documents),
            "total": len(documents),
            "has_next": False
        }
    )

    return ApiResponse(
        success=True,
        message="문서 목록 조회 성공",
        data=data
    )

@router.get("/{document_id}", response_model=ApiResponse[DetailedInfo])
def get_document(document_id: str, jwtToken: dict = Depends(jwtAuth), db: Session = Depends(get_db)):
    
    userName = jwtToken.get("sub")
    userInfo = db.query(User).filter(User.email == userName).first()
    
    document = (
        db.query(Document)
        .options(joinedload(Document.tag_objects))
        .filter(
            Document.id == document_id, 
            Document.user_id == userInfo.id,
            Document.deleted_at.is_(None)
        )
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "success": False,
                "message": "문서를 찾을 수 없습니다.",
                "error_code": "DOCUMENT_NOT_FOUND"
            }
        )
    

    return ApiResponse(
        success=True,
        message="문서 상세 조회 성공",
        data=document
    )

@router.patch("/{document_id}", response_model=ApiResponse[dict])
def update_document(update: UpdateDocuments, document_id: str, jwtToken: dict = Depends(jwtAuth), db: Session = Depends(get_db)):

    userName = jwtToken.get("sub")
    userInfo = db.query(User).filter(User.email == userName).first()

    document = db.query(Document).filter(
        Document.user_id == userInfo.id,
        Document.id == document_id,
        Document.deleted_at.is_(None)
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "success": False,
                "message": "문서를 찾을 수 없습니다.",
                "error_code": "DOCUMENT_NOT_FOUND"
            }
        )
    
    updateDict = update.model_dump(exclude_unset=True)
    
    for key, value in updateDict.items():
        setattr(document, key, value)

    db.commit()
    db.refresh(document)

    return ApiResponse(
        success=True,
        message="문서 수정 성공",
        data={}
    )

@router.delete("/{document_id}", response_model=ApiResponse[dict])
def delete_document(document_id: str, jwtToken: dict = Depends(jwtAuth), db: Session = Depends(get_db)):
    
    userName = jwtToken.get("sub")
    userInfo = db.query(User).filter(User.email == userName).first()

    document = db.query(Document).filter(
        Document.user_id == userInfo.id,
        Document.id == document_id,
        Document.deleted_at.is_(None)
    ).first()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "success": False,
                "message": "문서를 찾을 수 없습니다.",
                "error_code": "DOCUMENT_NOT_FOUND"
            }
        )
    
    document.deleted_at = func.now()
    db.commit()
    db.refresh(document)

    return ApiResponse(
        success=True,
        message="문서 삭제 성공",
        data={}
    )
