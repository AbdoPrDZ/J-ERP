"""Model API endpoint.

``POST /api/model/<model_name>/<func>`` calls an exposed method on the model,
passing the JSON body as keyword arguments:

* standard methods: ``all``, ``count``, ``find``, ``create``, ``update``, ``delete``
* any custom method decorated with ``@jerp.http.api_expose``

The response is ``{"result": <value>}``.
"""

from __future__ import annotations

from jerp import sessions
from jerp.env import Environment
from jerp.http import controller, request, response, router
from jerp.models import Model

#: System models whose records only administrators may read or change. Module
#: lifecycle lives on the virtual ``module`` model, which guards itself.
ADMIN_ONLY_MODELS = frozenset({
  'sys.module',
  'sys.model',
  'sys.field',
  'sys.session',
  'sys.translation',
})


def _serialize(value):
  if isinstance(value, Model):
    return type(value)._as_dict(value)
  if isinstance(value, (list, tuple)):
    return [_serialize(item) for item in value]
  return value


class ModelApiController(controller.Controller):

  @router.post('/model/<model_name>/<func>')
  def call(self, model_name, func):
    if not Environment.instance.active_database:
      return response.json(
        {'error': 'no_database', 'message': 'No database is selected.'}, status=400
      )

    registry = Environment.instance.registry()
    registry.ensure_loaded()
    model = registry.get(model_name)
    if model is None:
      return response.json(
        {'error': 'unknown_model', 'message': f'Unknown model "{model_name}".'},
        status=404,
      )

    if model_name in ADMIN_ONLY_MODELS:
      try:
        sessions.require_admin()
      except PermissionError as exc:
        return response.json({'error': 'forbidden', 'message': str(exc)}, status=403)

    methods = getattr(model, '_api_methods', {}) or {}
    if func not in methods:
      return response.json(
        {'error': 'unknown_method',
         'message': f'Method "{func}" is not exposed on "{model_name}".'},
        status=404,
      )

    body = request.current().json() if request.current() else {}

    try:
      result = model.call_exposed(func, body)
    except TypeError as exc:
      return response.json(
        {'error': 'bad_arguments', 'message': str(exc)}, status=400
      )
    except PermissionError as exc:
      return response.json({'error': 'forbidden', 'message': str(exc)}, status=403)
    except Exception as exc:
      return response.json(
        {'error': 'call_failed', 'message': str(exc)}, status=400
      )

    return response.json({'result': _serialize(result)})
