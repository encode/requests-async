from . import sessions


async def request(method, url, **kwargs):
    async with sessions.Session() as session:
        return await session.request(method=method, url=url, **kwargs)


async def get(url, params=None, **kwargs):
    kwargs.setdefault("allow_redirects", True)
    return await request("get", url, params=params, **kwargs)


async def options(url, **kwargs):
    kwargs.setdefault("allow_redirects", True)
    return await request("options", url, **kwargs)


async def head(url, **kwargs):
    kwargs.setdefault("allow_redirects", False)
    return await request("head", url, **kwargs)


async def post(url, data=None, json=None, **kwargs):
    return await request("post", url, data=data, json=json, **kwargs)


async def put(url, data=None, **kwargs):
    return await request("put", url, data=data, **kwargs)


async def patch(url, data=None, **kwargs):
    return await request("patch", url, data=data, **kwargs)


async def delete(url, **kwargs):
    return await request("delete", url, **kwargs)
