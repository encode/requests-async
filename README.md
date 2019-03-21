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
    <img src="https://badge.fury.io/py/requests-async.svg" alt="Package version">
</a>
</p>

**This is just a first-pass right now.**

Next set of things to deal with:

* https support, and certificate checking.
* streaming support for uploads and downloads.
* connection pooling.
* async cookie persistence, for on-disk cookie stores.
* make sure authentication works okay (does it use adapters, is the API broken there now?)
* timeouts

## Requirements

* Python 3.6, 3.7.

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
