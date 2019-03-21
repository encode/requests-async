# requests-async

Brings support for `async`/`await` syntax to Python's fabulous `requests` library.

**This is just a first-pass right now.**

Next set of things to deal with:

* https support, and certificate checking.
* streaming support for uploads and downloads.
* connection pooling.
* async redirections.
* async cookie persistence, for on-disk cookie stores.
* make sure authentication works okay (does it use adapters, is the API broken there now?)

## Installation:

```shell
$ pip install requests-async
```

## Usage:

Just use the standard requests API, but use `await` for making requests.

```python
import requests_async as requests


response = await requests.get('http://example.org')
print(response.status_code)
print(response.text)
```
