"""외부 Snapocket 백엔드 연동용 분석 엔드포인트."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from fastapi.responses import JSONResponse

from app.api.deps import get_state, require_api_key
from app.api.engine_selector import normalize_engine_hint, resolve_local_engine_hint
from app.api.uploads import validate_upload
from app.schemas.server import ServerKind
from app.services.backend_document_mapper import map_to_backend_document_schema
from app.services.dispatch_service import DispatchRequestError
from app.services.file_types import is_audio_content_type, resolve_content_type
from app.services.ocr.base import OCREngineBusyError
from app.services.state import AppState

router = APIRouter(tags=["backend-integration"])


def _legacy_success(data: dict, message: str = "분석 완료"):
    return {"success": True, "message": message, "data": data}


def _legacy_error(*, status_code: int, error_code: str, message: str):
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "message": message,
            "error_code": error_code,
        },
    )


@router.post("/analyze", dependencies=[Depends(require_api_key)])
@router.post("/v1/backend/analyze", dependencies=[Depends(require_api_key)])
async def analyze_for_backend(
    file: UploadFile = File(...),
    doc_id: str | None = Form(default=None),
    engine_hint: str | None = Form(default="auto"),
    state: AppState = Depends(get_state),
):
    if state.dispatch is None:
        return _legacy_error(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="DISPATCH_UNAVAILABLE",
            message="dispatch service is unavailable",
        )

    payload = await file.read()
    try:
        validate_upload(state, file, payload)
    except Exception as exc:
        if hasattr(exc, "status_code") and hasattr(exc, "detail"):
            detail = exc.detail if isinstance(exc.detail, dict) else {}
            return _legacy_error(
                status_code=int(exc.status_code),
                error_code=str(detail.get("code") or "INVALID_PAYLOAD"),
                message=str(detail.get("message") or "invalid payload"),
            )
        return _legacy_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="INVALID_PAYLOAD",
            message=str(exc),
        )

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
                return _legacy_error(
                    status_code=status.HTTP_409_CONFLICT,
                    error_code="MODEL_NOT_READY",
                    message=str(exc),
                )
    else:
        resolved_engine = "qwen-asr" if is_audio_upload else (normalize_engine_hint(engine_hint) or "auto")

    try:
        response_data = await state.dispatch.infer(
            filename=filename,
            file_bytes=payload,
            content_type=resolved_content_type,
            engine_hint=resolved_engine,
            doc_id=doc_id,
        )
    except DispatchRequestError as exc:
        return _legacy_error(
            status_code=int(exc.status_code),
            error_code=str(exc.code),
            message=str(exc.message),
        )
    except OCREngineBusyError as exc:
        return _legacy_error(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            error_code="ENGINE_BUSY",
            message=str(exc),
        )
    except Exception as exc:
        return _legacy_error(
            status_code=status.HTTP_400_BAD_REQUEST,
            error_code="INFER_FAILED",
            message=str(exc),
        )

    mapped = map_to_backend_document_schema(
        response_data,
        fallback_doc_id=doc_id,
    )
    state.persistence.insert_result(job_id=None, result_data=response_data)
    state.persistence.insert_audit(
        action="infer.backend",
        target_type="document",
        target_id=str(mapped.get("doc_id") or ""),
        detail={
            "filename": filename,
            "content_type": resolved_content_type,
            "engine_used": response_data.get("engine_used"),
        },
    )
    return _legacy_success(mapped)
