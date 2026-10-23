"""Declarative schema synchronization.

The syncer compares the fields declared on a model with the live PostgreSQL
schema and applies the differences: creating tables, adding / renaming / dropping
columns, altering types and managing indexes. It also persists a model/field
registry (``sys_model`` / ``sys_field``) which is what makes deterministic rename
detection possible.

Everything runs inside a single transaction, so a failed sync leaves the
database untouched (PostgreSQL DDL is transactional).
"""

from __future__ import annotations

from jerp.dialect import quote_ident, quote_table


class SchemaSyncer:
  def __init__(self, db):
    self.db = db
    self.dialect = db.dialect
    self.schema = db.schema

  # --- entry points -------------------------------------------------------

  def sync_models(self, models) -> None:
    models = [m for m in models if not getattr(m, '_virtual', False)]
    with self.db.connection() as conn:
      with conn.transaction():
        with conn.cursor() as cur:
          for model in models:
            self._sync_table(cur, model)
          for model in models:
            self._write_metadata(cur, model)

  def sync_model(self, model) -> None:
    self.sync_models([model])

  def drop_model(self, model) -> None:
    with self.db.connection() as conn:
      with conn.transaction():
        with conn.cursor() as cur:
          cur.execute(self.dialect.drop_table_sql(model._table))
          if self._table_exists(cur, 'sys_field'):
            cur.execute('DELETE FROM sys_field WHERE model = %s', [model._name])
          if self._table_exists(cur, 'sys_model'):
            cur.execute('DELETE FROM sys_model WHERE name = %s', [model._name])

  # --- introspection helpers ----------------------------------------------

  def _table_exists(self, cur, table: str) -> bool:
    cur.execute(
      "SELECT 1 FROM information_schema.tables "
      "WHERE table_schema = %s AND table_name = %s AND table_type = 'BASE TABLE'",
      [self.schema, table],
    )
    return cur.fetchone() is not None

  def _columns(self, cur, table: str) -> dict:
    cur.execute(self.dialect.columns_query(), [self.schema, table])
    return {r['column_name']: r for r in cur.fetchall()}

  def _indexes(self, cur, table: str) -> dict:
    cur.execute(self.dialect.indexes_query(), [self.schema, table])
    return {r['indexname']: r['indexdef'] for r in cur.fetchall()}

  def _stored_fields(self, cur, model) -> dict:
    """field_name -> column_name as recorded in ``sys_field``."""

    if not self._table_exists(cur, 'sys_field'):
      return {}
    cur.execute(
      'SELECT field_name, column_name FROM sys_field WHERE model = %s',
      [model._name],
    )
    return {r['field_name']: r['column_name'] for r in cur.fetchall()}

  def _normalize(self, info: dict) -> str:
    return self.dialect.normalize(
      info['data_type'],
      info.get('character_maximum_length'),
      info.get('numeric_precision'),
      info.get('numeric_scale'),
    )

  # --- table creation -----------------------------------------------------

  def _create_table(self, cur, model) -> None:
    cur.execute(self.dialect.create_table_sql(model))
    self._sync_indexes(cur, model)

  # --- table update -------------------------------------------------------

  def _sync_table(self, cur, model) -> None:
    legacy = self._legacy_table(cur, model)
    new_exists = self._table_exists(cur, model._table)

    if legacy and legacy != model._table and self._table_exists(cur, legacy):
      if new_exists:
        raise ValueError(
          f"Both legacy table '{legacy}' and new table '{model._table}' "
          f"exist for model '{model._name}'. Rename or drop one before syncing."
        )
      self._rename_legacy_table(cur, legacy, model._table)
      new_exists = True

    if not new_exists:
      self._create_table(cur, model)
      return
    self._update_table(cur, model)

  def _legacy_table(self, cur, model) -> str | None:
    """The previously recorded table name, if it differs from the new one."""

    legacy_name = getattr(model, '_rename_from', None) or model._name
    if not legacy_name or not self._table_exists(cur, 'sys_model'):
      return None

    cur.execute(
      'SELECT table_name FROM sys_model WHERE name = %s',
      [legacy_name],
    )
    row = cur.fetchone()
    if not row:
      return None

    table_name = row['table_name']
    if not table_name or table_name == model._table:
      return None
    return table_name

  def _rename_legacy_table(self, cur, old_table: str, new_table: str) -> None:
    cur.execute(self.dialect.rename_table_sql(old_table, new_table))

    # Keep managed index names aligned with the new table name.
    old_prefix = f'{old_table}_'
    for index_name in self._indexes(cur, new_table):
      if not (index_name.startswith(old_prefix) and index_name.endswith('_idx')):
        continue
      new_index = f'{new_table}_' + index_name[len(old_prefix):]
      cur.execute(self.dialect.rename_index_sql(index_name, new_index))

  def _update_table(self, cur, model) -> None:
    columns = self._columns(cur, model._table)
    stored = self._stored_fields(cur, model)
    declared = model._fields

    self._apply_renames(cur, model, declared, stored, columns)

    # Refresh after renames so added / altered columns see the new reality.
    columns = self._columns(cur, model._table)

    self._apply_adds(cur, model, declared, columns)

    columns = self._columns(cur, model._table)
    self._apply_type_changes(cur, model, declared, columns)
    self._apply_nullability(cur, model, declared, columns)

    self._apply_drops(cur, model, declared, stored, columns)
    self._sync_indexes(cur, model)

  def _apply_renames(self, cur, model, declared, stored, columns) -> None:
    declared_names = set(declared)
    used = set()

    for name, field in declared.items():
      if field.column_name in columns:
        continue
      for stored_name, stored_column in stored.items():
        if stored_name in declared_names or stored_name in used:
          continue
        if stored_column in columns:
          cur.execute(
            self.dialect.rename_column_sql(
              model._table, stored_column, field.column_name
            )
          )
          used.add(stored_name)
          break

  def _apply_adds(self, cur, model, declared, columns) -> None:
    for name, field in declared.items():
      if field.column_name in columns:
        continue

      default = field.sql_default()
      cur.execute(self.dialect.add_column_sql(model._table, field))

      if default is not None:
        cur.execute(self.dialect.set_default_sql(model._table, field))

      if not field.nullable():
        if default is not None:
          # SET DEFAULT does not backfill existing rows; do it before NOT NULL.
          cur.execute(
            f'UPDATE {quote_table(model._table)} '
            f'SET {quote_ident(field.column_name)} = DEFAULT '
            f'WHERE {quote_ident(field.column_name)} IS NULL'
          )
        elif self._table_has_rows(cur, model._table):
          # A new required field on an existing table needs a value for the old
          # rows. Use a neutral value where one is safe; otherwise refuse.
          neutral = self._neutral_default(field)
          if neutral is None:
            raise ValueError(
              f"Cannot add required field '{name}' to non-empty table "
              f"'{model._table}' without a static default. Add default=... "
              f"to the field or set required=False."
            )
          cur.execute(
            f'UPDATE {quote_table(model._table)} '
            f'SET {quote_ident(field.column_name)} = {neutral} '
            f'WHERE {quote_ident(field.column_name)} IS NULL'
          )

        cur.execute(self.dialect.set_not_null_sql(model._table, field, True))

  @staticmethod
  def _neutral_default(field):
    """A safe backfill value for a new required field, or ``None``."""

    from jerp import fields as field_types

    if getattr(field, 'comodel', None):
      return None
    if isinstance(
      field,
      (
        field_types.FloatField,
        field_types.NumericField,
        field_types.IntegerField,
      ),
    ):
      return '0'
    if isinstance(field, (field_types.StringField, field_types.TextField)):
      return "''"
    if isinstance(field, field_types.BooleanField):
      return 'FALSE'
    if isinstance(field, field_types.DateField):
      return 'CURRENT_DATE'
    return None

  @staticmethod
  def _table_has_rows(cur, table: str) -> bool:
    cur.execute(f'SELECT 1 FROM {quote_table(table)} LIMIT 1')
    return cur.fetchone() is not None

  def _apply_type_changes(self, cur, model, declared, columns) -> None:
    for name, field in declared.items():
      info = columns.get(field.column_name)
      if info is None or field.auto_increment:
        continue
      if self._normalize(info) != field.column_type():
        column = quote_ident(field.column_name)
        # A default may be incompatible with the new type (for example text
        # ``'{}'`` -> jsonb). Drop it before the cast, then restore the
        # declared default if there is one.
        cur.execute(
          f'ALTER TABLE {quote_table(model._table)} '
          f'ALTER COLUMN {column} DROP DEFAULT'
        )
        cur.execute(self.dialect.alter_type_sql(model._table, field))
        if field.sql_default() is not None:
          cur.execute(self.dialect.set_default_sql(model._table, field))

  def _apply_nullability(self, cur, model, declared, columns) -> None:
    for name, field in declared.items():
      info = columns.get(field.column_name)
      if info is None or field.auto_increment:
        continue
      desired_not_null = not field.nullable()
      current_not_null = info['is_nullable'] == 'NO'
      if desired_not_null != current_not_null:
        cur.execute(
          self.dialect.set_not_null_sql(model._table, field, desired_not_null)
        )

  def _apply_drops(self, cur, model, declared, stored, columns) -> None:
    declared_names = set(declared)
    for stored_name, stored_column in stored.items():
      if stored_name in declared_names:
        continue
      if stored_column in columns:
        cur.execute(self.dialect.drop_column_sql(model._table, stored_column))

  def _sync_indexes(self, cur, model) -> None:
    existing = self._indexes(cur, model._table)
    expected = set()

    for name, field in model._fields.items():
      if field.primary_key or field.auto_increment:
        continue
      if field.unique:
        index_name = self.dialect.index_name(model._table, field.column_name)
        expected.add(index_name)
        cur.execute(
          self.dialect.create_index_sql(model._table, field.column_name, unique=True)
        )
      elif field.index:
        index_name = self.dialect.index_name(model._table, field.column_name)
        expected.add(index_name)
        cur.execute(
          self.dialect.create_index_sql(model._table, field.column_name, unique=False)
        )

    # Drop managed indexes that are no longer declared.
    prefix = f'{model._table}_'
    for index_name in existing:
      if index_name in expected:
        continue
      if index_name.startswith(prefix) and index_name.endswith('_idx'):
        cur.execute(f'DROP INDEX IF EXISTS {quote_ident(index_name)}')

  # --- metadata -----------------------------------------------------------

  def _write_metadata(self, cur, model) -> None:
    if not self._table_exists(cur, 'sys_model'):
      return

    cur.execute(
      'INSERT INTO sys_model (name, table_name, created_at, updated_at) '
      'VALUES (%s, %s, NOW(), NOW()) '
      'ON CONFLICT (name) DO UPDATE SET '
      'table_name = EXCLUDED.table_name, updated_at = NOW()',
      [model._name, model._table],
    )

    if not self._table_exists(cur, 'sys_field'):
      self._delete_legacy_metadata(cur, model)
      return

    cur.execute(
      'SELECT id, field_name FROM sys_field WHERE model = %s',
      [model._name],
    )
    existing_fields = {
      row['field_name']: row['id'] for row in cur.fetchall()
    }

    for name, field in model._fields.items():
      label = field.name or name
      if name in existing_fields:
        cur.execute(
          'UPDATE sys_field SET column_name = %s, ttype = %s, label = %s, '
          'updated_at = NOW() WHERE id = %s',
          [field.column_name, field.ttype, label, existing_fields.pop(name)],
        )
      else:
        cur.execute(
          'INSERT INTO sys_field '
          '(model, field_name, column_name, ttype, label, created_at, updated_at) '
          'VALUES (%s, %s, %s, %s, %s, NOW(), NOW())',
          [model._name, name, field.column_name, field.ttype, label],
        )

    for field_id in existing_fields.values():
      cur.execute('DELETE FROM sys_field WHERE id = %s', [field_id])

    self._delete_legacy_metadata(cur, model)

  def _delete_legacy_metadata(self, cur, model) -> None:
    legacy = getattr(model, '_rename_from', None)
    if not legacy or legacy == model._name:
      return

    if self._table_exists(cur, 'sys_field'):
      cur.execute('DELETE FROM sys_field WHERE model = %s', [legacy])
    if self._table_exists(cur, 'sys_model'):
      cur.execute('DELETE FROM sys_model WHERE name = %s', [legacy])
