"""Model layer: declarative models, the model registry and a small CRUD API.

``ModelMeta`` collects the :class:`~jerp.fields.Field` instances declared on a
class into an ordered ``_fields`` mapping, derives the table name, and registers
the class in the global :class:`ModelRegistry`. Concrete models subclass
:class:`Model` and get basic create/search/read/write/unlink helpers.

Classes are *sources*: a base model, an extension (``_inherit``) or a new
multi-parent model (``_inherits``). The :mod:`jerp.builder` engine combines the
sources installed in a database into one built model class per model name.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import uuid4

from jerp import fields
from jerp.api import api_expose, is_exposed
from jerp.dialect import quote_ident, quote_table
from jerp.refs import model_module, resolve_key


def to_table_name(class_name: str) -> str:
  """``SysModule`` -> ``sys_module``."""

  return re.sub(r'(?<!^)(?=[A-Z])', '_', class_name).lower()


class ModelRegistry:
  """Global registry of model *sources* imported from the module packages.

  Sources are kept separately so an extension never overwrites the base model:

  * ``_models`` -- concrete base models without ``_inherit`` / ``_inherits``
  * ``_new_models`` -- concrete models declared with ``_inherits``
  * ``_extensions`` -- ``_inherit`` sources, grouped by target model name

  Built classes are produced per database by :class:`jerp.builder.ModelBuilder`
  and are deliberately **not** registered here.
  """

  _models: dict[str, type] = {}
  _new_models: dict[str, type] = {}
  _extensions: dict[str, list[type]] = {}

  @classmethod
  def register(cls, model) -> None:
    if getattr(model, '_composed', False):
      return

    name = getattr(model, '_name', None)
    if not name:
      raise ValueError(f"Model '{model.__name__}' has no name.")

    if getattr(model, '_is_extension', False):
      bucket = cls._extensions.setdefault(model._extends, [])
      if model not in bucket:
        bucket.append(model)
      return

    existing = cls._models.get(name) or cls._new_models.get(name)
    if existing is not None:
      if existing is model:
        return
      raise ValueError(
        f"Duplicate model '{name}': declared by both "
        f"'{existing.__module__}.{existing.__qualname__}' and "
        f"'{model.__module__}.{model.__qualname__}'."
      )

    if getattr(model, '_is_inherited', False):
      cls._new_models[name] = model
    else:
      cls._models[name] = model

  @classmethod
  def get(cls, name: str):
    return cls._models.get(name) or cls._new_models.get(name)

  @classmethod
  def all(cls) -> dict:
    """Base and new-model sources (not extensions)."""

    return {**cls._models, **cls._new_models}

  @classmethod
  def bases(cls) -> dict:
    return dict(cls._models)

  @classmethod
  def new_models(cls) -> dict:
    return dict(cls._new_models)

  @classmethod
  def extensions(cls, name: str) -> list:
    return list(cls._extensions.get(name, ()))

  @classmethod
  def all_classes(cls):
    """Every source class, including extensions."""

    yield from cls._models.values()
    yield from cls._new_models.values()
    for bucket in cls._extensions.values():
      yield from bucket

  @classmethod
  def clear(cls) -> None:
    cls._models.clear()
    cls._new_models.clear()
    cls._extensions.clear()


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
    cls._own_fields = own

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

    if attrs.get('_composed'):
      # Produced by the build engine. It is never a source and must not be
      # registered globally; its metadata is supplied by the builder.
      cls._composed = True
      cls._is_extension = False
      cls._is_inherited = False
      cls._extends = None
      cls._inherits = ()
      cls._sources = tuple(attrs.get('_sources') or ())
      cls._name = attrs.get('_name') or to_table_name(name)
      cls._table = attrs.get('_table') or cls._name.replace('.', '_')
      cls._virtual = bool(attrs.get('_virtual', False))
      return cls

    inherit = attrs.get('_inherit')
    inherits = attrs.get('_inherits')

    if inherit is not None and inherits is not None:
      raise ValueError(
        f"Model '{name}' cannot declare both _inherit and _inherits."
      )

    concrete_bases = [
      base
      for base in bases
      if getattr(base, '_name', None) and not getattr(base, '_abstract', False)
    ]

    cls._composed = False
    cls._is_extension = False
    cls._is_inherited = False
    cls._extends = None
    cls._inherits = ()

    if inherit is not None:
      if not isinstance(inherit, str) or not inherit:
        raise ValueError(
          f"Model '{name}': _inherit must be a model name (e.g. _inherit = 'sys.user')."
        )
      if concrete_bases:
        raise ValueError(
          f"Model '{name}': an _inherit source must not subclass a concrete "
          f"model ('{concrete_bases[0]._name}'). Declare _inherit = '<model>' instead."
        )
      forbidden = [key for key in ('_name', '_table', '_virtual') if key in attrs]
      if forbidden:
        raise ValueError(
          f"Model '{name}': an _inherit source cannot declare "
          f"{', '.join(forbidden)}; the target model provides them."
        )

      cls._name = inherit
      cls._table = None
      cls._extends = inherit
      cls._is_extension = True
      cls._virtual = False
      ModelRegistry.register(cls)
      return cls

    if inherits is not None:
      if not isinstance(inherits, (list, tuple)) or not inherits:
        raise ValueError(
          f"Model '{name}': _inherits must be a non-empty list of model names."
        )
      if not all(isinstance(item, str) and item for item in inherits):
        raise ValueError(
          f"Model '{name}': every _inherits entry must be a model name."
        )
      if concrete_bases:
        raise ValueError(
          f"Model '{name}': an _inherits source must not subclass a concrete "
          f"model ('{concrete_bases[0]._name}')."
        )

      declared_name = attrs.get('_name')
      if not declared_name:
        raise ValueError(
          f"Model '{name}': _inherits requires a new _name."
        )
      if declared_name in inherits:
        raise ValueError(
          f"Model '{name}': a new model cannot inherit from itself."
        )
      if len(set(inherits)) != len(inherits):
        raise ValueError(
          f"Model '{name}': _inherits contains duplicate model names."
        )

      cls._name = declared_name
      cls._table = attrs.get('_table') or declared_name.replace('.', '_')
      cls._virtual = bool(attrs.get('_virtual', False))
      cls._inherits = tuple(inherits)
      cls._is_inherited = True
      ModelRegistry.register(cls)
      return cls

    if concrete_bases:
      raise ValueError(
        f"Model '{name}' subclasses concrete model '{concrete_bases[0]._name}' "
        f"without _inherit. Use _inherit = '<model>' to extend an existing "
        f"model, or _inherits = [...] with a new _name to build a new model."
      )

    cls._name = attrs.get('_name') or to_table_name(name)
    cls._table = attrs.get('_table') or cls._name.replace('.', '_')
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
  _temporary = False

  #: Field used as the record's display label. Defaults to ``name`` when it
  #: exists, otherwise ``"<model>#<id>"``.
  _label: str | None = None

  #: Previous model name, used to migrate an existing table when the model is
  #: renamed (e.g. ``'user'`` -> ``'sys.user'``).
  _rename_from: str | None = None

  #: Whether every record should get an entry in ``sys.data``. Disabled for
  #: ``sys.data`` itself to avoid a recursive reference.
  _track_refs = True

  id = fields.IdField(
    name='ID',
    help='Unique database identifier.',
  )
  created_at = fields.DateTimeField(
    name='Created At', use_tz=True, auto_now_add=True, required=True,
    help='When this record was created.',
  )
  updated_at = fields.DateTimeField(
    name='Updated At', use_tz=True, auto_now=True, required=True,
    help='When this record was last modified.',
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
      if name in getattr(cls, '_extension_fields', ()):
        entry['extension'] = True
      if field.help:
        entry['help'] = field.help
      size = getattr(field, 'size', None)
      if size:
        entry['size'] = int(size)
      if field.default is not None:
        entry['has_default'] = True
        if not callable(field.default) and isinstance(
          field.default, (str, int, float, bool)
        ):
          entry['default'] = field.default
      if getattr(field, 'multi_language', False):
        entry['multi_language'] = True
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

  # --- external references ------------------------------------------------

  @classmethod
  def _language_model(cls):
    from jerp.env import Environment

    try:
      registry = Environment.instance.registry()
    except Exception:
      return None
    return registry.get('sys.lang')

  @classmethod
  def _translation_model(cls):
    from jerp.env import Environment

    try:
      registry = Environment.instance.registry()
    except Exception:
      return None
    return registry.get('sys.multi_lang_char')

  @classmethod
  def _default_language(cls):
    Language = cls._language_model()
    if Language is None:
      return None

    rows = Language.search([
      ('is_default', '=', True),
      ('active', '=', True),
    ], limit=1)
    if rows:
      return rows[0]

    rows = Language.search([('active', '=', True)], order='id', limit=1)
    return rows[0] if rows else None

  @classmethod
  def _field_meta(cls, field_name: str):
    from jerp.env import Environment

    try:
      registry = Environment.instance.registry()
    except Exception:
      return None

    SysField = registry.get('sys.field')
    if SysField is None:
      return None

    rows = SysField.search([
      ('model', '=', cls._name),
      ('field_name', '=', field_name),
    ], limit=1)
    return rows[0] if rows else None

  @classmethod
  def _split_multi_lang_values(cls, values: dict):
    """Split multi-language dict values into column value + translations."""

    translations: dict[str, dict[str, str]] = {}
    default_code = None
    default_loaded = False

    for name, value in list(values.items()):
      field = cls._fields.get(name)
      if field is None or not getattr(field, 'multi_language', False):
        continue
      if not isinstance(value, dict):
        continue

      if not default_loaded:
        default = cls._default_language()
        default_code = default.code if default is not None else None
        default_loaded = True

      codes = list(value.keys())
      code = (
        default_code
        if default_code in value
        else ('en' if 'en' in value else (codes[0] if codes else None))
      )
      if code is None:
        continue

      default_value = value.get(code)
      if default_value is None:
        for candidate in value.values():
          if candidate is not None:
            default_value = candidate
            break

      values[name] = default_value
      translations[name] = {
        lang: text
        for lang, text in value.items()
        if lang != code and text not in (None, '')
      }

    return values, translations

  @classmethod
  @api_expose
  def translations(cls, id, field=None):
    """Return translations for one field, or all multi-language fields."""

    records = cls.browse(id)
    if not records:
      return {}

    record = records[0]
    if field:
      field_names = [str(field)]
    else:
      field_names = [
        name
        for name, item in cls._fields.items()
        if getattr(item, 'multi_language', False)
      ]

    Language = cls._language_model()
    default = cls._default_language()
    Trans = cls._translation_model()
    default_code = default.code if default is not None else 'en'

    result = {}
    for field_name in field_names:
      item = cls._fields.get(field_name)
      if item is None:
        raise ValueError(f"Unknown field '{field_name}' on model '{cls._name}'.")

      values = {default_code: record.read([field_name])[field_name]}

      if Trans is not None:
        meta = cls._field_meta(field_name)
        if meta is not None:
          for row in Trans.search([
            ('field_id', '=', meta.id),
            ('res_id', '=', int(id)),
          ]):
            language = (
              Language.browse(row.lang_id) if Language is not None else []
            )
            if language:
              values[language[0].code] = row.value

      if field:
        return values
      result[field_name] = values

    return result

  @classmethod
  @api_expose
  def set_translation(cls, id, field, lang, value):
    """Set one translated value for a record field."""

    field_name = str(field)
    item = cls._fields.get(field_name)
    if item is None or not getattr(item, 'multi_language', False):
      raise ValueError(
        f"Field '{field_name}' on model '{cls._name}' is not multi-language."
      )

    records = cls.browse(id)
    if not records:
      raise ValueError(f"Record '{cls._name}#{id}' does not exist.")

    Language = cls._language_model()
    if Language is None:
      raise RuntimeError("The 'sys.lang' model is not installed.")

    languages = Language.search([('code', '=', str(lang))], limit=1)
    if not languages:
      raise ValueError(f"Unknown language code: {lang}")
    language = languages[0]

    default = cls._default_language()
    if default is not None and language.id == default.id:
      records[0].write({field_name: value})
      return cls.translations(id, field=field_name)

    meta = cls._field_meta(field_name)
    if meta is None:
      raise ValueError(
        f"Field metadata for '{cls._name}.{field_name}' is not available."
      )

    Trans = cls._translation_model()
    if Trans is None:
      raise RuntimeError("The 'sys.multi_lang_char' model is not installed.")

    key = f'{meta.id}:{int(id)}:{language.id}'
    rows = Trans.search([('key', '=', key)], limit=1)

    if value in (None, ''):
      if rows:
        rows[0].unlink()
    elif rows:
      rows[0].write({'value': str(value)})
    else:
      Trans.create(
        field_id=meta.id,
        lang_id=language.id,
        res_id=int(id),
        value=str(value),
        key=key,
      )

    return cls.translations(id, field=field_name)

  @classmethod
  @api_expose
  def set_translations(cls, id, field, values):
    """Set several translations at once (``{lang_code: value}``)."""

    if not isinstance(values, dict):
      raise ValueError('Translations must be a language-code dictionary.')

    for code, value in values.items():
      cls.set_translation(id, field, code, value)
    return cls.translations(id, field=field)

  @classmethod
  def _delete_translations(cls, record_id) -> None:
    from jerp.env import Environment

    try:
      registry = Environment.instance.registry()
    except Exception:
      return

    SysField = registry.get('sys.field')
    Trans = registry.get('sys.multi_lang_char')
    if SysField is None or Trans is None:
      return

    metas = SysField.search([('model', '=', cls._name)])
    if not metas:
      return
    field_ids = [meta.id for meta in metas]
    for row in Trans.search([
      ('field_id', 'in', field_ids),
      ('res_id', '=', int(record_id)),
    ]):
      row.unlink()

  @classmethod
  def register_ref(cls, record_id, key=None, module=None):
    """Ensure ``record_id`` has a ``sys.data`` external id.

    ``key`` may be fully qualified (``module.key``) or a short name. Short
    names become ``<module>.<model>.<key>``. Without a key, an existing
    reference is reused or a UUID key is generated.
    """

    if not getattr(cls, '_track_refs', True) or getattr(cls, '_virtual', False):
      return None

    from jerp.env import Environment

    try:
      registry = Environment.instance.registry()
    except Exception:
      return None

    Data = registry.get('sys.data')
    if Data is None:
      return None

    module_name = module or model_module(cls)
    if key:
      raw_key = str(key).strip()
      first = raw_key.split('.', 1)[0]
      if first in registry.modules:
        module_name = first
        full_key = raw_key
        short_name = raw_key[len(first) + 1:]
      else:
        full_key, short_name = resolve_key(module_name, cls._name, raw_key)
    else:
      existing = Data.search([
        ('model', '=', cls._name),
        ('res_id', '=', int(record_id)),
      ], limit=1)
      if existing:
        return existing[0]
      full_key = short_name = str(uuid4())

    rows = Data.search([('key', '=', full_key)], limit=1)
    if rows:
      data = rows[0]
      if data.model != cls._name:
        raise ValueError(
          f"External key '{full_key}' already belongs to model '{data.model}'."
        )
      if int(data.res_id) == int(record_id):
        return data

      OldModel = registry.get(data.model)
      old_records = OldModel.browse(data.res_id) if OldModel is not None else []
      if old_records:
        raise ValueError(
          f"External key '{full_key}' already points to "
          f"'{data.model}#{data.res_id}'."
        )

      data.write({
        'module': module_name,
        'name': short_name,
        'res_id': int(record_id),
      })
      return data

    return Data.create(
      module=module_name,
      model=cls._name,
      name=short_name,
      key=full_key,
      res_id=int(record_id),
    )

  @classmethod
  def _delete_refs(cls, record_id) -> None:
    from jerp.env import Environment

    try:
      registry = Environment.instance.registry()
    except Exception:
      return

    Data = registry.get('sys.data')
    if Data is None:
      return

    for data in Data.search([
      ('model', '=', cls._name),
      ('res_id', '=', int(record_id)),
    ]):
      data.unlink()

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
    external_key = values.pop('_key', None)
    ref_module = values.pop('_ref_module', None)
    values, translations = cls._split_multi_lang_values(values)
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

    if getattr(cls, '_track_refs', True) and not getattr(cls, '_virtual', False):
      cls.register_ref(obj.id, external_key, module=ref_module)

    for field_name, lang_values in translations.items():
      cls.set_translations(obj.id, field_name, lang_values)
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
    values, translations = type(self)._split_multi_lang_values(dict(values))
    sets: list[str] = []
    params: list = []
    now = self._now()

    for name, value in values.items():
      field = self._fields.get(name)
      if field is None:
        raise ValueError(f"Unknown field '{name}' on model '{self._name}'")
      sets.append(f'{quote_ident(field.column_name)} = %s')
      params.append(field.to_db(field.convert(value)))

    for name in ('updated_at',):
      if name in self._fields:
        sets.append(f'{quote_ident(self._fields[name].column_name)} = %s')
        params.append(now)

    if not sets:
      return False

    params.append(self._values['id'])
    sql = f'UPDATE {quote_table(self._table)} SET {", ".join(sets)} WHERE {quote_ident(self._fields["id"].column_name)} = %s'
    rowcount = db.execute(sql, params)
    self._values.update(values)
    if 'updated_at' in self._fields and rowcount > 0:
      self._values['updated_at'] = now

    if rowcount > 0:
      for field_name, lang_values in translations.items():
        type(self).set_translations(self._values['id'], field_name, lang_values)
    return rowcount > 0

  def unlink(self) -> bool:
    db = self._database()
    sql = f'DELETE FROM {quote_table(self._table)} WHERE {quote_ident(self._fields["id"].column_name)} = %s'
    rowcount = db.execute(sql, [self._values['id']])
    if rowcount > 0 and getattr(type(self), '_track_refs', True) and not getattr(type(self), '_virtual', False):
      type(self)._delete_refs(self._values['id'])
    if rowcount > 0:
      type(self)._delete_translations(self._values['id'])
    return rowcount > 0

  # --- standard API methods (exposed through POST /api/model/<name>/<func>) -

  @classmethod
  def temp_values(cls, values) -> dict:
    """Compute values stored in a temporary record before the parent exists."""

    return dict(values)

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
    """Number of records matching ``domain`` (without loading the records)."""

    db = cls._database()
    where, params = cls._build_where(domain)
    sql = f'SELECT COUNT(*) AS total FROM {quote_table(cls._table)}'
    if where:
      sql += f' WHERE {where}'
    row = db.fetchone(sql, params)
    return int(row['total']) if row else 0

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

  @classmethod
  @api_expose
  def delete_many(cls, ids) -> int:
    """Delete several records by id and return the number removed."""

    if not ids:
      return 0
    if getattr(cls, '_virtual', False):
      raise ValueError(f'Model "{cls._name}" does not support bulk delete.')

    deleted = 0
    for record in cls.browse([int(value) for value in ids]):
      if record.unlink():
        deleted += 1
    return deleted

  # --- source cooperation -------------------------------------------------

  @classmethod
  def call_parts(cls, method_name: str, *args, record=None, **kwargs):
    """Call every implementation of ``method_name`` in the built model.

    Class methods / static methods are called on every source that declares
    them; instance methods are called only when ``record`` is given. This
    complements normal overriding: ``super()`` walks the same chain one result
    at a time, while ``call_parts`` invokes every part.

    Returns the list of results in build order.
    """

    results = []
    for source in cls.__mro__:
      raw = source.__dict__.get(method_name)
      if raw is None:
        continue
      if isinstance(raw, (classmethod, staticmethod)):
        results.append(raw.__get__(None, cls)(*args, **kwargs))
      elif callable(raw):
        if record is None:
          continue
        results.append(raw.__get__(record, source)(*args, **kwargs))
    return results

  @classmethod
  def model_sources(cls) -> tuple:
    """The source classes that were combined into this built model."""

    return tuple(getattr(cls, '_sources', ()) or ())
