import jwt
from typing import Optional
from pydantic import BaseModel
from fastapi import Security, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from app.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
http_bearer = HTTPBearer(auto_error=False)

class AuthenticatedUser(BaseModel):
    id: str
    email: Optional[str] = None
    role: str = "authenticated"
    auth_type: str = "api_key"

def verify_token(token: str) -> Optional[dict]:
    # Try decoding Supabase JWT token
    try:
        secret = settings.supabase_jwt_secret or settings.supabase_key or ""
        # If secret is available, verify signature; otherwise decode claims
        if secret and len(secret) > 20:
            return jwt.decode(token, secret, algorithms=["HS256"], options={"verify_aud": False})
        return jwt.decode(token, options={"verify_signature": False})
    except Exception:
        return None

async def get_current_user(
    api_key: Optional[str] = Security(api_key_header),
    credentials: Optional[HTTPAuthorizationCredentials] = Security(http_bearer),
) -> AuthenticatedUser:
    if not settings.auth_enabled:
        return AuthenticatedUser(id="anonymous", role="admin", auth_type="disabled")

    # 1. Check X-API-Key header
    if api_key and settings.api_key and api_key == settings.api_key:
        return AuthenticatedUser(id="api_client", role="admin", auth_type="api_key")

    # 2. Check Authorization Bearer
    if credentials and credentials.credentials:
        token = credentials.credentials
        # Check if Bearer token matches API key
        if settings.api_key and token == settings.api_key:
            return AuthenticatedUser(id="api_client", role="admin", auth_type="api_key")

        # Check Supabase JWT
        payload = verify_token(token)
        if payload and payload.get("sub"):
            return AuthenticatedUser(
                id=str(payload["sub"]),
                email=payload.get("email"),
                role=payload.get("role", "authenticated"),
                auth_type="supabase_jwt",
            )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized: Please provide a valid X-API-Key or Authorization Bearer token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
