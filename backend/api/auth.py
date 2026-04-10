from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
import uuid
from core.security import createAccessToken #, createRefreshToken

router = APIRouter(prefix="/auth")

class UserCreate(BaseModel):
    email : str
    password : str
    name : str = None

# 회원가입
# 유저가 입력한 정보를 받아 유효성 검사 후 유저 id생성
@router.post("/signup", status_code = status.HTTP_201_CREATED)
def sighup(User : UserCreate):

    # 유효성 검사 부분
    if False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "message": "비밀번호 조건 미충족",
                "error_code": "INVALID_PASSWORD"
            }
        )
    
    if False:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "success": False,
                "message": "중복된 이메일 주소입니다.",
                "error_code": "EMAIL_ALREADY_EXISTS"
            }
        )

    # 유저 id생성
    userId = uuid.uuid1()

    # 유저정보 db저장 부분

    return {"success": True, "message": "회원가입을 성공했습니다!", "data": {"user_id": userId}}


# 로그인
# 로그인 정보를 받아 유저db와 비교 후 JWT토큰 발행
@router.post("/login")
def login(User : UserCreate):

    # db와 로그인 정보 비교

    
    if False:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "message": "비밀번호가 일치하지 않습니다.",
                "error_code": "INVALID_CREDENTIALS"
            }
        )
    
    if False:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "message": "존재하지 않는 계정입니다.",
                "error_code": "ACCOUNT_NOT_FOUND"
            }
        )

    # JWT 토큰 생성
    accessToken = createAccessToken(data={"sub": User.email})

    return {"success": True, "message": "로그인을 성공했습니다!", "data": {"access_token": accessToken, "token_type": "bearer"}}

# 현재 사용자 정보
@router.get("/me")
def me():
    
    return {"success": True, "message": "", "data": {}}