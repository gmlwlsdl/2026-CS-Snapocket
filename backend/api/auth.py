from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, ConfigDict
import uuid
from core.security import createAccessToken #, createRefreshToken
from sqlalchemy.orm import Session
from core.database import get_db
from core.security import jwtAuth
from models.user import User
from api.apiResponse import ApiResponse

router = APIRouter(prefix="/auth", tags=["auth"])

class UserCreate(BaseModel):
    email : str
    password : str
    name : str = None

class UserInfo(BaseModel):
    id: uuid.UUID
    email: str
    name: str

    model_config = ConfigDict(from_attributes=True)

# 회원가입
# 유저가 입력한 정보를 받아 유효성 검사 후 유저 id생성
@router.post("/signup", status_code = status.HTTP_201_CREATED, response_model=ApiResponse[dict])
def sighup(user : UserCreate, db: Session = Depends(get_db)):

    # 유효성 검사 부분
    if not user.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "message": "비밀번호 조건 미충족",
                "error_code": "INVALID_PASSWORD"
            }
        )
    
    duplicateEmail = db.query(User).filter(User.email == user.email).first()
    
    if duplicateEmail:
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
    newUser = User(
        id=userId,
        email=user.email,
        password_hash=user.password,
        name=user.name
    )

    db.add(newUser)
    db.commit()

    return ApiResponse(
        success=True,
        message="회원가입을 성공했습니다!",
        data={"user_id": userId}
    )

# 로그인
# 로그인 정보를 받아 유저db와 비교 후 JWT토큰 발행
@router.post("/login", response_model=ApiResponse[dict])
def login(login : UserCreate, db: Session = Depends(get_db)):

    # db와 로그인 정보 비교
    userInfo = db.query(User).filter(User.email == login.email).all()
    
    if not userInfo:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "message": "존재하지 않는 계정입니다.",
                "error_code": "ACCOUNT_NOT_FOUND"
            }
        )
    
    pwd = False

    for user in userInfo:
        if user.password_hash == login.password:
            pwd = True

    if pwd:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "success": False,
                "message": "비밀번호가 일치하지 않습니다.",
                "error_code": "INVALID_CREDENTIALS"
            }
        )

    # JWT 토큰 생성
    accessToken = createAccessToken(data={"sub": login.email})

    return ApiResponse(
        success=True,
        message="로그인을 성공했습니다!",
        data={
            "access_token": accessToken,
            "token_type": "bearer"
        }
    )

# 현재 사용자 정보
@router.get("/me", response_model=ApiResponse[UserInfo])
def me(jwtToken: dict = Depends(jwtAuth), db: Session = Depends(get_db)):

    userName = jwtToken.get("sub")
    userInfo = db.query(User).filter(User.email == userName).first()

    return ApiResponse(
        success=True,
        message="사용자를 성공적으로 불러왔습니다.",
        data=userInfo
    )

@router.post("/logout", response_model=ApiResponse[dict])
def logout(jwtToken: dict = Depends(jwtAuth)):
    return ApiResponse(
        success=True,
        message="로그아웃 성공",
        data={}
    )

@router.post("/test")
def test(login : UserCreate):
    # jwt발급 테스트
    return createAccessToken(data={"sub": login.email})