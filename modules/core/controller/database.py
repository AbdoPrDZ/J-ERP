"""Database management endpoints (list / create / select / drop).

Mounted under ``/api`` so the client calls ``/api/databases`` etc. Selecting a
database sets the ``jerp_db`` cookie, which the request middleware then uses to
scope the active database for subsequent requests.
"""

from __future__ import annotations

from urllib.parse import quote

from jerp import i18n, security
from jerp.db import DatabaseInUseError, is_valid_database_name
from jerp.env import Environment
from jerp.http import controller, request, response, router

#: Databases that must never be dropped from the UI/API.
PROTECTED_DATABASES = {'postgres', 'template0', 'template1'}


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
    denied = self._check_master_key(payload)
    if denied is not None:
      return denied

    name = str(payload.get('name') or '')
    if not is_valid_database_name(name):
      return response.json(
        {'error': 'invalid_name',
         'message': (
           'Use a non-empty name up to 63 bytes. Uppercase letters, spaces '
           'and punctuation are allowed.'
         )},
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
      admin_model = registry.get('sys.user')
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
    name = str(self._payload().get('name') or '')
    manager = Environment.instance.databases
    if not name or not manager.exists(name):
      return response.json(
        {'error': 'not_found', 'message': f'Database "{name}" does not exist.'},
        status=404,
      )

    result = response.json({'selected': name})
    result.headers['Set-Cookie'] = (
      f'jerp_db={quote(name, safe="")}; Path=/; SameSite=Lax'
    )
    return result

  @router.post('/databases/delete')
  def delete(self):
    """Drop a database and all of its data.

    Requires ``confirm`` to equal the database name. The active database's
    cookie is cleared so the next request returns to the manager.
    """

    payload = self._payload()
    denied = self._check_master_key(payload)
    if denied is not None:
      return denied

    name = str(payload.get('name') or '')
    confirm = str(payload.get('confirm') or '')

    if not is_valid_database_name(name):
      return response.json(
        {'error': 'invalid_name',
         'message': 'Invalid database name.'},
        status=400,
      )
    if name in PROTECTED_DATABASES:
      return response.json(
        {'error': 'protected',
         'message': f'Database "{name}" is protected and cannot be deleted.'},
        status=400,
      )
    if confirm != name:
      return response.json(
        {'error': 'confirm_required',
         'message': f'Type "{name}" to confirm deletion.'},
        status=400,
      )

    environment = Environment.instance
    manager = environment.databases
    if not manager.exists(name):
      return response.json(
        {'error': 'not_found', 'message': f'Database "{name}" does not exist.'},
        status=404,
      )

    active = environment.active_database == name
    try:
      manager.drop(name)
    except DatabaseInUseError as exc:
      sessions = ', '.join(
        f"{row.get('usename') or '?'} "
        f"({row.get('application_name') or 'unknown client'})"
        for row in exc.sessions
      )
      message = i18n._t(
        'error.database_in_use',
        'Cannot delete "{name}" while it is used by: {sessions}.',
        name=name,
        sessions=sessions,
      )
      if exc.admin_error is not None:
        hint = i18n._t(
          'error.database_admin_failed',
          'The admin force-drop failed: {error}. Check '
          'databases.admin_user / admin_password.',
          error=exc.admin_error,
        )
      else:
        hint = i18n._t(
          'error.database_in_use_hint',
          'Close those connections or configure databases.admin_user / '
          'admin_password to force the drop.',
        )
      return response.json(
        {'error': 'database_in_use', 'message': f'{message} {hint}'},
        status=409,
      )
    except Exception as exc:
      return response.json(
        {'error': 'delete_failed', 'message': str(exc)}, status=500
      )

    result = response.json({'deleted': name, 'active': active})
    if active:
      result.headers['Set-Cookie'] = 'jerp_db=; Path=/; Max-Age=0; SameSite=Lax'
    return result

  @staticmethod
  def _payload() -> dict:
    req = request.current()
    return req.json() if req is not None else {}

  @staticmethod
  def _check_master_key(payload: dict):
    """Validate the manager master key before a destructive operation."""

    expected = Environment.instance.databases.config.master_key
    if not expected:
      return response.json(
        {
          'error': 'master_key_not_configured',
          'message': (
            'No master key is configured. Set security.master_key in '
            'jerp.config.json or the JERP_MASTER_KEY environment variable.'
          ),
        },
        status=503,
      )

    supplied = str(payload.get('master_key') or '')
    if not security.verify_secret(supplied, expected):
      return response.json(
        {'error': 'invalid_master_key', 'message': 'Invalid master key.'},
        status=403,
      )
    return None
