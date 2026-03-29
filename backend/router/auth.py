from fastapi import APIRouter, Response, status
from pydantic import BaseModel
import uuid

router = APIRouter(prefix="/auth")

class UserCreate(BaseModel):
    email : str
    password : str
    name : str = None

#회원가입
#유저가 입력한 정보를 받아 유효성 검사 후 유저 id생성
@router.post("/signup")
def sighup(User : UserCreate, response : Response):

    #유효성 검사 부분

    userId = uuid.uuid1()

    #유저정보 db저장 부분

    response.status_code = status.HTTP_201_CREATED
    return {"success": True, "message": "회원가입을 성공했습니다!", "data": {"data.user_id": userId}}


#로그인
#로그인 정보를 받아 유저db와 비교 후 JWT토큰 발행
@router.post("/login")
def login(User : UserCreate, response : Response):

    #db와 로그인 정보 비교

    #JWT 토큰 생성

    return {"success": True, "message": "로그인을 성공했습니다!", "data": {"data.token_type": "bearer"}}

#현재 사용자 정보
@router.get("/me")
def me():
    
    return