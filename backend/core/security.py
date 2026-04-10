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
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        
    username: str = payload.get("sub")
    if username is None:
        raise ValueError("잘못된 토큰")
            
    return payload 
