"""API 공통 응답 포맷 헬퍼."""

from __future__ import annotations

from fastapi import Request

from app.schemas.common import ApiResponse, ResponseMeta


def ok_response(request: Request, data) -> ApiResponse:
    return ApiResponse(ok=True, meta=ResponseMeta(request_id=request.state.request_id), data=data)
