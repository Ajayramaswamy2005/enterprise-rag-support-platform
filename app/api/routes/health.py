from fastapi import APIRouter
from app import __version__
from app.config import settings
from app.core.qdrant_client import get_qdrant_client
from app.core.supabase_client import get_supabase_client
from app.models.database import engine
from app.models.schemas import HealthResponse

router = APIRouter(tags=["Health"])

@router.get("/health", response_model=HealthResponse)
def health_check():
    components = {}

    try:
        engine.connect()
        components["postgresql"] = "ok"
    except Exception as e:
        components["postgresql"] = f"error: {e}"

    try:
        client = get_qdrant_client()
        client.get_collections()
        components["qdrant"] = "ok"
    except Exception as e:
        components["qdrant"] = f"error: {e}"

    try:
        sb = get_supabase_client()
        components["supabase"] = "ok" if sb else "not_configured"
    except Exception as e:
        components["supabase"] = f"error: {e}"

    try:
        from app.core.groq_client import get_groq_client
        get_groq_client()
        components["groq"] = "ok"
    except Exception as e:
        components["groq"] = f"error: {e}"

    overall = "healthy" if all(v == "ok" or v == "not_configured" for v in components.values()) else "unhealthy"

    return HealthResponse(
        status=overall,
        version=__version__,
        components=components,
    )
