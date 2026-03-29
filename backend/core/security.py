from datetime import datetime, timedelta
from jose import jwt
from core.envReader import SECRET_KEY, ALGORITHM  #, ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS

def create_access_token(data: dict):
    encode = data.copy()

    #  
    # expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    # encode.update({"exp": expire})

    encodedJwt = jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)
    return encodedJwt

# def create_refresh_token(data: dict):
#     encode = data.copy()
#     expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
#     encode.update({"exp": expire})
#     return jwt.encode(encode, SECRET_KEY, algorithm=ALGORITHM)