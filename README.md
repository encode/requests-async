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

## Usage:

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
    response = await requests.get('https://example.org')
    print(response.status_code)
    print(response.text)
```

The `requests_async` package subclasses `requests`, so you're getting all the
standard behavior and API you'd expect.

## Limitations

* Streaming uploads and downloads are unsupported.
* SSL verification is not currently enabled.
* No timeout support yet.

See the [issues list][issues] for more details.

## Alternatives

The [`aiohttp` package][aiohttp] provides an alternative client for making async HTTP requests.

[issues]: https://github.com/encode/requests-async/issues
[aiohttp]: https://docs.aiohttp.org/en/stable/client.html
