"""Module dependency ordering and cycle detection (no database required)."""

from __future__ import annotations

import unittest
from pathlib import Path

from jerp.modules import ModuleInfo, ModuleManager
from jerp.registry import Registry


def info(name: str, depends=()) -> ModuleInfo:
  return ModuleInfo(
    name=name,
    version='1.0.0',
    summary='',
    depends=list(depends),
    path=Path(name),
  )


class ResolveOrderTests(unittest.TestCase):
  def setUp(self) -> None:
    self.manager = ModuleManager(None, 'modules')

  def test_dependencies_come_first(self) -> None:
    modules = {
      'core': info('core'),
      'stock': info('stock', ['core']),
      'sale': info('sale', ['core', 'stock']),
    }
    self.assertEqual(
      self.manager.resolve_order(modules, 'sale'), ['core', 'stock', 'sale']
    )

  def test_diamond_dependencies_are_ordered_once(self) -> None:
    modules = {
      'core': info('core'),
      'stock': info('stock', ['core']),
      'sale': info('sale', ['core']),
      'report': info('report', ['sale', 'stock']),
    }
    order = self.manager.resolve_order(modules, 'report')
    self.assertEqual(order[0], 'core')
    self.assertEqual(sorted(order), ['core', 'report', 'sale', 'stock'])
    self.assertLess(order.index('sale'), order.index('report'))
    self.assertLess(order.index('stock'), order.index('report'))

  def test_self_cycle_raises(self) -> None:
    modules = {'a': info('a', ['a'])}
    with self.assertRaises(ValueError) as caught:
      self.manager.resolve_order(modules, 'a')
    self.assertIn('Circular module dependency', str(caught.exception))
    self.assertIn('a -> a', str(caught.exception))

  def test_two_module_cycle_raises(self) -> None:
    modules = {'a': info('a', ['b']), 'b': info('b', ['a'])}
    with self.assertRaises(ValueError) as caught:
      self.manager.resolve_order(modules, 'a')
    self.assertIn('Circular module dependency', str(caught.exception))
    self.assertIn('a -> b -> a', str(caught.exception))

  def test_unknown_module_raises(self) -> None:
    with self.assertRaises(ValueError):
      self.manager.resolve_order({}, 'missing')

  def test_unknown_dependency_raises(self) -> None:
    modules = {'a': info('a', ['missing'])}
    with self.assertRaises(ValueError):
      self.manager.resolve_order(modules, 'a')


class InstalledOrderTests(unittest.TestCase):
  def test_installed_modules_are_ordered(self) -> None:
    discovered = {
      'core': info('core'),
      'stock': info('stock', ['core']),
      'sale': info('sale', ['core', 'stock']),
    }
    self.assertEqual(
      Registry._installed_order(discovered, {'sale', 'stock', 'core'}),
      ['core', 'stock', 'sale'],
    )

  def test_missing_dependency_is_skipped(self) -> None:
    discovered = {'sale': info('sale', ['core'])}
    self.assertEqual(Registry._installed_order(discovered, {'sale'}), ['sale'])

  def test_self_cycle_raises(self) -> None:
    discovered = {'a': info('a', ['a'])}
    with self.assertRaises(ValueError) as caught:
      Registry._installed_order(discovered, {'a'})
    self.assertIn('a -> a', str(caught.exception))

  def test_two_module_cycle_raises(self) -> None:
    discovered = {'a': info('a', ['b']), 'b': info('b', ['a'])}
    with self.assertRaises(ValueError) as caught:
      Registry._installed_order(discovered, {'a', 'b'})
    self.assertIn('Circular module dependency', str(caught.exception))
    self.assertIn('a -> b -> a', str(caught.exception))


if __name__ == '__main__':
  unittest.main()
