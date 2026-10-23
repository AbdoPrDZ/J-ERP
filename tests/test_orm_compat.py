"""Compatibility tests for the Odoo-style model API used by modules."""

from __future__ import annotations

import unittest

from jerp import fields
from jerp.api import depends_on, on_change
from jerp.models import RecordSet, dualmethod


class FieldCompatibilityTests(unittest.TestCase):
  def test_many2one_accepts_positional_comodel(self) -> None:
    field = fields.Many2oneField(
      'sys.contact', name='Customer', required=True
    )
    self.assertEqual(field.comodel, 'sys.contact')
    self.assertEqual(field.name, 'Customer')
    self.assertTrue(field.required)
    self.assertTrue(field.index)

  def test_selection_accepts_positional_selection(self) -> None:
    selection = [('draft', 'Draft'), ('done', 'Done')]
    field = fields.SelectionField(selection, name='Status', default='draft')
    self.assertEqual(field.selection, selection)
    self.assertEqual(field.name, 'Status')
    self.assertEqual(field.default, 'draft')

  def test_compute_fields_are_readonly(self) -> None:
    field = fields.FloatField(name='Total', compute='_compute_total')
    self.assertEqual(field.compute, '_compute_total')
    self.assertTrue(field.readonly)


class DecoratorCompatibilityTests(unittest.TestCase):
  def test_depends_on_accepts_a_list(self) -> None:
    @depends_on(['quantity', 'price_unit'])
    def compute(self):
      return None

    self.assertEqual(
      compute._jerp_depends, ('quantity', 'price_unit')
    )

  def test_depends_on_accepts_variadic_names(self) -> None:
    @depends_on('lines.subtotal')
    def compute(self):
      return None

    self.assertEqual(compute._jerp_depends, ('lines.subtotal',))

  def test_on_change_accepts_a_list(self) -> None:
    @on_change(['product_id'])
    def handler(self):
      return None

    self.assertEqual(handler._jerp_on_change_fields, ('product_id',))


class RecordSetTests(unittest.TestCase):
  def test_is_one_returns_the_single_record(self) -> None:
    record = object()
    self.assertIs(RecordSet([record]).is_one(), record)

  def test_is_one_rejects_zero_or_many(self) -> None:
    with self.assertRaises(ValueError):
      RecordSet([]).is_one()
    with self.assertRaises(ValueError):
      RecordSet([object(), object()]).is_one()

  def test_recordsets_are_lists(self) -> None:
    rows = RecordSet([1, 2])
    self.assertEqual(rows, [1, 2])
    self.assertEqual(rows[0], 1)


class DualMethodTests(unittest.TestCase):
  def test_instance_and_class_access_dispatch_differently(self) -> None:
    class Sample:
      def _instance(self):
        return 'instance'

      @classmethod
      def _class(cls):
        return 'class'

      both = dualmethod(_instance, _class)

    self.assertEqual(Sample().both(), 'instance')
    self.assertEqual(Sample.both(), 'class')


if __name__ == '__main__':
  unittest.main()
