import asyncio
import requests_async
import pytest


@pytest.mark.asyncio
async def test_session(server):
    url = "http://127.0.0.1:8000/"

    async with requests_async.Session() as session:
        response = await session.get(url)
        assert response.status_code == 200
        assert response.json() == {"method": "GET", "url": url, "body": ""}

        response = await session.post(url)
        assert response.status_code == 200
        assert response.json() == {"method": "POST", "url": url, "body": ""}

        response = await session.put(url)
        assert response.status_code == 200
        assert response.json() == {"method": "PUT", "url": url, "body": ""}

        response = await session.patch(url)
        assert response.status_code == 200
        assert response.json() == {"method": "PATCH", "url": url, "body": ""}

        response = await session.delete(url)
        assert response.status_code == 200
        assert response.json() == {"method": "DELETE", "url": url, "body": ""}

        response = await session.options(url)
        assert response.status_code == 200
        assert response.json() == {"method": "OPTIONS", "url": url, "body": ""}

        response = await session.head(url)
        assert response.status_code == 200
        assert response.text == ""


@pytest.mark.asyncio
async def test_session_redirection_disallowed(server):
    url = "http://127.0.0.1:8000/redirect1"
    async with requests_async.Session() as session:
        response = await session.get(url, allow_redirects=False)
        assert response.status_code == 302
        response = await session.send(response.next, allow_redirects=False)
        assert response.status_code == 302
        response = await session.send(response.next, allow_redirects=False)
        assert response.status_code == 200
        assert response.url == "http://127.0.0.1:8000/redirect3"
