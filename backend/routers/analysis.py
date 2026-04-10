from datetime import datetime
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from core.database import get_db
from models.document import Document
from models.analysis_job import AnalysisJob

router = APIRouter(prefix="/analysis", tags=["analysis"])

@router.post("/{document_id}/start")
def start_analysis(document_id: str, db: Session = Depends(get_db)):
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

    mock_result = {
        "title": document.title or "분석된 문서",
        "category": "lecture",
        "summary": "AI가 분석한 요약 결과입니다.",
        "tags": ["강의", "필기", "학습자료"]
    }

    document.status = "processing"

    analysis_job = AnalysisJob(
        document_id=document.id,
        status="processing", 
        raw_result=mock_result,
        started_at=datetime.now(),
    )

    db.add(analysis_job)
    db.commit()
    db.refresh(analysis_job)

    return {
        "success": True,
        "message": "AI 분석 시작",
        "data": {
            "job_id": str(analysis_job.id),
            "status": "processing"
        }
    }