import asyncio
from http.client import _encode
import io
import ssl
import typing
from urllib.parse import urlparse

import os
import h11
import requests
import urllib3


def no_verify_context():
    context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
    context.options |= ssl.OP_NO_SSLv2
    context.options |= ssl.OP_NO_SSLv3
    context.options |= ssl.OP_NO_COMPRESSION
    context.set_default_verify_paths()
    return context


def verify_context(verify, cert):
    if verify is True:
        ca_bundle_path = requests.utils.DEFAULT_CA_BUNDLE_PATH
    elif os.path.exists(verify):
        ca_bundle_path = verify
    else:
        raise IOError(
            "Could not find a suitable TLS CA certificate bundle, "
            "invalid path: {}".format(verify)
        )

    context = ssl.create_default_context()
    if os.path.isfile(ca_bundle_path):
        context.load_verify_locations(cafile=ca_bundle_path)
    elif os.path.isdir(ca_bundle_path):
        context.load_verify_locations(capath=ca_bundle_path)

    if cert is not None:
        if isinstance(cert, str):
            context.load_cert_chain(certfile=cert)
        else:
            context.load_cert_chain(certfile=cert[0], keyfile=cert[1])

    return context


def get_ssl(urlparts, verify, cert):
    if urlparts.scheme != 'https':
        return False

    if not verify:
        return no_verify_context()
    return verify_context(verify, cert)


class HTTPAdapter(requests.adapters.HTTPAdapter):
    async def send(
        self, request, stream=False, timeout=None, verify=True, cert=None, proxies=None
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

        ssl = get_ssl(urlparts, verify, cert)

        if isinstance(timeout, tuple):
            connect_timeout, read_timeout = timeout
        else:
            connect_timeout = timeout
            read_timeout = timeout

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(hostname, port, ssl=ssl), connect_timeout
            )
        except asyncio.TimeoutError:
            raise requests.ConnectTimeout()

        conn = h11.Connection(our_role=h11.CLIENT)

        message = h11.Request(method=request.method, target=target, headers=headers)
        data = conn.send(message)
        writer.write(data)

        if request.body:
            body = (
                _encode(request.body) if isinstance(request.body, str) else request.body
            )
            message = h11.Data(data=body)
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
                try:
                    data = await asyncio.wait_for(reader.read(2048), read_timeout)
                except asyncio.TimeoutError:
                    raise requests.ReadTimeout()
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
        if hasattr(writer, "wait_closed"):
            await writer.wait_closed()

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
