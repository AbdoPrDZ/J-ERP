"""Global search endpoints used by the drawer command palette.

``GET /api/models`` returns the available model -> page map (never cached) and
``GET /api/search?model=<model>&q=<text>`` searches one model's records by
display label. Menus are searched client-side from ``GET /api/menu``.
"""

from __future__ import annotations

import logging

from jerp.env import Environment
from jerp.http import controller, request, response, router

logger = logging.getLogger('jerp.search')


def _logged_in() -> bool:
  req = request.current()
  return bool(req and req.cookies.get('jerp_user'))


class SearchController(controller.Controller):

  @router.get('/search')
  def search(self):
    if not _logged_in():
      return response.json(
        {'error': 'not_authenticated', 'message': 'Login required.'},
        status=401,
      )

    environment = Environment.instance
    if not environment.active_database:
      return response.json(
        {'error': 'no_database', 'message': 'No database is selected.'},
        status=400,
      )

    req = request.current()
    query = dict(req.query) if req else {}
    model_name = str(query.get('model') or '').strip()
    text = str(query.get('q') or '').strip()

    try:
      limit = max(1, min(int(query.get('limit') or 10), 25))
    except (TypeError, ValueError):
      limit = 10

    if not model_name or not text:
      return response.json({'model': model_name, 'results': []})

    registry = environment.registry()
    registry.ensure_loaded()
    model = registry.get(model_name)
    if model is None:
      return response.json(
        {
          'error': 'unknown_model',
          'message': f'Unknown model "{model_name}".',
        },
        status=404,
      )

    return response.json(
      {'model': model._name, 'results': self._search(model, text, limit)}
    )

  @router.get('/models')
  def available_models(self):
    """Models exposed by installed pages, refreshed on every search open."""

    environment = Environment.instance
    active = environment.active_database
    if not active:
      result = response.json({'models': {}})
      result.headers['Cache-Control'] = 'no-store'
      return result

    try:
      from jerp import views

      registry = environment.registry(active)
      registry.ensure_loaded()
      installed = set(registry.module_manager.installed())
      config = environment.databases.config
      pages = views.collect_pages(config.modules_path, installed)
      models = views.collect_model_views(pages, installed, config.views_dir)
    except Exception as exc:
      logger.exception('Could not load available models for %s', active)
      return response.json(
        {'models': {}, 'error': 'models_failed', 'message': str(exc)},
        status=500,
      )

    result = response.json({'models': models})
    result.headers['Cache-Control'] = 'no-store'
    return result

  @staticmethod
  def _search(model, text: str, limit: int) -> list[dict]:
    """Records whose display label matches ``text`` (case-insensitive)."""

    needle = text.casefold()

    if getattr(model, '_virtual', False):
      # Virtual models expose their records without SQL; filter them here.
      results = []
      for record in model.all(limit=500):
        label = str(record.get('_label') or record.get('name') or '')
        if needle in label.casefold():
          results.append({'id': record.get('id'), 'label': label})
          if len(results) >= limit:
            break
      return results

    field = getattr(model, '_label', None) or 'name'
    if field not in model._fields:
      # No text label to search (for example sys.field); return no matches.
      return []

    records = model.search([[field, 'ilike', f'%{text}%']], order=field, limit=limit)
    return [
      {'id': record.id, 'label': model.display_name(record)}
      for record in records
    ]
