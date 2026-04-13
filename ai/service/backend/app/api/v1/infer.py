"""OCR 추론 API(동기 단건/동기 배치)."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Request, UploadFile, status

from app.api.deps import get_state, require_api_key
from app.api.engine_selector import normalize_engine_hint, resolve_local_engine_hint
from app.api.errors import api_error
from app.api.idempotency import infer_request_hash
from app.api.uploads import validate_upload
from app.api.utils import ok_response
from app.services.file_types import is_audio_content_type, resolve_content_type
from app.services.dispatch_service import DispatchRequestError
from app.services.idempotency import IdempotencyConflictError
from app.schemas.server import ServerKind
from app.services.ocr.base import OCREngineBusyError
from app.services.state import AppState

router = APIRouter(prefix="/v1", tags=["inference"])

_INFER_RESPONSE_EXAMPLE = {
    "ok": True,
    "meta": {"request_id": "ab12cd34", "timestamp": "2026-03-24T18:00:00+09:00"},
    "data": {
        "doc_id": "c8f5a8f8-8b3a-4ac2-9f3c-0d8bcf271111",
        "filename": "sample.pdf",
        "content_type": "application/pdf",
        "engine_used": "paddle",
        "confidence": 0.93,
        "raw_text": "raw extracted text",
        "corrected_text": "normalized text",
        "blocks": [],
        "domain": {
            "req_id": "c8f5a8f8-8b3a-4ac2-9f3c-0d8bcf271111",
            "title": "sample",
            "category": "notice",
            "summary": "문서의 핵심 내용을 요약한 문장",
            "raw_text": "정규화된 전체 문장",
            "tag": ["공지", "신청", "마감"],
        },
        "latency_ms": 832,
        "step_timings": {
            "preprocessing_ms": 48,
            "ocr_ms": 621,
            "postprocess_ms": 12,
            "transform_ms": 21,
        },
    },
}

_ERROR_EXAMPLE = {
    "ok": False,
    "meta": {"request_id": "ab12cd34"},
    "error": {"code": "INFER_FAILED", "message": "Unsupported file type"},
}


def _record_model_metric(state: AppState, engine_used: str, success: bool, latency_ms: int) -> None:
    # 엔진별 성능 통계를 모델 레지스트리에 누적해 라우팅/운영 지표로 사용한다.
    for model in state.model_registry.list_models():
        if model.engine == engine_used:
            state.model_registry.record(model.model_id, success=success, latency_ms=latency_ms)
            break


def _try_acquire_engine_gate(state: AppState, engine: str) -> bool:
    # 로컬 엔진 동시 실행 제한(엔진별 1개)용 게이트.
    gate = getattr(state, "engine_gate", None)
    if gate is None:
        return True
    return bool(gate.try_acquire(engine))


def _release_engine_gate(state: AppState, engine: str) -> None:
    # 예외 여부와 무관하게 게이트 해제를 보장해야 다음 요청이 진행된다.
    gate = getattr(state, "engine_gate", None)
    if gate is None:
        return
    gate.release(engine)


@router.post(
    "/infer",
    dependencies=[Depends(require_api_key)],
    responses={
        200: {"description": "Inference completed", "content": {"application/json": {"example": _INFER_RESPONSE_EXAMPLE}}},
        400: {"description": "Inference error", "content": {"application/json": {"example": _ERROR_EXAMPLE}}},
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
async def infer(
    request: Request,
    file: UploadFile = File(...),
    doc_id: str | None = Form(default=None),
    engine_hint: str | None = Form(default="auto"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    state: AppState = Depends(get_state),
):
    # dispatch가 초기화되지 않은 경우는 비정상 부팅 상태로 간주한다.
    if state.dispatch is None:
        raise api_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "DISPATCH_UNAVAILABLE", "dispatch service is unavailable")

    # 업로드를 전부 읽은 뒤 파일 정책(크기/타입/스캔)을 검증한다.
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
    req_hash = infer_request_hash(
        payload=payload,
        filename=filename,
        doc_id=doc_id,
        engine_hint=f"{active_server.server_id}|{resolved_engine}",
    )

    if idempotency_key:
        # 같은 키+같은 페이로드는 캐시 응답을 재사용해 OCR 재실행을 방지한다.
        try:
            cached = state.idempotency.get(
                route="/v1/infer",
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
            state.metrics.inc("infer_idempotent_hit_total")
            return ok_response(request, cached)

    gate_acquired = True
    if active_server.kind == ServerKind.local:
        # 로컬 엔진은 동시에 여러 추론이 겹치지 않도록 사전 점유를 시도한다.
        gate_acquired = _try_acquire_engine_gate(state, resolved_engine)
        if not gate_acquired:
            raise api_error(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "ENGINE_BUSY",
                f"{resolved_engine} inference already running",
            )
    try:
        response_data = await state.dispatch.infer(
            filename=filename,
            file_bytes=payload,
            content_type=resolved_content_type,
            engine_hint=resolved_engine,
            doc_id=doc_id,
        )
    except DispatchRequestError as exc:
        state.metrics.inc("infer_failure_total")
        raise api_error(exc.status_code, exc.code, exc.message) from exc
    except OCREngineBusyError as exc:
        raise api_error(status.HTTP_429_TOO_MANY_REQUESTS, "ENGINE_BUSY", str(exc)) from exc
    except Exception as exc:
        state.metrics.inc("infer_failure_total")
        raise api_error(status.HTTP_400_BAD_REQUEST, "INFER_FAILED", str(exc)) from exc
    finally:
        if active_server.kind == ServerKind.local and gate_acquired:
            _release_engine_gate(state, resolved_engine)

    state.metrics.inc("infer_success_total")
    engine_used = str(response_data.get("engine_used") or "")
    latency_ms = int(response_data.get("latency_ms", 0) or 0)
    if active_server.kind == ServerKind.local and engine_used:
        _record_model_metric(state, engine_used, success=True, latency_ms=latency_ms)
    if idempotency_key:
        state.idempotency.put(
            route="/v1/infer",
            key=idempotency_key,
            request_hash=req_hash,
            response_data=response_data,
        )
    # 동기 추론은 job wrapper가 없으므로 결과/감사 로그를 즉시 저장한다.
    state.persistence.insert_result(job_id=None, result_data=response_data)
    state.persistence.insert_audit(
        action="infer.sync",
        target_type="document",
        target_id=str(response_data.get("doc_id", "")),
        detail={
            "filename": response_data.get("filename"),
            "engine_used": response_data.get("engine_used"),
            "latency_ms": response_data.get("latency_ms"),
        },
    )
    return ok_response(request, response_data)


@router.post(
    "/infer/batch",
    dependencies=[Depends(require_api_key)],
    responses={
        200: {
            "description": "Batch inference completed",
            "content": {
                "application/json": {
                    "example": {
                        "ok": True,
                        "meta": {"request_id": "ab12cd34"},
                        "data": {
                            "total": 2,
                            "success": 1,
                            "failed": 1,
                            "results": [{"doc_id": "doc-1", "engine_used": "paddle"}],
                            "errors": [
                                {
                                    "index": 2,
                                    "filename": "bad.txt",
                                    "code": "INFER_FAILED",
                                    "message": "Unsupported extension: .txt",
                                }
                            ],
                        },
                    }
                }
            },
        }
    },
)
async def infer_batch(
    request: Request,
    files: list[UploadFile] = File(...),
    engine_hint: str | None = Form(default="auto"),
    state: AppState = Depends(get_state),
):
    if state.dispatch is None:
        raise api_error(status.HTTP_500_INTERNAL_SERVER_ERROR, "DISPATCH_UNAVAILABLE", "dispatch service is unavailable")

    if not files:
        raise api_error(status.HTTP_400_BAD_REQUEST, "INVALID_PAYLOAD", "No files provided")
    if len(files) > 20:
        raise api_error(status.HTTP_400_BAD_REQUEST, "INVALID_PAYLOAD", "Max 20 files per batch")

    active_server = state.dispatch.active_server()
    results: list[dict] = []
    errors: list[dict] = []
    prepared: list[tuple[int, str, str, bytes, bool]] = []

    for idx, file in enumerate(files, start=1):
        # 배치에서는 파일별 검증 실패를 누적해서 부분 성공 응답을 만든다.
        payload = await file.read()
        try:
            validate_upload(state, file, payload)
            filename = file.filename or f"upload-{idx}.bin"
            resolved_content_type = resolve_content_type(filename, file.content_type, payload)
            is_audio_upload = is_audio_content_type(resolved_content_type)
        except HTTPException as exc:
            state.metrics.inc("infer_failure_total")
            detail = exc.detail if isinstance(exc.detail, dict) else {"code": "INFER_FAILED", "message": str(exc.detail)}
            errors.append(
                {
                    "index": idx,
                    "filename": file.filename,
                    "code": str(detail.get("code", "INFER_FAILED")),
                    "message": str(detail.get("message", "Validation failed")),
                }
            )
            continue
        except Exception as exc:
            state.metrics.inc("infer_failure_total")
            errors.append(
                {
                    "index": idx,
                    "filename": file.filename,
                    "code": "INFER_FAILED",
                    "message": str(exc),
                }
            )
            continue
        prepared.append((idx, filename, resolved_content_type, payload, is_audio_upload))

    if active_server.kind == ServerKind.local:
        requires_ocr_engine = any(not is_audio for _idx, _name, _ctype, _payload, is_audio in prepared)
        local_ocr_engine = "auto"
        if requires_ocr_engine:
            try:
                local_ocr_engine = resolve_local_engine_hint(state, engine_hint)
            except RuntimeError as exc:
                raise api_error(status.HTTP_409_CONFLICT, "MODEL_NOT_READY", str(exc)) from exc
    else:
        # 원격 서버는 서버별 라우팅 정책을 따르므로 힌트만 정규화해서 전달한다.
        contains_audio = any(is_audio for _idx, _name, _ctype, _payload, is_audio in prepared)
        resolved_engine = "qwen-asr" if contains_audio else (normalize_engine_hint(engine_hint) or "auto")

    if active_server.kind != ServerKind.local:
        # 원격 서버 모드에서는 배치 전체를 upstream /v1/infer/batch로 위임한다.
        remote_files = [(filename, content_type, payload) for _idx, filename, content_type, payload, _is_audio in prepared]
        try:
            data = await state.dispatch.infer_batch(files=remote_files, engine_hint=resolved_engine)
        except DispatchRequestError as exc:
            raise api_error(exc.status_code, exc.code, exc.message) from exc
        return ok_response(request, data)

    concurrency = max(1, int(getattr(state.settings, "ocr_concurrency", 1)))
    # 로컬 배치는 세마포어로 동시 처리량을 제한해 과부하를 방지한다.
    sem = asyncio.Semaphore(concurrency)

    async def _run_one(
        idx: int,
        filename: str,
        content_type: str,
        payload: bytes,
        is_audio_upload: bool,
    ):
        async with sem:
            engine_for_file = "qwen-asr" if is_audio_upload else local_ocr_engine
            try:
                result = await state.pipeline.process_async(
                    filename=filename,
                    file_bytes=payload,
                    content_type=content_type,
                    engine_hint=engine_for_file,
                    doc_id=None,
                )
            except OCREngineBusyError as exc:
                raise RuntimeError(f"ENGINE_BUSY: {exc}") from exc
            return idx, filename, result

    outcomes = await asyncio.gather(
        *[
            _run_one(
                idx=idx,
                filename=filename,
                content_type=content_type,
                payload=payload,
                is_audio_upload=is_audio,
            )
            for idx, filename, content_type, payload, is_audio in prepared
        ],
        return_exceptions=True,
    )

    for (idx, filename, _content_type, _payload, _is_audio), outcome in zip(prepared, outcomes):
        if isinstance(outcome, Exception):
            state.metrics.inc("infer_failure_total")
            errors.append(
                {
                    "index": idx,
                    "filename": filename,
                    "code": "INFER_FAILED",
                    "message": str(outcome),
                }
            )
            continue

        _idx, _filename, result = outcome
        state.metrics.inc("infer_success_total")
        _record_model_metric(state, result.engine_used, success=True, latency_ms=result.latency_ms)
        dumped = result.model_dump()
        results.append(dumped)
        state.persistence.insert_result(job_id=None, result_data=dumped)

    return ok_response(
        request,
        {
            "total": len(files),
            "success": len(results),
            "failed": len(errors),
            "results": results,
            "errors": errors,
        },
    )
