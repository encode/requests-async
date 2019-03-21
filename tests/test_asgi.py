import asyncio

import pytest

from starlette.requests import ClientDisconnect, Request
from starlette.responses import JSONResponse, HTMLResponse, Response
from starlette.testclient import TestClient

from requests_async import ASGISession


app = JSONResponse({"hello": "world"})


@pytest.mark.asyncio
async def test_request_url():
    async def app(scope, receive, send):
        request = Request(scope, receive)
        data = {"method": request.method, "url": str(request.url)}
        response = JSONResponse(data)
        await response(scope, receive, send)

    client = ASGISession(app)
    response = await client.get("/123?a=abc")
    assert response.json() == {"method": "GET", "url": "http://mockserver/123?a=abc"}

    response = await client.get("https://example.org:123/")
    assert response.json() == {"method": "GET", "url": "https://example.org:123/"}


@pytest.mark.asyncio
async def test_request_query_params():
    async def app(scope, receive, send):
        request = Request(scope, receive)
        params = dict(request.query_params)
        response = JSONResponse({"params": params})
        await response(scope, receive, send)

    client = ASGISession(app)
    response = await client.get("/?a=123&b=456")
    assert response.json() == {"params": {"a": "123", "b": "456"}}


@pytest.mark.asyncio
async def test_request_headers():
    async def app(scope, receive, send):
        request = Request(scope, receive)
        headers = dict(request.headers)
        response = JSONResponse({"headers": headers})
        await response(scope, receive, send)

    client = ASGISession(app)
    response = await client.get("/", headers={"host": "example.org"})
    assert response.json() == {
        "headers": {
            "host": "example.org",
            "user-agent": "testclient",
            "accept-encoding": "gzip, deflate",
            "accept": "*/*",
            "connection": "keep-alive",
        }
    }


@pytest.mark.asyncio
async def test_request_client():
    async def app(scope, receive, send):
        request = Request(scope, receive)
        response = JSONResponse(
            {"host": request.client.host, "port": request.client.port}
        )
        await response(scope, receive, send)

    client = ASGISession(app)
    response = await client.get("/")
    assert response.json() == {"host": "testclient", "port": 50000}


@pytest.mark.asyncio
async def test_request_body():
    async def app(scope, receive, send):
        request = Request(scope, receive)
        body = await request.body()
        response = JSONResponse({"body": body.decode()})
        await response(scope, receive, send)

    client = ASGISession(app)

    response = await client.get("/")
    assert response.json() == {"body": ""}

    response = await client.post("/", json={"a": "123"})
    assert response.json() == {"body": '{"a": "123"}'}

    response = await client.post("/", data="abc")
    assert response.json() == {"body": "abc"}


@pytest.mark.asyncio
async def test_request_stream():
    async def app(scope, receive, send):
        request = Request(scope, receive)
        body = b""
        async for chunk in request.stream():
            body += chunk
        response = JSONResponse({"body": body.decode()})
        await response(scope, receive, send)

    client = ASGISession(app)

    response = await client.get("/")
    assert response.json() == {"body": ""}

    response = await client.post("/", json={"a": "123"})
    assert response.json() == {"body": '{"a": "123"}'}

    response = await client.post("/", data="abc")
    assert response.json() == {"body": "abc"}


@pytest.mark.asyncio
async def test_request_form_urlencoded():
    async def app(scope, receive, send):
        request = Request(scope, receive)
        form = await request.form()
        response = JSONResponse({"form": dict(form)})
        await response(scope, receive, send)

    client = ASGISession(app)

    response = await client.post("/", data={"abc": "123 @"})
    assert response.json() == {"form": {"abc": "123 @"}}


@pytest.mark.asyncio
async def test_request_json():
    async def app(scope, receive, send):
        request = Request(scope, receive)
        data = await request.json()
        response = JSONResponse({"json": data})
        await response(scope, receive, send)

    client = ASGISession(app)
    response = await client.post("/", json={"a": "123"})
    assert response.json() == {"json": {"a": "123"}}


@pytest.mark.asyncio
async def test_request_is_disconnected():
    """
    If a client disconnect occurs while reading request body
    then ClientDisconnect should be raised.
    """
    disconnected_after_response = None

    async def app(scope, receive, send):
        nonlocal disconnected_after_response

        request = Request(scope, receive)
        await request.body()
        disconnected = await request.is_disconnected()
        response = JSONResponse({"disconnected": disconnected})
        await response(scope, receive, send)
        disconnected_after_response = await request.is_disconnected()

    client = ASGISession(app)
    response = await client.get("/")
    assert response.json() == {"disconnected": False}
    assert disconnected_after_response


@pytest.mark.asyncio
async def test_request_state():
    async def app(scope, receive, send):
        request = Request(scope, receive)
        request.state.example = 123
        response = JSONResponse({"state.example": request["state"].example})
        await response(scope, receive, send)

    client = ASGISession(app)
    response = await client.get("/123?a=abc")
    assert response.json() == {"state.example": 123}


@pytest.mark.asyncio
async def test_request_cookies():
    async def app(scope, receive, send):
        request = Request(scope, receive)
        mycookie = request.cookies.get("mycookie")
        if mycookie:
            response = Response(mycookie, media_type="text/plain")
        else:
            response = Response("Hello, world!", media_type="text/plain")
            response.set_cookie("mycookie", "Hello, cookies!")

        await response(scope, receive, send)

    client = ASGISession(app)
    response = await client.get("/")
    assert response.text == "Hello, world!"
    response = await client.get("/")
    assert response.text == "Hello, cookies!"


@pytest.mark.asyncio
async def test_chunked_encoding():
    async def app(scope, receive, send):
        request = Request(scope, receive)
        body = await request.body()
        response = JSONResponse({"body": body.decode()})
        await response(scope, receive, send)

    client = ASGISession(app)

    def post_body():
        yield b"foo"
        yield "bar"

    response = await client.post("/", data=post_body())
    assert response.json() == {"body": "foobar"}


@pytest.mark.asyncio
async def test_exceptions():
    async def app(scope, receive, send):
        raise RuntimeError()

    client = ASGISession(app)
    with pytest.raises(RuntimeError):
        await client.get("/")


@pytest.mark.asyncio
async def test_suppress_execeptions():
    async def app(scope, receive, send):
        raise RuntimeError()

    client = ASGISession(app, suppress_exceptions=True)
    response = await client.get("/")
    assert response.status_code == 500


@pytest.mark.asyncio
async def test_template_responses():
    async def app(scope, receive, send):
        response = HTMLResponse('<html>Hello, world</html>')
        await response(scope, receive, send)
        await send({
            "type": "http.response.template",
            "template": "index.html",
            "context": {"username": "tom"},
        })

    client = ASGISession(app)
    response = await client.get("/")
    assert response.text == "<html>Hello, world</html>"
    assert response.template == "index.html"
    assert response.context == {"username": "tom"}


@pytest.mark.asyncio
async def test_unknown_phrase():
    app = HTMLResponse(b"", status_code=123)
    client = ASGISession(app)
    response = await client.get("/")
    assert response.reason == ""
