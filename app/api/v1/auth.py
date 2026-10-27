"""
app/api/v1/auth.py
==================
API key authentication dependency for FastAPI.

Week 2 implementation:
  - Hash the incoming key with SHA-256
  - Query ``api_keys`` table WHERE key_hash = <hash> AND status = 'ACTIVE'
  - Check expiry, update ``last_used_at``
  - Return the real ``user_id``
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.db.models import APIKey, APIKeyStatus

logger = logging.getLogger(__name__)


def _hash_api_key(raw_key: str) -> str:
    """Return the SHA-256 hex digest of the raw API key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def verify_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    db: AsyncSession = Depends(get_db_session),
) -> UUID:
    """Verify the ``X-API-Key`` request header and return the caller's user ID.

    Raises ``HTTP 401`` for missing or malformed keys.
    Raises ``HTTP 401`` for revoked / expired / unknown keys.

    Args:
        x_api_key: The raw API key from the request header.
        db: Injected async database session.

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

    # Hash and look up in DB
    key_hash = _hash_api_key(x_api_key)
    result = await db.execute(
        select(APIKey).where(
            APIKey.key_hash == key_hash,
            APIKey.status == APIKeyStatus.ACTIVE,
        )
    )
    api_key_obj = result.scalar_one_or_none()

    if api_key_obj is None:
        logger.warning("Request rejected: API key not found or inactive (hash prefix=%s...)", key_hash[:8])
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if api_key_obj.expires_at and api_key_obj.expires_at < datetime.now(timezone.utc):
        logger.warning("Request rejected: API key expired")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has expired.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    # Update last_used_at
    api_key_obj.last_used_at = datetime.now(timezone.utc)
    # Note: commit happens in the get_db_session dependency cleanup

    logger.debug("Auth OK for user=%s key_prefix=%r", api_key_obj.user_id, api_key_obj.key_prefix)
    return api_key_obj.user_id
