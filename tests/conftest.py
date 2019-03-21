import asyncio
import pytest

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from uvicorn.config import Config
from uvicorn.main import Server


async def echo_request(request):
    body = await request.body()
    return JSONResponse(
        {
            "method": request.method,
            "url": str(request.url),
            "body": body.decode("utf-8"),
        }
    )


async def echo_form_data(request):
    form = await request.form()
    return JSONResponse(
        {
            "method": request.method,
            "url": str(request.url),
            "form": {key: value for key, value in form.items()},
        }
    )


routes = [
    Route("/", echo_request, methods=["GET", "DELETE", "OPTIONS", "POST", "PUT", "PATCH"]),
    Route("/echo_form_data", echo_form_data, methods=["POST", "PUT", "PATCH"]),
]

app = Starlette(routes=routes)


@pytest.fixture
async def server():
    config = Config(app=app, lifespan="off")
    server = Server(config=config)
    task = asyncio.ensure_future(server.serve())
    try:
        while not server.started:
            await asyncio.sleep(0.0001)
        yield server
    finally:
        task.cancel()
