from datetime import datetime
import uuid
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from core.security import jwtAuth
from core.database import get_db
from models.document import Document
from models.analysis_job import AnalysisJob
from api.apiResponse import ApiResponse

router = APIRouter(prefix="/analysis", tags=["analysis"])

@router.post("/{document_id}/start", response_model=ApiResponse[dict])
def start_analysis(document_id: str, jwtToken: dict = Depends(jwtAuth), db: Session = Depends(get_db)):
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

    request_doc_id = document.doc_id or uuid.uuid4().hex
    raw_text = (
        "AI가 분석한 전체 문장입니다. 실제 연동 시에는 OCR/ASR이 추출한 전문 텍스트가 저장됩니다."
    )

    mock_result = {
        "doc_id": request_doc_id,
        "title": document.title or "분석된 문서",
        "category": "lecture",
        "summary": "AI가 분석한 요약 결과입니다.",
        "raw_text": raw_text,
        "tags": ["강의", "필기", "학습자료"]
    }

    document.doc_id = request_doc_id
    document.raw_text = raw_text
    document.status = "processing"

    analysis_job = AnalysisJob(
        document_id=document.id,
        status="processing", 
        raw_result=mock_result,
        created_at=datetime.now(),
    )

    db.add(analysis_job)
    db.commit()
    db.refresh(analysis_job)

    return ApiResponse(
        success=True,
        message="AI 분석 시작",
        data={
            "job_id": str(analysis_job.id),
            "status": "processing"
        }
    )

@router.get("/{document_id}/status", response_model=ApiResponse[dict])
def status_analysis(jwtToken: dict = Depends(jwtAuth), db: Session = Depends(get_db)):

    return ApiResponse(
        success=True,
        message="",
        data={}
    )

@router.get("/{document_id}/result", response_model=ApiResponse[dict])
def result_analysis(jwtToken: dict = Depends(jwtAuth), db: Session = Depends(get_db)):

    return ApiResponse(
        success=True,
        message="",
        data={}
    )

@router.post("/{document_id}/confirm", response_model=ApiResponse[dict])
def save_analysis(jwtToken: dict = Depends(jwtAuth), db: Session = Depends(get_db)):

    return ApiResponse(
        success=True,
        message="",
        data={}
    )

@router.post("/{document_id}/retry", response_model=ApiResponse[dict])
def retry_analysis(jwtToken: dict = Depends(jwtAuth), db: Session = Depends(get_db)):

    return ApiResponse(
        success=True,
        message="",
        data={}
    )
