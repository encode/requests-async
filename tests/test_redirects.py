import requests_async
import pytest


@pytest.mark.asyncio
async def test_redirects(server):
    url = "http://127.0.0.1:8000/redirect1"
    response = await requests_async.get(url)
    assert response.status_code == 200
    assert response.json() == {"hello": "world"}
    assert response.url == "http://127.0.0.1:8000/redirect3"
    assert len(response.history) == 2


@pytest.mark.asyncio
async def test_redirects_disallowed(server):
    url = "http://127.0.0.1:8000/redirect1"
    response = await requests_async.get(url, allow_redirects=False)
    assert response.status_code == 302
    assert response.url == "http://127.0.0.1:8000/redirect1"
    assert len(response.history) == 0
