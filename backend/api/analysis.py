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
from models.user import User
from services.ai_client import AIClientError, map_analysis_result, request_analysis
from services.graph_builder import refresh_document_edges
from services.semantic_search import (
    SemanticSearchError,
    serialize_document_for_index,
    sync_semantic_documents,
)

# 분석 API 라우터 (/analysis/*)
router = APIRouter(prefix="/analysis", tags=["analysis"])


# 사용자가 분석 결과를 확정 저장할 때 전달하는 본문 스키마
class ConfirmAnalysisRequest(BaseModel):
    title: str
    category: str
    capture_date: datetime
    summary: str
    tags: list[str]


def _resolve_document_file_path(file_path: str) -> str:
    # DB에 저장된 상대/절대 경로를 실제 파일 경로로 해석한다.
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
    # 문서별 최신 분석 Job 1건 조회
    return (
        db.query(AnalysisJob)
        .filter(AnalysisJob.document_id == document_id)
        .order_by(AnalysisJob.created_at.desc(), AnalysisJob.id.desc())
        .first()
    )


def _run_analysis_job(job_id: int, document_id: int):
    # 백그라운드에서 실제 AI 서버를 호출하고 결과를 반영한다.
    db = SessionLocal()
    try:
        job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if not job:
            return
        document = (
            db.query(Document)
            .filter(
                Document.id == document_id,
                Document.deleted_at.is_(None),
            )
            .first()
        )
        if not document:
            job.status = "failed"
            job.error_message = "문서를 찾을 수 없습니다."
            job.finished_at = datetime.now()
            db.commit()
            return

        # 분석 대상 파일 존재 확인
        resolved_path = _resolve_document_file_path(document.file_path)
        if not resolved_path:
            raise AIClientError("문서 파일을 찾을 수 없습니다.")

        if not document.doc_id:
            document.doc_id = uuid.uuid4().hex
            db.commit()

        backend_doc_id = str(document.doc_id)

        # AI 서버 분석 요청 및 응답 도메인 매핑
        payload = request_analysis(file_path=resolved_path, doc_id=backend_doc_id)
        mapped = map_analysis_result(payload, fallback_doc_id=backend_doc_id)
        mapped["doc_id"] = backend_doc_id

        # 성공 상태 반영
        job.status = "analyzed"
        job.raw_result = mapped
        job.error_message = None
        job.finished_at = datetime.now()

        document.status = "analyzed"
        document.doc_id = backend_doc_id
        document.raw_text = str(mapped.get("raw_text") or "")
        db.commit()
        db.refresh(document)
        try:
            sync_semantic_documents(
                user_id=str(document.user_id),
                documents=[serialize_document_for_index(document, user_id=str(document.user_id))],
                deleted_document_ids=[],
            )
        except SemanticSearchError:
            pass
        try:
            refresh_document_edges(
                db=db,
                document_id=str(document.id),
                user_id=str(document.user_id),
            )
        except Exception:
            db.rollback()
    except AIClientError as exc:
        # 예상 가능한 AI 통신/응답 오류
        db.rollback()
        document = (
            db.query(Document)
            .filter(
                Document.id == document_id,
                Document.deleted_at.is_(None),
            )
            .first()
        )
        job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if document:
            document.status = "failed"
        if job:
            job.status = "failed"
            job.error_message = str(exc)
            job.finished_at = datetime.now()
        db.commit()
    except Exception as exc:
        # 그 외 예외도 failed로 처리해 상태 일관성을 유지한다.
        db.rollback()
        document = (
            db.query(Document)
            .filter(
                Document.id == document_id,
                Document.deleted_at.is_(None),
            )
            .first()
        )
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
    # 분석 시작: 문서/파일 검증 -> Job 생성 -> 백그라운드 실행
    user_name = jwtToken.get("sub")
    user_info = db.query(User).filter(User.email == user_name).first()
    if not user_info:
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "message": "유효하지 않은 사용자입니다.",
                "error_code": "UNAUTHORIZED",
            },
        )
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.user_id == user_info.id,
            Document.deleted_at.is_(None),
        )
        .first()
    )
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
def status_analysis(
    document_id: str,
    jwtToken: dict = Depends(jwtAuth),
    db: Session = Depends(get_db),
):
    # 최신 Job 기준으로 분석 진행 상태와 시작/종료 시각을 반환
    user_name = jwtToken.get("sub")
    user_info = db.query(User).filter(User.email == user_name).first()
    if not user_info:
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "message": "유효하지 않은 사용자입니다.",
                "error_code": "UNAUTHORIZED",
            },
        )
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.user_id == user_info.id,
            Document.deleted_at.is_(None),
        )
        .first()
    )
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
def result_analysis(
    document_id: str,
    jwtToken: dict = Depends(jwtAuth),
    db: Session = Depends(get_db),
):
    # 분석 완료 문서의 최신 결과를 반환
    user_name = jwtToken.get("sub")
    user_info = db.query(User).filter(User.email == user_name).first()
    if not user_info:
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "message": "유효하지 않은 사용자입니다.",
                "error_code": "UNAUTHORIZED",
            },
        )
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.user_id == user_info.id,
            Document.deleted_at.is_(None),
        )
        .first()
    )
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

    # 리스트 타입 필드 방어적 파싱
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
    # 사용자 수정값으로 분석 결과를 확정 저장
    user_name = jwtToken.get("sub")
    user_info = db.query(User).filter(User.email == user_name).first()
    if not user_info:
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "message": "유효하지 않은 사용자입니다.",
                "error_code": "UNAUTHORIZED",
            },
        )
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.user_id == user_info.id,
            Document.deleted_at.is_(None),
        )
        .first()
    )
    if not document:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "message": "문서를 찾을 수 없습니다.",
                "error_code": "NOT_FOUND",
            },
        )

    if document.status not in {"analyzed"}:
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

    # 문서 메인 필드 저장
    document.title = confirm.title
    document.category = confirm.category
    document.capture_date = confirm.capture_date.date()
    document.summary = confirm.summary
    document.raw_text = str(latest_result.get("raw_text") or document.raw_text or "")
    document.status = "analyzed"

    # 최신 Job의 raw_result도 저장 데이터 기준으로 동기화
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
    db.refresh(document)
    try:
        sync_semantic_documents(
            user_id=str(user_info.id),
            documents=[serialize_document_for_index(document, user_id=str(user_info.id))],
            deleted_document_ids=[],
        )
    except SemanticSearchError:
        pass
    try:
        refresh_document_edges(
            db=db,
            document_id=str(document.id),
            user_id=str(user_info.id),
        )
    except Exception:
        db.rollback()

    return ApiResponse(
        success=True,
        message="분석 결과 저장 완료",
        data={
            "document_id": str(document.id),
            "status": "analyzed",
        },
    )


@router.post("/{document_id}/retry", response_model=ApiResponse[dict])
def retry_analysis(
    document_id: str,
    background_tasks: BackgroundTasks,
    jwtToken: dict = Depends(jwtAuth),
    db: Session = Depends(get_db),
):
    # 최신 분석 Job 기준으로 재분석을 시작한다.
    user_name = jwtToken.get("sub")
    user_info = db.query(User).filter(User.email == user_name).first()
    if not user_info:
        return JSONResponse(
            status_code=401,
            content={
                "success": False,
                "message": "유효하지 않은 사용자입니다.",
                "error_code": "UNAUTHORIZED",
            },
        )
    document = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.user_id == user_info.id,
            Document.deleted_at.is_(None),
        )
        .first()
    )
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

    if latest_job.status == "processing" or document.status == "processing":
        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "message": "이미 분석 중인 문서입니다.",
                "error_code": "ALREADY_PROCESSING",
            },
        )

    if latest_job.status not in {"analyzed", "failed"}:
        return JSONResponse(
            status_code=409,
            content={
                "success": False,
                "message": "분석 완료 또는 실패 상태에서만 재시도할 수 있습니다.",
                "error_code": "NOT_RETRYABLE_STATUS",
            },
        )

    # 재시도 Job 생성 후 동일 백그라운드 러너에 위임
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
