import asyncio

from app.database import engine
from app.db.models import Base


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("Tables created.")


if __name__ == "__main__":
    asyncio.run(main())
