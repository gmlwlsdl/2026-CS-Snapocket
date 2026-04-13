"""멀티모달 입력 라우팅을 위한 파일 타입 판별 유틸."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

IMAGE_MIME_TYPES: set[str] = {
    "image/png",
    "image/jpeg",
    "image/webp",
    "image/tiff",
}
PDF_MIME_TYPES: set[str] = {"application/pdf"}
AUDIO_MIME_TYPES: set[str] = {
    "audio/mpeg",
    "audio/mp3",
}
OFFICE_MIME_TYPES: set[str] = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
GENERIC_MIME_TYPES: set[str] = {
    "",
    "application/octet-stream",
    "binary/octet-stream",
    "application/zip",
}

EXT_TO_MIME: dict[str, str] = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".mp3": "audio/mpeg",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _normalize_content_type(value: str | None) -> str:
    if not value:
        return ""
    return value.split(";", 1)[0].strip().lower()


def _mime_from_magic(payload: bytes) -> str | None:
    if not payload:
        return None
    head = payload[:16]
    if head.startswith(b"%PDF-"):
        return "application/pdf"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"II*\x00") or head.startswith(b"MM\x00*"):
        return "image/tiff"
    if head.startswith(b"ID3"):
        return "audio/mpeg"
    if len(payload) >= 2 and payload[0] == 0xFF and (payload[1] & 0xE0) == 0xE0:
        return "audio/mpeg"
    if payload.startswith(b"RIFF") and payload[8:12] == b"WEBP":
        return "image/webp"
    if payload.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as zf:
                names = set(zf.namelist())
        except Exception:
            return None
        if "word/document.xml" in names:
            return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if any(name.startswith("ppt/slides/") for name in names):
            return "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        if any(name.startswith("xl/worksheets/") for name in names):
            return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return None


def resolve_content_type(filename: str, given_type: str | None, payload: bytes | None = None) -> str:
    """명시 타입/확장자/매직바이트를 조합해 MIME을 최대한 정확히 추정한다."""
    normalized = _normalize_content_type(given_type)
    if normalized and normalized not in GENERIC_MIME_TYPES:
        return normalized

    ext = Path(filename or "").suffix.lower()
    if ext in EXT_TO_MIME:
        return EXT_TO_MIME[ext]

    magic_guess = _mime_from_magic(payload or b"")
    if magic_guess:
        return magic_guess

    if normalized:
        return normalized
    return "application/octet-stream"


def is_image_content_type(content_type: str) -> bool:
    return _normalize_content_type(content_type) in IMAGE_MIME_TYPES


def is_pdf_content_type(content_type: str) -> bool:
    return _normalize_content_type(content_type) in PDF_MIME_TYPES


def is_audio_content_type(content_type: str) -> bool:
    return _normalize_content_type(content_type) in AUDIO_MIME_TYPES


def is_office_content_type(content_type: str) -> bool:
    return _normalize_content_type(content_type) in OFFICE_MIME_TYPES
