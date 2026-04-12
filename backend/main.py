from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from api import auth
from graph.schema import data, router
from graph.context import getContext
from graph.qlRouter import CustomGraphQLRouter

import models  # noqa: F401

from routers.documents import router as documents_router
from routers.tags import router as tags_router
from routers.upload import router as upload_router
from routers.analysis import router as analysis_router

app = FastAPI(title="Snapocket API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(router)

app.include_router(documents_router)
app.include_router(tags_router)
app.include_router(upload_router)
app.include_router(analysis_router)

graphql_app = CustomGraphQLRouter(data, context_getter=getContext)
app.include_router(graphql_app, prefix="/graphql")
@app.get("/")
def root():
    return {
        "success": True, 
        "message": "Snapocket API is running", 
        "data": {}
    }


@app.get("/health")
def health():
    return {
        "success": True, 
        "message": "Server is healthy", 
        "data": {"status": "healthy"}
    }