import hmac
import logging
from typing import Optional

import jwt
from pydantic import BaseModel
from fastapi import Security, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from app.config import settings

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
http_bearer = HTTPBearer(auto_error=False)

class AuthenticatedUser(BaseModel):
    id: str
    email: Optional[str] = None
    role: str = "authenticated"
    auth_type: str = "api_key"

def _matches_api_key(candidate: Optional[str]) -> bool:
    if not candidate or not settings.api_key:
        return False
    return hmac.compare_digest(candidate.encode(), settings.api_key.encode())

def verify_token(token: str) -> Optional[dict]:
    # Only trust Supabase JWTs whose signature we can verify. Decoding without
    # verification would let anyone forge a token with an arbitrary "sub".
    if not settings.supabase_jwt_secret:
        return None
    try:
        return jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except jwt.PyJWTError:
        return None

async def get_current_user(
    api_key: Optional[str] = Security(api_key_header),
    credentials: Optional[HTTPAuthorizationCredentials] = Security(http_bearer),
) -> AuthenticatedUser:
    if not settings.auth_enabled:
        return AuthenticatedUser(id="anonymous", role="admin", auth_type="disabled")

    # 1. Check X-API-Key header
    if _matches_api_key(api_key):
        return AuthenticatedUser(id="api_client", role="admin", auth_type="api_key")

    # 2. Check Authorization Bearer
    if credentials and credentials.credentials:
        token = credentials.credentials
        if _matches_api_key(token):
            return AuthenticatedUser(id="api_client", role="admin", auth_type="api_key")

        payload = verify_token(token)
        if payload and payload.get("sub"):
            return AuthenticatedUser(
                id=str(payload["sub"]),
                email=payload.get("email"),
                role=payload.get("role", "authenticated"),
                auth_type="supabase_jwt",
            )

    if not settings.api_key and not settings.supabase_jwt_secret:
        logger.warning("Auth is enabled but neither API_KEY nor SUPABASE_JWT_SECRET is configured; all requests are rejected.")

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized: Please provide a valid X-API-Key or Authorization Bearer token.",
        headers={"WWW-Authenticate": "Bearer"},
    )
