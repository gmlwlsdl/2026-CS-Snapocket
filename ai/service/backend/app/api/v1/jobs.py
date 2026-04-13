"""OCR 비동기 작업(Job) API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Header, Request, UploadFile, status

from app.api.deps import get_state, require_api_key
from app.api.engine_selector import normalize_engine_hint, resolve_local_engine_hint
from app.api.errors import api_error
from app.api.idempotency import job_request_hash
from app.api.uploads import validate_upload
from app.api.utils import ok_response
from app.services.file_types import is_audio_content_type, resolve_content_type
from app.schemas.job import JobStatus
from app.schemas.server import ServerKind
from app.services.dispatch_service import DispatchRequestError
from app.services.idempotency import IdempotencyConflictError
from app.services.state import AppState

router = APIRouter(prefix="/v1", tags=["jobs"])

_CREATE_JOB_RESPONSE_EXAMPLE = {
    "ok": True,
    "meta": {"request_id": "ab12cd34"},
    "data": {"job_id": "7d824500-5218-4055-a8c4-f7aedb8c5edc"},
}


@router.post(
    "/jobs",
    dependencies=[Depends(require_api_key)],
    responses={
        200: {"description": "Job created", "content": {"application/json": {"example": _CREATE_JOB_RESPONSE_EXAMPLE}}},
        409: {
            "description": "Idempotency conflict",
            "content": {
                "application/json": {
                    "example": {
                        "ok": False,
                        "meta": {"request_id": "ab12cd34"},
                        "error": {
                            "code": "IDEMPOTENCY_CONFLICT",
                            "message": "idempotency key reused with different payload",
                        },
                    }
                }
            },
        },
    },
)
async def create_job(
    request: Request,
    file: UploadFile = File(...),
    doc_id: str | None = Form(default=None),
    engine_hint: str | None = Form(default="auto"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    state: AppState = Depends(get_state),
):
    # dispatch 미초기화는 서비스 준비 실패 상태로 처리한다.
    if state.dispatch is None:
        raise api_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "DISPATCH_UNAVAILABLE", "dispatch service is unavailable")

    # 파일 정책 검증을 먼저 통과해야 큐에 작업을 넣을 수 있다.
    payload = await file.read()
    validate_upload(state, file, payload)
    filename = file.filename or "upload.bin"
    resolved_content_type = resolve_content_type(filename, file.content_type, payload)
    is_audio_upload = is_audio_content_type(resolved_content_type)
    active_server = state.dispatch.active_server()
    if active_server.kind == ServerKind.local:
        if is_audio_upload:
            resolved_engine = "qwen-asr"
        else:
            try:
                resolved_engine = resolve_local_engine_hint(state, engine_hint)
            except RuntimeError as exc:
                raise api_error(status.HTTP_409_CONFLICT, "MODEL_NOT_READY", str(exc)) from exc
    else:
        # 원격 서버는 서버별 라우팅 정책을 따르므로 힌트만 정규화해서 전달한다.
        resolved_engine = "qwen-asr" if is_audio_upload else (normalize_engine_hint(engine_hint) or "auto")

    req_hash = job_request_hash(
        payload=payload,
        filename=filename,
        doc_id=doc_id,
        engine_hint=f"{active_server.server_id}|{resolved_engine}",
    )
    if idempotency_key:
        # 같은 키+같은 요청이면 기존 job_id를 반환해 중복 큐잉을 방지한다.
        try:
            cached = state.idempotency.get(
                route="/v1/jobs",
                key=idempotency_key,
                request_hash=req_hash,
            )
        except IdempotencyConflictError as exc:
            raise api_error(
                status.HTTP_409_CONFLICT,
                "IDEMPOTENCY_CONFLICT",
                str(exc),
            ) from exc
        if cached is not None:
            state.metrics.inc("jobs_idempotent_hit_total")
            return ok_response(request, cached)

    try:
        # 활성 서버(local/remote) 정책에 맞춰 dispatch 계층이 실제 작업을 생성한다.
        job_id = state.dispatch.create_job(
            filename=filename,
            file_bytes=payload,
            content_type=resolved_content_type,
            engine_hint=resolved_engine,
            doc_id=doc_id,
        )
    except DispatchRequestError as exc:
        raise api_error(exc.status_code, exc.code, exc.message) from exc

    response_data = {"job_id": job_id}
    if idempotency_key:
        state.idempotency.put(
            route="/v1/jobs",
            key=idempotency_key,
            request_hash=req_hash,
            response_data=response_data,
        )
    state.persistence.insert_audit(
        action="job.create",
        target_type="job",
        target_id=job_id,
        detail={"filename": filename, "engine_hint": resolved_engine},
    )
    return ok_response(request, response_data)


@router.get("/jobs", dependencies=[Depends(require_api_key)])
def list_jobs(request: Request, state: AppState = Depends(get_state)):
    # 목록/조회/결과 API는 dispatch가 local/remote 차이를 숨겨 동일 인터페이스로 제공한다.
    if state.dispatch is None:
        raise api_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "DISPATCH_UNAVAILABLE", "dispatch service is unavailable")
    try:
        jobs = state.dispatch.list_jobs()
    except DispatchRequestError as exc:
        raise api_error(exc.status_code, exc.code, exc.message) from exc
    return ok_response(request, jobs)


@router.get("/jobs/{job_id}", dependencies=[Depends(require_api_key)])
def get_job(job_id: str, request: Request, state: AppState = Depends(get_state)):
    if state.dispatch is None:
        raise api_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "DISPATCH_UNAVAILABLE", "dispatch service is unavailable")
    try:
        info = state.dispatch.get_job(job_id=job_id)
    except KeyError as exc:
        raise api_error(status.HTTP_404_NOT_FOUND, "JOB_NOT_FOUND", "Job not found") from exc
    except DispatchRequestError as exc:
        raise api_error(exc.status_code, exc.code, exc.message) from exc
    return ok_response(request, info)


@router.get("/jobs/{job_id}/result", dependencies=[Depends(require_api_key)])
def get_job_result(job_id: str, request: Request, state: AppState = Depends(get_state)):
    if state.dispatch is None:
        raise api_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "DISPATCH_UNAVAILABLE", "dispatch service is unavailable")
    try:
        payload = state.dispatch.get_job_result(job_id=job_id)
    except KeyError as exc:
        raise api_error(status.HTTP_404_NOT_FOUND, "JOB_NOT_FOUND", "Job not found") from exc
    except DispatchRequestError as exc:
        raise api_error(exc.status_code, exc.code, exc.message) from exc
    return ok_response(request, payload)


@router.post("/jobs/{job_id}/cancel", dependencies=[Depends(require_api_key)])
def cancel_job(job_id: str, request: Request, state: AppState = Depends(get_state)):
    if state.dispatch is None:
        raise api_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "DISPATCH_UNAVAILABLE", "dispatch service is unavailable")
    try:
        cancelled = state.dispatch.cancel_job(job_id=job_id)
    except KeyError as exc:
        raise api_error(status.HTTP_404_NOT_FOUND, "JOB_NOT_FOUND", "Job not found") from exc
    except DispatchRequestError as exc:
        raise api_error(exc.status_code, exc.code, exc.message) from exc

    if not cancelled:
        # 이미 종료된 상태 등으로 취소 불가인 경우 현재 상태를 반환해 원인을 명확히 한다.
        try:
            info = state.dispatch.get_job(job_id=job_id)
            status_value = info.get("status")
        except Exception:
            status_value = "unknown"
        if status_value in {JobStatus.running.value, JobStatus.succeeded.value, JobStatus.failed.value}:
            raise api_error(status.HTTP_409_CONFLICT, "JOB_NOT_CANCELLABLE", f"Job status is {status_value}")

    state.persistence.insert_audit(
        action="job.cancel",
        target_type="job",
        target_id=job_id,
        detail={"cancelled": cancelled},
    )
    return ok_response(request, {"job_id": job_id, "cancelled": cancelled})


@router.post("/jobs/{job_id}/retry", dependencies=[Depends(require_api_key)])
def retry_job(job_id: str, request: Request, state: AppState = Depends(get_state)):
    if state.dispatch is None:
        raise api_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "DISPATCH_UNAVAILABLE", "dispatch service is unavailable")
    try:
        info = state.dispatch.get_job(job_id=job_id)
        # 실패/취소 상태에서만 재시도를 허용한다.
        status_value = str(info.get("status") or "")
        if status_value not in {JobStatus.failed.value, JobStatus.cancelled.value}:
            raise api_error(
                status.HTTP_409_CONFLICT,
                "JOB_NOT_RETRIABLE",
                f"Job status is {status_value}",
            )
        new_job_id = state.dispatch.retry_job(job_id=job_id)
    except KeyError as exc:
        raise api_error(status.HTTP_404_NOT_FOUND, "JOB_NOT_FOUND", "Job not found") from exc
    except DispatchRequestError as exc:
        raise api_error(exc.status_code, exc.code, exc.message) from exc
    state.persistence.insert_audit(
        action="job.retry",
        target_type="job",
        target_id=job_id,
        detail={"retry_job_id": new_job_id},
    )
    return ok_response(request, {"job_id": job_id, "retry_job_id": new_job_id})
