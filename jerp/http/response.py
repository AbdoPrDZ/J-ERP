"""HTTP responses.

The server turns handler return values into :class:`Response` objects. Handlers
may return a ``Response`` directly, a ``str`` (HTML), ``bytes``, a ``dict``/``list``
(JSON), ``None`` (204), or a ``(body, status[, headers])`` tuple.

``render()`` remains a stub until template rendering is implemented.
"""

from __future__ import annotations

import json as _json


class Response:
  def __init__(
    self,
    body=b'',
    status: int = 200,
    headers: dict | None = None,
    content_type: str | None = None,
  ):
    self.status = status
    self.headers: dict = dict(headers or {})
    self.body: bytes = body if isinstance(body, bytes) else str(body).encode('utf-8')
    if content_type:
      self.headers.setdefault('Content-Type', content_type)

  @property
  def content_type(self) -> str | None:
    return self.headers.get('Content-Type')

  def with_status(self, status: int, headers: dict | None = None) -> 'Response':
    self.status = status
    if headers:
      self.headers.update(headers)
    return self


def text(body: str, status: int = 200) -> Response:
  return Response(body, status, content_type='text/plain; charset=utf-8')


def html(body: str, status: int = 200) -> Response:
  return Response(body, status, content_type='text/html; charset=utf-8')


def json(data, status: int = 200) -> Response:
  return Response(
    _json.dumps(data, default=str).encode('utf-8'),
    status,
    content_type='application/json; charset=utf-8',
  )


def redirect(location: str, status: int = 302) -> Response:
  return Response(b'', status, headers={'Location': location})


def not_found(message: str = 'Not Found') -> Response:
  return json({'error': 'not_found', 'message': message}, status=404)


def server_error(message: str = 'Internal Server Error') -> Response:
  return json({'error': 'server_error', 'message': message}, status=500)


def make_response(value) -> Response:
  """Normalize whatever a handler returned into a :class:`Response`."""

  if isinstance(value, Response):
    return value

  if value is None:
    return Response(b'', status=204)

  if isinstance(value, tuple):
    body = value[0] if value else b''
    status = value[1] if len(value) > 1 else 200
    headers = value[2] if len(value) > 2 else None
    return make_response(body).with_status(status, headers)

  if isinstance(value, (dict, list)):
    return json(value)

  if isinstance(value, bytes):
    return Response(value, content_type='application/octet-stream')

  return html(str(value))


def render(template_name: str, context: dict | None = None):
  """Render a view by key (e.g. ``core.index``) into a full HTML shell."""

  from jerp import views

  return html(views.render(template_name, context or {}))
