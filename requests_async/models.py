import codecs

from requests.models import PreparedRequest, Request, Response as BaseResponse

from .exceptions import ContentNotAvailable

ITER_CHUNK_SIZE = 512


async def stream_decode_response_unicode(aiterator, encoding):
    decoder = codecs.getincrementaldecoder(encoding)(errors="replace")
    async for chunk in aiterator:
        rv = decoder.decode(chunk)
        if rv:
            yield rv
    rv = decoder.decode(b"", final=True)
    if rv:
        yield rv


class Response(BaseResponse):
    @property
    def content(self):
        if self._content is False:
            raise ContentNotAvailable("Cannot access .content on a streaming response")
        return self._content

    async def read(self):
        if self._content is False:
            body = b""
            async for chunk in self.iter_content(ITER_CHUNK_SIZE):
                body += chunk
            self._content = body
        return self._content

    async def iter_content(self, chunk_size=1, decode_unicode=False):
        if self._content is False:
            stream = self.raw.stream
        else:

            async def stream():
                yield self._content

        async def generate():
            data = b""
            async for part in stream():
                data += part
                while len(data) >= chunk_size:
                    yield data[:chunk_size]
                    data = data[chunk_size:]
            if data:
                yield data

        if decode_unicode and self.encoding is not None:
            async for chunk in stream_decode_response_unicode(
                generate(), self.encoding
            ):
                yield chunk
        else:
            async for chunk in generate():
                yield chunk

    async def iter_lines(
        self, chunk_size=ITER_CHUNK_SIZE, decode_unicode=False, delimiter=None
    ):
        pending = None

        async for chunk in self.iter_content(
            chunk_size=chunk_size, decode_unicode=decode_unicode
        ):

            if pending is not None:
                chunk = pending + chunk

            if delimiter:
                lines = chunk.split(delimiter)
            else:
                lines = chunk.splitlines()

            if lines and lines[-1] and chunk and lines[-1][-1] == chunk[-1]:
                pending = lines.pop()
            else:
                pending = None

            for line in lines:
                yield line

        if pending is not None:
            yield pending

    async def __aiter__(self):
        """Allows you to use a response as an iterator."""
        async for chunk in self.iter_content(128):
            yield chunk

    async def close(self):
        await self.raw.close()
