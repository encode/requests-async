import asyncio
import http
import inspect
import io
import json
import queue
import threading
import types
import typing
from urllib.parse import unquote, urljoin, urlsplit

import requests

import httpcore

from .adapters import HTTPAdapter
from .sessions import Session


class _HeaderDict(requests.packages.urllib3._collections.HTTPHeaderDict):
    def get_all(self, key: str, default: str) -> str:
        return self.getheaders(key)


class _MockOriginalResponse:
    """
    We have to jump through some hoops to present the response as if
    it was made using urllib3.
    """

    def __init__(self, headers: typing.List[typing.Tuple[bytes, bytes]]) -> None:
        self.msg = _HeaderDict(headers)
        self.closed = False

    def isclosed(self) -> bool:
        return self.closed


def _get_reason_phrase(status_code: int) -> str:
    try:
        return http.HTTPStatus(status_code).phrase
    except ValueError:
        return ""


class ASGIAdapter(HTTPAdapter):
    def __init__(self, app, suppress_exceptions: bool = False) -> None:
        self.app = app
        self.suppress_exceptions = suppress_exceptions

    async def send(  # type: ignore
        self, request: requests.PreparedRequest, *args: typing.Any, **kwargs: typing.Any
    ) -> requests.Response:
        scheme, netloc, path, query, fragment = urlsplit(request.url)  # type: ignore

        default_port = {"http": 80, "ws": 80, "https": 443, "wss": 443}[scheme]

        if ":" in netloc:
            host, port_string = netloc.split(":", 1)
            port = int(port_string)
        else:
            host = netloc
            port = default_port

        # Include the 'host' header.
        if "host" in request.headers:
            headers = []  # type: typing.List[typing.Tuple[bytes, bytes]]
        elif port == default_port:
            headers = [(b"host", host.encode())]
        else:
            headers = [(b"host", (f"{host}:{port}").encode())]

        # Include other request headers.
        headers += [
            (key.lower().encode(), value.encode())
            for key, value in request.headers.items()
        ]

        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": request.method,
            "path": unquote(path),
            "root_path": "",
            "scheme": scheme,
            "query_string": query.encode(),
            "headers": headers,
            "client": ["testclient", 50000],
            "server": [host, port],
            "extensions": {"http.response.template": {}},
        }

        async def receive():
            nonlocal request_complete, response_complete

            if request_complete:
                while not response_complete:
                    await asyncio.sleep(0.0001)
                return {"type": "http.disconnect"}

            body = request.body
            if isinstance(body, str):
                body_bytes = body.encode("utf-8")  # type: bytes
            elif body is None:
                body_bytes = b""
            elif isinstance(body, types.GeneratorType):
                try:
                    chunk = body.send(None)
                    if isinstance(chunk, str):
                        chunk = chunk.encode("utf-8")
                    return {"type": "http.request", "body": chunk, "more_body": True}
                except StopIteration:
                    request_complete = True
                    return {"type": "http.request", "body": b""}
            else:
                body_bytes = body

            request_complete = True
            return {"type": "http.request", "body": body_bytes}

        async def send(message) -> None:
            nonlocal raw_kwargs, response_started, response_complete, template, context

            if message["type"] == "http.response.start":
                assert (
                    not response_started
                ), 'Received multiple "http.response.start" messages.'
                raw_kwargs["status_code"] = message["status"]
                raw_kwargs["headers"] = message["headers"]
                response_started = True
            elif message["type"] == "http.response.body":
                assert (
                    response_started
                ), 'Received "http.response.body" without "http.response.start".'
                assert (
                    not response_complete
                ), 'Received "http.response.body" after response completed.'
                body = message.get("body", b"")
                more_body = message.get("more_body", False)
                if request.method != "HEAD":
                    raw_kwargs["content"] += body
                if not more_body:
                    response_complete = True
            elif message["type"] == "http.response.template":
                template = message["template"]
                context = message["context"]

        request_complete = False
        response_started = False
        response_complete = False
        raw_kwargs = {"content": b""}  # type: typing.Dict[str, typing.Any]
        template = None
        context = None

        try:
            await self.app(scope, receive, send)
        except BaseException as exc:
            if not self.suppress_exceptions:
                raise exc from None

        if not self.suppress_exceptions:
            assert response_started, "TestClient did not receive any response."
        elif not response_started:
            raw_kwargs = {"status_code": 500, "headers": []}

        raw = httpcore.Response(**raw_kwargs)
        response = self.build_response(request, raw)
        if template is not None:
            response.template = template
            response.context = context
        return response


class ASGISession(Session):
    def __init__(
        self,
        app,
        base_url: str = "http://mockserver",
        suppress_exceptions: bool = False,
    ) -> None:
        super(ASGISession, self).__init__()
        adapter = ASGIAdapter(app, suppress_exceptions=suppress_exceptions)
        self.mount("http://", adapter)
        self.mount("https://", adapter)
        self.headers.update({"user-agent": "testclient"})
        self.app = app
        self.base_url = base_url

    async def request(self, method, url, *args, **kwargs) -> requests.Response:
        url = urljoin(self.base_url, url)
        return await super().request(method, url, *args, **kwargs)
