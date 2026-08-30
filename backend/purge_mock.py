import asyncio
from sqlalchemy import text
from app.core.database import get_db_context, init_db

async def clean():
    await init_db()
    async with get_db_context() as session:
        # Delete any test data from 2099 or synthetic sources
        res1 = await session.execute(text("DELETE FROM thermal_observations WHERE acquisition_datetime >= '2090-01-01'"))
        res2 = await session.execute(text("DELETE FROM thermal_events WHERE started_at >= '2090-01-01'"))
        await session.commit()
        print(f"Purged synthetic records: {res1.rowcount} observations, {res2.rowcount} events.")

if __name__ == "__main__":
    asyncio.run(clean())
