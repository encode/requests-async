# requests-async

Brings support for `async`/`await` syntax to Python's fabulous `requests` library.

<p>
<a href="https://travis-ci.org/encode/requests-async">
    <img src="https://travis-ci.org/encode/requests-async.svg?branch=master" alt="Build Status">
</a>
<a href="https://codecov.io/gh/encode/requests-async">
    <img src="https://codecov.io/gh/encode/requests-async/branch/master/graph/badge.svg" alt="Coverage">
</a>
<a href="https://pypi.org/project/requests-async/">
    <img src="https://badge.fury.io/py/requests-async.svg?cache0" alt="Package version">
</a>
</p>

**Contributions towards closing off our [outstanding issues][issues] would be very welcome!** ✨ 🍰 ✨

## Requirements

* Python 3.6, 3.7.

## Installation

```shell
$ pip install requests-async
```

## Usage

Just use *the standard requests API*, but use `await` for making requests.

**Note**: Use `ipython` to try this from the console, since it supports `await`.

```python
import requests_async as requests


response = await requests.get('https://example.org')
print(response.status_code)
print(response.text)
```

Or use explicit sessions.

```python
import requests_async as requests


with requests.Session() as session:
    response = await session.get('https://example.org')
    print(response.status_code)
    print(response.text)
```

The `requests_async` package subclasses `requests`, so you're getting all the
standard behavior and API you'd expect.

## Mock Requests

In some situations, such as when you're testing a web application, you may
not want to make actual outgoing network requests, but would prefer instead
to mock out the endpoints.

You can do this using the `ASGISession`, which allows you to plug into
any ASGI application, instead of making actual network requests.

```python
import requests_async

# Create a mock service, with Starlette, Responder, Quart, FastAPI, Bocadillo,
# or any other ASGI web framework.
mock_app = ...

if TESTING:
    # Issue requests to the the mock application.
    requests = requests_async.ASGISession(mock_app)
else:
    # Make live network requests.
    requests = requests_async.Session()
```

## Test Client

You can also use `ASGISession` as a test client for any ASGI application.

You'll probably want to install `pytest` and `pytest-asyncio`, or something
equivalent, to allow you to write `async` test cases.

```python
from requests_async import ASGISession
from myproject import app
import pytest

@pytest.mark.asyncio
async def test_homepage():
    client = ASGISession(app)
    response = await client.get("/")
    assert response.status_code == 200
```

## Limitations

* Streaming uploads and downloads are unsupported.
* SSL verification is not currently enabled.
* No timeout support yet.

See the [issues list][issues] for more details.

## Alternatives

The [`aiohttp` package][aiohttp] provides an alternative client for making async HTTP requests.

[issues]: https://github.com/encode/requests-async/issues
[aiohttp]: https://docs.aiohttp.org/en/stable/client.html
