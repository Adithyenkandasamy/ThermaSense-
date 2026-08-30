"""
Quick script to verify Module 2 API endpoints against database.
"""

import asyncio
from httpx import ASGITransport, AsyncClient
from app.main import app


async def main():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Health
        health = await ac.get("/health")
        print("1. Health Endpoint:", health.status_code, health.json())

        # 2. Monitoring Status
        status = await ac.get("/api/monitoring/status")
        print("2. Monitoring Status Endpoint:", status.status_code, status.json())

        # 3. Monitoring Logs
        logs = await ac.get("/api/monitoring/logs", params={"limit": 5})
        print("3. Monitoring Logs Endpoint:", logs.status_code, f"Total logs: {logs.json()['total']}")
        if logs.json()["logs"]:
            print("   Latest log item:", logs.json()["logs"][0])


if __name__ == "__main__":
    asyncio.run(main())
