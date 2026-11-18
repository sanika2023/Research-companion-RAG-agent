from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import ask, documents, health
from app.core.config import CorsSettings

app = FastAPI(title="Paper RAG")
# The frontend is served from another origin (port 3000 locally, Vercel when deployed).
app.add_middleware(
    CORSMiddleware,
    allow_origins=CorsSettings().origins,
    allow_methods=["GET", "POST"],
    allow_headers=["content-type"],
)
app.include_router(health.router)
app.include_router(documents.router)
app.include_router(ask.router)
