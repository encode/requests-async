from starlette.responses import JSONResponse
import requests_async as requests
import pytest


app = JSONResponse({"hello": "world"})


@pytest.mark.asyncio
async def test_the_test_client():
    client = requests.ASGISession(app)
    response = await client.get('/')
    assert response.status_code == 200
