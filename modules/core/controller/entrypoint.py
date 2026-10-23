from __future__ import annotations

from urllib.parse import quote

from jerp.env import Environment
from jerp.http import controller, request, response, router


def _logged_in() -> bool:
  req = request.current()
  return bool(req and req.cookies.get('jerp_user'))


class EntryPointController(controller.Controller):
  """Only routes that need logic. Plain pages come from the modules'
  ``configure.json`` (see jerp.routes)."""

  @router.route('/')
  def index(self):
    """Home: route to login, or to the database manager / selected database."""

    environment = Environment.instance
    manager = environment.databases

    if _logged_in():
      return response.redirect('/home')

    if environment.active_database:
      return response.redirect('/login')

    try:
      databases = manager.list_databases()
    except Exception:
      databases = []

    # A single database is selected automatically.
    if len(databases) == 1:
      result = response.redirect('/login')
      result.headers['Set-Cookie'] = (
        f'jerp_db={quote(databases[0], safe="")}; Path=/; SameSite=Lax'
      )
      return result

    return response.redirect('/db/manager')

  @router.route('/view')
  def standard_view(self):
    """Standard endpoint for pages without an explicit endpoint.

    ``/view?name=<view>&<params>`` renders a view by name; the remaining query
    parameters become the view context.
    """

    req = request.current()
    query = dict(req.query) if req else {}
    name = query.pop('name', None)

    if name:
      from jerp import views

      if not views.view_installed(name):
        return response.not_found(
          f'View "{name}" is not installed in this database.'
        )
      if views.view_auth(name) and not _logged_in():
        return response.redirect('/login')
      return response.render(name, query)

    # Descriptor-based rendering (``/view?model=<model>&type=<table|form|cards>``).
    if not _logged_in():
      return response.redirect('/login')

    model_name = str(query.get('model') or '')
    view_type = str(query.get('type') or 'table')

    registry = Environment.instance.registry()
    registry.ensure_loaded()
    model = registry.get(model_name)
    if model is None:
      return response.json(
        {'error': 'unknown_model', 'message': f'Unknown model "{model_name}".'},
        status=404,
      )

    descriptor = model.view_descriptor(view_type)
    field_names = [f['name'] for f in descriptor['fields']]
    records = model.all(fields=field_names, limit=50)

    return response.render('jerp.view', {'view': descriptor, 'records': records})
