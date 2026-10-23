"""Minimal HTTP request object.

Only what the framework needs today: the method, path, headers, cookies, body,
and a way to resolve which database the request targets. The request for the
in-flight dispatch is also exposed through :func:`current`.
"""

from __future__ import annotations

import json as _json
from contextlib import contextmanager
from contextvars import ContextVar


class Request:
  DB_COOKIE = 'jerp_db'
  DB_HEADER = 'x-jerp-db'

  def __init__(
    self,
    method: str = 'GET',
    path: str = '/',
    headers: dict | None = None,
    cookies: dict | None = None,
    query: dict | None = None,
    body=None,
  ):
    self.method = method.upper()
    self.path = path
    self.headers = {k.lower(): v for k, v in (headers or {}).items()}
    self.cookies = dict(cookies or {})
    self.query = dict(query or {})
    self.body = body

  def database(self) -> str | None:
    """Resolve the requested database name, or ``None`` for the default."""

    return self.cookies.get(self.DB_COOKIE) or self.headers.get(self.DB_HEADER)

  def json(self) -> dict:
    """Parse the request body as JSON (empty dict on failure)."""

    if not self.body:
      return {}
    raw = self.body.decode('utf-8') if isinstance(self.body, (bytes, bytearray)) else self.body
    try:
      data = _json.loads(raw)
    except (ValueError, TypeError):
      return {}
    return data if isinstance(data, dict) else {}

  def __repr__(self) -> str:
    return f'<Request {self.method} {self.path}>'

  @classmethod
  def from_http(cls, method: str, target: str, headers=None, body=None) -> 'Request':
    """Build a request from a raw HTTP request line target and headers."""

    from http.cookies import SimpleCookie
    from urllib.parse import parse_qs, urlparse

    parsed = urlparse(target)
    headers = {k.lower(): v for k, v in dict(headers or {}).items()}

    cookies: dict = {}
    raw_cookie = headers.get('cookie')
    if raw_cookie:
      jar = SimpleCookie()
      jar.load(raw_cookie)
      cookies = {key: morsel.value for key, morsel in jar.items()}

    query = {
      key: (values[0] if len(values) == 1 else values)
      for key, values in parse_qs(parsed.query).items()
    }

    return cls(
      method=method,
      path=parsed.path or '/',
      headers=headers,
      cookies=cookies,
      query=query,
      body=body,
    )


_current: ContextVar = ContextVar('jerp_request', default=None)


def current() -> 'Request | None':
  """The request currently being dispatched, if any."""

  return _current.get()


@contextmanager
def bind(request: 'Request | None'):
  token = _current.set(request)
  try:
    yield request
  finally:
    _current.reset(token)
