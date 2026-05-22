import json
import mimetypes
import os
import uuid
from urllib import error as urlerror
from urllib import request as urlrequest
from urllib.parse import urlparse, urlunparse

from core.config import AI_SERVER_API_KEY, AI_SERVER_TIMEOUT_S, AI_SERVER_URL


class AIClientError(RuntimeError):
    pass


_KNOWN_ANALYSIS_PATHS = {"/v1/infer", "/analyze", "/v1/backend/analyze"}


def _normalize_ai_server_url(raw_url: str) -> str:
    token = str(raw_url or "").strip()
    if not token:
        return ""

    parsed = urlparse(token)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise AIClientError(
            "AI_SERVER_URL 형식이 올바르지 않습니다. 예: http://127.0.0.1:18080/v1/infer"
        )

    path = (parsed.path or "").rstrip("/")
    if path in {"", "/v1"}:
        path = "/v1/infer"
    elif path.startswith("/ops"):
        path = "/v1/infer"
    elif path and path not in _KNOWN_ANALYSIS_PATHS:
        # 커스텀 프록시 경로를 쓰는 경우를 위해 알 수 없는 path는 그대로 둔다.
        path = parsed.path

    return urlunparse((parsed.scheme, parsed.netloc, path, "", parsed.query, ""))


def _make_multipart_body(*, fields: list[tuple[str, str]], file_path: str) -> tuple[str, bytes]:
    boundary = f"----snapocket-{uuid.uuid4().hex}"
    chunks: list[bytes] = []

    for name, value in fields:
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode("utf-8"))

    filename = os.path.basename(file_path)
    safe_name = filename.replace('"', "'")
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    with open(file_path, "rb") as fp:
        file_bytes = fp.read()

    chunks.append(f"--{boundary}\r\n".encode("utf-8"))
    chunks.append(
        (
            f'Content-Disposition: form-data; name="file"; filename="{safe_name}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n"
        ).encode("utf-8")
    )
    chunks.append(file_bytes)
    chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))

    return f"multipart/form-data; boundary={boundary}", b"".join(chunks)


def _normalize_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [token.strip() for token in value.split(",") if token.strip()]
    return []


def _unwrap_response(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise AIClientError("AI 응답 형식이 올바르지 않습니다.")

    if "ok" in payload:
        if not bool(payload.get("ok")):
            error = payload.get("error")
            if isinstance(error, dict):
                raise AIClientError(str(error.get("message") or "AI 분석 실패"))
            raise AIClientError("AI 분석 실패")
        data = payload.get("data")
        return data if isinstance(data, dict) else {}

    if "success" in payload:
        if not bool(payload.get("success")):
            raise AIClientError(str(payload.get("message") or "AI 분석 실패"))
        data = payload.get("data")
        return data if isinstance(data, dict) else {}

    return payload


def request_analysis(*, file_path: str, doc_id: str) -> dict:
    if not AI_SERVER_URL:
        raise AIClientError("AI_SERVER_URL이 설정되지 않았습니다.")
    if not os.path.exists(file_path):
        raise AIClientError("분석할 파일이 존재하지 않습니다.")
    target_url = _normalize_ai_server_url(AI_SERVER_URL)

    content_type, body = _make_multipart_body(
        fields=[("doc_id", str(doc_id)), ("engine_hint", "auto")],
        file_path=file_path,
    )
    headers = {
        "Accept": "application/json",
        "Content-Type": content_type,
    }
    if AI_SERVER_API_KEY:
        headers["x-api-key"] = AI_SERVER_API_KEY

    req = urlrequest.Request(
        url=target_url,
        method="POST",
        data=body,
        headers=headers,
    )
    try:
        with urlrequest.urlopen(req, timeout=AI_SERVER_TIMEOUT_S) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except urlerror.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace") if exc.fp is not None else ""
        try:
            payload = json.loads(body_text) if body_text else {}
        except Exception:
            payload = {}
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict) and error.get("message"):
                message = str(error.get("message"))
                if exc.code == 401 and "Invalid API key" in message:
                    raise AIClientError(
                        "Invalid API key: 백엔드 AI_SERVER_API_KEY 값이 aiops-api의 AIOPS_API_KEY와 일치해야 합니다."
                    ) from exc
                raise AIClientError(message) from exc
            if payload.get("message"):
                raise AIClientError(str(payload.get("message"))) from exc
        if exc.code == 405:
            raise AIClientError(
                f"AI 엔드포인트가 잘못됐습니다: {target_url} (권장: /v1/infer 또는 /analyze)"
            ) from exc
        raise AIClientError(f"AI 서버 요청 실패(HTTP {exc.code})") from exc
    except urlerror.URLError as exc:
        raise AIClientError(f"AI 서버 연결 실패: {exc.reason}") from exc

    try:
        payload = json.loads(raw) if raw else {}
    except Exception as exc:
        raise AIClientError("AI 응답 파싱 실패") from exc

    return _unwrap_response(payload)


def map_analysis_result(payload: dict, *, fallback_doc_id: str) -> dict:
    data = payload if isinstance(payload, dict) else {}
    domain = data.get("domain") if isinstance(data.get("domain"), dict) else {}
    backend_doc_id = str(fallback_doc_id or "").strip()
    ai_reported_doc_id = str(data.get("doc_id") or domain.get("req_id") or "").strip()
    if ai_reported_doc_id and backend_doc_id and ai_reported_doc_id != backend_doc_id:
        raise AIClientError(
            "AI 응답 doc_id가 요청 doc_id와 일치하지 않습니다."
        )

    raw_text = (
        data.get("raw_text")
        or domain.get("raw_text")
        or data.get("corrected_text")
        or ""
    )
    mapped = {
        "doc_id": backend_doc_id,
        "title": str(domain.get("title") or data.get("title") or ""),
        "category": str(domain.get("category") or data.get("category") or "unknown"),
        "capture_date": data.get("capture_date") or domain.get("capture_date"),
        "summary": str(domain.get("summary") or data.get("summary") or ""),
        "tags": _normalize_list(domain.get("tag") or domain.get("tags") or data.get("tags")),
        "raw_text": str(raw_text),
        "key_concepts": _normalize_list(data.get("key_concepts") or domain.get("key_concepts")),
        "deadline": data.get("deadline") or domain.get("deadline"),
    }
    return mapped
