from fastapi import FastAPI

from app.api.routes import documents, health

app = FastAPI(title="Paper RAG")
app.include_router(health.router)
app.include_router(documents.router)
