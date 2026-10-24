"""Low-level SQL dialect helpers for J-ERP.

Only PostgreSQL is supported for now. The dialect is responsible for turning
declarative model metadata into DDL and for normalizing what the database
reports back through ``information_schema`` / ``pg_catalog`` so that the schema
syncer can compare the two.
"""

from __future__ import annotations


def quote_ident(name: str) -> str:
  """Safely quote an SQL identifier (table, column, index, ...).

  Identifiers in J-ERP come from Python attribute names, but we still quote
  defensively and reject anything that is not a non-empty string.
  """

  if not isinstance(name, str) or not name:
    raise ValueError(f"Invalid SQL identifier: {name!r}")

  return '"' + name.replace('"', '""') + '"'


def quote_table(name: str) -> str:
  return quote_ident(name)


def _type_family(code: str) -> str:
  """The part of a canonical type before its parameters (``numeric(16,2)``)."""

  family = str(code or '').split('(', 1)[0].strip()
  # ``double precision`` is spelled out in field types but is one family.
  return 'double' if family == 'double precision' else family


def _type_params(code: str) -> tuple | None:
  """Integer parameters of a canonical type, or ``None`` when unconstrained."""

  text = str(code or '')
  if '(' not in text or ')' not in text:
    return None
  inner = text[text.index('(') + 1:text.rindex(')')]
  try:
    return tuple(int(part) for part in inner.split(','))
  except ValueError:
    return None


class PostgresDialect:
  """PostgreSQL specific SQL generation and type normalization."""

  name = 'postgresql'

  def __init__(self, schema: str = 'public'):
    self.schema = schema

  # --- type normalization -------------------------------------------------

  # Map canonical field type codes to the string PostgreSQL reports in
  # ``information_schema.columns.data_type``.
  _PG_DATA_TYPE = {
    'varchar': 'character varying',
    'text': 'text',
    'integer': 'integer',
    'bigint': 'bigint',
    'smallint': 'smallint',
    'numeric': 'numeric',
    'double': 'double precision',
    'boolean': 'boolean',
    'timestamp': 'timestamp without time zone',
    'timestamptz': 'timestamp with time zone',
    'date': 'date',
    'time': 'time without time zone',
    'jsonb': 'jsonb',
    'json': 'json',
  }

  # Reverse map: ``data_type`` -> canonical code.
  _CODE_BY_DATA_TYPE = {v: k for k, v in _PG_DATA_TYPE.items()}

  def normalize(self, data_type: str, char_max=None, precision=None, scale=None) -> str:
    """Build a canonical type string from an ``information_schema`` row."""

    code = self._CODE_BY_DATA_TYPE.get(data_type, data_type)

    if code == 'varchar' and char_max is not None:
      return f'varchar({char_max})'
    if code == 'numeric' and precision is not None:
      if scale is not None:
        return f'numeric({precision},{scale})'
      return f'numeric({precision})'
    # ``double`` is the canonical code but the field type spells out
    # ``double precision``; compare against the same spelling.
    if code == 'double':
      return 'double precision'
    return code

  def column_signature(self, field) -> str:
    """Canonical type string for a declared field."""

    return field.column_type()

  def can_cast_losslessly(self, old: str, new: str) -> bool:
    """Whether ``old -> new`` can run as ``USING column::new`` without loss.

    Used by the schema syncer to decide if a type change may be applied
    automatically. Anything that can truncate, round, re-parse or reinterpret
    values returns ``False`` and must be handled by an explicit migration.
    """

    if old == new:
      return True

    old_family = _type_family(old)
    new_family = _type_family(new)

    # Everything can be rendered as text; this is the one cast that never
    # rejects existing values.
    if new_family == 'text':
      return True

    # varchar -> varchar may widen; narrowing silently truncates.
    if old_family == 'varchar' and new_family == 'varchar':
      old_size = _type_params(old)
      new_size = _type_params(new)
      if new_size is None:
        return True  # unbounded varchar
      return old_size is not None and new_size[0] >= old_size[0]

    # Integers may widen into integers, numeric or float. bigint -> float loses
    # precision above 2**53, so floats are only accepted from smaller integers.
    if old_family == 'smallint':
      return new_family in ('integer', 'bigint', 'numeric', 'double')
    if old_family == 'integer':
      return new_family in ('bigint', 'numeric', 'double')
    if old_family == 'bigint':
      return new_family == 'numeric'

    # numeric -> numeric is safe while precision and scale only grow.
    if old_family == 'numeric' and new_family == 'numeric':
      old_params = _type_params(old)
      new_params = _type_params(new)
      if new_params is None:
        return True  # unbounded numeric
      if old_params is None:
        return False
      old_precision, old_scale = old_params
      new_precision, new_scale = new_params
      return (
        new_scale >= old_scale
        and (new_precision - new_scale) >= (old_precision - old_scale)
      )

    # Calendar dates convert to timestamps at midnight; the reverse truncates.
    if old_family == 'date' and new_family == 'timestamp':
      return True

    # JSON and JSONB share the same value domain (jsonb normalises it).
    if {old_family, new_family} == {'json', 'jsonb'}:
      return True

    return False

  # --- DDL ----------------------------------------------------------------

  def column_definition(self, field) -> str:
    """Full column definition used inside CREATE TABLE."""

    parts = [quote_ident(field.column_name), field.column_type()]

    if field.primary_key:
      parts.append('PRIMARY KEY')

    if not field.nullable():
      parts.append('NOT NULL')

    # UNIQUE / non-unique indexes are created separately (see _sync_indexes) so
    # that they can be diffed and applied idempotently on existing tables.

    default = field.sql_default()
    if default is not None:
      parts.append(f'DEFAULT {default}')

    return ' '.join(parts)

  def create_table_sql(self, model) -> str:
    columns = [self.column_definition(f) for f in model._fields.values()]
    table = quote_table(model._table)
    body = ',\n  '.join(columns)
    return f'CREATE TABLE {table} (\n  {body}\n)'

  def add_column_sql(self, table: str, field) -> str:
    # PostgreSQL requires a NULL-safe default when adding NOT NULL columns to a
    # table that already has rows; we add the column nullable and then tighten
    # it, which keeps the operation safe for existing data.
    col = quote_ident(field.column_name)
    return f'ALTER TABLE {quote_table(table)} ADD COLUMN {col} {field.column_type()}'

  def alter_type_sql(self, table: str, field) -> str:
    col = quote_ident(field.column_name)
    return (
      f'ALTER TABLE {quote_table(table)} ALTER COLUMN {col} '
      f'TYPE {field.column_type()} USING {col}::{field.column_type()}'
    )

  def set_not_null_sql(self, table: str, field, not_null: bool = True) -> str:
    col = quote_ident(field.column_name)
    action = 'SET NOT NULL' if not_null else 'DROP NOT NULL'
    return f'ALTER TABLE {quote_table(table)} ALTER COLUMN {col} {action}'

  def set_default_sql(self, table: str, field) -> str:
    col = quote_ident(field.column_name)
    default = field.sql_default()
    if default is None:
      return f'ALTER TABLE {quote_table(table)} ALTER COLUMN {col} DROP DEFAULT'
    return f'ALTER TABLE {quote_table(table)} ALTER COLUMN {col} SET DEFAULT {default}'

  def rename_column_sql(self, table: str, old: str, new: str) -> str:
    return (
      f'ALTER TABLE {quote_table(table)} '
      f'RENAME COLUMN {quote_ident(old)} TO {quote_ident(new)}'
    )

  def drop_column_sql(self, table: str, column: str) -> str:
    return f'ALTER TABLE {quote_table(table)} DROP COLUMN {quote_ident(column)}'

  def drop_table_sql(self, table: str) -> str:
    return f'DROP TABLE IF EXISTS {quote_table(table)} CASCADE'

  def rename_table_sql(self, old: str, new: str) -> str:
    return (
      f'ALTER TABLE {quote_table(old)} '
      f'RENAME TO {quote_ident(new)}'
    )

  def rename_index_sql(self, old: str, new: str) -> str:
    return (
      f'ALTER INDEX {quote_ident(old)} '
      f'RENAME TO {quote_ident(new)}'
    )

  def index_name(self, table: str, column: str) -> str:
    return f'{table}_{column}_idx'

  def create_index_sql(self, table: str, column: str, unique: bool = False) -> str:
    unique_kw = 'UNIQUE ' if unique else ''
    name = quote_ident(self.index_name(table, column))
    return (
      f'CREATE {unique_kw}INDEX IF NOT EXISTS {name} '
      f'ON {quote_table(table)} ({quote_ident(column)})'
    )

  def drop_index_sql(self, table: str, column: str) -> str:
    return f'DROP INDEX IF EXISTS {quote_ident(self.index_name(table, column))}'

  # --- introspection ------------------------------------------------------

  def columns_query(self) -> str:
    return """
      SELECT column_name, data_type, is_nullable, column_default,
             character_maximum_length, numeric_precision, numeric_scale
      FROM information_schema.columns
      WHERE table_schema = %s AND table_name = %s
      ORDER BY ordinal_position
    """

  def tables_query(self) -> str:
    return """
      SELECT table_name
      FROM information_schema.tables
      WHERE table_schema = %s AND table_type = 'BASE TABLE'
    """

  def primary_key_query(self) -> str:
    return """
      SELECT kcu.column_name
      FROM information_schema.table_constraints tc
      JOIN information_schema.key_column_usage kcu
        ON tc.constraint_name = kcu.constraint_name
       AND tc.table_schema = kcu.table_schema
      WHERE tc.constraint_type = 'PRIMARY KEY'
        AND tc.table_schema = %s AND tc.table_name = %s
    """

  def indexes_query(self) -> str:
    return """
      SELECT indexname, indexdef
      FROM pg_indexes
      WHERE schemaname = %s AND tablename = %s
    """
