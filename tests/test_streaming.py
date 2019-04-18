import asyncio

import pytest

import requests_async


@pytest.mark.asyncio
async def test_get(server):
    url = "http://127.0.0.1:8000/"
    response = await requests_async.get(url, stream=True)
    assert response.status_code == 200
    with pytest.raises(requests_async.exceptions.ContentNotAvailable):
        response.content
