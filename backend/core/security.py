from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from core.config import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES#, REFRESH_TOKEN_EXPIRE_DAYS

security = HTTPBearer()

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
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
    userName: str = payload.get("sub")
    if userName is None:
        raise ValueError("잘못된 토큰")
            
    return payload 

def jwtAuth(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    
    try:
        payload = verifyToken(token)
        return payload
        
    except (JWTError, ValueError):
        raise HTTPException(
            status_code=401,
            detail="유효하지 않거나 만료된 토큰입니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )