from supabase import create_client, Client
from app.config import settings

_supabase_client: Client | None = None

def get_supabase_client() -> Client | None:
    global _supabase_client
    if settings.supabase_url and settings.supabase_key:
        if _supabase_client is None:
            _supabase_client = create_client(settings.supabase_url, settings.supabase_key)
        return _supabase_client
    return None

class SupabaseService:
    """Thin wrapper around Supabase for auth / user metadata. Knowledge base lives in Qdrant + PostgreSQL."""

    def __init__(self):
        self.client = get_supabase_client()

    def is_configured(self) -> bool:
        return self.client is not None

    def get_user(self, user_id: str) -> dict | None:
        if not self.client:
            return None
        try:
            resp = self.client.table("users").select("*").eq("id", user_id).single().execute()
            return resp.data
        except Exception:
            return None
