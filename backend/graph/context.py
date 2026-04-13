from fastapi import Depends, Request
from core.security import verifyToken
from core.database import get_db
from sqlalchemy.orm import Session

async def getContext(request: Request, db: Session = Depends(get_db)):

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
        "request": request,
        "db": db
    }