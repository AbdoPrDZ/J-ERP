"""View rendering + page/route/menu collection.

Modules declare a single ``routes`` tree in ``configure.json``. Each entry is
either:

* a **page**: ``view`` (+ optional ``endpoint``, ``params``, ``label``, ``img``,
  ``auth``, ``header``, ``menu``, ``hide``)
* a **group**: ``label`` + ``children`` (no ``view``)

Every entry must have a ``view`` or ``children`` (otherwise a ``ValueError`` is
raised). Pages with an ``endpoint`` become server routes; pages without one are
served by ``/view?name=<view>``. Labelled entries become the (nested) menu.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlencode

#: Specifier -> url. ``react`` and friends share one instance via react-runtime.js.
IMPORT_MAP = {
  'react': '/react-runtime.js',
  'react/jsx-runtime': '/react-runtime.js',
  'react-dom': '/react-runtime.js',
  'react-dom/client': '/react-runtime.js',
  '@jerp/ui': '/runtime.js',
}

HEAD_MARKER = '<!--jerp:head-->'
BODY_MARKER = '<!--jerp:body-->'
VIEW_ATTR = 'data-view=""'


def collect_views(module_names, cache_dir: str | Path = 'data/view') -> dict[str, str]:
  """View name -> url, from the cached build manifests (``data/view/<m>``)."""

  cache_dir = Path(cache_dir)
  result: dict[str, str] = {}

  for name in module_names:
    manifest = cache_dir / name / 'manifest.json'
    if not manifest.is_file():
      continue
    try:
      data = json.loads(manifest.read_text(encoding='utf-8'))
    except (OSError, ValueError):
      continue
    for key, filename in (data.get('views') or {}).items():
      result[key] = f'/views/{name}/{filename}'

  return result


# --- declarations ---------------------------------------------------------


def _read_module_entries(modules_dir: str | Path, module_names):
  modules_dir = Path(modules_dir)
  for name in module_names:
    manifest = modules_dir / name / 'configure.json'
    if not manifest.is_file():
      continue
    try:
      data = json.loads(manifest.read_text(encoding='utf-8'))
    except (OSError, ValueError):
      continue
    entries = data.get('routes') or data.get('pages') or []
    _validate_entries(entries, name)
    yield name, entries


def _validate_entries(entries, module_name: str) -> None:
  for item in entries:
    if not isinstance(item, dict):
      raise ValueError(f'[{module_name}] entry must be an object, got {item!r}')
    if not item.get('view') and not item.get('children'):
      label = item.get('label') or '(unlabelled)'
      raise ValueError(
        f'[{module_name}] entry "{label}" needs a "view" or "children"'
      )
    if item.get('children'):
      _validate_entries(item['children'], module_name)


def _iter_entries(entries):
  for item in entries:
    yield item
    yield from _iter_entries(item.get('children') or [])


def _normalize(item: dict) -> dict:
  return {
    'view': item['view'],
    'label': item.get('label'),
    'endpoint': item.get('endpoint') or item.get('path'),
    'params': dict(item.get('params') or {}),
    'img': item.get('img'),
    'auth': bool(item.get('auth', True)),
    'header': bool(item.get('header', True)),
    'menu': bool(item.get('menu', True)),
    'hide': bool(item.get('hide', False)),
  }


def collect_pages(modules_dir: str | Path, module_names) -> list[dict]:
  """Flat list of normalized page declarations."""

  pages: list[dict] = []
  for _name, entries in _read_module_entries(modules_dir, module_names):
    for item in _iter_entries(entries):
      if item.get('view'):
        pages.append(_normalize(item))
  return pages


def menu_href(page: dict) -> str:
  endpoint = page.get('endpoint')
  params = dict(page.get('params') or {})
  if endpoint:
    return endpoint + (('?' + urlencode(params)) if params else '')
  return '/view?' + urlencode({'name': page['view'], **params})


def _menu_node(item: dict):
  if item.get('hide') or not item.get('label'):
    return None

  node: dict = {'label': item['label'], 'sequence': item.get('sequence', 0)}
  if item.get('view'):
    node['href'] = menu_href(_normalize(item))
    node['auth'] = bool(item.get('auth', True))
  if item.get('img'):
    node['img'] = item['img']

  children = [
    child
    for child in (_menu_node(c) for c in item.get('children') or [])
    if child
  ]
  if children:
    children.sort(key=lambda n: (n.get('sequence', 0), n['label']))
    node['children'] = children
  return node


def collect_menu_tree(modules_dir: str | Path, module_names) -> list[dict]:
  """Nested menu built from the labelled entries, sorted by ``sequence``."""

  tree: list[dict] = []
  for _name, entries in _read_module_entries(modules_dir, module_names):
    for item in entries:
      node = _menu_node(item)
      if node:
        tree.append(node)
  tree.sort(key=lambda n: (n.get('sequence', 0), n['label']))
  return tree


def routes_from_pages(pages) -> dict[str, str]:
  """endpoint -> view (only pages that declare an endpoint)."""

  return {page['endpoint']: page['view'] for page in pages if page.get('endpoint')}


def view_auth(view_name: str) -> bool:
  """Whether a view requires login (defaults to ``True``)."""

  config = _config()
  modules = _installed_modules(config)
  for page in collect_pages(config.modules_path, modules):
    if page['view'] == view_name:
      return page['auth']
  return True


class ViewRenderer:
  def __init__(self, dist_dir: str | Path = 'data/ui'):
    self.dist_dir = Path(dist_dir)
    self._shell: str | None = None
    self._shell_mtime: int | None = None

  def shell(self) -> str:
    index = self.dist_dir / 'index.html'
    mtime = index.stat().st_mtime_ns
    if self._shell is None or self._shell_mtime != mtime:
      self._shell = index.read_text(encoding='utf-8')
      self._shell_mtime = mtime
    return self._shell

  def render(self, view_key, context, views, menus=None, routes=None, pages=None) -> str:
    html = self.shell()

    import_map = (
      '<script type="importmap">'
      + json.dumps({'imports': IMPORT_MAP})
      + '</script>'
    )

    body = '\n'.join([
      '<script id="__JERP_VIEWS__" type="application/json">'
      + json.dumps(views) + '</script>',
      '<script id="__JERP_ROUTES__" type="application/json">'
      + json.dumps(routes or {}) + '</script>',
      '<script id="__JERP_PAGES__" type="application/json">'
      + json.dumps(pages or {}) + '</script>',
      '<script id="__JERP_MENUS__" type="application/json">'
      + json.dumps(menus or []) + '</script>',
      '<script id="__JERP_CONTEXT__" type="application/json">'
      + json.dumps(context or {}, default=str) + '</script>',
    ])

    html = html.replace(HEAD_MARKER, import_map)
    html = html.replace(BODY_MARKER, body)
    if view_key:
      html = html.replace(VIEW_ATTR, f'data-view="{view_key}"')
    return html


_renderer: ViewRenderer | None = None


def _config():
  try:
    from jerp.env import Environment

    return Environment.instance.databases.config
  except Exception:
    from jerp.config import Config

    return Config.load()


def _installed_modules(config):
  # Prefer the loaded registry (the real per-database module set); fall back to
  # the modules discovered on disk when no database is selected/reachable.
  try:
    from jerp.env import Environment

    active = Environment.instance.active_database
    if active:
      registry = Environment.instance.databases.registry(active)
      if registry.ready:
        return registry.list_modules()
  except Exception:
    pass

  modules_dir = Path(config.modules_path)
  if not modules_dir.is_dir():
    return []
  return [
    path.name
    for path in modules_dir.iterdir()
    if (path / 'configure.json').is_file()
  ]


def render(view_key=None, context: dict | None = None) -> str:
  global _renderer

  config = _config()
  if _renderer is None or _renderer.dist_dir != Path(config.ui_dist):
    _renderer = ViewRenderer(config.ui_dist)

  modules = _installed_modules(config)
  views = collect_views(modules, config.views_dir)
  pages = collect_pages(config.modules_path, modules)
  menus = collect_menu_tree(config.modules_path, modules)
  pages_map = {
    page['view']: {
      'auth': page['auth'],
      'header': page['header'],
      'menu': page['menu'],
    }
    for page in pages
  }
  return _renderer.render(
    view_key,
    context or {},
    views,
    menus,
    routes_from_pages(pages),
    pages_map,
  )
