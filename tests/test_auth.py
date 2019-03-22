import requests_async
import pytest


@pytest.mark.asyncio
async def test_auth(server):
    url = "http://127.0.0.1:8000/echo_headers"
    response = await requests_async.get(url, auth=("tom", "pass"))
    assert response.status_code == 200
    assert response.json()["headers"]["authorization"] == "Basic dG9tOnBhc3M="
