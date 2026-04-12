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
# REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS"))

# 키 누락 방지
if not SECRET_KEY:
    raise ValueError("환경 변수에 SECRET_KEY가 설정되지 않았습니다!")
if not DATABASE_URL:
    raise ValueError("환경 변수에 DATABASE_URL가 설정되지 않았습니다!")