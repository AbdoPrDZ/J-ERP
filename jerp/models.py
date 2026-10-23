"""Model layer: declarative models, the model registry and a small CRUD API.

``ModelMeta`` collects the :class:`~jerp.fields.Field` instances declared on a
class into an ordered ``_fields`` mapping, derives the table name, and registers
the class in the global :class:`ModelRegistry`. Concrete models subclass
:class:`Model` and get basic create/search/read/write/unlink helpers.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from jerp import fields
from jerp.api import api_expose, is_exposed
from jerp.dialect import quote_ident, quote_table


def to_table_name(class_name: str) -> str:
  """``SysModule`` -> ``sys_module``."""

  return re.sub(r'(?<!^)(?=[A-Z])', '_', class_name).lower()


class ModelRegistry:
  """Global registry of every model class that has been imported."""

  _models: dict[str, type] = {}

  @classmethod
  def register(cls, model) -> None:
    cls._models[model._name] = model

  @classmethod
  def get(cls, name: str):
    return cls._models.get(name)

  @classmethod
  def all(cls) -> dict:
    return dict(cls._models)

  @classmethod
  def clear(cls) -> None:
    cls._models.clear()


class ModelMeta(type):
  """Metaclass that turns class attributes into model metadata."""

  def __new__(mcs, name, bases, attrs):
    cls = super().__new__(mcs, name, bases, attrs)

    # Collect inherited fields first, then this class' own declarations.
    collected: dict[str, fields.Field] = {}
    for base in bases:
      collected.update(getattr(base, '_fields', {}) or {})

    own: dict[str, fields.Field] = {}
    for key, value in attrs.items():
      if isinstance(value, fields.Field):
        if value.column_name is None:
          value.column_name = key
        own[key] = value
    collected.update(own)

    cls._fields = collected

    # API-exposed methods (inherited from bases, then this class' own).
    api_methods: dict[str, str] = {}
    for base in bases:
      api_methods.update(getattr(base, '_api_methods', {}) or {})
    for key, value in attrs.items():
      if is_exposed(value):
        api_methods[key] = key
    cls._api_methods = api_methods

    if attrs.get('_abstract'):
      return cls

    cls._name = attrs.get('_name') or to_table_name(name)
    cls._table = attrs.get('_table') or to_table_name(name)
    if '_virtual' in attrs:
      cls._virtual = bool(attrs['_virtual'])

    ModelRegistry.register(cls)
    return cls


class BaseModel(metaclass=ModelMeta):
  """Abstract base providing the common ``sys`` columns."""

  _abstract = True

  #: Standard view definitions: view type -> list of field names to display.
  #: e.g. ``_views = {'form': ['name'], 'table': ['name'], 'cards': ['name']}``.
  #: A missing/``None`` entry means "all fields".
  _views: dict = {}

  #: Virtual models have no table (their data comes from elsewhere); the schema
  #: syncer skips them.
  _virtual = False

  #: Field used as the record's display label. Defaults to ``name`` when it
  #: exists, otherwise ``"<model>#<id>"``.
  _label: str | None = None

  id = fields.IdField(name='ID')
  created_at = fields.DateTimeField(
    name='Created At', use_tz=True, auto_now_add=True, required=True
  )
  updated_at = fields.DateTimeField(
    name='Updated At', use_tz=True, auto_now=True, required=True
  )

  @classmethod
  def field_schema(cls, only=None) -> list[dict]:
    """Descriptors the client uses to render forms/views.

    ``only`` restricts the result to the given field names (order preserved by
    the model's field order).
    """

    selected = set(only) if only is not None else None
    schema: list[dict] = []
    for name, field in cls._fields.items():
      if field.auto_increment:
        continue
      if selected is not None and name not in selected:
        continue
      entry: dict = {
        'name': name,
        'label': field.name or name,
        'ttype': field.ttype,
        'required': bool(field.required),
        'readonly': bool(field.readonly),
        'hide': bool(field.hide),
      }
      if field.help:
        entry['help'] = field.help
      selection = getattr(field, 'selection', None)
      if selection:
        entry['selection'] = [list(item) for item in selection]
      comodel = getattr(field, 'comodel', None)
      if comodel:
        entry['relation'] = comodel
      schema.append(entry)
    return schema

  @classmethod
  def view_fields(cls, view_type: str):
    """Field names for a standard view type, or ``None`` for "all fields"."""

    spec = (getattr(cls, '_views', None) or {}).get(view_type)
    return None if spec is None else list(spec)

  @classmethod
  def view_descriptor(cls, view_type: str) -> dict:
    """A standard view descriptor the client can render."""

    return {
      'type': view_type,
      'model': cls._name,
      'title': cls._name.replace('_', ' ').title(),
      'fields': cls.field_schema(cls.view_fields(view_type)),
    }


_DOMAIN_OPERATORS = {
  '=': '=',
  '==': '=',
  '!=': '<>',
  '<>': '<>',
  '>': '>',
  '>=': '>=',
  '<': '<',
  '<=': '<=',
  'like': 'LIKE',
  'not like': 'NOT LIKE',
  'ilike': 'ILIKE',
  'not ilike': 'NOT ILIKE',
}


class Model(BaseModel):
  """Abstract model with basic CRUD behaviour."""

  _abstract = True

  # --- helpers ------------------------------------------------------------

  @classmethod
  def _database(cls):
    from jerp import env

    return env.Environment.instance.db

  @classmethod
  def _column(cls, name: str) -> str:
    field = cls._fields.get(name)
    if field is not None:
      return field.column_name
    for f in cls._fields.values():
      if f.column_name == name:
        return f.column_name
    raise ValueError(f"Unknown field '{name}' on model '{cls._name}'")

  @classmethod
  def _field_by_column(cls) -> dict:
    return {f.column_name: f for f in cls._fields.values()}

  @classmethod
  def _row_to_values(cls, row: dict) -> dict:
    by_column = cls._field_by_column()
    values = {}
    for column, value in row.items():
      field = by_column.get(column)
      if field is None:
        continue
      values[field.attr_name] = field.to_python(value)
    return values

  @classmethod
  def _instantiate(cls, row: dict):
    obj = cls.__new__(cls)
    obj._values = cls._row_to_values(row)
    return obj

  @classmethod
  def _build_where(cls, domain) -> tuple[str, list]:
    if not domain:
      return '', []

    if isinstance(domain, dict):
      domain = [(k, '=', v) for k, v in domain.items()]

    clauses: list[str] = []
    params: list = []

    for item in domain:
      if len(item) == 3:
        name, operator, value = item
      elif len(item) == 2:
        name, value = item
        operator = '='
      else:
        raise ValueError(f'Invalid domain leaf: {item!r}')

      column = quote_ident(cls._column(name))
      operator = str(operator).lower()

      if operator in ('is null', 'is not null'):
        clauses.append(f'{column} {operator.upper()}')
        continue

      if operator in ('in', 'not in'):
        values = list(value or [])
        if not values:
          clauses.append('TRUE' if operator == 'in' else 'FALSE')
          continue
        placeholders = ', '.join(['%s'] * len(values))
        clauses.append(f'{column} {operator.upper()} ({placeholders})')
        params.extend(values)
        continue

      if operator not in _DOMAIN_OPERATORS:
        raise ValueError(f'Unsupported domain operator: {operator!r}')

      clauses.append(f'{column} {_DOMAIN_OPERATORS[operator]} %s')
      params.append(value)

    return ' AND '.join(clauses), params

  @classmethod
  def _build_order(cls, order) -> str:
    if not order:
      return ''

    if isinstance(order, str):
      order = [part.strip() for part in order.split(',') if part.strip()]

    parts = []
    for spec in order:
      tokens = spec.split()
      column = quote_ident(cls._column(tokens[0]))
      direction = 'DESC' if len(tokens) > 1 and tokens[1].lower() == 'desc' else 'ASC'
      parts.append(f'{column} {direction}')
    return ', '.join(parts)

  @staticmethod
  def _now() -> datetime:
    return datetime.now(timezone.utc)

  @classmethod
  def _auto_value(cls, field, creating: bool):
    if isinstance(field, fields.DateTimeField):
      if field.auto_now_add and creating:
        return cls._now()
      if field.auto_now:
        return cls._now()
    if field.default is not None and callable(field.default):
      return field.default()
    return field.default

  # --- CRUD ---------------------------------------------------------------

  @classmethod
  @api_expose
  def create(cls, **values):
    db = cls._database()
    columns: list[str] = []
    placeholders: list[str] = []
    params: list = []
    stored: dict = {}

    for name, field in cls._fields.items():
      if field.auto_increment:
        continue
      if name in values:
        raw = field.convert(values[name])
      else:
        raw = cls._auto_value(field, creating=True)
      columns.append(quote_ident(field.column_name))
      placeholders.append('%s')
      params.append(field.to_db(raw))
      stored[name] = field.to_python(raw)

    sql = (
      f'INSERT INTO {quote_table(cls._table)} '
      f'({", ".join(columns)}) VALUES ({", ".join(placeholders)}) RETURNING id'
    )
    row = db.fetchone(sql, params)
    obj = cls.__new__(cls)
    obj._values = stored
    obj._values['id'] = row['id']
    return obj

  @classmethod
  def search(cls, domain=None, order=None, limit=None, offset=None):
    db = cls._database()
    where, params = cls._build_where(domain)
    sql = f'SELECT * FROM {quote_table(cls._table)}'
    if where:
      sql += f' WHERE {where}'
    order_sql = cls._build_order(order)
    if order_sql:
      sql += f' ORDER BY {order_sql}'
    if limit is not None:
      sql += f' LIMIT {int(limit)}'
    if offset is not None:
      sql += f' OFFSET {int(offset)}'
    rows = db.fetchall(sql, params)
    return [cls._instantiate(row) for row in rows]

  @classmethod
  def browse(cls, ids):
    if isinstance(ids, int):
      ids = [ids]
    return cls.search([('id', 'in', list(ids))], order='id')

  def read(self, field_names=None) -> dict:
    if field_names is None:
      field_names = list(self._fields.keys())
    return {name: self._values.get(name) for name in field_names}

  def write(self, values) -> bool:
    db = self._database()
    sets: list[str] = []
    params: list = []

    for name, value in values.items():
      field = self._fields.get(name)
      if field is None:
        raise ValueError(f"Unknown field '{name}' on model '{self._name}'")
      sets.append(f'{quote_ident(field.column_name)} = %s')
      params.append(field.to_db(field.convert(value)))

    for name in ('updated_at',):
      if name in self._fields:
        sets.append(f'{quote_ident(self._fields[name].column_name)} = %s')
        params.append(self._now())

    if not sets:
      return False

    params.append(self._values['id'])
    sql = f'UPDATE {quote_table(self._table)} SET {", ".join(sets)} WHERE {quote_ident(self._fields["id"].column_name)} = %s'
    rowcount = db.execute(sql, params)
    self._values.update(values)
    return rowcount > 0

  def unlink(self) -> bool:
    db = self._database()
    sql = f'DELETE FROM {quote_table(self._table)} WHERE {quote_ident(self._fields["id"].column_name)} = %s'
    rowcount = db.execute(sql, [self._values['id']])
    return rowcount > 0

  # --- standard API methods (exposed through POST /api/model/<name>/<func>) -

  @classmethod
  def _as_dict(cls, record, fields=None) -> dict:
    if fields is None:
      names = [name for name, field in cls._fields.items() if not field.hide]
    else:
      names = [name for name in fields if name in cls._fields and not cls._fields[name].hide]
    values = record.read(names)
    values['id'] = record.id
    values['_label'] = cls.display_name(record)
    return values

  @classmethod
  def display_name(cls, record) -> str:
    """The record's display label: ``_label`` field, else ``name``, else ``model#id``."""

    def get(name: str):
      if name in cls._fields:
        return record.get(name) if isinstance(record, dict) else record.read([name]).get(name)
      if isinstance(record, dict):
        return record.get(name)
      return None

    for name in (cls._label, 'name'):
      if not name:
        continue
      value = get(name)
      if value not in (None, ''):
        return str(value)

    identity = record.get('id') if isinstance(record, dict) else record.id
    return f'{cls._name}#{identity}'

  @classmethod
  @api_expose
  def all(cls, domain=None, fields=None, order=None, limit=None, offset=None):
    """Filtered, paginated list of records (as dicts)."""

    records = cls.search(domain or [], order=order, limit=limit, offset=offset)
    return [cls._as_dict(record, fields) for record in records]

  @classmethod
  @api_expose
  def count(cls, domain=None) -> int:
    return len(cls.search(domain or []))

  @classmethod
  @api_expose
  def fields(cls) -> list[dict]:
    """Field descriptors (used by the client to pick the right widget)."""

    return cls.field_schema()

  @classmethod
  @api_expose
  def find(cls, id, fields=None):
    records = cls.browse(id)
    return cls._as_dict(records[0], fields) if records else None

  @classmethod
  @api_expose
  def update(cls, id, values=None, **extra):
    payload = dict(values or {})
    payload.update(extra)
    records = cls.browse(id)
    if not records:
      return None
    records[0].write(payload)
    return cls.find(id)

  @classmethod
  @api_expose
  def delete(cls, id) -> bool:
    records = cls.browse(id)
    return records[0].unlink() if records else False
