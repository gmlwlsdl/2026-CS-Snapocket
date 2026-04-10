from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from core.database import get_db
from models.document import Document

router = APIRouter(prefix="/documents", tags=["documents"])

@router.get("")
def read_documents(db: Session = Depends(get_db)):
    documents = db.query(Document).all()
    
    # 공통 Response 맞춰서 반환
    return {
        "success": True,
        "message": "문서 목록 조회 성공",
        "data": {
            "items": documents,
            "pagination": {
                "page": 1,
                "size": len(documents),
                "total": len(documents),
                "has_next": False
            }
        }
    }

@router.get("/{document_id}")
def get_document(document_id: str, db: Session = Depends(get_db)):
    document = db.query(Document).filter(Document.id == document_id).first()

    if not document:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "message": "문서를 찾을 수 없습니다.",
                "error_code": "DOCUMENT_NOT_FOUND"
            }
        )

    return {
        "success": True,
        "message": "문서 상세 조회 성공",
        "data": {
            "document": document
        }
    }