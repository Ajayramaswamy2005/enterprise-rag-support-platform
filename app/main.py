import logging
from contextlib import asynccontextmanager

import threading
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.models.database import init_db, SessionLocal
from app.api.routes import chat, knowledge, health
from app.core.opik_tracker import init_opik

logger = logging.getLogger(__name__)

def _bootstrap():
    """Create tables and rebuild the in-memory BM25 index from PostgreSQL.

    BM25 lives in process memory, so without this step sparse retrieval returns
    nothing after every restart until a document is re-ingested.
    """
    init_db()
    try:
        from app.services.knowledge_service import KnowledgeService
        db = SessionLocal()
        try:
            service = KnowledgeService()
            service.set_db(db)
            count = service.warm_retrieval_index()
            logger.info("BM25 index warmed with %d chunks", count)
            # Repair vectors for documents added while Qdrant was unreachable
            try:
                result = service.reindex()
                logger.info("Vector sync: %s", result)
            except Exception as e:
                logger.warning("Could not sync vectors on startup: %s", e)
        finally:
            db.close()
    except Exception as e:
        logger.warning("Could not warm retrieval index on startup: %s", e)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_opik()
    # Run in the background so the server starts accepting requests (and passes
    # health checks) while the database and models are still warming up.
    threading.Thread(target=_bootstrap, name="bootstrap", daemon=True).start()
    yield

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI Customer Support Platform with Hybrid Search and LangGraph",
    lifespan=lifespan,
)

_origins = settings.cors_origin_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    # Browsers reject credentialed requests to a wildcard origin
    allow_credentials="*" not in _origins,
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
