from .adapters import HTTPAdapter
from .sessions import Session
from .api import request, get, head, post, patch, put, delete, options

__version__ = "0.0.1"
__all__ = [
    "request",
    "get",
    "head",
    "post",
    "patch",
    "put",
    "delete",
    "options",
    "Session",
]
