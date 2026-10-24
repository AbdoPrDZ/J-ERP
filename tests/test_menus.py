"""Menu tree loading tests (no database required)."""

from __future__ import annotations

import unittest

from jerp.menus import menu_tree

ROWS = [
  {
    'id': 1,
    'module': 'core',
    'parent_id': None,
    'label': 'Home',
    'href': '/home',
    'sequence': 1,
    'auth': True,
  },
  {
    'id': 2,
    'module': 'core',
    'parent_id': None,
    'label': 'Contacts',
    'href': None,
    'sequence': 20,
    'auth': True,
  },
  {
    'id': 3,
    'module': 'core',
    'parent_id': 2,
    'label': 'Countries',
    'href': '/view?name=core.countries&view=list',
    'sequence': 2,
    'auth': True,
  },
  {
    'id': 4,
    'module': 'core',
    'parent_id': 2,
    'label': 'Contacts',
    'href': '/view?name=core.contacts&view=list',
    'sequence': 1,
    'auth': True,
  },
  {
    'id': 5,
    'module': 'stock',
    'parent_id': None,
    'label': 'Stock',
    'href': None,
    'sequence': 30,
    'auth': True,
  },
]


class MenuTreeTest(unittest.TestCase):

  def test_builds_nested_tree_and_sorts_siblings(self):
    tree = menu_tree(ROWS)

    self.assertEqual([node['label'] for node in tree], [
      'Home', 'Contacts', 'Stock',
    ])
    contacts = tree[1]
    self.assertNotIn('href', contacts)
    self.assertEqual(
      [child['label'] for child in contacts['children']],
      ['Contacts', 'Countries'],
    )

  def test_filters_uninstalled_modules(self):
    tree = menu_tree(ROWS, {'core'})

    self.assertEqual([node['label'] for node in tree], ['Home', 'Contacts'])

  def test_keeps_href_and_auth_on_pages_only(self):
    tree = menu_tree(ROWS)
    home = tree[0]

    self.assertEqual(home['href'], '/home')
    self.assertTrue(home['auth'])
    self.assertNotIn('auth', tree[1])


if __name__ == '__main__':
  unittest.main()
