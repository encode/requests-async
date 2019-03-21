import asyncio
import io
import typing
from urllib.parse import urlparse

import h11
import requests
import urllib3


class HTTPAdapter(requests.adapters.HTTPAdapter):
    async def send(
        self, request: requests.PreparedRequest, *args: typing.Any, **kwargs: typing.Any
    ) -> requests.Response:
        urlparts = urlparse(request.url)

        hostname = urlparts.hostname
        port = urlparts.port
        if port is None:
            port = {"http": 80, "https": 443}[urlparts.scheme]
        target = urlparts.path
        if urlparts.query:
            target += "?" + urlparts.query
        headers = [("host", urlparts.netloc)] + list(request.headers.items())

        reader, writer = await asyncio.open_connection(hostname, port)

        conn = h11.Connection(our_role=h11.CLIENT)

        message = h11.Request(method=request.method, target=target, headers=headers)
        data = conn.send(message)
        writer.write(data)

        if request.body:
            message = h11.Data(data=request.body.encode("utf-8"))
            data = conn.send(message)
            writer.write(data)

        message = h11.EndOfMessage()
        data = conn.send(message)
        writer.write(data)

        status_code = 0
        headers = []
        reason = b""
        buffer = io.BytesIO()

        while True:
            event = conn.next_event()
            event_type = type(event)

            if event_type is h11.NEED_DATA:
                data = await reader.read(2048)
                conn.receive_data(data)

            elif event_type is h11.Response:
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

        writer.close()
        await writer.wait_closed()

        resp = urllib3.HTTPResponse(
            body=buffer,
            headers=headers,
            status=status_code,
            reason=reason,
            preload_content=False,
        )

        return self.build_response(request, resp)
