from datetime import datetime, timedelta, timezone
from jose import jwt
from core.envReader import SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES#, REFRESH_TOKEN_EXPIRE_DAYS

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