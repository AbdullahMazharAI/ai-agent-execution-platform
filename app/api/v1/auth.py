"""
app/api/v1/auth.py
==================
API key authentication dependency for FastAPI.

Current implementation (Week 1):
  - Validates header presence and "sk-" prefix format
  - Returns a mock user UUID so endpoint stubs run end-to-end

Week 2 upgrade path:
  - Hash the incoming key with SHA-256
  - Query ``api_keys`` table WHERE key_hash = <hash> AND status = 'ACTIVE'
  - Check expiry, update ``last_used_at``
  - Return the real ``user_id``
"""

from __future__ import annotations

import hashlib
import logging
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session

logger = logging.getLogger(__name__)

# Sentinel UUID used as the mock user in Week 1 before real auth is wired up.
_MOCK_USER_ID = UUID("550e8400-e29b-41d4-a716-446655440000")


def _hash_api_key(raw_key: str) -> str:
    """Return the SHA-256 hex digest of the raw API key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def verify_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db_session),
) -> UUID:
    """Verify the ``X-API-Key`` request header and return the caller's user ID.

    Raises ``HTTP 401`` for missing or malformed keys.
    Raises ``HTTP 403`` for revoked / expired keys (Week 2).

    Args:
        x_api_key: The raw API key from the request header.
        db: Injected async database session (used in Week 2 for DB lookup).

    Returns:
        The UUID of the authenticated user.
    """
    if not x_api_key:
        logger.warning("Request rejected: missing X-API-Key header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if not x_api_key.startswith("sk-"):
        logger.warning("Request rejected: invalid API key format (prefix mismatch)")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format. Keys must start with 'sk-'.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # ── Week 2: replace below with real DB lookup ──────────────────────────
    # key_hash = _hash_api_key(x_api_key)
    # result = await db.execute(
    #     select(APIKey).where(
    #         APIKey.key_hash == key_hash,
    #         APIKey.status == APIKeyStatus.ACTIVE,
    #     )
    # )
    # api_key_obj = result.scalar_one_or_none()
    # if api_key_obj is None:
    #     raise HTTPException(status_code=401, detail="Invalid or revoked API key")
    # if api_key_obj.expires_at and api_key_obj.expires_at < datetime.now(timezone.utc):
    #     raise HTTPException(status_code=401, detail="API key has expired")
    # # Update last_used_at asynchronously (fire-and-forget acceptable here)
    # api_key_obj.last_used_at = datetime.now(timezone.utc)
    # await db.commit()
    # return api_key_obj.user_id
    # ──────────────────────────────────────────────────────────────────────

    logger.debug("Auth OK (mock) for key prefix=%r", x_api_key[:8])
    return _MOCK_USER_ID
