"""Declarative field types used by J-ERP models.

A :class:`Field` carries two kinds of information:

* **Schema** – how the column is created in PostgreSQL (``column_type``,
  nullability, defaults, uniqueness, indexes).
* **Values** – how Python values are converted to and from the database.

Field instances are declared as class attributes on a model; the model
metaclass collects them (see :mod:`jerp.models`).
"""

from __future__ import annotations

from psycopg.types.json import Json


def _relation_value(instance, field, value):
  """Resolve a many2one value into a recordset of the related model."""

  from jerp.models import BaseModel, RecordSet

  if isinstance(value, BaseModel):
    return RecordSet([value])
  if value in (None, False, '', 0, '0'):
    return RecordSet()

  from jerp.env import Environment

  try:
    registry = Environment.instance.registry()
    comodel = registry.get(field.comodel)
  except Exception:
    comodel = None
  if comodel is None:
    return value

  if isinstance(value, str) and value.startswith('draft:'):
    record = comodel._draft_record(int(value.split(':', 1)[1]))
    if record is not None:
      return RecordSet([record])
    return RecordSet()
  if isinstance(value, dict):
    value = value.get('id')
    if value in (None, ''):
      return RecordSet()
  try:
    return comodel.browse(int(value))
  except (TypeError, ValueError):
    return value


class Field:
  """Base class for every field type.

  ``renamed_from`` opts a renamed field into an automatic column rename. Without
  it the syncer treats the old column as retired data and leaves it in place, so
  a rename can never be guessed from declaration order.
  """

  #: Canonical type code, also used by the dialect for normalization.
  ttype = 'field'

  #: True for the auto-generated primary key column.
  auto_increment = False

  #: True for the primary key column.
  primary_key = False

  def __init__(
    self,
    name=None,
    required=False,
    default=None,
    unique=False,
    index=False,
    column_name=None,
    renamed_from=None,
    readonly=False,
    help=None,
    hide=False,
    multi_language=False,
    compute=None,
    store=True,
  ):
    self.name = name
    self.required = required
    self.default = default
    self.unique = unique
    self.index = index
    self.column_name = column_name
    #: Previous attribute name of this field. The syncer renames its column
    #: instead of adding a new one and leaving the old data behind.
    self.renamed_from = renamed_from
    self.readonly = readonly
    self.help = help
    #: Exclude the field's value from API record data (reads). It stays in the
    #: field schema so forms can still write it (e.g. passwords).
    self.hide = hide
    #: Store alternate-language values in ``sys.multi_lang_char`` while the
    #: column itself keeps the default language value.
    self.multi_language = bool(multi_language)
    #: Name of a model method (or a callable) computing this field's value.
    self.compute = compute
    #: Whether the computed value is stored in the database.
    self.store = store
    if compute:
      # Computed fields are never edited directly by the client.
      self.readonly = True
    self.attr_name = None

  # --- descriptor protocol ------------------------------------------------
  # Fields behave as descriptors, so ``record.name`` returns the stored value
  # while ``Model.name`` still returns the Field instance (used for metadata).

  def __set_name__(self, owner, name):
    if self.attr_name is None:
      self.attr_name = name
    if self.column_name is None:
      self.column_name = name

  def __get__(self, instance, owner=None):
    if instance is None:
      return self
    if self.compute and hasattr(instance, '_compute_field'):
      return instance._compute_field(self.attr_name)
    value = instance.__dict__.get('_values', {}).get(self.attr_name)
    if getattr(self, 'comodel', None):
      return _relation_value(instance, self, value)
    return value

  def __set__(self, instance, value):
    if (
      getattr(instance, '_persisted', False)
      and not self.compute
      and hasattr(instance, 'write')
    ):
      instance.write({self.attr_name: value})
      return
    if getattr(self, 'comodel', None) and hasattr(
      type(instance), '_coerce_write_value'
    ):
      value = type(instance)._coerce_write_value(self.attr_name, value)
    instance.__dict__.setdefault('_values', {})[self.attr_name] = value

  # --- schema -------------------------------------------------------------

  def column_type(self) -> str:
    """The PostgreSQL type used for this field's column."""

    raise NotImplementedError

  def nullable(self) -> bool:
    """Whether the column accepts NULL values."""

    if self.primary_key or self.auto_increment:
      return False
    return not self.required

  def sql_default(self):
    """A literal SQL default, or ``None`` when the default is computed."""

    if self.auto_increment:
      # serial / bigserial columns manage their own default through a sequence.
      return None
    if self.default is None or callable(self.default):
      return None
    return self._literal(self.default)

  def _literal(self, value) -> str:
    if value is True:
      return 'TRUE'
    if value is False:
      return 'FALSE'
    if value is None:
      return 'NULL'
    if isinstance(value, (int, float)):
      return str(value)
    return "'" + str(value).replace("'", "''") + "'"

  # --- values -------------------------------------------------------------

  def to_db(self, value):
    """Convert a Python value into something psycopg can send."""

    return value

  def to_python(self, value):
    """Convert a value coming from the database into a Python value."""

    return value

  def convert(self, value):
    """Apply defaults / required checks before writing."""

    if value is None and self.default is not None and not callable(self.default):
      value = self.default
    return value


class StringField(Field):
  ttype = 'char'

  def __init__(self, name=None, default='', size=255, **kwargs):
    super().__init__(name=name, default=default, **kwargs)
    self.size = size

  def column_type(self) -> str:
    return f'varchar({self.size})'


class TextField(Field):
  ttype = 'text'

  def __init__(self, default='', **kwargs):
    super().__init__(default=default, **kwargs)

  def column_type(self) -> str:
    return 'text'


class PasswordField(StringField):
  ttype = 'password'


class IntegerField(Field):
  ttype = 'integer'

  def __init__(self, name=None, default=0, **kwargs):
    super().__init__(name=name, default=default, **kwargs)

  def column_type(self) -> str:
    return 'integer'

  def to_db(self, value):
    return None if value is None else int(value)

  def to_python(self, value):
    return None if value is None else int(value)


class BigIntField(IntegerField):
  ttype = 'bigint'

  def __init__(self, default=0, **kwargs):
    super().__init__(default=default, **kwargs)

  def column_type(self) -> str:
    return 'bigint'


class NumericField(Field):
  ttype = 'numeric'

  def __init__(self, name=None, default=0.0, precision=16, scale=2, **kwargs):
    super().__init__(name=name, default=default, **kwargs)
    self.precision = precision
    self.scale = scale

  def column_type(self) -> str:
    if self.scale is None:
      return f'numeric({self.precision})'
    return f'numeric({self.precision},{self.scale})'


class FloatField(Field):
  ttype = 'double'

  def __init__(self, default=0.0, **kwargs):
    super().__init__(default=default, **kwargs)

  def column_type(self) -> str:
    return 'double precision'

  def to_db(self, value):
    return None if value is None else float(value)


class BooleanField(Field):
  ttype = 'boolean'

  def __init__(self, default=False, **kwargs):
    super().__init__(default=default, **kwargs)

  def column_type(self) -> str:
    return 'boolean'

  def _literal(self, value) -> str:
    return 'TRUE' if value else 'FALSE'


class DateField(Field):
  ttype = 'date'

  def column_type(self) -> str:
    return 'date'


class DateTimeField(Field):
  ttype = 'timestamp'

  def __init__(self, name=None, use_tz=False, auto_now=False, auto_now_add=False, **kwargs):
    super().__init__(name=name, **kwargs)
    self.use_tz = use_tz
    self.auto_now = auto_now
    self.auto_now_add = auto_now_add

  def column_type(self) -> str:
    return 'timestamptz' if self.use_tz else 'timestamp'


class JsonField(Field):
  ttype = 'jsonb'

  def column_type(self) -> str:
    return 'jsonb'

  def to_db(self, value):
    if value is None:
      return None
    return Json(value)


class SelectionField(StringField):
  ttype = 'selection'

  def __init__(self, selection=None, *, name=None, **kwargs):
    super().__init__(name=name, **kwargs)
    self.selection = list(selection or [])


class Many2oneField(BigIntField):
  ttype = 'many2one'

  def __init__(self, comodel=None, *, name=None, index=True, **kwargs):
    super().__init__(name=name, index=index, **kwargs)
    self.comodel = comodel


class FileField(IntegerField):
  """A reference to a stored file (the ``file`` model id)."""

  ttype = 'file'


class ImageField(FileField):
  """A file field rendered with an image preview (same storage as FileField)."""

  ttype = 'image'


class IdField(BigIntField):
  """Auto-incrementing primary key (``bigserial``)."""

  ttype = 'id'
  auto_increment = True
  primary_key = True

  def __init__(self, name=None, **kwargs):
    super().__init__(name=name, required=True, **kwargs)

  def column_type(self) -> str:
    return 'bigserial'

  def nullable(self) -> bool:
    return False
