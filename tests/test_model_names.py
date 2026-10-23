"""Tests for model/table naming defaults."""

from __future__ import annotations

import unittest

from jerp import fields, models


class ModelNameTests(unittest.TestCase):
  def setUp(self) -> None:
    models.ModelRegistry.clear()

  def test_table_defaults_from_model_name(self) -> None:
    class Dotted(models.Model):
      _name = 'test.dotted.product'
      name = fields.StringField(name='Name')

    self.assertEqual(Dotted._name, 'test.dotted.product')
    self.assertEqual(Dotted._table, 'test_dotted_product')

  def test_table_defaults_from_class_name(self) -> None:
    class SimpleModel(models.Model):
      name = fields.StringField(name='Name')

    self.assertEqual(SimpleModel._name, 'simple_model')
    self.assertEqual(SimpleModel._table, 'simple_model')

  def test_inherits_table_defaults_from_new_model_name(self) -> None:
    class Child(models.Model):
      _name = 'test.child'
      _inherits = ['test.parent']
      name = fields.StringField(name='Name')

    self.assertEqual(Child._name, 'test.child')
    self.assertEqual(Child._table, 'test_child')

  def test_explicit_table_still_wins(self) -> None:
    class LegacyTable(models.Model):
      _name = 'test.legacy'
      _table = 'legacy_rows'
      name = fields.StringField(name='Name')

    self.assertEqual(LegacyTable._table, 'legacy_rows')


if __name__ == '__main__':
  unittest.main()
