from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import auth, analysis, documents, upload, tags, search
from core.database import (
    ensure_documents_schema_compatibility,
    ensure_graph_edges_schema_compatibility,
)
from graph.schema import data, router
from graph.context import getContext
from graph.qlRouter import CustomGraphQLRouter
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Snapocket API", version="0.1.0")


@app.on_event("startup")
def startup():
    ensure_documents_schema_compatibility()
    ensure_graph_edges_schema_compatibility()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://snapocket.site"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(router)

app.include_router(documents.router)
app.include_router(tags.router)
app.include_router(upload.router)
app.include_router(analysis.router)
app.include_router(search.router)

graphql_app = CustomGraphQLRouter(data, context_getter=getContext)
app.include_router(graphql_app, prefix="/graphql", tags=["graphql"])

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

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
