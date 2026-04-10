from fastapi import Depends, Request
from core.security import verifyToken

async def getContext(request: Request):

    authHeader = request.headers.get("Authorization")

    if not authHeader or not authHeader.startswith("bearer "):
        return {"user": None, "request": request}
        
    token = authHeader.split(" ")[1]
    
    try:
        user_info = verifyToken(token)
    except Exception:
        return {"user": None, "request": request}
        
    return {
        "user": user_info,
        "request": request
    }