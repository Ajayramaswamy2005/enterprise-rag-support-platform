from fastapi import APIRouter
from sqlalchemy import text
from app import __version__
from app.config import settings
from app.core.qdrant_client import get_qdrant_client
from app.core.supabase_client import get_supabase_client
from app.models.database import engine
from app.models.schemas import HealthResponse

router = APIRouter(tags=["Health"])

def _short_error(e: Exception) -> str:
    return f"error: {str(e).splitlines()[0][:200]}" if str(e) else f"error: {type(e).__name__}"

@router.get("/healthz")
def liveness():
    """Cheap liveness probe for the platform health check. /health touches every
    dependency and can be slow or degraded without the process being unhealthy."""
    return {"status": "ok"}

@router.get("/health", response_model=HealthResponse)
def health_check():
    components = {}

    try:
        # Context manager returns the connection to the pool instead of leaking it
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        components["postgresql"] = "ok"
    except Exception as e:
        components["postgresql"] = _short_error(e)

    try:
        get_qdrant_client().get_collections()
        components["qdrant"] = "ok"
    except Exception as e:
        components["qdrant"] = _short_error(e)

    try:
        sb = get_supabase_client()
        components["supabase"] = "ok" if sb else "not_configured"
    except Exception as e:
        components["supabase"] = _short_error(e)

    try:
        from app.core.groq_client import get_groq_client
        get_groq_client()
        components["groq"] = "ok"
    except Exception as e:
        components["groq"] = _short_error(e)

    overall = "healthy" if all(v in ("ok", "not_configured") for v in components.values()) else "degraded"

    return HealthResponse(
        status=overall,
        version=__version__,
        components={**components, "model": settings.groq_model},
    )
