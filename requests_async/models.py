from requests.models import PreparedRequest, Request, Response as BaseResponse
from .exceptions import ContentNotAvailable


ITER_CHUNK_SIZE = 512


class Response(BaseResponse):
    @property
    def content(self):
        if self._content is False:
            raise ContentNotAvailable("Cannot access .content on a streaming response")
        return self._content

    async def iter_content(self, chunk_size=1, decode_unicode=False):
        async def generate():
            if self._content is False:
                stream = self.raw.stream
            else:
                async def stream():
                    yield self._content

            data = b''
            async for part in stream():
                data += part
                while len(data) >= chunk_size:
                    yield data[:chunk_size]
                    data = data[chunk_size:]
            if data:
                yield data

        pass

    async def iter_lines(self, chunk_size=ITER_CHUNK_SIZE, decode_unicode=False, delimiter=None):
        pass

    async def __aiter__(self):
        """Allows you to use a response as an iterator."""
        return await self.iter_content(128)
