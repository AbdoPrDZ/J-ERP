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

import inspect
import json
import re
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

from jerp import fields
from jerp.api import api_expose, is_exposed
from jerp.dialect import quote_ident, quote_table
from jerp.refs import model_module, resolve_key


class RecordSet(list):
  """A list of records that also behaves like an Odoo recordset.

  ``search`` and ``browse`` return this type. It is a real ``list`` so the
  existing code that indexes, iterates or truth-tests the result keeps working.
  """

  def is_one(self):
    if len(self) != 1:
      raise ValueError(
        f'Expected exactly one record, got {len(self)}.'
      )
    return self[0]

  ensure_one = is_one

  def __getattr__(self, name):
    if name.startswith('_'):
      raise AttributeError(name)
    if len(self) != 1:
      raise AttributeError(
        f'Field "{name}" can only be read on a single record.'
      )
    return getattr(self[0], name)

  def __setattr__(self, name, value):
    if name.startswith('_'):
      return super().__setattr__(name, value)
    if len(self) != 1:
      raise AttributeError(
        f'Field "{name}" can only be written on a single record.'
      )
    return setattr(self[0], name, value)

  def __str__(self):
    return ', '.join(str(record) for record in self)


class dualmethod:
  """Descriptor dispatching to a class method or an instance method.

  Used for ``save``: ``Model.save(draft_id)`` keeps the exposed API behaviour,
  while ``record.save()`` saves an in-memory new record.
  """

  def __init__(self, instance_func, class_func, exposed=None):
    self.instance_func = instance_func
    if isinstance(class_func, classmethod):
      class_func = class_func.__func__
    self.class_func = class_func
    self._jerp_exposed = (
      is_exposed(class_func) if exposed is None else bool(exposed)
    )
    self.__name__ = getattr(class_func, '__name__', 'save')
    self.__doc__ = getattr(class_func, '__doc__', None)

  def __get__(self, obj, cls=None):
    if obj is None:
      return self.class_func.__get__(cls, cls)
    return self.instance_func.__get__(obj, cls)



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

  # --- recordset behaviour ------------------------------------------------

  def __iter__(self):
    yield self

  def __len__(self):
    return 1

  def __bool__(self):
    return True

  def is_one(self):
    return self

  ensure_one = is_one

  def __str__(self):
    try:
      display = type(self).display_name(self)
    except Exception:
      display = None
    return display or f'{type(self)._name}#{self._values.get("id")}'

  @classmethod
  def _reverse_relations(cls) -> dict:
    """Map one2many attribute names to ``(child_model, inverse_field)``.

    The relation is derived from many2one fields pointing at this model. For
    example ``sale.order.line.order_id`` also becomes ``sale.order.lines``.
    """

    cache = cls.__dict__.get('_reverse_relation_cache')
    if cache is not None:
      return cache

    cache = {}
    loaded = False
    try:
      from jerp.env import Environment

      registry = Environment.instance.registry()
      models = list(registry.models.items())
      loaded = bool(getattr(registry, 'ready', False))
    except Exception:
      models = []

    for other_name, other in models:
      if other is cls:
        continue
      for field_name, field in other._fields.items():
        if getattr(field, 'comodel', None) != cls._name:
          continue
        suffix = other_name.split('.')[-1]
        for candidate in (f'{suffix}s', f'{suffix}_ids'):
          if candidate not in cls._fields:
            cache.setdefault(candidate, (other, field_name))
        if field_name.endswith('_id'):
          candidate = f'{field_name[:-3]}s'
          if candidate not in cache and candidate not in cls._fields:
            cache[candidate] = (other, field_name)

    if loaded:
      cls._reverse_relation_cache = cache
    return cache

  def _one2many_records(self, name, child_model, inverse_name):
    result = []
    base_id = None
    if getattr(self, '_persisted', False):
      base_id = self._values.get('id')
    else:
      base_id = getattr(self, '_record_id', None)

    drafts = []
    by_record = {}
    if base_id:
      rows = child_model.search([(inverse_name, '=', base_id)], order='id')
      token = getattr(self, '_token', None)
      if token:
        try:
          Temp = child_model._draft_model()
          drafts = Temp.search(
            [
              ('token', '=', token),
              ('model', '=', child_model._name),
            ],
            order='id',
          )
        except Exception:
          drafts = []
        for draft in drafts:
          if draft.record_id:
            by_record[draft.record_id] = draft
      for row in rows:
        draft = by_record.get(row.id)
        if draft is not None:
          if draft.state == 'delete':
            continue
          if draft.state == 'update':
            values = dict(row._values)
            values.update(child_model._draft_load(draft.data))
            result.append(
              child_model._pseudo_record(
                values,
                draft_id=draft.id,
                token=draft.token,
                record_id=row.id,
                state='update',
              )
            )
            continue
        result.append(row)

    if getattr(self, '_is_new', False):
      result.extend(self.__dict__.get('_one2many_cache', {}).get(name, []))
    if getattr(self, '_draft_id', None):
      token = getattr(self, '_token', None)
      if token:
        try:
          Temp = child_model._draft_model()
          drafts = Temp.search(
            [
              ('token', '=', token),
              ('model', '=', child_model._name),
            ],
            order='id',
          )
        except Exception:
          drafts = []
        for draft in drafts:
          if draft.state != 'create':
            continue
          data = child_model._draft_load(draft.data)
          if data.get(inverse_name) != f'draft:{self._draft_id}':
            continue
          result.append(child_model._draft_record_from_row(draft))

    return RecordSet(result)

  def _assign_one2many(self, name, commands, child_model, inverse_name):
    if commands is None:
      commands = []
    if isinstance(commands, (list, tuple)) and commands and not isinstance(
      commands[0], (list, tuple)
    ):
      commands = [commands]

    if not getattr(self, '_persisted', False):
      cache = self.__dict__.setdefault('_one2many_cache', {})
      children = cache.setdefault(name, [])
      for command in commands:
        if not isinstance(command, (list, tuple)) or not command:
          continue
        operation = command[0]
        if operation == 0:
          values = dict(command[2] or {})
          values[inverse_name] = self
          children.append(child_model._new_record(values))
        elif operation == 1:
          record_id, values = command[1], dict(command[2] or {})
          for child in children:
            if str(child._values.get('id')) == str(record_id) or str(
              getattr(child, '_record_id', None)
            ) == str(record_id):
              for field_name, value in values.items():
                setattr(child, field_name, value)
        elif operation == 2:
          record_id = command[1]
          children[:] = [
            child
            for child in children
            if not (
              str(child._values.get('id')) == str(record_id)
              or str(getattr(child, '_record_id', None)) == str(record_id)
            )
          ]
        elif operation == 6:
          keep = {str(value) for value in (command[2] or [])}
          children[:] = [
            child
            for child in children
            if str(child._values.get('id')) in keep
          ]
      return

    for command in commands:
      if not isinstance(command, (list, tuple)) or not command:
        continue
      operation = command[0]
      if operation == 0:
        values = dict(command[2] or {})
        values[inverse_name] = self._values['id']
        child_model.create(**values)
      elif operation == 1:
        records = child_model.browse(command[1])
        if records:
          records[0].write(dict(command[2] or {}))
      elif operation == 2:
        records = child_model.browse(command[1])
        if records:
          records[0].unlink()
      elif operation == 6:
        keep = {str(value) for value in (command[2] or [])}
        for record in child_model.search([(inverse_name, '=', self._values['id'])]):
          if str(record.id) not in keep:
            record.unlink()

  def __getattr__(self, name):
    if name.startswith('_'):
      raise AttributeError(name)
    relation = type(self)._reverse_relations().get(name)
    if relation is not None:
      return self._one2many_records(name, *relation)
    raise AttributeError(
      f"'{type(self)._name}' has no attribute '{name}'"
    )

  def __setattr__(self, name, value):
    if name.startswith('_') or name in type(self)._fields:
      object.__setattr__(self, name, value)
      return
    relation = type(self)._reverse_relations().get(name)
    if relation is not None:
      self._assign_one2many(name, value, *relation)
      return
    object.__setattr__(self, name, value)

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
      if getattr(field, 'compute', None):
        entry['compute'] = True
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
    obj._persisted = True
    obj._is_new = False
    obj._pseudo = False
    obj._draft_id = None
    obj._draft_state = None
    obj._record_id = obj._values.get('id')
    obj._token = None
    obj._one2many_cache = {}
    obj._computing = set()
    return obj

  @classmethod
  def _new_base(cls, values, persisted=False):
    obj = cls.__new__(cls)
    obj._values = dict(values or {})
    obj._persisted = persisted
    obj._is_new = not persisted
    obj._pseudo = not persisted
    obj._draft_id = None
    obj._draft_state = None
    obj._record_id = obj._values.get('id') if persisted else None
    obj._token = None
    obj._one2many_cache = {}
    obj._computing = set()
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
      field = cls._fields.get(name)

      def scalar(item):
        if isinstance(item, RecordSet):
          return item[0]._values.get('id') if item else None
        if isinstance(item, BaseModel):
          return (
            item._values.get('id')
            if not getattr(item, '_is_new', False)
            else None
          )
        return item

      if field is not None and getattr(field, 'comodel', None):
        value = scalar(value)

      if operator in ('is null', 'is not null'):
        clauses.append(f'{column} {operator.upper()}')
        continue

      if operator in ('in', 'not in'):
        values = [scalar(item) for item in (value or [])]
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
    value = field.default
    if (
      value is None
      and getattr(field, 'comodel', None) is None
      and not field.auto_increment
      and isinstance(
        field,
        (fields.FloatField, fields.NumericField, fields.IntegerField),
      )
    ):
      return 0
    return value

  # --- CRUD ---------------------------------------------------------------

  @classmethod
  def _coerce_write_value(cls, name, value):
    if isinstance(value, RecordSet):
      value = value[0] if value else None
    field = cls._fields.get(name)
    if field is None:
      return value
    if getattr(field, 'comodel', None):
      if isinstance(value, BaseModel):
        if getattr(value, '_draft_id', None):
          return f'draft:{value._draft_id}'
        if getattr(value, '_is_new', False):
          return value
        return value._values.get('id')
      if isinstance(value, dict):
        return value.get('id')
      return value
    if isinstance(value, BaseModel):
      return value._values.get('id')
    return value

  @classmethod
  @api_expose
  def create(cls, values=None, **kwargs):
    payload = dict(values or {})
    payload.update(kwargs)
    external_key = payload.pop('_key', None)
    ref_module = payload.pop('_ref_module', None)
    payload = {
      name: cls._coerce_write_value(name, value)
      for name, value in payload.items()
    }
    payload, translations = cls._split_multi_lang_values(payload)
    db = cls._database()
    columns: list[str] = []
    placeholders: list[str] = []
    params: list = []
    stored: dict = {}

    for name, field in cls._fields.items():
      if field.auto_increment:
        continue
      if name in payload:
        raw = payload[name]
        if isinstance(raw, BaseModel) and getattr(raw, '_is_new', False):
          raw = raw.save()
        if (
          raw is None
          and field.required
          and isinstance(field, (fields.StringField, fields.TextField))
        ):
          raw = ''
        raw = field.convert(raw)
      else:
        raw = cls._auto_value(field, creating=True)
        if (
          raw is None
          and field.required
          and isinstance(field, (fields.StringField, fields.TextField))
        ):
          # Python callers commonly omit required text fields; an empty string
          # satisfies the column while the UI still validates user input.
          raw = ''
      columns.append(quote_ident(field.column_name))
      placeholders.append('%s')
      params.append(field.to_db(raw))
      stored[name] = field.to_python(raw)

    sql = (
      f'INSERT INTO {quote_table(cls._table)} '
      f'({", ".join(columns)}) VALUES ({", ".join(placeholders)}) RETURNING id'
    )
    row = db.fetchone(sql, params)
    obj = cls._new_base({**stored, 'id': row['id']}, persisted=True)

    if getattr(cls, '_track_refs', True) and not getattr(cls, '_virtual', False):
      cls.register_ref(obj.id, external_key, module=ref_module)

    for field_name, lang_values in translations.items():
      cls.set_translations(obj.id, field_name, lang_values)

    obj._recompute_computed()
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
    return RecordSet(cls._instantiate(row) for row in rows)

  @classmethod
  def browse(cls, ids):
    if isinstance(ids, int):
      ids = [ids]
    return cls.search([('id', 'in', list(ids))], order='id')

  def read(self, field_names=None) -> dict:
    if field_names is None:
      field_names = list(self._fields.keys())
    result = {}
    for name in field_names:
      field = self._fields.get(name)
      if field is not None and getattr(field, 'compute', None):
        result[name] = self._compute_field(name)
      else:
        result[name] = self._values.get(name)
    return result

  def write(self, values) -> bool:
    db = self._database()
    payload = {
      name: type(self)._coerce_write_value(name, value)
      for name, value in dict(values).items()
    }
    payload, translations = type(self)._split_multi_lang_values(payload)
    sets: list[str] = []
    params: list = []
    now = self._now()

    for name, value in payload.items():
      field = self._fields.get(name)
      if field is None:
        raise ValueError(f"Unknown field '{name}' on model '{self._name}'")
      if isinstance(value, BaseModel) and getattr(value, '_is_new', False):
        value = value.save()
        payload[name] = value._values.get('id') if isinstance(value, BaseModel) else value
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
    self._values.update(payload)
    if 'updated_at' in self._fields and rowcount > 0:
      self._values['updated_at'] = now

    if rowcount > 0:
      for field_name, lang_values in translations.items():
        type(self).set_translations(self._values['id'], field_name, lang_values)
      self._recompute_computed()
    return rowcount > 0

  @classmethod
  def _references_to(cls, record_id) -> list[dict]:
    """References that would be left dangling by deleting ``record_id``."""

    from jerp.env import Environment

    try:
      registry = Environment.instance.registry()
      registry.ensure_loaded()
    except Exception:
      return []

    db = cls._database()
    references: list[dict] = []

    for model_name, model in registry.models.items():
      if getattr(model, '_virtual', False) or not getattr(model, '_table', None):
        continue

      table_checked = False
      table_exists = False

      for field_name, field in model._fields.items():
        comodel = getattr(field, 'comodel', None)
        # File/image fields store a ``sys.file`` id without declaring a comodel.
        if not comodel and isinstance(field, fields.FileField):
          comodel = 'sys.file'
        if comodel != cls._name:
          continue
        if not getattr(field, 'store', True) or not field.column_name:
          continue

        if not table_checked:
          table_exists = db.table_exists(model._table)
          table_checked = True
        if not table_exists:
          break

        where = f'{quote_ident(field.column_name)} = %s'
        params = [record_id]
        if model._table == cls._table:
          # A self-referencing field must not count the record itself.
          where += f' AND {quote_ident(model._fields["id"].column_name)} <> %s'
          params.append(record_id)

        row = db.fetchone(
          f'SELECT COUNT(*) AS total FROM {quote_table(model._table)} '
          f'WHERE {where}',
          params,
        )
        total = int(row['total']) if row and row.get('total') is not None else 0
        if total:
          references.append({
            'model': model._name,
            'field': field_name,
            'label': field.name or field_name,
            'count': total,
          })

    return references

  @classmethod
  def _assert_deletable(cls, record) -> None:
    references = cls._references_to(record._values['id'])
    if not references:
      return

    details = ', '.join(
      f"{reference['count']} "
      f"{reference['model'].split('.')[-1].replace('_', ' ')}"
      f"{'' if reference['count'] == 1 else 's'} via {reference['label']}"
      for reference in references
    )
    raise ValueError(
      f'Cannot delete {cls._name} "{cls.display_name(record)}": '
      f'it is referenced by {details}.'
    )

  def unlink(self) -> bool:
    type(self)._assert_deletable(self)
    db = self._database()
    sql = f'DELETE FROM {quote_table(self._table)} WHERE {quote_ident(self._fields["id"].column_name)} = %s'
    rowcount = db.execute(sql, [self._values['id']])
    if rowcount > 0 and getattr(type(self), '_track_refs', True) and not getattr(type(self), '_virtual', False):
      type(self)._delete_refs(self._values['id'])
    if rowcount > 0:
      type(self)._delete_translations(self._values['id'])
    return rowcount > 0

  # --- computed fields ----------------------------------------------------

  @classmethod
  def _computed_field_names(cls) -> list[str]:
    return [
      name
      for name, field in cls._fields.items()
      if getattr(field, 'compute', None)
    ]

  @classmethod
  def _compute_dependencies(cls, name: str) -> tuple:
    field = cls._fields.get(name)
    compute = getattr(field, 'compute', None)
    if not compute:
      return ()
    if callable(compute):
      return tuple(getattr(compute, '_jerp_depends', ()) or ())
    method = getattr(cls, str(compute), None)
    target = getattr(method, '__func__', method)
    return tuple(getattr(target, '_jerp_depends', ()) or ())

  def _compute_field(self, name: str):
    field = self._fields.get(name)
    compute = getattr(field, 'compute', None)
    if not compute:
      return self._values.get(name)

    computing = self.__dict__.setdefault('_computing', set())
    if name in computing:
      return self._values.get(name)
    computing.add(name)
    try:
      if callable(compute):
        compute(self)
      else:
        handler = getattr(self, str(compute), None)
        if handler is not None:
          handler()
    except Exception:
      # A missing optional value must not make the whole form unusable. The
      # stored/default value is returned instead.
      import logging

      logging.getLogger(__name__).debug(
        'Compute error for %s.%s', type(self)._name, name, exc_info=True
      )
      stored = self._values.get(name)
      if stored is None and isinstance(
        field, (fields.FloatField, fields.NumericField, fields.IntegerField)
      ):
        stored = 0
      return stored
    finally:
      computing.discard(name)
    return self._values.get(name)

  def _compute_all(self):
    for name in type(self)._computed_field_names():
      self._compute_field(name)

  def _write_computed(self, values: dict) -> None:
    if not values or not getattr(self, '_persisted', False):
      self._values.update(values)
      return
    db = self._database()
    sets = []
    params = []
    for name, value in values.items():
      field = self._fields.get(name)
      if field is None:
        continue
      sets.append(f'{quote_ident(field.column_name)} = %s')
      params.append(field.to_db(field.convert(value)))
    if not sets:
      self._values.update(values)
      return
    params.append(self._values['id'])
    sql = (
      f'UPDATE {quote_table(self._table)} SET {", ".join(sets)} '
      f'WHERE {quote_ident(self._fields["id"].column_name)} = %s'
    )
    db.execute(sql, params)
    self._values.update(values)

  def _recompute_computed(self, write: bool = True) -> None:
    names = type(self)._computed_field_names()
    if not names:
      return
    values = {name: self._compute_field(name) for name in names}
    if write and getattr(self, '_persisted', False):
      self._write_computed(values)
    else:
      self._values.update(values)

  # --- draft records ------------------------------------------------------

  _DRAFT_STANDARD_FIELDS = ('id', 'created_at', 'updated_at')

  @classmethod
  def _draft_model(cls):
    from jerp.env import Environment

    registry = Environment.instance.registry()
    Temp = registry.get('temp.model')
    if Temp is None:
      raise RuntimeError("The 'temp.model' draft model is not installed.")
    return Temp

  @staticmethod
  def _draft_token(token=None) -> str:
    value = str(token or '').strip()
    return value or str(uuid4())

  @classmethod
  def _draft_json(cls, values: dict) -> dict:
    def clean(value):
      if isinstance(value, BaseModel):
        if getattr(value, '_draft_id', None):
          return f'draft:{value._draft_id}'
        return value._values.get('id')
      if isinstance(value, (datetime, date)):
        return value.isoformat()
      if isinstance(value, Decimal):
        return float(value)
      if isinstance(value, dict):
        return {key: clean(item) for key, item in value.items()}
      if isinstance(value, (list, tuple)):
        return [clean(item) for item in value]
      return value

    return {name: clean(value) for name, value in (values or {}).items()}

  @staticmethod
  def _draft_load(text) -> dict:
    if isinstance(text, dict):
      return text
    if text is None:
      return {}
    if not isinstance(text, str):
      try:
        return dict(text)
      except (TypeError, ValueError):
        return {}
    try:
      data = json.loads(text or '{}')
    except (TypeError, ValueError):
      data = {}
    return data if isinstance(data, dict) else {}

  @classmethod
  def _draft_filter_values(cls, values) -> dict:
    result = {}
    for name, value in (values or {}).items():
      field = cls._fields.get(name)
      if (
        field is None
        or name in cls._DRAFT_STANDARD_FIELDS
        or field.readonly
        or field.hide
        or getattr(field, 'compute', None)
      ):
        continue
      result[name] = cls._coerce_write_value(name, value)
    return cls._draft_json(result)

  @classmethod
  def _draft_defaults(cls) -> dict:
    values = {}
    for name, field in cls._fields.items():
      if (
        name in cls._DRAFT_STANDARD_FIELDS
        or field.auto_increment
        or field.hide
        or getattr(field, 'compute', None)
      ):
        continue
      value = cls._auto_value(field, creating=True)
      if value is not None:
        values[name] = value
    return cls._draft_json(values)

  @classmethod
  def _draft_record_values(cls, record) -> dict:
    names = [
      name
      for name in cls._fields
      if name not in cls._DRAFT_STANDARD_FIELDS
      and not cls._fields[name].hide
    ]
    return cls._draft_json(record.read(names))

  @classmethod
  def _draft_dict(cls, draft) -> dict:
    data = cls._draft_load(draft.data)
    if draft.state != 'delete':
      try:
        record = cls._draft_record_from_row(draft)
        record._compute_all()
        for name in cls._computed_field_names():
          if name in record._values:
            data[name] = record._values[name]
      except Exception:
        pass
    return {
      'id': draft.id,
      'draft_id': draft.id,
      'model': draft.model,
      'record_id': draft.record_id,
      'state': draft.state,
      'values': data,
      'dirty': cls._draft_load(draft.dirty),
      'version': int(draft.version or 0),
      'base_stamp': (
        draft.base_stamp.isoformat() if draft.base_stamp else None
      ),
    }

  @classmethod
  def _pseudo_record(
    cls,
    values,
    draft_id=None,
    token=None,
    record_id=None,
    state=None,
  ):
    obj = cls._new_base(values, persisted=False)
    obj._pseudo = True
    obj._is_new = record_id is None or state == 'create'
    obj._draft_id = draft_id
    obj._draft_state = state
    obj._record_id = record_id
    obj._token = token
    return obj

  @classmethod
  def _draft_record_from_row(cls, row):
    data = cls._draft_load(row.data)
    return cls._pseudo_record(
      data,
      draft_id=row.id,
      token=row.token,
      record_id=row.record_id,
      state=row.state,
    )

  @classmethod
  def _draft_record(cls, draft_id):
    try:
      Temp = cls._draft_model()
    except Exception:
      return None
    rows = Temp.browse(draft_id)
    if not rows:
      return None
    row = rows[0]
    if row.model != cls._name:
      return None
    return cls._draft_record_from_row(row)

  @classmethod
  def _new_record(cls, values=None):
    data = cls._draft_defaults()
    incoming = dict(values or {})
    one2many = {}
    relation_names = cls._reverse_relations()
    for name, value in list(incoming.items()):
      if name in relation_names:
        one2many[name] = incoming.pop(name)
        continue
      field = cls._fields.get(name)
      if field is None or name in cls._DRAFT_STANDARD_FIELDS:
        incoming.pop(name, None)
        continue
      incoming[name] = cls._coerce_write_value(name, value)
    for name, value in incoming.items():
      data[name] = (
        value
        if isinstance(value, BaseModel)
        else cls._draft_json({name: value})[name]
      )

    obj = cls._pseudo_record(data, state='create')
    obj._is_new = True
    obj._pseudo = True

    if incoming:
      cls._run_on_change(
        data,
        list(incoming),
        record=obj,
      )
      obj._values.update(data)

    for name, commands in one2many.items():
      obj._assign_one2many(name, commands, *relation_names[name])

    obj._compute_all()
    return obj

  @classmethod
  def _run_on_change(
    cls,
    values: dict,
    changed_fields,
    record_id=None,
    draft_id=None,
    token=None,
    record=None,
  ) -> dict:
    """Run every on-change handler triggered by ``changed_fields``.

    Handlers may be instance methods (Odoo style: they mutate ``self``) or
    classmethods returning a values dictionary. Computed fields are evaluated
    afterwards and included in ``values``.
    """

    handlers: dict[str, list[tuple[str, object, str]]] = {}
    for method_name in dir(cls):
      try:
        static = inspect.getattr_static(cls, method_name)
      except Exception:
        continue
      if isinstance(static, classmethod):
        kind = 'class'
        target = static.__func__
      elif isinstance(static, staticmethod):
        kind = 'static'
        target = static.__func__
      else:
        kind = 'instance'
        target = static
      declared = getattr(target, '_jerp_on_change_fields', None)
      if not declared:
        continue
      for field_name in declared:
        if field_name in cls._fields:
          handlers.setdefault(field_name, []).append(
            (method_name, static, kind)
          )

    if record is None:
      record = cls._pseudo_record(
        values,
        draft_id=draft_id,
        token=token,
        record_id=record_id,
        state='create' if record_id is None else 'update',
      )
    record._values.update(values)

    warnings = []
    errors = {}
    domains = {}

    def apply_result(result):
      if not isinstance(result, dict):
        return
      if any(
        key in result for key in ('values', 'warnings', 'errors', 'domains')
      ):
        new_values = result.get('values') or {}
        warnings.extend(result.get('warnings') or [])
        errors.update(result.get('errors') or {})
        domains.update(result.get('domains') or {})
      else:
        new_values = result
      for name, value in new_values.items():
        if name not in cls._fields or name in cls._DRAFT_STANDARD_FIELDS:
          continue
        value = cls._coerce_write_value(name, value)
        if values.get(name) != value:
          values[name] = cls._draft_json({name: value})[name]
          record._values[name] = value
          if name not in visited:
            queue.append(name)

    queue = [
      name for name in changed_fields if name in cls._fields
    ]
    visited = set()
    executed = set()
    steps = 0

    while queue and steps < 100:
      steps += 1
      field_name = queue.pop(0)
      if field_name in visited:
        continue
      visited.add(field_name)

      for method_name, static, kind in handlers.get(field_name, []):
        if method_name in executed:
          continue
        executed.add(method_name)

        kwargs = {}
        method = getattr(cls, method_name)
        try:
          parameters = inspect.signature(method).parameters
        except (TypeError, ValueError):
          parameters = {}
        if 'record_id' in parameters:
          kwargs['record_id'] = record_id
        if 'draft_id' in parameters:
          kwargs['draft_id'] = draft_id

        if kind in ('class', 'static'):
          apply_result(method(dict(values), **kwargs))
          continue

        before = dict(record._values)
        result = getattr(record, method_name)()
        apply_result(result)
        for name in cls._fields:
          if name in cls._DRAFT_STANDARD_FIELDS:
            continue
          value = record._values.get(name)
          if before.get(name) != value:
            values[name] = cls._draft_json({name: value})[name]
            if name not in visited:
              queue.append(name)

    record._values.update(values)
    record._compute_all()
    for name in cls._computed_field_names():
      if name in record._values:
        values[name] = cls._draft_json({name: record._values[name]})[name]

    return {
      'warnings': warnings,
      'errors': errors,
      'domains': domains,
    }

  @classmethod
  def resolve_draft(cls, value, model_name=None) -> dict | None:
    """Resolve a ``draft:<id>`` value for on-change methods."""

    if not (isinstance(value, str) and value.startswith('draft:')):
      return None

    Temp = cls._draft_model()
    draft_id = int(value.split(':', 1)[1])
    rows = Temp.browse(draft_id)
    if not rows:
      raise ValueError(f'Draft {draft_id} does not exist.')
    draft = rows[0]
    if model_name and draft.model != model_name:
      raise ValueError(
        f'Draft {draft_id} is a {draft.model}, not {model_name}.'
      )
    from jerp.env import Environment

    registry = Environment.instance.registry()
    owner = registry.get(draft.model) or cls
    return owner._draft_dict(draft)

  @classmethod
  @api_expose
  def new(cls, token=None, values=None, reuse=True):
    """Create a new record.

    Without a draft token this returns an in-memory pseudo-record (Odoo style)
    that ``record.save()`` writes directly. With a token it keeps the existing
    server-side draft behaviour used by forms. Pass ``reuse=False`` to create a
    second draft for the same model/token (one row per table record).
    """

    if getattr(cls, '_virtual', False):
      raise ValueError('Virtual models do not support drafts.')
    if token is None:
      return cls._new_record(values)
    token = cls._draft_token(token)
    Temp = cls._draft_model()
    existing = []
    if reuse:
      existing = Temp.search(
        [
          ('token', '=', token),
          ('model', '=', cls._name),
          ('state', '=', 'create'),
          ('record_id', 'is null', None),
        ],
        limit=1,
      )
    if existing:
      return cls._draft_dict(existing[0])

    data = cls._draft_defaults()
    data.update(cls._draft_filter_values(values))
    draft = Temp.create(
      token=token,
      model=cls._name,
      record_id=None,
      state='create',
      data=json.dumps(data),
      dirty={},
      version=0,
    )
    return cls._draft_dict(draft)

  @classmethod
  @api_expose
  def edit(cls, id, token=None, values=None):
    """Create (or return) a draft copy of an existing record."""

    if getattr(cls, '_virtual', False):
      raise ValueError('Virtual models do not support drafts.')
    token = cls._draft_token(token)
    record_id = int(id)
    Temp = cls._draft_model()

    existing = Temp.search(
      [
        ('token', '=', token),
        ('model', '=', cls._name),
        ('record_id', '=', record_id),
      ],
      limit=1,
    )
    if existing:
      draft = existing[0]
      if draft.state == 'delete':
        records = cls.browse(record_id)
        if not records:
          raise ValueError(f'{cls._name}#{record_id} no longer exists.')
        record = records[0]
        stamp = record.read(['updated_at']).get('updated_at')
        draft.write(
          {
            'state': 'update',
            'data': json.dumps(cls._draft_record_values(record)),
            'dirty': {},
            'base_stamp': stamp,
            'version': int(draft.version or 0) + 1,
          }
        )
      return cls._draft_dict(draft)

    records = cls.browse(record_id)
    if not records:
      raise ValueError(f'{cls._name}#{record_id} does not exist.')
    record = records[0]
    data = cls._draft_record_values(record)
    initial = cls._draft_filter_values(values)
    data.update(initial)
    stamp = record.read(['updated_at']).get('updated_at')
    draft = Temp.create(
      token=token,
      model=cls._name,
      record_id=record_id,
      state='update',
      data=json.dumps(data),
      dirty=initial,
      base_stamp=stamp,
      version=0,
    )
    return cls._draft_dict(draft)

  @classmethod
  @api_expose
  def change(cls, draft_id, values):
    """Apply field changes to a draft and run server-side on-change methods."""

    if getattr(cls, '_virtual', False):
      raise ValueError('Virtual models do not support drafts.')
    Temp = cls._draft_model()
    rows = Temp.browse(draft_id)
    if not rows:
      raise ValueError(f'Draft {draft_id} does not exist.')
    draft = rows[0]
    if draft.model != cls._name:
      raise ValueError(
        f'Draft {draft_id} belongs to {draft.model}, not {cls._name}.'
      )
    if draft.state == 'delete':
      raise ValueError('A draft staged for deletion cannot be changed.')

    data = cls._draft_load(draft.data)
    dirty = cls._draft_load(draft.dirty)
    before = dict(data)
    incoming = cls._draft_filter_values(values)
    changed = []

    for name, value in incoming.items():
      if data.get(name) != value:
        data[name] = value
        changed.append(name)

    result = cls._run_on_change(
      data,
      changed,
      record_id=draft.record_id,
      draft_id=draft.id,
      token=draft.token,
    )

    if draft.state == 'update':
      for name, value in data.items():
        if before.get(name) != value and name in cls._fields:
          dirty[name] = value

    version = int(draft.version or 0) + 1
    draft.write(
      {
        'data': json.dumps(cls._draft_json(data)),
        'dirty': cls._draft_json(dirty),
        'version': version,
      }
    )
    cls._refresh_parent_drafts(draft, data)
    values = cls._draft_json(data)
    return {
      'id': draft.id,
      'draft_id': draft.id,
      'model': draft.model,
      'record_id': draft.record_id,
      'state': draft.state,
      'values': values,
      'dirty': dirty,
      'version': version,
      'changed': changed,
      'warnings': result['warnings'],
      'errors': result['errors'],
      'domains': result['domains'],
    }

  @classmethod
  def _refresh_parent_drafts(cls, draft, values):
    """Recompute computed fields on drafts referring to ``draft``."""

    try:
      from jerp.env import Environment

      registry = Environment.instance.registry()
      Temp = cls._draft_model()
    except Exception:
      return

    for name, value in values.items():
      field = cls._fields.get(name)
      comodel = getattr(field, 'comodel', None) if field else None
      if not comodel:
        continue
      if not (isinstance(value, str) and value.startswith('draft:')):
        continue
      try:
        parent_id = int(value.split(':', 1)[1])
      except ValueError:
        continue
      rows = Temp.browse(parent_id)
      if not rows:
        continue
      parent_row = rows[0]
      if parent_row.model != comodel:
        continue
      Parent = registry.get(comodel)
      if Parent is None or not Parent._computed_field_names():
        continue
      parent_data = Parent._draft_load(parent_row.data)
      parent = Parent._pseudo_record(
        parent_data,
        draft_id=parent_id,
        token=parent_row.token,
        record_id=parent_row.record_id,
        state=parent_row.state,
      )
      parent._compute_all()
      changed = False
      for computed in Parent._computed_field_names():
        computed_value = parent._values.get(computed)
        if parent_data.get(computed) != computed_value:
          parent_data[computed] = computed_value
          changed = True
      if changed:
        parent_row.write(
          {
            'data': json.dumps(Parent._draft_json(parent_data)),
            'version': int(parent_row.version or 0) + 1,
          }
        )

  @classmethod
  @api_expose
  def drafts(cls, token=None):
    """List every draft in a token, across models."""

    from jerp.env import Environment

    token = cls._draft_token(token)
    Temp = cls._draft_model()
    registry = Environment.instance.registry()
    rows = Temp.search([('token', '=', token)], order='id')
    result = []
    for row in rows:
      owner = registry.get(row.model) or cls
      result.append(owner._draft_dict(row))
    return result

  @classmethod
  @api_expose
  def discard(cls, draft_id):
    """Discard one draft without touching the real record."""

    Temp = cls._draft_model()
    rows = Temp.browse(draft_id)
    if not rows:
      return False
    draft = rows[0]
    if draft.model != cls._name:
      raise ValueError(
        f'Draft {draft_id} belongs to {draft.model}, not {cls._name}.'
      )
    return draft.unlink()

  @classmethod
  @api_expose
  def discard_all(cls, token=None):
    """Discard every draft in a token."""

    token = cls._draft_token(token)
    Temp = cls._draft_model()
    drafts = Temp.search([('token', '=', token)])
    for draft in drafts:
      draft.unlink()
    return len(drafts)

  @classmethod
  @api_expose
  def remove(cls, token, id):
    """Stage deletion of an existing record."""

    if getattr(cls, '_virtual', False):
      raise ValueError('Virtual models do not support drafts.')
    token = cls._draft_token(token)
    record_id = int(id)
    Temp = cls._draft_model()

    existing = Temp.search(
      [
        ('token', '=', token),
        ('model', '=', cls._name),
        ('record_id', '=', record_id),
      ],
      limit=1,
    )
    if existing:
      draft = existing[0]
      if draft.state == 'create':
        draft.unlink()
        return None
      draft.write(
        {
          'state': 'delete',
          'dirty': {},
          'version': int(draft.version or 0) + 1,
        }
      )
      return cls._draft_dict(draft)

    records = cls.browse(record_id)
    if not records:
      raise ValueError(f'{cls._name}#{record_id} does not exist.')
    record = records[0]
    stamp = record.read(['updated_at']).get('updated_at')
    draft = Temp.create(
      token=token,
      model=cls._name,
      record_id=record_id,
      state='delete',
      data=json.dumps({}),
      dirty={},
      base_stamp=stamp,
      version=0,
    )
    return cls._draft_dict(draft)

  @classmethod
  def _record_write_values(cls, record) -> dict:
    values = {}
    for name, field in cls._fields.items():
      if (
        name in cls._DRAFT_STANDARD_FIELDS
        or field.auto_increment
        or getattr(field, 'compute', None)
        or field.hide
      ):
        continue
      if name in record._values:
        value = record._values.get(name)
        if value is None and field.required and isinstance(
          field, (fields.StringField, fields.TextField)
        ):
          value = ''
        values[name] = cls._coerce_write_value(name, value)
    return values

  def _save_record(self):
    """Save this record (instance form of ``Model.save``)."""

    cls = type(self)
    if self._draft_id:
      results = cls.commit(self._token)
      for result in results:
        if result.get('draft_id') == self._draft_id:
          rows = cls.browse(result['id'])
          if rows:
            real = rows[0]
            self._values = dict(real._values)
            self._persisted = True
            self._is_new = False
            self._pseudo = False
            self._record_id = real.id
            self._draft_id = None
            self._one2many_cache = {}
          break
      return self

    if self._persisted:
      return self

    database = cls._database()
    with database.transaction():
      self._compute_all()
      created = cls.create(**cls._record_write_values(self))
      children = []
      relations = cls._reverse_relations()
      for name, rows in self.__dict__.get('_one2many_cache', {}).items():
        relation = relations.get(name)
        if relation is None:
          continue
        child_model, inverse_name = relation
        for child in rows:
          child._compute_all()
          values = child_model._record_write_values(child)
          values[inverse_name] = created.id
          children.append(child_model.create(**values))
      for child in children:
        child._recompute_computed()
      created._recompute_computed()
      self._values = dict(created._values)
      self._persisted = True
      self._is_new = False
      self._pseudo = False
      self._record_id = created.id
      self._one2many_cache = {}
    return self

  @classmethod
  def _save_draft(cls, draft_id):
    """Commit the token containing one draft."""

    Temp = cls._draft_model()
    rows = Temp.browse(draft_id)
    if not rows:
      raise ValueError(f'Draft {draft_id} does not exist.')
    return cls.commit(rows[0].token)

  save = dualmethod(_save_record, _save_draft, exposed=True)

  @classmethod
  @api_expose
  def commit(cls, token=None, parent_field=None, parent_id=None):
    """Commit every draft in a token atomically."""

    from jerp.env import Environment

    token = cls._draft_token(token)
    registry = Environment.instance.registry()
    Temp = cls._draft_model()
    rows = Temp.search([('token', '=', token)], order='id')
    if not rows:
      return []

    items = []
    by_id = {}
    for row in rows:
      real = registry.get(row.model)
      if real is None:
        raise ValueError(f'Draft points to unknown model "{row.model}".')
      data = cls._draft_load(row.data)
      dirty = cls._draft_load(row.dirty)
      item = {
        'draft': row,
        'real': real,
        'state': row.state,
        'data': data,
        'dirty': dirty,
        'deps': set(),
      }
      items.append(item)
      by_id[row.id] = item

    for item in items:
      if item['state'] == 'delete':
        continue
      for name, value in item['data'].items():
        field = item['real']._fields.get(name)
        if field is None or not getattr(field, 'comodel', None):
          continue
        if not (isinstance(value, str) and value.startswith('draft:')):
          continue
        try:
          target_id = int(value.split(':', 1)[1])
        except ValueError:
          raise ValueError(f'Invalid draft reference: {value!r}')
        target = by_id.get(target_id)
        if target is None:
          raise ValueError(
            f'Referenced draft {target_id} is not in token {token}.'
          )
        if target['state'] == 'delete':
          raise ValueError(
            f'Draft {item["draft"].id} references a record staged for deletion.'
          )
        if target['real']._name != field.comodel:
          raise ValueError(
            f'Draft reference {value!r} does not match {field.comodel}.'
          )
        item['deps'].add(target_id)

    resolved = {}
    for item in items:
      if item['state'] in ('update', 'delete') and item['draft'].record_id:
        resolved[item['draft'].id] = item['draft'].record_id

    def resolve_value(value):
      if isinstance(value, str) and value.startswith('draft:'):
        target_id = int(value.split(':', 1)[1])
        if target_id not in resolved:
          raise ValueError(f'Unresolved draft reference: {value!r}')
        return resolved[target_id]
      return value

    results = []
    pending = [
      item for item in items if item['state'] in ('create', 'update')
    ]
    database = cls._database()

    with database.transaction():
      while pending:
        progressed = False
        for item in list(pending):
          if not item['deps'].issubset(resolved):
            continue

          real = item['real']
          draft = item['draft']

          def resolved_values(values):
            result = {}
            for name, value in values.items():
              field = real._fields.get(name)
              if field is None or name in cls._DRAFT_STANDARD_FIELDS:
                continue
              result[name] = (
                resolve_value(value)
                if getattr(field, 'comodel', None)
                else value
              )
            return result

          if item['state'] == 'create':
            values = resolved_values(item['data'])
            if (
              parent_field
              and parent_field in real._fields
              and parent_field not in values
              and parent_id not in (None, '')
            ):
              values[parent_field] = parent_id
            record = real.create(**values)
            resolved[draft.id] = record.id
            results.append(
              {
                'draft_id': draft.id,
                'model': real._name,
                'id': record.id,
                'state': 'create',
              }
            )
          else:
            record_id = draft.record_id
            records = real.browse(record_id)
            if not records:
              raise ValueError(
                f'{real._name}#{record_id} no longer exists.'
              )
            record = records[0]
            if draft.base_stamp and 'updated_at' in real._fields:
              current = record.read(['updated_at']).get('updated_at')
              if current != draft.base_stamp:
                raise ValueError(
                  f'{real._name}#{record_id} changed since the draft was created.'
                )
            changes = resolved_values(item['dirty'])
            if changes:
              record.write(changes)
            results.append(
              {
                'draft_id': draft.id,
                'model': real._name,
                'id': record_id,
                'state': 'update',
              }
            )

          pending.remove(item)
          progressed = True

        if not progressed:
          raise ValueError('Circular draft references cannot be committed.')

      for item in items:
        if item['state'] != 'delete':
          continue
        real = item['real']
        draft = item['draft']
        records = real.browse(draft.record_id)
        if not records:
          continue
        record = records[0]
        if draft.base_stamp and 'updated_at' in real._fields:
          current = record.read(['updated_at']).get('updated_at')
          if current != draft.base_stamp:
            raise ValueError(
              f'{real._name}#{draft.record_id} changed since the draft was created.'
            )
        record.unlink()
        results.append(
          {
            'draft_id': draft.id,
            'model': real._name,
            'id': draft.record_id,
            'state': 'delete',
          }
        )

      # Recompute stored computed fields once every created/updated record
      # exists, so parent totals see their committed children.
      for result in results:
        if result['state'] not in ('create', 'update'):
          continue
        real = registry.get(result['model'])
        if real is None or not real._computed_field_names():
          continue
        records = real.browse(result['id'])
        if records:
          records[0]._recompute_computed()

      for row in rows:
        row.unlink()

    return results

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
    database = cls._database()
    with database.transaction():
      for record in cls.browse([int(value) for value in ids]):
        if record.unlink():
          deleted += 1
    return deleted

  # --- source cooperation -------------------------------------------------

  @classmethod
  def call_exposed(cls, func: str, body=None):
    """Call an exposed model method from the API controller."""

    payload = dict(body or {})
    raw = inspect.getattr_static(cls, func)
    if isinstance(raw, dualmethod):
      return getattr(cls, func)(**payload)
    if isinstance(raw, (classmethod, staticmethod)):
      return getattr(cls, func)(**payload)

    record_id = payload.pop('id', None)
    draft_id = payload.pop('draft_id', None)
    if record_id is not None:
      records = cls.browse(record_id)
      if len(records) != 1:
        raise ValueError(f'{cls._name}#{record_id} does not exist.')
      return getattr(records[0], func)(**payload)
    if draft_id is not None:
      record = cls._draft_record(draft_id)
      if record is None:
        raise ValueError(f'Draft {draft_id} does not exist.')
      return getattr(record, func)(**payload)
    raise ValueError(f'Method "{func}" requires a record id.')

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
