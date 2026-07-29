from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.models.database import init_db
from app.api.routes import chat, knowledge, health
from app.core.opik_tracker import init_opik

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    init_opik()
    yield

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI Customer Support Platform with Hybrid Search and LangGraph",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(knowledge.router)

@app.get("/")
def root():
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
    }
