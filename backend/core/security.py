from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from core.envReader import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES#, REFRESH_TOKEN_EXPIRE_DAYS
from core.exceptions import UnauthorizedError

def createAccessToken(data: dict):
    encode = data.copy()

    #  jwt 토큰 만료시간 설정 
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    encode.update({"exp": expire})

    encodedJwt = jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)
    return encodedJwt

# def createRefreshToken(data: dict):
#     encode = data.copy()
#     expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
#     encode.update({"exp": expire})
#     return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)

def verifyToken(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
        # 2. 페이로드에서 필요한 정보(예: 유저 ID 또는 이메일) 추출
        username: str = payload.get("sub")
        if username is None:
            raise UnauthorizedError("유효하지 않은 토큰입니다. (사용자 정보 없음)")
            
        return payload # 검증 성공 시 유저 정보가 담긴 페이로드 반환

    except jwt.ExpiredSignatureError:
        # 토큰의 유효시간이 만료된 경우
        raise UnauthorizedError()
        
    except JWTError:
        # 토큰 서명이 틀렸거나 구조가 잘못된 경우
        raise UnauthorizedError()