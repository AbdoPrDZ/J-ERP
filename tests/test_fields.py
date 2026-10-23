"""Tests for automatic field indexes."""

from __future__ import annotations

import unittest

from jerp import fields


class FieldIndexTests(unittest.TestCase):
  def test_many2one_is_indexed_automatically(self) -> None:
    field = fields.Many2oneField(name='Country', comodel='sys.country')
    self.assertTrue(field.index)

  def test_many2one_can_opt_out(self) -> None:
    field = fields.Many2oneField(
      name='Country',
      comodel='sys.country',
      index=False,
    )
    self.assertFalse(field.index)

  def test_plain_fields_are_not_indexed_automatically(self) -> None:
    field = fields.StringField(name='Name')
    self.assertFalse(field.index)

  def test_unique_does_not_require_manual_index(self) -> None:
    field = fields.StringField(name='Code', unique=True)
    self.assertFalse(field.index)
    self.assertTrue(field.unique)


if __name__ == '__main__':
  unittest.main()
