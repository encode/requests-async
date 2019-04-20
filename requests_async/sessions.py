import datetime
from urllib.parse import urljoin, urlparse

import requests
from requests.cookies import merge_cookies
from requests.exceptions import (
    ChunkedEncodingError,
    ContentDecodingError,
    InvalidSchema,
    TooManyRedirects,
)
from requests.status_codes import codes
from requests.utils import requote_uri, rewind_body

from . import adapters
from .cookies import extract_cookies_to_jar


def to_native_string(string, encoding="ascii"):
    """Given a string object, regardless of type, returns a representation of
    that string in the native string type, encoding and decoding where
    necessary. This assumes ASCII unless told otherwise.
    """
    if isinstance(string, str):
        return string
    return string.decode(encoding)


class Session(requests.Session):
    def __init__(self, *args, **kwargs) -> None:
        super(Session, self).__init__(*args, **kwargs)
        adapter = adapters.HTTPAdapter()
        self.mount("http://", adapter)
        self.mount("https://", adapter)

    async def request(
        self,
        method,
        url,
        params=None,
        data=None,
        headers=None,
        cookies=None,
        files=None,
        auth=None,
        timeout=None,
        allow_redirects=True,
        proxies=None,
        hooks=None,
        stream=None,
        verify=None,
        cert=None,
        json=None,
    ):
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
        send_kwargs = {"timeout": timeout, "allow_redirects": allow_redirects}
        send_kwargs.update(settings)
        resp = await self.send(prep, **send_kwargs)

        return resp

    async def get(self, url, **kwargs):
        kwargs.setdefault("allow_redirects", True)
        return await self.request("GET", url, **kwargs)

    async def options(self, url, **kwargs):
        kwargs.setdefault("allow_redirects", True)
        return await self.request("OPTIONS", url, **kwargs)

    async def head(self, url, **kwargs):
        kwargs.setdefault("allow_redirects", False)
        return await self.request("HEAD", url, **kwargs)

    async def post(self, url, data=None, json=None, **kwargs):
        return await self.request("POST", url, data=data, json=json, **kwargs)

    async def put(self, url, data=None, **kwargs):
        return await self.request("PUT", url, data=data, **kwargs)

    async def patch(self, url, data=None, **kwargs):
        return await self.request("PATCH", url, data=data, **kwargs)

    async def delete(self, url, **kwargs):
        return await self.request("DELETE", url, **kwargs)

    async def send(self, request, **kwargs):
        """Send a given PreparedRequest.

        :rtype: requests.Response
        """
        # Set defaults that the hooks can utilize to ensure they always have
        # the correct parameters to reproduce the previous request.
        kwargs.setdefault("stream", self.stream)
        kwargs.setdefault("verify", self.verify)
        kwargs.setdefault("cert", self.cert)
        kwargs.setdefault("proxies", self.proxies)

        # It's possible that users might accidentally send a Request object.
        # Guard against that specific failure case.
        if isinstance(request, requests.models.Request):
            raise ValueError("You can only send PreparedRequests.")

        # Set up variables needed for resolve_redirects and dispatching of hooks
        allow_redirects = kwargs.pop("allow_redirects", True)
        stream = kwargs.get("stream")
        hooks = request.hooks

        # Get the appropriate adapter to use
        adapter = self.get_adapter(url=request.url)

        # Start time (approximately) of the request
        start = requests.sessions.preferred_clock()

        # Send the request
        r = await adapter.send(request, **kwargs)

        # Total elapsed time of the request (approximately)
        elapsed = requests.sessions.preferred_clock() - start
        r.elapsed = datetime.timedelta(seconds=elapsed)

        # Response manipulation hooks
        r = requests.hooks.dispatch_hook("response", hooks, r, **kwargs)

        # Persist cookies
        if r.history:

            # If the hooks create history then we want those cookies too
            for resp in r.history:
                extract_cookies_to_jar(self.cookies, resp.request, resp.raw)

        extract_cookies_to_jar(self.cookies, request, r.raw)

        # Redirect resolving.
        history = []
        if allow_redirects:
            async for resp in self.resolve_redirects(r, request, **kwargs):
                history.append(resp)

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
                redirect_gen = self.resolve_redirects(
                    r, request, yield_requests=True, **kwargs
                )
                r._next = await redirect_gen.__anext__()
            except StopAsyncIteration:
                pass

        if not stream:
            await r.read()

        return r

    async def resolve_redirects(
        self,
        resp,
        req,
        stream=False,
        timeout=None,
        verify=True,
        cert=None,
        proxies=None,
        yield_requests=False,
        **adapter_kwargs
    ):
        """Receives a Response. Returns a generator of Responses or Requests."""
        hist = []  # keep track of history

        url = self.get_redirect_target(resp)
        previous_fragment = urlparse(req.url).fragment
        while url:
            prepared_request = req.copy()

            # Update history and keep track of redirects.
            # resp.history must ignore the original request in this loop
            hist.append(resp)
            resp.history = hist[1:]

            # Release the connection back into the pool.
            try:
                await resp.read()
            finally:
                await resp.close()

            if len(resp.history) >= self.max_redirects:
                raise TooManyRedirects(
                    "Exceeded %s redirects." % self.max_redirects, response=resp
                )

            # Handle redirection without scheme (see: RFC 1808 Section 4)
            if url.startswith("//"):
                parsed_rurl = urlparse(resp.url)
                url = "%s:%s" % (to_native_string(parsed_rurl.scheme), url)

            # Normalize url case and attach previous fragment if needed (RFC 7231 7.1.2)
            parsed = urlparse(url)
            if parsed.fragment == "" and previous_fragment:
                parsed = parsed._replace(fragment=previous_fragment)
            elif parsed.fragment:
                previous_fragment = parsed.fragment
            url = parsed.geturl()

            # Facilitate relative 'location' headers, as allowed by RFC 7231.
            # (e.g. '/path/to/resource' instead of 'http://domain.tld/path/to/resource')
            # Compliant with RFC3986, we percent encode the url.
            if not parsed.netloc:
                url = urljoin(resp.url, requote_uri(url))
            else:
                url = requote_uri(url)

            prepared_request.url = to_native_string(url)

            self.rebuild_method(prepared_request, resp)

            # https://github.com/requests/requests/issues/1084
            if resp.status_code not in (
                codes.temporary_redirect,
                codes.permanent_redirect,
            ):
                # https://github.com/requests/requests/issues/3490
                purged_headers = ("Content-Length", "Content-Type", "Transfer-Encoding")
                for header in purged_headers:
                    prepared_request.headers.pop(header, None)
                prepared_request.body = None

            headers = prepared_request.headers
            try:
                del headers["Cookie"]
            except KeyError:
                pass

            # Extract any cookies sent on the response to the cookiejar
            # in the new request. Because we've mutated our copied prepared
            # request, use the old one that we haven't yet touched.
            extract_cookies_to_jar(prepared_request._cookies, req, resp.raw)
            merge_cookies(prepared_request._cookies, self.cookies)
            prepared_request.prepare_cookies(prepared_request._cookies)

            # Rebuild auth and proxy information.
            proxies = self.rebuild_proxies(prepared_request, proxies)
            self.rebuild_auth(prepared_request, resp)

            # A failed tell() sets `_body_position` to `object()`. This non-None
            # value ensures `rewindable` will be True, allowing us to raise an
            # UnrewindableBodyError, instead of hanging the connection.
            rewindable = prepared_request._body_position is not None and (
                "Content-Length" in headers or "Transfer-Encoding" in headers
            )

            # Attempt to rewind consumed file-like object.
            if rewindable:
                rewind_body(prepared_request)

            # Override the original request.
            req = prepared_request

            if yield_requests:
                yield req
            else:

                resp = await self.send(
                    req,
                    stream=stream,
                    timeout=timeout,
                    verify=verify,
                    cert=cert,
                    proxies=proxies,
                    allow_redirects=False,
                    **adapter_kwargs
                )

                extract_cookies_to_jar(self.cookies, prepared_request, resp.raw)

                # extract redirect url, if any, for the next loop
                url = self.get_redirect_target(resp)
                yield resp

    async def close(self):
        for v in self.adapters.values():
            await v.close()

    def __enter__(self):
        raise NotImplementedError("Use 'async with Session', instead of 'with Session'")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
