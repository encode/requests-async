import requests_async as requests


def test_imports():
    from requests_async.models import Request
    from requests_async.status_codes import codes
    from requests_async.exceptions import RequestException


def test_exposed_interfaces():
    assert requests.Request is not None
    assert requests.codes is not None
    assert requests.RequestException is not None
