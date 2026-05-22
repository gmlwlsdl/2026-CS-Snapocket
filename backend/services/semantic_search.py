import json
import logging
import time
from datetime import datetime, timezone
from urllib import error as urlerror
from urllib import request as urlrequest
from urllib.parse import urlparse, urlunparse

from core.database import SessionLocal
from core.config import AI_SERVER_API_KEY, AI_SERVER_TIMEOUT_S, AI_SERVER_URL
from models.document import Document

logger = logging.getLogger(__name__)


class SemanticSearchError(RuntimeError):
    pass


_HEALTH_CACHE_TTL_S = 10.0
_health_cache: dict[str, object] = {"expires_at": 0.0, "value": None}


def _normalize_ai_server_base_url(raw_url: str) -> str:
    token = str(raw_url or "").strip()
    if not token:
        raise SemanticSearchError("AI_SERVER_URL이 설정되지 않았습니다.")

    parsed = urlparse(token)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SemanticSearchError("AI_SERVER_URL 형식이 올바르지 않습니다.")

    return urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))


def _extract_error_message(raw: str, fallback: str) -> str:
    try:
        payload = json.loads(raw) if raw else {}
    except Exception:
        return raw or fallback

    if not isinstance(payload, dict):
        return raw or fallback

    detail = payload.get("detail")
    if isinstance(detail, dict):
        return str(detail.get("message") or detail.get("error_code") or fallback)
    if isinstance(detail, str) and detail.strip():
        return detail

    error = payload.get("error")
    if isinstance(error, dict):
        return str(error.get("message") or fallback)
    if isinstance(error, str) and error.strip():
        return error

    message = payload.get("message")
    if isinstance(message, str) and message.strip():
        return message
    return raw or fallback


def _request_json(*, path: str, method: str = "GET", payload: dict | list | None = None) -> dict:
    base_url = _normalize_ai_server_base_url(AI_SERVER_URL)
    headers = {"Accept": "application/json"}
    if AI_SERVER_API_KEY:
        headers["x-api-key"] = AI_SERVER_API_KEY

    body = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(payload).encode("utf-8")

    req = urlrequest.Request(url=f"{base_url}{path}", method=method, data=body, headers=headers)
    try:
        with urlrequest.urlopen(req, timeout=AI_SERVER_TIMEOUT_S) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urlerror.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace") if exc.fp is not None else ""
        fallback = f"AI server request failed (HTTP {exc.code})"
        raise SemanticSearchError(_extract_error_message(detail, fallback)) from exc
    except urlerror.URLError as exc:
        raise SemanticSearchError(f"AI server connection failed: {exc.reason}") from exc
    except TimeoutError as exc:
        raise SemanticSearchError(f"AI server request timed out after {AI_SERVER_TIMEOUT_S}s") from exc

    try:
        payload = json.loads(raw) if raw else {}
    except Exception as exc:
        raise SemanticSearchError("AI 서버 응답 파싱 실패") from exc

    if not isinstance(payload, dict):
        raise SemanticSearchError("AI 서버 응답 형식이 올바르지 않습니다.")
    return payload


def _unwrap_ok_response(payload: dict) -> dict:
    if "ok" in payload:
        if not bool(payload.get("ok")):
            error = payload.get("error")
            if isinstance(error, dict):
                raise SemanticSearchError(str(error.get("message") or "semantic request failed"))
            raise SemanticSearchError("semantic request failed")
        data = payload.get("data")
        return data if isinstance(data, dict) else {}
    return payload


def _serialize_datetime(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.isoformat()


def _normalize_datetime_token(value: str | None) -> datetime | None:
    token = str(value or "").strip()
    if not token:
        return None

    normalized = token.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)
    return parsed.replace(microsecond=0)


def _is_same_updated_at(indexed_value: str | None, db_value: datetime | None) -> bool:
    indexed_dt = _normalize_datetime_token(indexed_value)
    db_dt = _normalize_datetime_token(_serialize_datetime(db_value))
    if indexed_dt is None or db_dt is None:
        return not indexed_value and db_value is None
    return indexed_dt == db_dt


def ai_search_status(*, force_refresh: bool = False) -> dict:
    # 상태 조회는 검색 입력 중 자주 호출될 수 있어 짧은 TTL 캐시를 둔다.
    now = time.monotonic()
    if not force_refresh and now < float(_health_cache.get("expires_at") or 0):
        cached = _health_cache.get("value")
        if isinstance(cached, dict):
            return cached

    try:
        live = _request_json(path="/health/live", method="GET")
        live_ok = bool(live.get("ok"))
    except SemanticSearchError as exc:
        result = {
            "available": False,
            "live": False,
            "reason": str(exc),
        }
        _health_cache.update({"expires_at": now + _HEALTH_CACHE_TTL_S, "value": result})
        return result

    try:
        detail = _unwrap_ok_response(_request_json(path="/v1/search/status", method="GET"))
        available = bool(detail.get("available"))
        reason = str(detail.get("error") or "")
    except SemanticSearchError as exc:
        detail = {}
        available = False
        reason = str(exc)

    result = {
        "available": live_ok and available,
        "live": live_ok,
        "reason": reason,
        "detail": detail,
    }
    _health_cache.update({"expires_at": now + _HEALTH_CACHE_TTL_S, "value": result})
    return result


def sync_semantic_documents(*, user_id: str, documents: list[dict], deleted_document_ids: list[str]) -> dict:
    payload = {
        "user_id": user_id,
        "documents": documents,
        "deleted_document_ids": deleted_document_ids,
    }
    return _unwrap_ok_response(_request_json(path="/v1/search/sync", method="POST", payload=payload))


def upsert_semantic_documents(documents: list[dict]) -> dict:
    return _unwrap_ok_response(_request_json(path="/v1/search/upsert", method="POST", payload=documents))


def delete_semantic_documents(*, document_ids: list[str], user_id: str | None = None) -> dict:
    payload = {"document_ids": document_ids, "user_id": user_id}
    return _unwrap_ok_response(_request_json(path="/v1/search/delete", method="POST", payload=payload))


def search_semantic_documents(*, query: str, user_id: str, limit: int = 10) -> list[dict]:
    payload = {"query": query, "user_id": user_id, "limit": limit}
    data = _unwrap_ok_response(_request_json(path="/v1/search/semantic", method="POST", payload=payload))
    items = data.get("items")
    return items if isinstance(items, list) else []


def request_graph_links(payload: dict) -> dict:
    return _unwrap_ok_response(_request_json(path="/v1/graph/link", method="POST", payload=payload))


def request_graph_links_batch(payload: dict) -> dict:
    return _unwrap_ok_response(_request_json(path="/v1/graph/link/batch", method="POST", payload=payload))


def list_semantic_documents(*, user_id: str) -> list[dict]:
    payload = {"user_id": user_id}
    data = _unwrap_ok_response(_request_json(path="/v1/search/index-state", method="POST", payload=payload))
    items = data.get("items")
    return items if isinstance(items, list) else []


def serialize_document_for_index(document, *, user_id: str) -> dict:
    # 현재 PRD 범위에서는 raw_text와 updated_at만 올려도 정합성 검증이 가능하다.
    return {
        "document_id": str(document.id),
        "user_id": str(user_id),
        "updated_at": _serialize_datetime(getattr(document, "updated_at", None)),
        "raw_text": str(getattr(document, "raw_text", "") or ""),
    }


def reconcile_semantic_replica_for_user(*, user_id: str) -> dict[str, int]:
    # 로그인 직후 1회 수행되는 레플리카 점검 로직:
    # MySQL 원본과 Qdrant 메타데이터를 비교해 차이 나는 문서만 재임베딩한다.
    db = SessionLocal()
    try:
        documents = db.query(Document).filter(Document.user_id == user_id).all()
        indexed_items = list_semantic_documents(user_id=user_id)
        indexed_by_id = {
            str(item.get("document_id") or ""): str(item.get("updated_at") or "")
            for item in indexed_items
            if str(item.get("document_id") or "").strip()
        }

        active_documents = {
            str(document.id): document
            for document in documents
            if document.deleted_at is None
        }
        stale_or_missing_documents = [
            document
            for document_id, document in active_documents.items()
            if not _is_same_updated_at(indexed_by_id.get(document_id), document.updated_at)
        ]
        deleted_doc_ids = [
            document_id
            for document_id in indexed_by_id
            if document_id not in active_documents
        ]

        if not stale_or_missing_documents and not deleted_doc_ids:
            return {"upserted": 0, "deleted": 0}

        return sync_semantic_documents(
            user_id=user_id,
            documents=[
                serialize_document_for_index(document, user_id=user_id)
                for document in stale_or_missing_documents
            ],
            deleted_document_ids=deleted_doc_ids,
        )
    except Exception as exc:
        logger.exception("Semantic replica reconciliation failed for user %s: %s", user_id, exc)
        raise
    finally:
        db.close()
