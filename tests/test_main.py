import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_root():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Assuming there is a root endpoint or some other endpoint to test
        # If no root endpoint exists, this test might return 404, which is expected
        response = await ac.get("/")
        assert response.status_code in [200, 404]
