"""Tests for PostgreSQL database name handling."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch
from urllib.parse import quote

from psycopg.conninfo import conninfo_to_dict

from jerp.config import Config
from jerp.db import is_valid_database_name
from jerp.http.request import Request


class DatabaseNameTests(unittest.TestCase):
  def test_valid_names(self) -> None:
    self.assertTrue(is_valid_database_name('My DB'))
    self.assertTrue(is_valid_database_name('Sales DB 2026'))
    self.assertTrue(is_valid_database_name('MixedCase'))
    self.assertTrue(is_valid_database_name('a' * 63))
    self.assertTrue(is_valid_database_name('O\'Brien DB'))

  def test_invalid_names(self) -> None:
    self.assertFalse(is_valid_database_name(''))
    self.assertFalse(is_valid_database_name('   '))
    self.assertFalse(is_valid_database_name('a' * 64))
    self.assertFalse(is_valid_database_name('bad\x00name'))
    self.assertFalse(is_valid_database_name('bad\nname'))
    self.assertFalse(is_valid_database_name('bad\tname'))

  def test_dsn_preserves_name(self) -> None:
    with patch.dict(os.environ, {}, clear=True):
      config = Config({
        'databases': {
          'host': 'localhost',
          'port': 5432,
          'user': 'jerp',
          'password': 'secret',
          'sslmode': 'prefer',
        },
      })
    parsed = conninfo_to_dict(config.dsn('My DB'))
    self.assertEqual(parsed['dbname'], 'My DB')

    parsed = conninfo_to_dict(config.dsn("O'Brien DB"))
    self.assertEqual(parsed['dbname'], "O'Brien DB")

  def test_cookie_roundtrip(self) -> None:
    name = 'My DB'
    request = Request(cookies={'jerp_db': quote(name, safe='')})
    self.assertEqual(request.database(), name)


if __name__ == '__main__':
  unittest.main()
