import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
# print("DATABASE_URL:", DATABASE_URL)

# os.getenv로 값을 가져옴
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM", "HS256")

# 토큰 만료시간 설정
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS"))

# AI Server
AI_SERVER_URL = os.getenv("AI_SERVER_URL", "").strip()
# 운영 환경에 따라 키 이름이 다를 수 있어 AIOPS_API_KEY를 보조 fallback으로 허용한다.
AI_SERVER_API_KEY = os.getenv("AI_SERVER_API_KEY", os.getenv("AIOPS_API_KEY", "")).strip()
AI_SERVER_TIMEOUT_S = float(os.getenv("AI_SERVER_TIMEOUT_S", "60"))

# Backend only controls graph rebuild fan-out. Semantic hierarchy scoring runs in
# the AI service where embedding search and VLM-adjacent workloads live.
GRAPH_MAX_TOP_K = int(os.getenv("GRAPH_MAX_TOP_K", "8"))
GRAPH_MAX_EDGES_PER_DOC = int(os.getenv("GRAPH_MAX_EDGES_PER_DOC", "3"))
GRAPH_RUN_WHEN_VLM_IDLE = os.getenv("GRAPH_RUN_WHEN_VLM_IDLE", "true").strip().lower() == "true"

# 키 누락 방지
if not SECRET_KEY:
    raise ValueError("환경 변수에 SECRET_KEY가 설정되지 않았습니다!")
if not DATABASE_URL:
    raise ValueError("환경 변수에 DATABASE_URL가 설정되지 않았습니다!")
