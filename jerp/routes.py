"""Bind declared page endpoints to views.

Pages come from each module's ``configure.json`` ``routes``. A page with an
``endpoint`` gets a server route that renders its view (guarded by login unless
``auth`` is false). Pages without an endpoint are served by the standard
``/view?name=<view>`` endpoint instead.
"""

from __future__ import annotations

from pathlib import Path


def _module_names(modules_dir: str | Path) -> list[str]:
  modules_dir = Path(modules_dir)
  if not modules_dir.is_dir():
    return []
  return [
    path.name
    for path in modules_dir.iterdir()
    if (path / 'configure.json').is_file()
  ]


def _view_handler(view: str, auth: bool):
  def handler():
    from jerp.http import request, response

    if auth:
      req = request.current()
      if not (req and req.cookies.get('jerp_user')):
        return response.redirect('/login')
    return response.render(view, {})

  handler.__name__ = f'view_{view.replace(".", "_")}'
  return handler


def register_view_routes(environment, modules_dir: str | Path) -> list[str]:
  """Register every page that declares an endpoint."""

  from jerp.views import collect_pages

  pages = collect_pages(modules_dir, _module_names(modules_dir))
  registered: list[str] = []
  for page in pages:
    endpoint = page.get('endpoint')
    if not endpoint:
      continue
    environment.router.add_route('GET', endpoint, _view_handler(page['view'], page['auth']))
    registered.append(endpoint)
  return registered
