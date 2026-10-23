"""Unit tests for the model build engine (no database required)."""

from __future__ import annotations

import unittest

from jerp import fields, models
from jerp.api import api_expose
from jerp.builder import ModelBuilder


class ModelBuilderTests(unittest.TestCase):
  def setUp(self) -> None:
    models.ModelRegistry.clear()

  # --- helpers ------------------------------------------------------------

  @staticmethod
  def build(builder, modules, depends=None):
    return builder.build(modules, depends or {})

  # --- _inherit -----------------------------------------------------------

  def test_inherit_merges_fields_and_methods(self) -> None:
    class Base(models.Model):
      _name = 'test_users'
      _table = 'test_users'

      name = fields.StringField(name='Name')

      def label(self):
        return self.name or 'base'

      @classmethod
      @api_expose
      def ping(cls):
        return 'base'

    class Extension(models.Model):
      _inherit = 'test_users'

      job_title = fields.StringField(name='Job title')

      def label(self):
        return f'{super().label()}+ext'

      @classmethod
      @api_expose
      def ping(cls):
        return 'ext'

    result = self.build(
      ModelBuilder(),
      {'base_mod': [Base], 'ext_mod': [Extension]},
      {'base_mod': [], 'ext_mod': ['base_mod']},
    )

    built = result.models['test_users']
    self.assertIsNot(built, Base)
    self.assertTrue(getattr(built, '_composed', False))
    self.assertFalse(getattr(built, '_is_extension', False))
    self.assertEqual(built._table, 'test_users')
    self.assertEqual(
      list(built._fields),
      ['id', 'created_at', 'updated_at', 'name', 'job_title'],
    )
    self.assertEqual(built._field_sources['name'], f'{Base.__module__}.{Base.__qualname__}')
    self.assertEqual(set(built._extension_fields), {'job_title'})
    schema = {entry['name']: entry for entry in built.field_schema()}
    self.assertTrue(schema['job_title'].get('extension'))
    self.assertNotIn('extension', schema['name'])

    record = built.__new__(built)
    record._values = {'name': 'Ada', 'job_title': 'Engineer'}
    self.assertEqual(record.label(), 'Ada+ext')
    self.assertEqual(built.ping(), 'ext')
    self.assertEqual(built.call_parts('ping'), ['ext', 'base'])
    self.assertEqual(
      built.call_parts('label', record=record),
      ['Ada+ext', 'Ada'],
    )

  def test_duplicate_field_is_rejected(self) -> None:
    class Base(models.Model):
      _name = 'test_dup'
      _table = 'test_dup'
      name = fields.StringField(name='Name')

    class Extension(models.Model):
      _inherit = 'test_dup'
      name = fields.StringField(name='Other name')

    with self.assertRaisesRegex(ValueError, "field 'name' is declared twice"):
      self.build(
        ModelBuilder(),
        {'base_mod': [Base], 'ext_mod': [Extension]},
        {'base_mod': [], 'ext_mod': ['base_mod']},
      )

  def test_extension_requires_declared_dependency(self) -> None:
    class Base(models.Model):
      _name = 'test_dep'
      _table = 'test_dep'
      name = fields.StringField(name='Name')

    class Extension(models.Model):
      _inherit = 'test_dep'
      extra = fields.StringField(name='Extra')

    with self.assertRaisesRegex(ValueError, 'not in its dependencies'):
      self.build(
        ModelBuilder(),
        {'base_mod': [Base], 'ext_mod': [Extension]},
        {'base_mod': [], 'ext_mod': []},
      )

  def test_missing_inherit_target_is_rejected(self) -> None:
    class Extension(models.Model):
      _inherit = 'test_missing'
      extra = fields.StringField(name='Extra')

    with self.assertRaisesRegex(ValueError, "target 'test_missing'"):
      self.build(ModelBuilder(), {'ext_mod': [Extension]}, {'ext_mod': []})

  # --- _inherits ----------------------------------------------------------

  def test_inherits_builds_new_model_with_parent_fields(self) -> None:
    class ParentA(models.Model):
      _name = 'test_parent_a'
      _table = 'test_parent_a'
      name = fields.StringField(name='Name')

      def a_label(self):
        return f'A:{self.name}'

    class ParentB(models.Model):
      _name = 'test_parent_b'
      _table = 'test_parent_b'
      title = fields.StringField(name='Title')

      def b_label(self):
        return f'B:{self.title}'

    class Child(models.Model):
      _name = 'test_child'
      _table = 'test_child'
      _inherits = ['test_parent_a', 'test_parent_b']

      badge = fields.StringField(name='Badge')

      def describe(self):
        return f'{self.name}/{self.title}/{self.badge}'

    result = self.build(
      ModelBuilder(),
      {'parents': [ParentA, ParentB], 'child': [Child]},
      {'parents': [], 'child': ['parents']},
    )

    built = result.models['test_child']
    self.assertEqual(built._table, 'test_child')
    self.assertTrue(issubclass(built, ParentA))
    self.assertTrue(issubclass(built, ParentB))
    self.assertEqual(
      list(built._fields),
      [
        'id',
        'created_at',
        'updated_at',
        'name',
        'title',
        'badge',
      ],
    )

    record = built.__new__(built)
    record._values = {
      'name': 'Ada',
      'title': 'Engineer',
      'badge': 'A-1',
    }
    self.assertEqual(record.describe(), 'Ada/Engineer/A-1')
    self.assertEqual(record.a_label(), 'A:Ada')
    self.assertEqual(record.b_label(), 'B:Engineer')

  def test_inherits_requires_a_new_name(self) -> None:
    with self.assertRaisesRegex(ValueError, 'requires a new _name'):
      class Child(models.Model):
        _inherits = ['some_parent']
        badge = fields.StringField(name='Badge')

  def test_inherit_can_extend_an_inherits_model(self) -> None:
    class Parent(models.Model):
      _name = 'test_chain_parent'
      _table = 'test_chain_parent'
      name = fields.StringField(name='Name')

      def chain(self):
        return 'parent'

    class Child(models.Model):
      _name = 'test_chain_child'
      _table = 'test_chain_child'
      _inherits = ['test_chain_parent']
      badge = fields.StringField(name='Badge')

      def chain(self):
        return f'child+{super().chain()}'

    class ChildExtension(models.Model):
      _inherit = 'test_chain_child'
      note = fields.StringField(name='Note')

      def chain(self):
        return f'ext+{super().chain()}'

    result = self.build(
      ModelBuilder(),
      {
        'parent_mod': [Parent],
        'child_mod': [Child],
        'ext_mod': [ChildExtension],
      },
      {
        'parent_mod': [],
        'child_mod': ['parent_mod'],
        'ext_mod': ['child_mod'],
      },
    )

    built = result.models['test_chain_child']
    self.assertEqual(
      list(built._fields),
      ['id', 'created_at', 'updated_at', 'name', 'badge', 'note'],
    )
    record = built.__new__(built)
    record._values = {'name': 'Ada', 'badge': 'B', 'note': 'N'}
    self.assertEqual(record.chain(), 'ext+child+parent')

  def test_duplicate_inherits_parents_are_rejected(self) -> None:
    with self.assertRaisesRegex(ValueError, 'duplicate model names'):
      class Child(models.Model):
        _name = 'test_duplicate_parents'
        _table = 'test_duplicate_parents'
        _inherits = ['test_parent_x', 'test_parent_x']
        badge = fields.StringField(name='Badge')

  def test_inherits_cycle_is_rejected(self) -> None:
    class CycleA(models.Model):
      _name = 'test_cycle_a'
      _table = 'test_cycle_a'
      _inherits = ['test_cycle_b']
      name = fields.StringField(name='Name')

    class CycleB(models.Model):
      _name = 'test_cycle_b'
      _table = 'test_cycle_b'
      _inherits = ['test_cycle_a']
      name = fields.StringField(name='Name')

    with self.assertRaisesRegex(ValueError, 'Circular _inherits dependency'):
      self.build(
        ModelBuilder(),
        {'cycle_a': [CycleA], 'cycle_b': [CycleB]},
        {'cycle_a': ['cycle_b'], 'cycle_b': ['cycle_a']},
      )

  # --- per-database and cache --------------------------------------------

  def test_uninstalled_extension_does_not_change_model(self) -> None:
    class Base(models.Model):
      _name = 'test_scope'
      _table = 'test_scope'
      name = fields.StringField(name='Name')

    class Extension(models.Model):
      _inherit = 'test_scope'
      extra = fields.StringField(name='Extra')

    builder = ModelBuilder()
    plain = builder.build({'base_mod': [Base]}, {'base_mod': []})
    self.assertNotIn('extra', plain.models['test_scope']._fields)

    extended = builder.build(
      {'base_mod': [Base], 'ext_mod': [Extension]},
      {'base_mod': [], 'ext_mod': ['base_mod']},
    )
    self.assertIn('extra', extended.models['test_scope']._fields)

  def test_unchanged_sources_reuse_the_built_class(self) -> None:
    class Base(models.Model):
      _name = 'test_cache'
      _table = 'test_cache'
      name = fields.StringField(name='Name')

    builder = ModelBuilder()
    first = builder.build({'base_mod': [Base]}, {'base_mod': []})
    second = builder.build({'base_mod': [Base]}, {'base_mod': []})

    self.assertIs(first.models['test_cache'], second.models['test_cache'])
    self.assertEqual(second.changed, set())


if __name__ == '__main__':
  unittest.main()
