from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from core.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS

security = HTTPBearer()

def createAccessToken(data: dict):
    encode = data.copy()

    #  jwt 토큰 만료시간 설정 
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    encode.update({"exp": expire, "type": "access"})

    encodedJwt = jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)
    return encodedJwt

def createRefreshToken(data: dict):
    encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)

def verifyToken(token: str, expectedType: str):
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
    userName: str = payload.get("sub")
    tokenType: str = payload.get("type")

    if userName is None:
        raise ValueError("잘못된 토큰")
    
    if tokenType != expectedType:
        raise ValueError("잘못된 토큰")
            
    return payload 

def jwtAuth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    
    try:
        payload = verifyToken(token, expectedType="access")
        return payload
        
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않거나 만료된 토큰입니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
def jwtRefreshAuth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials

    try:
        payload = verifyToken(token, expectedType="refresh")
        return payload
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"유효하지 않거나 만료된 Refresh 토큰입니다. 재로그인이 필요합니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )