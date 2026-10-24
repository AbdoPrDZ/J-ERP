"""Declarative schema synchronization.

The syncer compares the fields declared on a model with the live PostgreSQL
schema and applies the differences: creating tables, adding columns, retyping
columns that can be widened safely, renaming columns that declare
``renamed_from``, and managing indexes. It also persists a model/field registry
(``sys_model`` / ``sys_field``) which is what makes deterministic change
detection possible.

Safety rules:

* additive changes (tables, nullable / defaulted columns, indexes) are applied
  automatically;
* a column is only renamed when the field declares ``renamed_from``;
* a column is only dropped when the caller passes ``allow_drop``; otherwise the
  field is marked retired in ``sys_field`` and the data stays in place;
* a type change is only applied when the dialect can cast it without loss, and
  only when the caller allows it (the request path defers even lossless ones).

Every sync can run in ``plan`` mode, which records the same statements without
executing them, so a preview cannot drift from the real run.

Everything runs inside a single transaction, so a failed sync leaves the
database untouched (PostgreSQL DDL is transactional).
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field

from jerp.dialect import quote_ident, quote_table


class SchemaBlocked(Exception):
  """Raised after a sync that could not apply one or more declared changes.

  Safe changes were already committed; ``plan`` lists what was skipped and why.
  """

  def __init__(self, plan: 'SchemaPlan'):
    self.plan = plan
    reasons = '; '.join(
      f"{blocked.get('model', '?')}.{blocked.get('column') or blocked.get('field', '?')}: "
      f"{blocked['reason']}"
      for blocked in plan.blocked[:5]
    )
    more = '' if len(plan.blocked) <= 5 else f' (+{len(plan.blocked) - 5} more)'
    super().__init__(f'Schema sync blocked: {reasons}{more}')


@dataclass
class SchemaPlan:
  """What a sync did (``apply``) or would do (``plan``)."""

  mode: str = 'apply'
  allow_drop: bool = False
  models: list = dc_field(default_factory=list)
  changes: list = dc_field(default_factory=list)
  blocked: list = dc_field(default_factory=list)
  warnings: list = dc_field(default_factory=list)

  def add(self, op: str, **data) -> dict:
    change = {'op': op, **data}
    self.changes.append(change)
    return change

  def block(self, op: str, reason: str, **data) -> dict:
    blocked = {'op': op, 'reason': reason, **data}
    self.blocked.append(blocked)
    return blocked

  def warn(self, message: str) -> None:
    if message not in self.warnings:
      self.warnings.append(message)

  @property
  def destructive(self) -> bool:
    """Whether applying the plan actually removes data.

    Retiring a column keeps it, and a type change only reaches this list when
    the cast is lossless, so neither counts.
    """

    return any(change['op'] == 'drop_column' for change in self.changes)

  def as_dict(self) -> dict:
    return {
      'mode': self.mode,
      'allow_drop': self.allow_drop,
      'models': list(self.models),
      'changes': self.changes,
      'blocked': self.blocked,
      'warnings': self.warnings,
      'destructive': self.destructive,
    }


class SchemaSyncer:
  def __init__(self, db):
    self.db = db
    self.dialect = db.dialect
    self.schema = db.schema
    self._state_column: bool | None = None

  # --- entry points -------------------------------------------------------

  def sync_models(
    self,
    models,
    *,
    mode: str = 'apply',
    allow_drop: bool = False,
    allow_type_change: bool = True,
    allow_unsafe: bool = False,
  ) -> SchemaPlan:
    """Synchronize ``models`` and return the plan that was (or would be) run.

    ``allow_type_change=False`` is used by the request path: safe (lossless)
    type changes are reported as blocked instead of rewriting a table while a
    request is being served. Removed columns are always retired unless
    ``allow_drop`` is set.
    """

    models = [m for m in models if not getattr(m, '_virtual', False)]
    plan = SchemaPlan(mode=mode, allow_drop=allow_drop)
    plan.models = [model._name for model in models]

    self._state_column = None
    with self.db.connection() as conn:
      with conn.transaction():
        with conn.cursor() as cur:
          for model in models:
            self._sync_table(cur, model, plan, allow_type_change)
          if plan.mode == 'apply':
            for model in models:
              self._write_metadata(cur, model, plan)

    if plan.blocked and plan.mode == 'apply' and not allow_unsafe:
      raise SchemaBlocked(plan)
    return plan

  def sync_model(self, model, **kwargs) -> SchemaPlan:
    return self.sync_models([model], **kwargs)

  def plan(self, models, *, allow_drop: bool = False) -> SchemaPlan:
    """Describe what :meth:`sync_models` would change, without changing it."""

    return self.sync_models(models, mode='plan', allow_drop=allow_drop)

  def retired_fields(self, models=None) -> list[dict]:
    """Retired fields whose column is still present in the database.

    Read-only: this is what ``doctor`` and ``--allow-drop`` report. ``models``
    supply the live table name for each model; ``sys_model`` is the fallback.
    Raises when ``sys_field.state`` does not exist yet, because a database that
    was never synchronized with this version does not record retirement.
    """

    tables = {model._name: model._table for model in (models or ())}

    with self.db.connection() as conn:
      with conn.cursor() as cur:
        if not self._table_exists(cur, 'sys_field'):
          return []
        if not self._has_state_column(cur):
          raise RuntimeError(
            'sys_field.state is missing: run a module update once before '
            'inspecting retired columns.'
          )

        cur.execute(
          "SELECT model, field_name, column_name, ttype FROM sys_field "
          "WHERE state = 'retired' ORDER BY model, field_name"
        )
        rows = [dict(row) for row in cur.fetchall()]

        retired: list[dict] = []
        for row in rows:
          table = tables.get(row['model'])
          if table is None and self._table_exists(cur, 'sys_model'):
            cur.execute(
              'SELECT table_name FROM sys_model WHERE name = %s', [row['model']]
            )
            found = cur.fetchone()
            table = found['table_name'] if found else None
          if not table or not self._table_exists(cur, table):
            continue
          if row['column_name'] not in self._columns(cur, table):
            continue
          retired.append({**row, 'table_name': table})
        return retired

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

  # --- statement helpers --------------------------------------------------

  def _run(self, cur, plan: SchemaPlan, change: dict, statements) -> None:
    """Attach the SQL to a plan change and execute it when applying."""

    statements = [sql for sql in statements if sql]
    if statements:
      change.setdefault('sql', []).extend(statements)
    if plan.mode == 'apply':
      for sql in statements:
        cur.execute(sql)

  # --- table creation -----------------------------------------------------

  def _create_table(self, cur, model, plan: SchemaPlan) -> None:
    change = plan.add('create_table', model=model._name, table=model._table)
    self._run(cur, plan, change, [self.dialect.create_table_sql(model)])
    self._sync_indexes(cur, model, plan, model._table, created=True)

  # --- table update -------------------------------------------------------

  def _sync_table(self, cur, model, plan: SchemaPlan, allow_type_change: bool) -> None:
    legacy = self._legacy_table(cur, model)
    new_exists = self._table_exists(cur, model._table)
    source_table = model._table
    pending_rename = False

    if legacy and legacy != model._table and self._table_exists(cur, legacy):
      if new_exists:
        raise ValueError(
          f"Both legacy table '{legacy}' and new table '{model._table}' "
          f"exist for model '{model._name}'. Rename or drop one before syncing."
        )
      pending_rename = True
      # While planning, the rename has not run: introspect the old table.
      source_table = legacy if plan.mode == 'plan' else model._table
      self._rename_legacy_table(cur, legacy, model._table, plan)
      new_exists = True

    if not new_exists:
      self._create_table(cur, model, plan)
      return
    self._update_table(
      cur, model, plan, source_table, pending_rename, allow_type_change
    )

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

  def _rename_legacy_table(self, cur, old_table, new_table, plan: SchemaPlan) -> None:
    change = plan.add('rename_table', table=new_table, old=old_table)
    self._run(
      cur, plan, change, [self.dialect.rename_table_sql(old_table, new_table)]
    )

    # Keep managed index names aligned with the new table name.
    read_table = old_table if plan.mode == 'plan' else new_table
    old_prefix = f'{old_table}_'
    for index_name in self._indexes(cur, read_table):
      if not (index_name.startswith(old_prefix) and index_name.endswith('_idx')):
        continue
      new_index = f'{new_table}_' + index_name[len(old_prefix):]
      index_change = plan.add(
        'rename_index', table=new_table, old=index_name, index=new_index
      )
      self._run(
        cur, plan, index_change,
        [self.dialect.rename_index_sql(index_name, new_index)],
      )

  def _update_table(
    self,
    cur,
    model,
    plan: SchemaPlan,
    source_table,
    pending_rename,
    allow_type_change: bool,
  ) -> None:
    columns = self._columns(cur, source_table)
    stored = self._stored_fields(cur, model)
    declared = model._fields

    columns, pending = self._apply_renames(
      cur, model, declared, stored, columns, plan
    )
    if plan.mode == 'apply':
      # Refresh after renames so added / altered columns see the new reality.
      columns = self._columns(cur, model._table)

    added = self._apply_adds(cur, model, declared, columns, plan, skip=pending)
    if plan.mode == 'apply':
      columns = self._columns(cur, model._table)

    self._apply_type_changes(
      cur, model, declared, columns, plan, added, allow_type_change
    )
    self._apply_nullability(cur, model, declared, columns, plan, added)
    self._apply_drops(cur, model, declared, stored, columns, plan)

    if pending_rename and plan.mode == 'plan':
      # Index names follow the table rename; previewing them separately would
      # report renames as creations. The apply run handles them.
      plan.warn(
        f'{model._table}: index plan deferred while the table rename is pending.'
      )
      return
    self._sync_indexes(cur, model, plan, source_table)

  def _apply_renames(self, cur, model, declared, stored, columns, plan: SchemaPlan):
    """Rename columns only for fields that declare ``renamed_from``.

    Returns ``(columns, pending)`` where ``pending`` holds field names whose
    rename was blocked. Those fields are excluded from ``_apply_adds`` so a
    broken rename cannot add the target column and make the rename impossible
    to run later.
    """

    declared_names = set(declared)
    pending: set = set()

    for name, field in declared.items():
      if field.column_name in columns:
        continue

      source = getattr(field, 'renamed_from', None)
      if not source:
        continue

      if source in declared_names:
        pending.add(name)
        plan.block(
          'rename_column',
          f"renamed_from='{source}' is also declared on '{model._name}'.",
          model=model._name,
          table=model._table,
          column=field.column_name,
        )
        continue

      old_column = stored.get(source)
      if not old_column:
        pending.add(name)
        plan.block(
          'rename_column',
          f"renamed_from='{source}' is not recorded in sys_field.",
          model=model._name,
          table=model._table,
          column=field.column_name,
        )
        continue

      if old_column not in columns:
        pending.add(name)
        plan.block(
          'rename_column',
          f"renamed_from='{source}' points at column '{old_column}', "
          f"which does not exist.",
          model=model._name,
          table=model._table,
          column=field.column_name,
        )
        continue

      change = plan.add(
        'rename_column',
        model=model._name,
        table=model._table,
        column=field.column_name,
        old=old_column,
        via='renamed_from',
      )
      self._run(
        cur, plan, change,
        [self.dialect.rename_column_sql(model._table, old_column, field.column_name)],
      )

      if plan.mode == 'apply' and self._table_exists(cur, 'sys_field'):
        # The old field name is gone; keep the metadata free of stale rows.
        cur.execute(
          'DELETE FROM sys_field WHERE model = %s AND field_name = %s',
          [model._name, source],
        )

      # Keep the local view of the table aligned with the rename.
      columns[field.column_name] = columns.pop(old_column)

    return columns, pending

  def _apply_adds(self, cur, model, declared, columns, plan: SchemaPlan,
                  skip=()) -> set:
    added: set = set()

    for name, field in declared.items():
      if name in skip or field.column_name in columns:
        continue

      default = field.sql_default()
      statements = [self.dialect.add_column_sql(model._table, field)]
      if default is not None:
        statements.append(self.dialect.set_default_sql(model._table, field))

      if not field.nullable():
        if default is not None:
          # SET DEFAULT does not backfill existing rows; do it before NOT NULL.
          statements.append(
            f'UPDATE {quote_table(model._table)} '
            f'SET {quote_ident(field.column_name)} = DEFAULT '
            f'WHERE {quote_ident(field.column_name)} IS NULL'
          )
        elif self._table_has_rows(cur, model._table):
          # A new required field on an existing table needs a value for the old
          # rows. Use a neutral value where one is safe; otherwise refuse.
          neutral = self._neutral_default(field)
          if neutral is None:
            reason = (
              f"Cannot add required field '{name}' to non-empty table "
              f"'{model._table}' without a static default. Add default=... "
              f"to the field or set required=False."
            )
            if plan.mode == 'plan':
              plan.block('add_column', reason, model=model._name,
                         table=model._table, column=field.column_name)
              added.add(field.column_name)
              continue
            raise ValueError(reason)
          statements.append(
            f'UPDATE {quote_table(model._table)} '
            f'SET {quote_ident(field.column_name)} = {neutral} '
            f'WHERE {quote_ident(field.column_name)} IS NULL'
          )

        statements.append(self.dialect.set_not_null_sql(model._table, field, True))

      change = plan.add(
        'add_column',
        model=model._name,
        table=model._table,
        column=field.column_name,
        required=not field.nullable(),
      )
      self._run(cur, plan, change, statements)
      added.add(field.column_name)

    return added

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

  def _apply_type_changes(
    self, cur, model, declared, columns, plan, added, allow_type_change: bool = True
  ) -> None:
    for name, field in declared.items():
      if field.column_name in added:
        continue
      info = columns.get(field.column_name)
      if info is None or field.auto_increment:
        continue
      current = self._normalize(info)
      desired = field.column_type()
      if current == desired:
        continue

      if not self.dialect.can_cast_losslessly(current, desired):
        plan.block(
          'alter_type',
          f"Changing '{current}' to '{desired}' can lose data; "
          f"handle it in a migration script.",
          model=model._name,
          table=model._table,
          column=field.column_name,
          **{'from': current, 'to': desired},
        )
        continue

      if not allow_type_change:
        plan.block(
          'alter_type',
          f"Changing '{current}' to '{desired}' is safe but deferred; "
          f"run the module update to apply it.",
          model=model._name,
          table=model._table,
          column=field.column_name,
          **{'from': current, 'to': desired},
        )
        continue

      column = quote_ident(field.column_name)
      # A default may be incompatible with the new type (for example text
      # ``'{}'`` -> jsonb). Drop it before the cast, then restore the
      # declared default if there is one.
      statements = [
        f'ALTER TABLE {quote_table(model._table)} '
        f'ALTER COLUMN {column} DROP DEFAULT',
        self.dialect.alter_type_sql(model._table, field),
      ]
      if field.sql_default() is not None:
        statements.append(self.dialect.set_default_sql(model._table, field))

      change = plan.add(
        'alter_type',
        model=model._name,
        table=model._table,
        column=field.column_name,
        **{'from': current, 'to': desired},
      )
      self._run(cur, plan, change, statements)

  def _apply_nullability(self, cur, model, declared, columns, plan, added) -> None:
    for name, field in declared.items():
      if field.column_name in added:
        continue
      info = columns.get(field.column_name)
      if info is None or field.auto_increment:
        continue
      desired_not_null = not field.nullable()
      current_not_null = info['is_nullable'] == 'NO'
      if desired_not_null != current_not_null:
        change = plan.add(
          'set_nullable',
          model=model._name,
          table=model._table,
          column=field.column_name,
          nullable=not desired_not_null,
        )
        self._run(
          cur, plan, change,
          [self.dialect.set_not_null_sql(model._table, field, desired_not_null)],
        )

  def _apply_drops(self, cur, model, declared, stored, columns, plan: SchemaPlan) -> None:
    declared_names = set(declared)

    for stored_name, stored_column in stored.items():
      if stored_name in declared_names:
        continue
      if stored_column not in columns:
        # Column already gone: nothing to keep or drop.
        continue

      if not plan.allow_drop:
        plan.add(
          'retire_column',
          model=model._name,
          table=model._table,
          field=stored_name,
          column=stored_column,
          reason='drop not allowed; column kept',
        )
        continue

      change = plan.add(
        'drop_column',
        model=model._name,
        table=model._table,
        field=stored_name,
        column=stored_column,
      )
      self._run(
        cur, plan, change,
        [self.dialect.drop_column_sql(model._table, stored_column)],
      )
      if plan.mode == 'apply' and self._table_exists(cur, 'sys_field'):
        cur.execute(
          'DELETE FROM sys_field WHERE model = %s AND field_name = %s',
          [model._name, stored_name],
        )

  def _sync_indexes(self, cur, model, plan: SchemaPlan, read_table=None,
                    created: bool = False) -> None:
    table = read_table or model._table
    existing = {} if created else self._indexes(cur, table)
    expected = set()

    for name, field in model._fields.items():
      if field.primary_key or field.auto_increment:
        continue
      if not (field.unique or field.index):
        continue

      index_name = self.dialect.index_name(model._table, field.column_name)
      expected.add(index_name)
      sql = self.dialect.create_index_sql(
        model._table, field.column_name, unique=field.unique
      )
      if plan.mode == 'apply':
        cur.execute(sql)
      if index_name not in existing:
        change = plan.add(
          'create_index',
          model=model._name,
          table=model._table,
          index=index_name,
          unique=bool(field.unique),
        )
        change['sql'] = [sql]

    # Drop managed indexes that are no longer declared.
    prefix = f'{model._table}_'
    for index_name in existing:
      if index_name in expected:
        continue
      if not (index_name.startswith(prefix) and index_name.endswith('_idx')):
        continue
      change = plan.add(
        'drop_index',
        model=model._name,
        table=model._table,
        index=index_name,
      )
      self._run(
        cur, plan, change,
        [f'DROP INDEX IF EXISTS {quote_ident(index_name)}'],
      )

  # --- metadata -----------------------------------------------------------

  def _has_state_column(self, cur) -> bool:
    if self._state_column is None:
      info = self._columns(cur, 'sys_field')
      self._state_column = 'state' in info
    return self._state_column

  def _write_metadata(self, cur, model, plan: SchemaPlan | None = None) -> None:
    if plan is not None and plan.mode == 'plan':
      return
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

    has_state = self._has_state_column(cur)
    fields_sql = 'SELECT id, field_name' + (', state' if has_state else '')
    cur.execute(
      f'{fields_sql} FROM sys_field WHERE model = %s',
      [model._name],
    )
    existing_fields = {row['field_name']: row['id'] for row in cur.fetchall()}

    for name, field in model._fields.items():
      label = field.name or name
      if name in existing_fields:
        if has_state:
          cur.execute(
            "UPDATE sys_field SET column_name = %s, ttype = %s, label = %s, "
            "state = 'active', updated_at = NOW() WHERE id = %s",
            [field.column_name, field.ttype, label, existing_fields.pop(name)],
          )
        else:
          cur.execute(
            'UPDATE sys_field SET column_name = %s, ttype = %s, label = %s, '
            'updated_at = NOW() WHERE id = %s',
            [field.column_name, field.ttype, label, existing_fields.pop(name)],
          )
      else:
        if has_state:
          cur.execute(
            "INSERT INTO sys_field "
            "(model, field_name, column_name, ttype, label, state, "
            "created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, 'active', NOW(), NOW())",
            [model._name, name, field.column_name, field.ttype, label],
          )
        else:
          cur.execute(
            'INSERT INTO sys_field '
            '(model, field_name, column_name, ttype, label, created_at, updated_at) '
            'VALUES (%s, %s, %s, %s, %s, NOW(), NOW())',
            [model._name, name, field.column_name, field.ttype, label],
          )

    # Fields that are no longer declared stay recorded (their columns may still
    # hold data) but are marked retired so ``--allow-drop`` can find them later.
    for field_id in existing_fields.values():
      if has_state:
        cur.execute(
          "UPDATE sys_field SET state = 'retired', updated_at = NOW() "
          'WHERE id = %s',
          [field_id],
        )
      else:
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
