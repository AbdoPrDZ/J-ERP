"""Schema sync planning and safety tests (no database required).

The syncer is exercised against a fake connection that answers the
introspection queries from dictionaries and records every statement. That is
enough to prove what a sync would do without touching PostgreSQL.
"""

from __future__ import annotations

import unittest
from contextlib import nullcontext

from jerp import fields, models
from jerp.dialect import PostgresDialect
from jerp.schema import SchemaBlocked, SchemaPlan, SchemaSyncer

DDL_PREFIXES = ('ALTER ', 'CREATE ', 'DROP ', 'INSERT ', 'UPDATE ', 'DELETE ')


def column(name, data_type, *, nullable='YES', char_max=None,
           precision=None, scale=None):
  return {
    'column_name': name,
    'data_type': data_type,
    'is_nullable': nullable,
    'character_maximum_length': char_max,
    'numeric_precision': precision,
    'numeric_scale': scale,
  }


def VARCHAR(name='name'):
  return column(name, 'character varying', nullable='NO', char_max=255)


def BIGINT(name='id'):
  return column(name, 'bigint', nullable='NO')


def FLOAT(name='price'):
  return column(name, 'double precision')


def TEXT(name='label'):
  return column(name, 'text')


def TS(name):
  return column(name, 'timestamp with time zone', nullable='NO')


class FakeCursor:
  def __init__(self, db):
    self.db = db
    self._rows: list = []

  def execute(self, sql, params=None):
    text = ' '.join(str(sql).split())
    self.db.statements.append((text, params))
    params = params or []

    if 'information_schema.tables' in text:
      table = params[1] if len(params) > 1 else None
      self._rows = (
        [{'table_name': table}] if table in self.db.tables else []
      )
    elif 'information_schema.columns' in text:
      table = params[1] if len(params) > 1 else None
      self._rows = list(self.db.columns.get(table, {}).values())
    elif 'pg_indexes' in text:
      table = params[1] if len(params) > 1 else None
      self._rows = [
        {'indexname': name, 'indexdef': ''}
        for name in self.db.indexes.get(table, [])
      ]
    elif text.startswith("SELECT model, field_name, column_name, ttype"):
      self._rows = [dict(row) for row in self.db.retired]
    elif text.startswith('SELECT field_name, column_name FROM sys_field'):
      model = params[0] if params else None
      self._rows = [
        {'field_name': name, 'column_name': target}
        for name, target in self.db.stored.get(model, {}).items()
      ]
    elif text.startswith('SELECT id, field_name'):
      self._rows = []
    elif text.startswith('SELECT table_name FROM sys_model'):
      self._rows = []
    elif text.startswith('SELECT 1 FROM'):
      self._rows = []
    else:
      self._rows = []

  def fetchone(self):
    return self._rows[0] if self._rows else None

  def fetchall(self):
    return list(self._rows)

  def __enter__(self):
    return self

  def __exit__(self, *exc):
    return False


class FakeConnection:
  def __init__(self, db):
    self.db = db

  def transaction(self):
    return nullcontext()

  def cursor(self):
    return FakeCursor(self.db)


class FakeDatabase:
  schema = 'public'

  def __init__(self, *, tables, columns, stored=None, indexes=None,
               retired=None):
    self.dialect = PostgresDialect(self.schema)
    self.tables = set(tables)
    self.columns = columns
    self.stored = stored or {}
    self.indexes = indexes or {}
    self.retired = retired or []
    self.statements: list = []

  def connection(self):
    return nullcontext(FakeConnection(self))

  # --- assertions helpers -------------------------------------------------

  def executed(self):
    return [sql for sql, _params in self.statements]

  def ddl(self):
    return [sql for sql in self.executed() if sql.startswith(DDL_PREFIXES)]


def make_db(model, columns, stored, indexes=None, system=True):
  tables = {model._table}
  if system:
    tables |= {'sys_model', 'sys_field'}
  # Every model carries the standard ``id`` / timestamps columns.
  base = {
    'id': BIGINT(),
    'created_at': TS('created_at'),
    'updated_at': TS('updated_at'),
  }
  base.update(columns)
  return FakeDatabase(
    tables=tables,
    columns={
      model._table: base,
      'sys_field': {
        'state': column('state', 'character varying', nullable='NO', char_max=255),
      },
    },
    stored={model._name: stored},
    indexes=indexes or {},
  )


class SchemaPlanTests(unittest.TestCase):
  def setUp(self) -> None:
    models.ModelRegistry.clear()

  # --- renamed_from -------------------------------------------------------

  def test_rename_is_not_guessed(self) -> None:
    class MarginModel(models.Model):
      _name = 'test.margin'
      name = fields.StringField(name='Name', required=True)
      margin = fields.FloatField(name='Margin')

    db = make_db(
      MarginModel,
      {'id': BIGINT(), 'name': VARCHAR(), 'discount': FLOAT('discount')},
      {'name': 'name', 'discount': 'discount'},
    )
    plan = SchemaSyncer(db).plan([MarginModel])

    ops = [change['op'] for change in plan.changes]
    self.assertIn('add_column', ops)
    self.assertIn('retire_column', ops)
    self.assertNotIn('rename_column', ops)
    self.assertEqual(db.ddl(), [])
    retired = next(c for c in plan.changes if c['op'] == 'retire_column')
    self.assertEqual(retired['column'], 'discount')
    added = next(c for c in plan.changes if c['op'] == 'add_column')
    self.assertEqual(added['column'], 'margin')

  def test_declared_rename_moves_the_column(self) -> None:
    class MarginModel(models.Model):
      _name = 'test.margin'
      name = fields.StringField(name='Name', required=True)
      margin = fields.FloatField(name='Margin', renamed_from='discount')

    db = make_db(
      MarginModel,
      {'id': BIGINT(), 'name': VARCHAR(), 'discount': FLOAT('discount')},
      {'name': 'name', 'discount': 'discount'},
    )
    plan = SchemaSyncer(db).plan([MarginModel])

    ops = [change['op'] for change in plan.changes]
    self.assertEqual(ops.count('rename_column'), 1)
    self.assertNotIn('add_column', ops)
    self.assertNotIn('retire_column', ops)
    rename = next(c for c in plan.changes if c['op'] == 'rename_column')
    self.assertEqual(rename['old'], 'discount')
    self.assertEqual(rename['column'], 'margin')
    self.assertTrue(any('RENAME COLUMN' in sql for sql in db.ddl() + [
      ' '.join(change.get('sql') or []) for change in plan.changes
    ]))

  def test_unknown_renamed_from_is_blocked(self) -> None:
    class MarginModel(models.Model):
      _name = 'test.margin'
      name = fields.StringField(name='Name', required=True)
      margin = fields.FloatField(name='Margin', renamed_from='nope')

    db = make_db(
      MarginModel,
      {'id': BIGINT(), 'name': VARCHAR()},
      {'name': 'name'},
    )
    plan = SchemaSyncer(db).plan([MarginModel])

    self.assertEqual(len(plan.blocked), 1)
    self.assertEqual(plan.blocked[0]['op'], 'rename_column')
    self.assertIn('nope', plan.blocked[0]['reason'])
    # The target column must not be added: doing so would make the declared
    # rename impossible to run later and leave the data in the old column.
    self.assertNotIn('add_column', [c['op'] for c in plan.changes])

  def test_renamed_from_still_declared_is_blocked(self) -> None:
    class MarginModel(models.Model):
      _name = 'test.margin'
      name = fields.StringField(name='Name', required=True)
      discount = fields.FloatField(name='Discount')
      margin = fields.FloatField(name='Margin', renamed_from='discount')

    db = make_db(
      MarginModel,
      {'id': BIGINT(), 'name': VARCHAR(), 'discount': FLOAT('discount')},
      {'name': 'name', 'discount': 'discount'},
    )
    plan = SchemaSyncer(db).plan([MarginModel])

    self.assertEqual(len(plan.blocked), 1)
    self.assertEqual(plan.blocked[0]['op'], 'rename_column')
    self.assertIn('also declared', plan.blocked[0]['reason'])

  def test_apply_raises_schema_blocked(self) -> None:
    class MarginModel(models.Model):
      _name = 'test.margin'
      name = fields.StringField(name='Name', required=True)
      margin = fields.FloatField(name='Margin', renamed_from='nope')

    db = make_db(
      MarginModel,
      {'id': BIGINT(), 'name': VARCHAR()},
      {'name': 'name'},
    )
    with self.assertRaises(SchemaBlocked) as caught:
      SchemaSyncer(db).sync_models([MarginModel])
    self.assertEqual(caught.exception.plan.blocked[0]['op'], 'rename_column')

  # --- drops --------------------------------------------------------------

  def test_removed_field_is_retired_by_default(self) -> None:
    class KeepModel(models.Model):
      _name = 'test.keep'
      name = fields.StringField(name='Name', required=True)

    db = make_db(
      KeepModel,
      {'id': BIGINT(), 'name': VARCHAR(), 'discount': FLOAT('discount')},
      {'name': 'name', 'discount': 'discount'},
    )
    plan = SchemaSyncer(db).plan([KeepModel])

    self.assertEqual([c['op'] for c in plan.changes], ['retire_column'])
    self.assertFalse(plan.destructive)
    self.assertEqual(db.ddl(), [])

  def test_removed_field_is_dropped_when_allowed(self) -> None:
    class KeepModel(models.Model):
      _name = 'test.keep'
      name = fields.StringField(name='Name', required=True)

    db = make_db(
      KeepModel,
      {'id': BIGINT(), 'name': VARCHAR(), 'discount': FLOAT('discount')},
      {'name': 'name', 'discount': 'discount'},
    )
    plan = SchemaSyncer(db).plan([KeepModel], allow_drop=True)

    self.assertEqual([c['op'] for c in plan.changes], ['drop_column'])
    self.assertTrue(plan.destructive)
    self.assertEqual(db.ddl(), [])
    change = plan.changes[0]
    self.assertEqual(change['column'], 'discount')
    self.assertIn('DROP COLUMN', ' '.join(change['sql']))

  # --- type changes -------------------------------------------------------

  def test_lossless_type_change_is_planned(self) -> None:
    class CountModel(models.Model):
      _name = 'test.count'
      name = fields.StringField(name='Name', required=True)
      total = fields.BigIntField(name='Total')

    columns = {'id': BIGINT(), 'name': VARCHAR(),
               'total': column('total', 'integer')}
    db = make_db(CountModel, columns, {'name': 'name', 'total': 'total'})
    plan = SchemaSyncer(db).plan([CountModel])

    ops = [c['op'] for c in plan.changes]
    self.assertIn('alter_type', ops)
    self.assertEqual(plan.blocked, [])

  def test_lossy_type_change_is_blocked(self) -> None:
    class PriceModel(models.Model):
      _name = 'test.price'
      name = fields.StringField(name='Name', required=True)
      price = fields.FloatField(name='Price')

    columns = {'id': BIGINT(), 'name': VARCHAR(), 'price': TEXT('price')}
    db = make_db(PriceModel, columns, {'name': 'name', 'price': 'price'})
    plan = SchemaSyncer(db).plan([PriceModel])

    self.assertEqual(plan.blocked[0]['op'], 'alter_type')
    self.assertNotIn('alter_type', [c['op'] for c in plan.changes])

  def test_request_path_defers_lossless_type_change(self) -> None:
    class CountModel(models.Model):
      _name = 'test.count'
      name = fields.StringField(name='Name', required=True)
      total = fields.BigIntField(name='Total')

    columns = {'id': BIGINT(), 'name': VARCHAR(),
               'total': column('total', 'integer')}
    db = make_db(CountModel, columns, {'name': 'name', 'total': 'total'})
    plan = SchemaSyncer(db).sync_models(
      [CountModel], allow_type_change=False, allow_unsafe=True
    )

    self.assertEqual(plan.blocked[0]['op'], 'alter_type')
    self.assertIn('deferred', plan.blocked[0]['reason'])
    self.assertNotIn('alter_type', [c['op'] for c in plan.changes])
    self.assertFalse(any('ALTER COLUMN' in sql for sql in db.ddl()))

  def test_request_path_type_change_raises_after_committing(self) -> None:
    class CountModel(models.Model):
      _name = 'test.count'
      name = fields.StringField(name='Name', required=True)
      total = fields.BigIntField(name='Total')

    columns = {'id': BIGINT(), 'name': VARCHAR(),
               'total': column('total', 'integer')}
    db = make_db(CountModel, columns, {'name': 'name', 'total': 'total'})
    with self.assertRaises(SchemaBlocked) as caught:
      SchemaSyncer(db).sync_models([CountModel], allow_type_change=False)

    self.assertEqual(caught.exception.plan.blocked[0]['op'], 'alter_type')
    self.assertFalse(any('ALTER COLUMN' in sql for sql in db.ddl()))

  def test_request_path_still_applies_a_declared_rename(self) -> None:
    class MarginModel(models.Model):
      _name = 'test.margin'
      name = fields.StringField(name='Name', required=True)
      margin = fields.FloatField(name='Margin', renamed_from='discount')

    db = make_db(
      MarginModel,
      {'id': BIGINT(), 'name': VARCHAR(), 'discount': FLOAT('discount')},
      {'name': 'name', 'discount': 'discount'},
    )
    plan = SchemaSyncer(db).sync_models(
      [MarginModel], allow_type_change=False, allow_unsafe=True
    )

    self.assertEqual(plan.blocked, [])
    self.assertIn('rename_column', [c['op'] for c in plan.changes])
    self.assertTrue(any('RENAME COLUMN' in sql for sql in db.ddl()))

  # --- plan/apply separation ---------------------------------------------

  def test_plan_mode_executes_no_ddl(self) -> None:
    class AddModel(models.Model):
      _name = 'test.add'
      name = fields.StringField(name='Name', required=True)
      note = fields.TextField(name='Note')

    db = make_db(AddModel, {'id': BIGINT(), 'name': VARCHAR()},
                 {'name': 'name'})
    plan = SchemaSyncer(db).plan([AddModel])

    self.assertIn('add_column', [c['op'] for c in plan.changes])
    self.assertEqual(db.ddl(), [])

  def test_apply_mode_runs_the_planned_sql(self) -> None:
    class AddModel(models.Model):
      _name = 'test.add'
      name = fields.StringField(name='Name', required=True)
      note = fields.TextField(name='Note')

    db = make_db(AddModel, {'id': BIGINT(), 'name': VARCHAR()},
                 {'name': 'name'})
    plan = SchemaSyncer(db).sync_models([AddModel])

    self.assertIn('add_column', [c['op'] for c in plan.changes])
    ddl = db.ddl()
    self.assertTrue(any('ADD COLUMN' in sql for sql in ddl))

  def test_missing_table_is_created(self) -> None:
    class NewModel(models.Model):
      _name = 'test.new'
      name = fields.StringField(name='Name', required=True)

    db = FakeDatabase(tables=set(), columns={}, stored={})
    plan = SchemaSyncer(db).plan([NewModel])

    ops = [c['op'] for c in plan.changes]
    self.assertEqual(ops, ['create_table'])
    self.assertEqual(db.ddl(), [])

  def test_as_dict_is_json_ready(self) -> None:
    class NewModel(models.Model):
      _name = 'test.new'
      name = fields.StringField(name='Name', required=True)

    db = FakeDatabase(tables=set(), columns={}, stored={})
    data = SchemaSyncer(db).plan([NewModel]).as_dict()

    self.assertEqual(data['mode'], 'plan')
    self.assertFalse(data['allow_drop'])
    self.assertEqual(data['models'], ['test.new'])
    self.assertIsInstance(data['changes'], list)
    self.assertFalse(data['destructive'])


class RetiredFieldTests(unittest.TestCase):
  def setUp(self) -> None:
    models.ModelRegistry.clear()

  def test_lists_only_retired_columns_still_present(self) -> None:
    class KeepModel(models.Model):
      _name = 'test.keep'
      name = fields.StringField(name='Name', required=True)

    db = make_db(
      KeepModel,
      {'id': BIGINT(), 'name': VARCHAR(), 'discount': FLOAT('discount')},
      {'name': 'name'},
    )
    db.retired = [
      {'model': 'test.keep', 'field_name': 'discount',
       'column_name': 'discount', 'ttype': 'float'},
      {'model': 'test.keep', 'field_name': 'gone',
       'column_name': 'gone', 'ttype': 'text'},
      {'model': 'test.unknown', 'field_name': 'x',
       'column_name': 'x', 'ttype': 'text'},
    ]

    rows = SchemaSyncer(db).retired_fields([KeepModel])

    self.assertEqual([row['column_name'] for row in rows], ['discount'])
    self.assertEqual(rows[0]['table_name'], KeepModel._table)
    self.assertEqual(rows[0]['model'], 'test.keep')
    self.assertEqual(db.ddl(), [])

  def test_requires_the_state_column(self) -> None:
    db = FakeDatabase(
      tables={'sys_field'},
      columns={'sys_field': {'model': VARCHAR('model')}},
      stored={},
    )
    with self.assertRaises(RuntimeError) as caught:
      SchemaSyncer(db).retired_fields([])
    self.assertIn('sys_field.state is missing', str(caught.exception))


class PlanFormatTests(unittest.TestCase):
  def test_lists_changes_blocked_and_warnings(self) -> None:
    from jerp.cli import _format_plan

    plan = SchemaPlan(mode='plan', allow_drop=True)
    plan.add('add_column', model='test.x', table='test_x', column='state')
    plan.add('rename_column', model='test.x', table='test_x',
             column='margin', old='discount')
    plan.add('drop_column', model='test.x', table='test_x', column='old')
    plan.block('alter_type', 'can lose data', model='test.x',
               table='test_x', column='price',
               **{'from': 'text', 'to': 'double precision'})
    plan.warn('index plan deferred')

    text = _format_plan(plan, 'demo')

    self.assertIn('Schema plan for demo (dry run)', text)
    self.assertIn('allow-drop', text)
    self.assertIn('add_column', text)
    self.assertIn('test_x.margin (from discount)', text)
    self.assertIn('test_x.old (destructive)', text)
    self.assertIn('Blocked (1)', text)
    self.assertIn('test_x.price (text -> double precision)', text)
    self.assertIn('Warning: index plan deferred', text)
    self.assertIn('drops columns', text)

  def test_reports_when_nothing_changes(self) -> None:
    from jerp.cli import _format_plan

    text = _format_plan(SchemaPlan(mode='apply'), 'demo')

    self.assertIn('Schema plan for demo (applied)', text)
    self.assertIn('no changes', text)
    self.assertNotIn('Blocked', text)


class CastSafetyTests(unittest.TestCase):
  def setUp(self) -> None:
    self.dialect = PostgresDialect()

  def test_widening_integers(self) -> None:
    self.assertTrue(self.dialect.can_cast_losslessly('integer', 'bigint'))
    self.assertTrue(self.dialect.can_cast_losslessly('bigint', 'numeric(20,0)'))
    self.assertTrue(self.dialect.can_cast_losslessly('integer', 'double precision'))

  def test_narrowing_integers(self) -> None:
    self.assertFalse(self.dialect.can_cast_losslessly('bigint', 'integer'))
    self.assertFalse(self.dialect.can_cast_losslessly('numeric(20,0)', 'integer'))

  def test_varchar_rules(self) -> None:
    self.assertTrue(self.dialect.can_cast_losslessly('varchar(255)', 'varchar(500)'))
    self.assertTrue(self.dialect.can_cast_losslessly('varchar(255)', 'text'))
    self.assertFalse(self.dialect.can_cast_losslessly('varchar(255)', 'varchar(100)'))

  def test_numeric_precision_rules(self) -> None:
    self.assertTrue(self.dialect.can_cast_losslessly('numeric(10,2)', 'numeric(12,4)'))
    self.assertFalse(self.dialect.can_cast_losslessly('numeric(10,2)', 'numeric(10,0)'))
    self.assertFalse(self.dialect.can_cast_losslessly('numeric(10,2)', 'numeric(9,2)'))

  def test_text_parsing_is_never_automatic(self) -> None:
    self.assertFalse(self.dialect.can_cast_losslessly('text', 'integer'))
    self.assertFalse(self.dialect.can_cast_losslessly('varchar(50)', 'date'))
    self.assertFalse(self.dialect.can_cast_losslessly('text', 'double precision'))

  def test_temporal_and_json(self) -> None:
    self.assertTrue(self.dialect.can_cast_losslessly('date', 'timestamp'))
    self.assertFalse(self.dialect.can_cast_losslessly('timestamp', 'date'))
    self.assertTrue(self.dialect.can_cast_losslessly('json', 'jsonb'))

  def test_same_type(self) -> None:
    self.assertTrue(self.dialect.can_cast_losslessly('double precision', 'double precision'))


class RenamedFromFieldTests(unittest.TestCase):
  def test_field_exposes_renamed_from(self) -> None:
    field = fields.StringField(name='Code', renamed_from='reference')
    self.assertEqual(field.renamed_from, 'reference')

  def test_default_is_none(self) -> None:
    self.assertIsNone(fields.StringField(name='Code').renamed_from)


if __name__ == '__main__':
  unittest.main()
