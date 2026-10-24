"""Navigation menu endpoint.

``GET /api/menu`` returns the menu tree stored in ``sys.menu`` for the selected
database. Rows are synchronized from each installed module's ``configure.json``
when the module is installed or updated.
"""

from __future__ import annotations

import logging

from jerp.env import Environment
from jerp.http import controller, response, router
from jerp.menus import load_rows, menu_tree

logger = logging.getLogger('jerp.menu')


class MenuController(controller.Controller):

  @router.get('/menu')
  def index(self):
    environment = Environment.instance
    active = environment.active_database
    if not active:
      result = response.json({'menus': []})
      result.headers['Cache-Control'] = 'no-store'
      return result

    try:
      registry = environment.registry(active)
      registry.ensure_loaded()
      registry.ensure_menus()
      rows = load_rows(registry.db)
      installed = set(registry.module_manager.installed())
      result = response.json({'menus': menu_tree(rows, installed)})
      result.headers['Cache-Control'] = 'no-store'
      return result
    except Exception as exc:
      logger.exception('Could not load menus for database %s', active)
      return response.json(
        {'menus': [], 'error': 'menu_failed', 'message': str(exc)},
        status=500,
      )
