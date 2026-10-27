"""
scripts/seed_user.py
====================
Seed an initial user and API key into the database for development and testing.

Usage:
    python scripts/seed_user.py

Prints the raw API key once. Only the SHA-256 hash is stored in the database.
"""

from __future__ import annotations

import asyncio
import hashlib
import secrets
from datetime import datetime, timezone

from sqlalchemy import select

from app.database import async_session_factory
from app.db.models import APIKey, APIKeyStatus, User


async def seed() -> None:
    async with async_session_factory() as session:
        # Check if default user already exists
        result = await session.execute(
            select(User).where(User.email == "developer@example.com")
        )
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                username="developer",
                email="developer@example.com",
                is_active=True,
            )
            session.add(user)
            await session.flush()
            print(f"Created user: {user.email} (ID: {user.id})")
        else:
            print(f"Using existing user: {user.email} (ID: {user.id})")

        # Generate a new API key
        raw_token = secrets.token_urlsafe(32)
        raw_key = f"sk-{raw_token}"
        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        key_prefix = raw_key[:7]

        api_key = APIKey(
            user_id=user.id,
            key_hash=key_hash,
            key_prefix=key_prefix,
            status=APIKeyStatus.ACTIVE,
        )
        session.add(api_key)
        await session.commit()

        print("\n" + "=" * 60)
        print("API KEY GENERATED SUCCESSFULLY")
        print("=" * 60)
        print(f"Raw API Key : {raw_key}")
        print(f"Key Prefix  : {key_prefix}")
        print(f"User ID     : {user.id}")
        print("=" * 60)
        print("SAVE THIS KEY NOW. It will never be shown again.\n")


if __name__ == "__main__":
    asyncio.run(seed())
