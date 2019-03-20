import asyncio
import requests
import typing
import io
from datetime import timedelta

from urllib.parse import urlparse
import h11
import urllib3


class ASyncAdapter(requests.adapters.HTTPAdapter):
    async def send(
        self, request: requests.PreparedRequest, *args: typing.Any, **kwargs: typing.Any
    ):
        urlparts = urlparse(request.url)

        hostname = urlparts.hostname
        port = urlparts.port
        if port is None:
            port = {'http': 80, 'https': 443}[urlparts.scheme]

        reader, writer = await asyncio.open_connection(hostname, port)

        conn = h11.Connection(our_role=h11.CLIENT)

        message = h11.Request(
            method=request.method,
            target=urlparts.path,
            headers=[('host', hostname)] + list(request.headers.items())
        )
        data = conn.send(message)
        writer.write(data)

        message = h11.EndOfMessage()
        data = conn.send(message)
        writer.write(data)

        status_code = 0
        headers = []
        reason = b''
        buffer = io.BytesIO()

        while True:
            event = conn.next_event()
            event_type = type(event)

            if event_type is h11.NEED_DATA:
                data = await reader.read(2048)
                conn.receive_data(data)

            elif event_type is h11.Response:
                status_code = event.status_code
                headers = [(key.decode(), value.decode()) for key, value in event.headers]
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
            preload_content=False
        )

        return self.build_response(request, resp)


class ASyncRequests(requests.Session):
    def __init__(self, *args, **kwargs) -> None:
        super(ASyncRequests, self).__init__(*args, **kwargs)
        adapter = ASyncAdapter()
        self.mount("http://", adapter)
        self.mount("https://", adapter)

    async def request(self, method, url,
            params=None, data=None, headers=None, cookies=None, files=None,
            auth=None, timeout=None, allow_redirects=True, proxies=None,
            hooks=None, stream=None, verify=None, cert=None, json=None):
        # Create the Request.
        req = requests.models.Request(
            method=method.upper(),
            url=url,
            headers=headers,
            files=files,
            data=data or {},
            json=json,
            params=params or {},
            auth=auth,
            cookies=cookies,
            hooks=hooks,
        )
        prep = self.prepare_request(req)

        proxies = proxies or {}

        settings = self.merge_environment_settings(
            prep.url, proxies, stream, verify, cert
        )

        # Send the request.
        send_kwargs = {
            'timeout': timeout,
            'allow_redirects': allow_redirects,
        }
        send_kwargs.update(settings)
        resp = await self.send(prep, **send_kwargs)

        return resp

    async def get(self, url, **kwargs):
        kwargs.setdefault('allow_redirects', True)
        return await self.request('GET', url, **kwargs)

    async def options(self, url, **kwargs):
        kwargs.setdefault('allow_redirects', True)
        return await self.request('OPTIONS', url, **kwargs)

    async def head(self, url, **kwargs):
        kwargs.setdefault('allow_redirects', False)
        return await self.request('HEAD', url, **kwargs)

    async def post(self, url, data=None, json=None, **kwargs):
        return await self.request('POST', url, data=data, json=json, **kwargs)

    async def put(self, url, data=None, **kwargs):
        return await self.request('PUT', url, data=data, **kwargs)

    async def patch(self, url, data=None, **kwargs):
        return await self.request('PATCH', url, data=data, **kwargs)

    async def delete(self, url, **kwargs):
        return await self.request('DELETE', url, **kwargs)

    async def send(self, request, **kwargs):
        """Send a given PreparedRequest.

        :rtype: requests.Response
        """
        # Set defaults that the hooks can utilize to ensure they always have
        # the correct parameters to reproduce the previous request.
        kwargs.setdefault('stream', self.stream)
        kwargs.setdefault('verify', self.verify)
        kwargs.setdefault('cert', self.cert)
        kwargs.setdefault('proxies', self.proxies)

        # It's possible that users might accidentally send a Request object.
        # Guard against that specific failure case.
        if isinstance(request, requests.models.Request):
            raise ValueError('You can only send PreparedRequests.')

        # Set up variables needed for resolve_redirects and dispatching of hooks
        allow_redirects = kwargs.pop('allow_redirects', True)
        stream = kwargs.get('stream')
        hooks = request.hooks

        # Get the appropriate adapter to use
        adapter = self.get_adapter(url=request.url)

        # Start time (approximately) of the request
        start = requests.sessions.preferred_clock()

        # Send the request
        r = await adapter.send(request, **kwargs)

        # Total elapsed time of the request (approximately)
        elapsed = requests.sessions.preferred_clock() - start
        r.elapsed = timedelta(seconds=elapsed)

        # Response manipulation hooks
        r = requests.hooks.dispatch_hook('response', hooks, r, **kwargs)

        # Persist cookies
        if r.history:

            # If the hooks create history then we want those cookies too
            for resp in r.history:
                requests.cookies.extract_cookies_to_jar(self.cookies, resp.request, resp.raw)

        requests.cookies.extract_cookies_to_jar(self.cookies, request, r.raw)

        # Redirect resolving generator.
        gen = self.resolve_redirects(r, request, **kwargs)

        # Resolve redirects if allowed.
        history = [resp for resp in gen] if allow_redirects else []

        # Shuffle things around if there's history.
        if history:
            # Insert the first (original) request at the start
            history.insert(0, r)
            # Get the last request made
            r = history.pop()
            r.history = history

        # If redirects aren't being followed, store the response on the Request for Response.next().
        if not allow_redirects:
            try:
                r._next = next(self.resolve_redirects(r, request, yield_requests=True, **kwargs))
            except StopIteration:
                pass

        if not stream:
            r.content

        return r


async def main():
    session = ASyncRequests()
    response = await session.get('http://example.org')
    print('STATUS CODE:', response.status_code)
    print('HEADERS:', response.headers)
    print('TEXT:', response.text)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
