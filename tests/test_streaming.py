import asyncio

import pytest

import requests_async


@pytest.mark.asyncio
async def test_content_not_available_on_stream(server):
    url = "http://127.0.0.1:8000/hello_world"
    response = await requests_async.get(url, stream=True)
    assert response.status_code == 200
    with pytest.raises(requests_async.exceptions.ContentNotAvailable):
        response.content


@pytest.mark.asyncio
async def test_iter_content_on_stream(server):
    url = "http://127.0.0.1:8000/hello_world"
    response = await requests_async.get(url, stream=True)
    assert response.status_code == 200
    content = b""
    async for chunk in response.iter_content():
        assert len(chunk) == 1
        content += chunk
    assert content == b"Hello, world!"


@pytest.mark.asyncio
async def test_iter_text_on_stream(server):
    url = "http://127.0.0.1:8000/hello_world"
    response = await requests_async.get(url, stream=True)
    assert response.status_code == 200
    content = ""
    async for chunk in response.iter_content(decode_unicode=True):
        assert len(chunk) == 1
        content += chunk
    assert content == "Hello, world!"


@pytest.mark.asyncio
async def test_iter_content_on_content(server):
    url = "http://127.0.0.1:8000/hello_world"
    response = await requests_async.get(url)
    assert response.status_code == 200
    content = b""
    async for chunk in response.iter_content():
        assert len(chunk) == 1
        content += chunk
    assert content == b"Hello, world!"


@pytest.mark.asyncio
async def test_iter_text_on_content(server):
    url = "http://127.0.0.1:8000/hello_world"
    response = await requests_async.get(url)
    assert response.status_code == 200
    content = ""
    async for chunk in response.iter_content(decode_unicode=True):
        assert len(chunk) == 1
        content += chunk
    assert content == "Hello, world!"


@pytest.mark.asyncio
async def test_iter(server):
    url = "http://127.0.0.1:8000/hello_world"
    response = await requests_async.get(url, stream=True)
    assert response.status_code == 200
    content = b""
    async for chunk in response:
        content += chunk
    assert content == b"Hello, world!"


@pytest.mark.asyncio
async def test_iter_lines(server):
    url = "http://127.0.0.1:8000/hello_world"
    response = await requests_async.get(url, stream=True)
    assert response.status_code == 200
    lines = []
    async for line in response.iter_lines(decode_unicode=True):
        lines.append(line)
    assert lines == ["Hello, world!"]


@pytest.mark.asyncio
async def test_iter_lines_with_delimiter(server):
    url = "http://127.0.0.1:8000/hello_world"
    response = await requests_async.get(url, stream=True)
    assert response.status_code == 200
    lines = []
    async for line in response.iter_lines(decode_unicode=True, delimiter=" "):
        lines.append(line)
    assert lines == ["Hello,", "world!"]
