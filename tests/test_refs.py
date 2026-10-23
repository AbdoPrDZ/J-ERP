"""Tests for external reference key composition."""

from __future__ import annotations

import unittest

from jerp.refs import resolve_key


class RefKeyTests(unittest.TestCase):
  def test_full_key_is_kept(self) -> None:
    self.assertEqual(
      resolve_key('l10n_dz', 'sys.country', 'l10n_dz.sys_country_dz'),
      ('l10n_dz.sys_country_dz', 'sys_country_dz'),
    )

  def test_short_key_is_expanded(self) -> None:
    self.assertEqual(
      resolve_key('l10n_dz', 'sys.country', 'dz'),
      ('l10n_dz.sys.country.dz', 'dz'),
    )

  def test_short_key_with_dots(self) -> None:
    self.assertEqual(
      resolve_key('custom', 'sale.order', 'partner.main'),
      ('custom.sale.order.partner.main', 'partner.main'),
    )


if __name__ == '__main__':
  unittest.main()
