"""Development/production HTTP server for J-ERP.

Serves:

* ``/api/*``       -> the framework router (request-scoped database)
* ``/views/<m>/*`` -> built module view bundles (``data/view/<m>``)
* ``/__assets/<m>/*`` -> raw module assets (``modules/<m>/ui/assets``)
* everything else  -> the built UI (``data/ui``), with an SPA fallback

Built on the standard library only.
"""

from __future__ import annotations

import logging
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from jerp.http.request import Request
from jerp.http.response import (
  Response,
  json,
  not_found,
  redirect,
  server_error,
  make_response,
)
from jerp.http.router import RouteNotFound

logger = logging.getLogger('jerp.server')

VIEWS_PREFIX = '/views/'
ASSET_PREFIX = '/__assets/'
STORAGE_PREFIX = '/__storage/'
ENDPOINTS_PATH = '/__endpoints'
MODULES_PATH = '/__modules'


class Application:
  """Turns a :class:`~jerp.http.request.Request` into a :class:`Response`."""

  def __init__(
    self,
    environment,
    static_dir: str | Path,
    modules_dir: str | Path = 'modules',
    views_dir: str | Path = 'cache/view',
    api_prefix: str = '/api',
    index_file: str = 'index.html',
  ):
    self.environment = environment
    self.static_dir = Path(static_dir).resolve()
    self.modules_dir = Path(modules_dir).resolve()
    self.views_dir = Path(views_dir).resolve()
    self.api_prefix = api_prefix.rstrip('/')
    self.index_file = index_file

  # --- entry point --------------------------------------------------------

  def handle(self, request: Request) -> Response:
    try:
      return self._handle(request)
    except RouteNotFound:
      return not_found(f'No route for {request.method} {request.path}')
    except Exception:  # pragma: no cover - defensive
      logger.exception('Unhandled error for %s %s', request.method, request.path)
      return server_error('Unhandled server error')

  def _handle(self, request: Request) -> Response:
    path = request.path

    # The dev server reads this to build its proxies (no hardcoded prefixes).
    if path == ENDPOINTS_PATH:
      return self._endpoints()

    # The dev server uses this to hide menus for modules that are not installed
    # in the database selected by the browser cookie.
    if path == MODULES_PATH:
      return self._modules(request)

    if path == self.api_prefix or path.startswith(self.api_prefix + '/'):
      return self._dispatch(request, strip=len(self.api_prefix))

    if path.startswith(VIEWS_PREFIX):
      return self._views_file(path[len(VIEWS_PREFIX):])

    if path.startswith(ASSET_PREFIX):
      return self._asset_file(path[len(ASSET_PREFIX):])

    # A selected database that no longer exists: clear the cookie, go to the manager.
    if request.method in ('GET', 'HEAD') and self._wants_html(request):
      stale = self._stale_database(request, path)
      if stale is not None:
        return stale

    if request.method in ('GET', 'HEAD'):
      file = self._safe_file(self.static_dir, path.lstrip('/'))
      if file is not None:
        return self._serve_file(file)

    # Server-rendered pages (registered routes) take precedence over the SPA
    # fallback, so controllers can render views and issue redirects.
    if self.environment.router.get_route(request.method, path) is not None:
      return self._dispatch(request)

    if request.method in ('GET', 'HEAD') and self._wants_html(request):
      return self._serve_index()

    return self._dispatch(request)

  # --- dispatch -----------------------------------------------------------

  def _endpoints(self) -> Response:
    """The backend's URL prefixes (used by Vite dev to build its proxies)."""

    return json({
      'endpoints': [
        self.api_prefix,
        VIEWS_PREFIX.rstrip('/'),
        ASSET_PREFIX.rstrip('/'),
        STORAGE_PREFIX.rstrip('/'),
      ],
    })

  def _modules(self, request: Request) -> Response:
    """Modules installed in the database selected for this request."""

    from jerp.env import Environment

    active = request.database()
    if not active:
      return json({'modules': []})
    try:
      registry = Environment.instance.registry(active)
      modules = list(registry.module_manager.installed())
    except Exception:
      modules = []
    return json({'modules': modules})

  def _dispatch(self, request: Request, strip: int = 0) -> Response:
    endpoint = request.path[strip:] if strip else request.path
    if not endpoint.startswith('/'):
      endpoint = '/' + endpoint

    # Router.dispatch applies the request-scoped database middleware.
    result = self.environment.router.dispatch(request.method, endpoint, request)
    return make_response(result)

  def _stale_database(self, request: Request, path: str) -> Response | None:
    """If the ``jerp_db`` cookie points at a missing database, clear it."""

    if path == '/db/manager':
      return None

    selected = request.database()
    if not selected:
      return None

    try:
      if self.environment.databases.exists(selected):
        return None
    except Exception:
      return None

    result = redirect('/db/manager')
    result.headers['Set-Cookie'] = 'jerp_db=; Path=/; Max-Age=0; SameSite=Lax'
    return result

  def _views_file(self, rest: str) -> Response:
    # /views/<module>/<file> -> cache/view/<module>/<file>
    module, _, relative = rest.partition('/')
    if not module or not relative:
      return not_found('Not Found')
    file = self._safe_file(self.views_dir / module, relative)
    if file is None:
      return not_found('Not Found')
    return self._serve_file(file)

  def _asset_file(self, rest: str) -> Response:
    # /__assets/<module>/<file> -> modules/<module>/ui/assets/<file>
    module, _, relative = rest.partition('/')
    if not module or not relative:
      return not_found('Not Found')
    file = self._safe_file(self.modules_dir / module / 'ui' / 'assets', relative)
    if file is None:
      return not_found('Not Found')
    return self._serve_file(file)

  # --- static files -------------------------------------------------------

  @staticmethod
  def _safe_file(base: Path, relative: str) -> Path | None:
    if not relative:
      return None
    base = base.resolve()
    candidate = (base / relative).resolve()
    if base not in candidate.parents and candidate != base:
      return None  # path traversal
    return candidate if candidate.is_file() else None

  def _serve_file(self, path: Path) -> Response:
    content_type, _ = mimetypes.guess_type(str(path))
    headers = {'Cache-Control': 'no-cache'}
    if content_type:
      headers['Content-Type'] = content_type
    return Response(path.read_bytes(), status=200, headers=headers)

  def _serve_index(self) -> Response:
    # Render the shell (with the installed modules' view map injected) so the
    # client bootstrap can mount the default view.
    from jerp import views

    try:
      html = views.render()
    except FileNotFoundError:
      return server_error(
        f'UI build not found at {self.static_dir}. Run "npm run build".'
      )
    return Response(
      html.encode('utf-8'),
      status=200,
      headers={'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-cache'},
    )

  @staticmethod
  def _wants_html(request: Request) -> bool:
    return 'text/html' in request.headers.get('accept', '')


class _RequestHandler(BaseHTTPRequestHandler):
  protocol_version = 'HTTP/1.1'
  server_version = 'J-ERP/1.0'

  def log_message(self, fmt, *args):
    logger.info('%s - %s', self.address_string(), fmt % args)

  def _read_body(self) -> bytes:
    try:
      length = int(self.headers.get('Content-Length') or 0)
    except ValueError:
      length = 0
    return self.rfile.read(length) if length > 0 else b''

  def _respond(self, method: str) -> None:
    request = Request.from_http(method, self.path, self.headers, self._read_body())
    response = self.server.application.handle(request)

    body = response.body or b''
    self.send_response(response.status)
    for name, value in response.headers.items():
      self.send_header(name, value)
    self.send_header('Content-Length', str(len(body)))
    self.end_headers()
    if method != 'HEAD' and body:
      self.wfile.write(body)

  def do_GET(self):
    self._respond('GET')

  def do_HEAD(self):
    self._respond('HEAD')

  def do_POST(self):
    self._respond('POST')

  def do_PUT(self):
    self._respond('PUT')

  def do_PATCH(self):
    self._respond('PATCH')

  def do_DELETE(self):
    self._respond('DELETE')

  def do_OPTIONS(self):
    self._respond('OPTIONS')


def create_server(
  environment,
  host: str = '127.0.0.1',
  port: int = 1347,
  static_dir: str | Path = 'data/ui',
  modules_dir: str | Path = 'modules',
  views_dir: str | Path = 'data/view',
  api_prefix: str = '/api',
) -> ThreadingHTTPServer:
  application = Application(
    environment,
    static_dir,
    modules_dir=modules_dir,
    views_dir=views_dir,
    api_prefix=api_prefix,
  )
  httpd = ThreadingHTTPServer((host, port), _RequestHandler)
  httpd.daemon_threads = True
  httpd.application = application
  return httpd


def serve(
  environment,
  host='127.0.0.1',
  port=1347,
  static_dir='data/ui',
  modules_dir='modules',
  views_dir='data/view',
  api_prefix='/api',
):
  httpd = create_server(environment, host, port, static_dir, modules_dir, views_dir, api_prefix)
  logger.info(
    'J-ERP serving on http://%s:%s (static: %s)', host, port, httpd.application.static_dir
  )
  try:
    httpd.serve_forever()
  except KeyboardInterrupt:
    logger.info('Shutting down')
  finally:
    httpd.server_close()
    environment.databases.close_all()
