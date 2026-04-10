from fastapi import Depends, Request
from core.security import verifyToken

async def getContext(request: Request):
    auth_header = request.headers.get("Authorization")
    
    user_info = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        user_info = verifyToken(token) 
        
    return {
        "user": user_info,
        "request": request
    }