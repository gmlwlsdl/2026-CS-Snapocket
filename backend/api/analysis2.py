import os
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.apiResponse import ApiResponse
from core.database import SessionLocal, get_db
from core.security import jwtAuth
from models.analysis_job import AnalysisJob
from models.document import Document
from services.ai_client import AIClientError, map_analysis_result, request_analysis

router = APIRouter(prefix="/analysis2", tags=["analysis2"])


class ConfirmAnalysisRequest(BaseModel):
    title: str
    category: str
    capture_date: datetime
    summary: str
    tags: list[str]


def _resolve_document_file_path(file_path: str) -> str:
    token = str(file_path or "").strip()
    if not token:
        return ""
    if os.path.isabs(token) and os.path.exists(token):
        return token

    backend_dir = os.path.dirname(os.path.dirname(__file__))
    project_dir = os.path.dirname(backend_dir)
    candidates = [
        token,
        os.path.join(os.getcwd(), token),
        os.path.join(backend_dir, token),
        os.path.join(project_dir, token),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate
    return ""


def _latest_job(db: Session, document_id: int) -> AnalysisJob | None:
    return (
        db.query(AnalysisJob)
        .filter(AnalysisJob.document_id == document_id)
        .order_by(AnalysisJob.created_at.desc(), AnalysisJob.id.desc())
        .first()
    )


def _run_analysis_job(job_id: int, document_id: int):
    db = SessionLocal()
    try:
        document = db.query(Document).filter(Document.id == document_id).first()
        job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if not document or not job:
            return

        resolved_path = _resolve_document_file_path(document.file_path)
        if not resolved_path:
            raise AIClientError("문서 파일을 찾을 수 없습니다.")

        payload = request_analysis(file_path=resolved_path, doc_id=str(document.doc_id))
        mapped = map_analysis_result(payload, fallback_doc_id=str(document.doc_id))

        job.status = "analyzed"
        job.raw_result = mapped
        job.error_message = None
        job.finished_at = datetime.now()

        document.status = "analyzed"
        document.doc_id = str(mapped.get("doc_id") or document.doc_id)
        document.raw_text = str(mapped.get("raw_text") or "")
        db.commit()
    except AIClientError as exc:
        db.rollback()
        document = db.query(Document).filter(Document.id == document_id).first()
        job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if document:
            document.status = "failed"
        if job:
            job.status = "failed"
            job.error_message = str(exc)
            job.finished_at = datetime.now()
        db.commit()
    except Exception as exc:
        db.rollback()
        document = db.query(Document).filter(Document.id == document_id).first()
        job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if document:
            document.status = "failed"
        if job:
            job.status = "failed"
            job.error_message = f"분석 처리 실패: {exc}"
            job.finished_at = datetime.now()
        db.commit()
    finally:
        db.close()


@router.post("/{document_id}/start", response_model=ApiResponse[dict])
def start_analysis(
    document_id: str,
    background_tasks: BackgroundTasks,
    jwtToken: dict = Depends(jwtAuth),
    db: Session = Depends(get_db),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "message": "문서를 찾을 수 없습니다.",
                "error_code": "DOCUMENT_NOT_FOUND",
            },
        )

    if document.status == "processing":
        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "message": "이미 분석 중인 문서입니다.",
                "error_code": "ALREADY_PROCESSING",
            },
        )

    resolved_path = _resolve_document_file_path(document.file_path)
    if not resolved_path:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "message": "문서 파일을 찾을 수 없습니다.",
                "error_code": "NOT_FOUND",
            },
        )

    if not document.doc_id:
        document.doc_id = uuid.uuid4().hex
    document.status = "processing"

    analysis_job = AnalysisJob(
        document_id=document.id,
        status="processing",
        raw_result={"doc_id": document.doc_id},
        created_at=datetime.now(),
    )
    db.add(analysis_job)
    db.commit()
    db.refresh(analysis_job)

    background_tasks.add_task(_run_analysis_job, analysis_job.id, document.id)

    return ApiResponse(
        success=True,
        message="AI 분석 시작",
        data={
            "job_id": str(analysis_job.id),
            "status": "processing",
        },
    )


@router.get("/{document_id}/status", response_model=ApiResponse[dict])
def status_analysis(document_id: str, jwtToken: dict = Depends(jwtAuth), db: Session = Depends(get_db)):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "message": "문서를 찾을 수 없습니다.",
                "error_code": "NOT_FOUND",
            },
        )

    latest_job = _latest_job(db, document.id)
    return ApiResponse(
        success=True,
        message="분석 상태 조회 성공",
        data={
            "status": document.status,
            "started_at": latest_job.created_at if latest_job else None,
            "finished_at": latest_job.finished_at if latest_job else None,
        },
    )


@router.get("/{document_id}/result", response_model=ApiResponse[dict])
def result_analysis(document_id: str, jwtToken: dict = Depends(jwtAuth), db: Session = Depends(get_db)):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "message": "문서를 찾을 수 없습니다.",
                "error_code": "NOT_FOUND",
            },
        )

    if document.status != "analyzed":
        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "message": "분석이 아직 완료되지 않았습니다.",
                "error_code": "NOT_ANALYZED_YET",
            },
        )

    latest_job = _latest_job(db, document.id)
    result = latest_job.raw_result if latest_job and isinstance(latest_job.raw_result, dict) else {}

    tags = result.get("tags") if isinstance(result.get("tags"), list) else []
    key_concepts = result.get("key_concepts") if isinstance(result.get("key_concepts"), list) else []

    return ApiResponse(
        success=True,
        message="분석 결과 조회 성공",
        data={
            "title": result.get("title") or document.title or "",
            "category": result.get("category") or document.category or "",
            "capture_date": result.get("capture_date"),
            "summary": result.get("summary") or document.summary or "",
            "tags": [str(tag) for tag in tags],
            "raw_text": result.get("raw_text") or document.raw_text or "",
            "key_concepts": [str(item) for item in key_concepts],
            "deadline": result.get("deadline"),
        },
    )


@router.post("/{document_id}/confirm", response_model=ApiResponse[dict])
def save_analysis(
    confirm: ConfirmAnalysisRequest,
    document_id: str,
    jwtToken: dict = Depends(jwtAuth),
    db: Session = Depends(get_db),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "message": "문서를 찾을 수 없습니다.",
                "error_code": "NOT_FOUND",
            },
        )

    if document.status not in {"analyzed", "saved"}:
        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "message": "분석 완료 후 저장할 수 있습니다.",
                "error_code": "NOT_ANALYZED_YET",
            },
        )

    latest_job = _latest_job(db, document.id)
    latest_result = latest_job.raw_result if latest_job and isinstance(latest_job.raw_result, dict) else {}

    document.title = confirm.title
    document.category = confirm.category
    document.capture_date = confirm.capture_date.date()
    document.summary = confirm.summary
    document.raw_text = str(latest_result.get("raw_text") or document.raw_text or "")
    document.status = "saved"

    if latest_job:
        updated_result = dict(latest_result)
        updated_result.update(
            {
                "doc_id": document.doc_id,
                "title": confirm.title,
                "category": confirm.category,
                "capture_date": confirm.capture_date.isoformat(),
                "summary": confirm.summary,
                "tags": confirm.tags,
                "raw_text": document.raw_text,
            }
        )
        latest_job.raw_result = updated_result

    db.commit()

    return ApiResponse(
        success=True,
        message="분석 결과 저장 완료",
        data={
            "document_id": str(document.id),
            "status": "saved",
        },
    )


@router.post("/{document_id}/retry", response_model=ApiResponse[dict])
def retry_analysis(
    document_id: str,
    background_tasks: BackgroundTasks,
    jwtToken: dict = Depends(jwtAuth),
    db: Session = Depends(get_db),
):
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "message": "문서를 찾을 수 없습니다.",
                "error_code": "NOT_FOUND",
            },
        )

    latest_job = _latest_job(db, document.id)
    if not latest_job:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "message": "분석 이력이 없습니다.",
                "error_code": "NOT_FOUND",
            },
        )

    if latest_job.status != "failed":
        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "message": "실패한 분석만 재시도할 수 있습니다.",
                "error_code": "NOT_FAILED_STATUS",
            },
        )

    if not document.doc_id:
        document.doc_id = uuid.uuid4().hex
    document.status = "processing"

    retry_job = AnalysisJob(
        document_id=document.id,
        status="processing",
        raw_result={"doc_id": document.doc_id},
        created_at=datetime.now(),
    )
    db.add(retry_job)
    db.commit()
    db.refresh(retry_job)

    background_tasks.add_task(_run_analysis_job, retry_job.id, document.id)

    return ApiResponse(
        success=True,
        message="분석 재시도 시작",
        data={
            "job_id": str(retry_job.id),
            "status": "processing",
        },
    )
