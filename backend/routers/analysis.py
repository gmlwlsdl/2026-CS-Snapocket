from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from core.database import get_db
from models.document import Document
from models.analysis_job import AnalysisJob

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/{document_id}/start")
def start_analysis(document_id: int, db: Session = Depends(get_db)):
    document = db.query(Document).filter(Document.id == document_id).first()

    if not document:
        return {"error": "Document not found"}

    # 🔥 AI 대신 가짜 결과 (mock)
    mock_result = {
        "title": document.title or "분석된 문서",
        "category": "lecture",  # 여기 나중에 AI가 결정
        "summary": "AI가 분석한 요약 결과입니다.",
        "tags": ["강의", "필기", "학습자료"]
    }

    # DB 업데이트
    document.title = mock_result["title"]
    document.category = mock_result["category"]
    document.summary = mock_result["summary"]
    document.status = "analyzed"

    # 분석 기록 저장
    analysis_job = AnalysisJob(
        document_id=document.id,
        status="analyzed",
        raw_result=mock_result,
        finished_at=datetime.now(),
    )

    db.add(analysis_job)
    db.commit()
    db.refresh(analysis_job)

    return {
        "message": "AI 분석 완료",
        "document_id": document.id,
        "result": mock_result,
    }