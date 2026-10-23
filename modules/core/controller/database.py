"""Database management endpoints (list / create / select / drop).

Mounted under ``/api`` so the client calls ``/api/databases`` etc. Selecting a
database sets the ``jerp_db`` cookie, which the request middleware then uses to
scope the active database for subsequent requests.
"""

from __future__ import annotations

import re

from jerp.env import Environment
from jerp.http import controller, request, response, router

_NAME_RE = re.compile(r'^[a-z_][a-z0-9_]{0,62}$')


class DatabaseController(controller.Controller):

  @router.get('/databases')
  def index(self):
    environment = Environment.instance
    manager = environment.databases
    error = None
    try:
      databases = manager.list_databases()
    except Exception as exc:  # database unreachable
      databases = []
      error = str(exc)
    return response.json({
      'databases': databases,
      'active': environment.active_database,
      'error': error,
    })

  @router.post('/databases')
  def create(self):
    payload = self._payload()
    name = str(payload.get('name') or '').strip().lower()
    if not _NAME_RE.match(name):
      return response.json(
        {'error': 'invalid_name',
         'message': 'Use lowercase letters, digits and underscores (max 63).'},
        status=400,
      )

    admin_login = str(payload.get('admin_login') or 'admin').strip() or 'admin'
    admin_password = str(payload.get('admin_password') or '')
    if not admin_password:
      return response.json(
        {'error': 'password_required', 'message': 'An admin password is required.'},
        status=400,
      )

    environment = Environment.instance
    manager = environment.databases
    try:
      if manager.exists(name):
        return response.json(
          {'error': 'exists', 'message': f'Database "{name}" already exists.'},
          status=409,
        )

      # Create the database and install its modules (core by default).
      manager.create(name)
      modules = payload.get('modules') or ['core']
      registry = manager.registry(name)
      for module in modules:
        registry.install(module)

      # Seed the admin user inside the new database.
      admin_model = registry.get('user')
      if admin_model is not None:
        with environment.using(name):
          admin_model.create(
            username=admin_login,
            name=admin_login,
            password=admin_password,
          )

      return response.json(
        {'created': name, 'modules': list(modules), 'admin': admin_login},
        status=201,
      )
    except Exception as exc:
      return response.json(
        {'error': 'create_failed', 'message': str(exc)}, status=500
      )

  @router.post('/databases/select')
  def select(self):
    name = str(self._payload().get('name') or '').strip()
    manager = Environment.instance.databases
    if not name or not manager.exists(name):
      return response.json(
        {'error': 'not_found', 'message': f'Database "{name}" does not exist.'},
        status=404,
      )

    result = response.json({'selected': name})
    result.headers['Set-Cookie'] = f'jerp_db={name}; Path=/; SameSite=Lax'
    return result

  @staticmethod
  def _payload() -> dict:
    req = request.current()
    return req.json() if req is not None else {}
