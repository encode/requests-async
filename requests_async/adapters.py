import asyncio
import io
import os
import ssl
import typing
from http.client import _encode
from urllib.parse import urlparse

import h11
import requests
import urllib3

from .connections import ConnectionManager


class HTTPAdapter:
    def __init__(self):
        self.manager = ConnectionManager()

    async def send(
        self, request, stream=False, timeout=None, verify=True, cert=None, proxies=None
    ) -> requests.Response:
        urlparts = urlparse(request.url)

        if isinstance(timeout, tuple):
            connect_timeout, read_timeout = timeout
        else:
            connect_timeout = timeout
            read_timeout = timeout

        connection = await self.manager.get_connection(
            url=urlparts, verify=verify, cert=cert, timeout=connect_timeout
        )

        target = urlparts.path
        if urlparts.query:
            target += "?" + urlparts.query
        headers = [("host", urlparts.netloc)] + list(request.headers.items())

        message = h11.Request(method=request.method, target=target, headers=headers)
        await connection.send_event(message)

        if request.body:
            body = (
                _encode(request.body) if isinstance(request.body, str) else request.body
            )
            message = h11.Data(data=body)
            await connection.send_event(message)

        message = h11.EndOfMessage()
        await connection.send_event(message)

        status_code = 0
        headers = []
        reason = b""
        buffer = io.BytesIO()

        while True:
            event = await connection.receive_event(read_timeout)
            event_type = type(event)

            if event_type is h11.Response:
                status_code = event.status_code
                headers = [
                    (key.decode(), value.decode()) for key, value in event.headers
                ]
                reason = event.reason

            elif event_type is h11.Data:
                buffer.write(event.data)

            elif event_type is h11.EndOfMessage:
                buffer.seek(0)
                break

        await connection.close()

        resp = urllib3.HTTPResponse(
            body=buffer,
            headers=headers,
            status=status_code,
            reason=reason,
            preload_content=False,
        )

        return self.build_response(request, resp)

    async def close(self):
        pass

    def build_response(self, req, resp):
        """Builds a :class:`Response <requests.Response>` object from a urllib3
        response. This should not be called from user code, and is only exposed
        for use when subclassing the
        :class:`HTTPAdapter <requests.adapters.HTTPAdapter>`
        :param req: The :class:`PreparedRequest <PreparedRequest>` used to generate the response.
        :param resp: The urllib3 response object.
        :rtype: requests.Response
        """
        response = requests.models.Response()

        # Fallback to None if there's no status_code, for whatever reason.
        response.status_code = getattr(resp, "status", None)

        # Make headers case-insensitive.
        response.headers = requests.structures.CaseInsensitiveDict(
            getattr(resp, "headers", {})
        )

        # Set encoding.
        response.encoding = requests.utils.get_encoding_from_headers(response.headers)
        response.raw = resp
        response.reason = response.raw.reason

        if isinstance(req.url, bytes):
            response.url = req.url.decode("utf-8")
        else:
            response.url = req.url

        # Add new cookies from the server.
        requests.cookies.extract_cookies_to_jar(response.cookies, req, resp)

        # Give the Response some context.
        response.request = req
        response.connection = self

        return response
