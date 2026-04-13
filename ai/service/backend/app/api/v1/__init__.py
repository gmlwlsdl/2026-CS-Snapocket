"""v1 버전 API 라우터를 한곳에서 등록/노출한다."""

from . import infer, jobs, models, servers, system

# app.main 에서 include_router 할 수 있도록 모듈 참조를 명시적으로 export 한다.
__all__ = ["infer", "jobs", "models", "servers", "system"]
