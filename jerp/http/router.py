"""Decorator based routing.

Handlers register themselves on the :class:`Environment` router. Endpoints may
contain ``<name>`` path segments (e.g. ``/model/<model_name>/<func>``); matched
values are passed to the handler as keyword arguments.

Dispatching can optionally receive a :class:`~jerp.http.request.Request`; when it
does, the request-scoped database middleware selects the database for the
duration of the call.
"""

from __future__ import annotations

import re
from enum import Enum
from functools import wraps


class RequestMethod(Enum):
  GET = 'GET'
  POST = 'POST'
  PUT = 'PUT'
  DELETE = 'DELETE'
  PATCH = 'PATCH'
  OPTIONS = 'OPTIONS'
  HEAD = 'HEAD'


class RouteNotFound(Exception):
  """Raised by :meth:`Router.dispatch` when no route matches."""


def route(method, endpoint=None, auth=False):
  # ``@route('/')`` (endpoint only) defaults to GET; ``@route('POST', '/x')``
  # keeps the explicit form used by the method helpers below.
  if endpoint is None:
    endpoint = method
    method = RequestMethod.GET

  if isinstance(method, RequestMethod):
    method = method.value
  if isinstance(method, str):
    method = method.upper()
  if method not in RequestMethod.__members__:
    raise ValueError(f'Invalid HTTP method: {method}')

  def decorator(func):
    # Record route metadata so controllers can be instantiated later and their
    # methods registered as bound handlers (see jerp.http.controllers).
    routes = getattr(func, '_jerp_routes', None)
    if routes is None:
      routes = []
      func._jerp_routes = routes
    routes.append((method, endpoint, auth))

    @wraps(func)
    def wrapper(*args, **kwargs):
      return func(*args, **kwargs)

    # Imported lazily to avoid a circular import with jerp.env.
    from jerp.env import Environment

    Environment.instance.router.add_route(method, endpoint, wrapper, auth=auth)
    return wrapper

  return decorator


def get(endpoint, auth=False):
  return route(RequestMethod.GET, endpoint, auth=auth)


def post(endpoint, auth=False):
  return route(RequestMethod.POST, endpoint, auth=auth)


def put(endpoint, auth=False):
  return route(RequestMethod.PUT, endpoint, auth=auth)


def delete(endpoint, auth=False):
  return route(RequestMethod.DELETE, endpoint, auth=auth)


def patch(endpoint, auth=False):
  return route(RequestMethod.PATCH, endpoint, auth=auth)


def options(endpoint, auth=False):
  return route(RequestMethod.OPTIONS, endpoint, auth=auth)


def head(endpoint, auth=False):
  return route(RequestMethod.HEAD, endpoint, auth=auth)


def _compile_pattern(endpoint: str):
  """Compile an endpoint containing ``<name>`` segments into a regex."""

  if '<' not in endpoint:
    return None
  regex = ['^']
  for index, part in enumerate(endpoint.split('/')):
    if index == 0 and part == '':
      continue  # leading slash
    regex.append('/')
    match = re.fullmatch(r'<([A-Za-z_]\w*)>', part)
    if match:
      regex.append(f'(?P<{match.group(1)}>[^/]+)')
    else:
      regex.append(re.escape(part))
  regex.append('$')
  return re.compile(''.join(regex))


class Router:
  def __init__(self):
    self.routes: dict = {}
    self._patterns: list = []

  def add_route(self, method, endpoint, handler, auth=False):
    route = {'handler': handler, 'auth': auth}
    self.routes[(method, endpoint)] = route

    compiled = _compile_pattern(endpoint)
    if compiled is None:
      return
    # Replace any previous pattern for the same endpoint (e.g. re-registered
    # with a bound controller method).
    self._patterns = [
      pattern
      for pattern in self._patterns
      if not (pattern[0] == method and pattern[1] == endpoint)
    ]
    self._patterns.append((method, endpoint, compiled, route))

  def get_route(self, method, endpoint):
    """Return ``(route, params)`` for a match, or ``None``."""

    if isinstance(method, RequestMethod):
      method = method.value
    method = str(method).upper()

    route = self.routes.get((method, endpoint))
    if route is not None:
      return route, {}

    for pattern_method, _pattern_endpoint, regex, pattern_route in self._patterns:
      if pattern_method != method:
        continue
      match = regex.match(endpoint)
      if match is not None:
        return pattern_route, match.groupdict()

    return None

  def dispatch(self, method, endpoint, request=None):
    match = self.get_route(method, endpoint)
    if match is None:
      raise RouteNotFound(f'No route found for {method} {endpoint}')

    route, params = match

    # Imported lazily to avoid a circular import with jerp.env.
    from jerp.http.middleware import database_scope
    from jerp.http.request import bind

    with database_scope(request), bind(request):
      return route['handler'](**params)
