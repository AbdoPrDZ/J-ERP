"""Temporary record API used by form-embedded tables.

Temporary records live in ``temp.model``. They are grouped by a random token and
are moved into the target model by :func:`commit` once the parent record exists.
"""

from __future__ import annotations

import json

from jerp.env import Environment
from jerp.http import controller, request, response, router


def _error(message: str, status: int = 400):
  return response.json({'error': 'temp_error', 'message': message}, status=status)


def _load_data(record) -> dict:
  try:
    data = json.loads(record.data or '{}')
  except (TypeError, ValueError):
    data = {}
  if not isinstance(data, dict):
    data = {}
  data['id'] = record.id
  return data


def _sort_value(value):
  if value is None:
    return (1, '')
  if isinstance(value, bool):
    return (0, int(value))
  if isinstance(value, (int, float)):
    return (0, float(value))
  return (0, str(value))


class TempApiController(controller.Controller):

  @router.post('/temp/<model_name>/<func>')
  def call(self, model_name, func):
    if not Environment.instance.active_database:
      return response.json(
        {'error': 'no_database', 'message': 'No database is selected.'},
        status=400,
      )

    registry = Environment.instance.registry()
    registry.ensure_loaded()
    model = registry.get(model_name)
    if model is None or getattr(model, '_virtual', False):
      return _error(f'Unknown model "{model_name}".', status=404)

    Temp = registry.get('temp.model')
    if Temp is None:
      return _error('The temporary model is not installed.', status=404)

    body = request.current().json() if request.current() else {}
    token = str(body.get('token') or '').strip()
    if not token:
      return _error('A temporary token is required.')

    domain = [('token', '=', token), ('model', '=', model_name)]

    if func == 'all':
      records = Temp.search(domain, order='id')
      rows = [_load_data(record) for record in records]
      order = body.get('order')
      if order:
        specs = [
          part.strip() for part in str(order).split(',') if part.strip()
        ]
        for spec in reversed(specs):
          tokens = spec.split()
          name = tokens[0]
          reverse = len(tokens) > 1 and tokens[1].lower() == 'desc'
          rows.sort(
            key=lambda row: _sort_value(row.get(name)),
            reverse=reverse,
          )
      offset = int(body.get('offset') or 0)
      if offset:
        rows = rows[offset:]
      limit = body.get('limit')
      if limit is not None:
        rows = rows[:int(limit)]
      return response.json({'result': rows})

    if func == 'count':
      return response.json({'result': len(Temp.search(domain))})

    if func == 'find':
      record = self._find(Temp, domain, body.get('id'))
      return response.json({'result': _load_data(record) if record else None})

    if func == 'create':
      values = self._values(model, body)
      record = Temp.create(
        token=token,
        model=model_name,
        data=json.dumps(values),
      )
      return response.json({'result': _load_data(record)})

    if func == 'update':
      record = self._find(Temp, domain, body.get('id'))
      if record is None:
        return _error('Temporary record not found.', status=404)
      current = _load_data(record)
      current.pop('id', None)
      current.update(self._values(model, body))
      record.write({'data': json.dumps(current)})
      return response.json({'result': _load_data(record)})

    if func == 'delete':
      record = self._find(Temp, domain, body.get('id'))
      return response.json({'result': bool(record and record.unlink())})

    if func == 'delete_many':
      ids = [int(value) for value in (body.get('ids') or [])]
      if not ids:
        return response.json({'result': 0})
      deleted = 0
      for record in Temp.search(domain + [('id', 'in', ids)]):
        if record.unlink():
          deleted += 1
      return response.json({'result': deleted})

    if func == 'commit':
      parent_field = str(body.get('parent_field') or '')
      parent_id = body.get('parent_id')
      if not parent_field or parent_id in (None, ''):
        return _error('A parent field and parent id are required.')
      if parent_field not in model._fields:
        return _error(f'Unknown parent field "{parent_field}".')

      created = 0
      for record in Temp.search(domain, order='id'):
        values = _load_data(record)
        values.pop('id', None)
        values[parent_field] = parent_id
        model.create(**values)
        record.unlink()
        created += 1
      return response.json({'result': created})

    return _error(f'Unknown temporary function "{func}".', status=404)

  @staticmethod
  def _find(Temp, domain, record_id):
    if record_id in (None, ''):
      return None
    rows = Temp.search(domain + [('id', '=', record_id)], limit=1)
    return rows[0] if rows else None

  @staticmethod
  def _values(model, body) -> dict:
    values = body.get('values')
    if not isinstance(values, dict):
      return {}
    # Keep only real model fields; relational ids and simple values are enough.
    filtered = {
      name: value
      for name, value in values.items()
      if name in model._fields and name not in ('id', 'created_at', 'updated_at')
    }
    return model.temp_values(filtered)
