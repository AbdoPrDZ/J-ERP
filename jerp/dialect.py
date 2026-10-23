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
    return code

  def column_signature(self, field) -> str:
    """Canonical type string for a declared field."""

    return field.column_type()

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
