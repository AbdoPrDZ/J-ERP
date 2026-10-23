"""Tests for manager secrets and configuration."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from jerp.config import Config
from jerp.security import verify_secret


class SecretTests(unittest.TestCase):
  def test_verify_secret(self) -> None:
    self.assertTrue(verify_secret('master', 'master'))
    self.assertFalse(verify_secret('wrong', 'master'))
    self.assertFalse(verify_secret('', 'master'))
    self.assertFalse(verify_secret('master', ''))
    self.assertFalse(verify_secret(None, 'master'))

  def test_master_key_from_config(self) -> None:
    with patch.dict(os.environ, {}, clear=True):
      config = Config({'security': {'master_key': 'from-config'}})
    self.assertEqual(config.master_key, 'from-config')

  def test_master_key_from_environment(self) -> None:
    with patch.dict(os.environ, {'JERP_MASTER_KEY': 'from-env'}):
      config = Config({'security': {'master_key': 'from-config'}})
    self.assertEqual(config.master_key, 'from-env')

  def test_master_key_defaults_to_empty(self) -> None:
    with patch.dict(os.environ, {}, clear=True):
      config = Config({})
    self.assertEqual(config.master_key, '')


if __name__ == '__main__':
  unittest.main()
