from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import auth
from graph import schema
from strawberry.fastapi import GraphQLRouter

app = FastAPI(title="Snapocket API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(schema.router)

graphql_app = GraphQLRouter(schema.data)
app.include_router(graphql_app, prefix="/graphql")

@app.get("/")
def root():
    return {"status": "ok", "message": "Snapocket API is running"}


@app.get("/health")
def health():
    return {"status": "healthy"}
