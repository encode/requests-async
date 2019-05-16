from http.client import HTTPMessage

import requests


def extract_cookies_to_jar(jar, request, response):
    """Extract the cookies from the response into a CookieJar.
    :param jar: cookielib.CookieJar (not necessarily a RequestsCookieJar)
    :param request: our own requests.Request object
    :param response: httpcore.Response object
    """
    msg = HTTPMessage()
    for k, v in response.headers.raw:
        msg.add_header(k.decode(), v.decode())

    # the _original_response field is the wrapped httplib.HTTPResponse object,
    req = requests.cookies.MockRequest(request)
    # pull out the HTTPMessage with the headers and put it in the mock:
    res = requests.cookies.MockResponse(msg)
    jar.extract_cookies(res, req)
