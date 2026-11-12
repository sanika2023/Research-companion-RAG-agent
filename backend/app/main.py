from fastapi import FastAPI

from app.api.routes import health

app = FastAPI(title="Paper RAG")
app.include_router(health.router)
