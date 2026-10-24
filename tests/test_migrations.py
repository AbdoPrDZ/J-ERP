"""Versioned migration discovery and execution (no database required)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from jerp.migrations import MigrationRunner, discover, version_tuple


def module_info(path, version: str = '1.2.0', name: str = 'demo'):
  return SimpleNamespace(name=name, version=version, path=Path(path))


def write_script(folder: Path, name: str, body: str) -> Path:
  folder.mkdir(parents=True, exist_ok=True)
  script = folder / name
  script.write_text(body, encoding='utf-8')
  return script


def recorder(phase: str, version: str) -> str:
  return (
    'def migrate(cr, version):\n'
    f'  cr.calls.append(("{phase}", "{version}", version))\n'
  )


class FakeConnection:
  def __init__(self):
    self.calls: list = []


class VersionTupleTests(unittest.TestCase):
  def test_numeric_order_is_not_lexicographic(self) -> None:
    self.assertLess(version_tuple('1.9.0'), version_tuple('1.10.0'))
    self.assertLess(version_tuple('1.10.0'), version_tuple('2.0.0'))

  def test_trailing_zeros_are_ignored(self) -> None:
    self.assertEqual(version_tuple('1.1'), version_tuple('1.1.0'))
    self.assertEqual(version_tuple('v2'), version_tuple('2.0.0'))

  def test_suffixes_are_ignored(self) -> None:
    self.assertEqual(version_tuple('1.2.0-beta1'), version_tuple('1.2.0'))

  def test_empty_and_invalid_are_empty(self) -> None:
    self.assertEqual(version_tuple(None), ())
    self.assertEqual(version_tuple(''), ())
    self.assertEqual(version_tuple('dev'), ())


class DiscoveryTests(unittest.TestCase):
  def test_folders_are_sorted_numerically(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      root = Path(tmp)
      for version in ('1.10.0', '1.9.0', '2.0.0'):
        (root / 'migrations' / version).mkdir(parents=True)

      found = [migration.version for migration in discover(root)]
      self.assertEqual(found, ['1.9.0', '1.10.0', '2.0.0'])

  def test_missing_folder_is_empty(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      self.assertEqual(discover(tmp), [])

  def test_folder_must_be_a_version(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      (Path(tmp) / 'migrations' / 'dev').mkdir(parents=True)
      with self.assertRaises(ValueError):
        discover(tmp)


class PendingTests(unittest.TestCase):
  def test_fresh_install_runs_nothing(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      write_script(
        Path(tmp) / 'migrations' / '1.1.0', 'pre-a.py', recorder('pre', '1.1.0')
      )
      runner = MigrationRunner()
      self.assertEqual(runner.pending(module_info(tmp), None), [])

  def test_only_folders_up_to_the_target_run(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      for version in ('1.1.0', '1.2.0', '1.3.0'):
        (Path(tmp) / 'migrations' / version).mkdir(parents=True)

      pending = [
        migration.version
        for migration in MigrationRunner().pending(module_info(tmp), '1.1.5')
      ]
      self.assertEqual(pending, ['1.2.0'])

  def test_same_version_and_downgrades_run_nothing(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      (Path(tmp) / 'migrations' / '1.2.0').mkdir(parents=True)
      runner = MigrationRunner()
      self.assertEqual(runner.pending(module_info(tmp), '1.2.0'), [])
      self.assertEqual(runner.pending(module_info(tmp), '1.3.0'), [])

  def test_applied_folders_are_skipped(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      (Path(tmp) / 'migrations' / '1.1.0').mkdir(parents=True)
      (Path(tmp) / 'migrations' / '1.2.0').mkdir(parents=True)
      pending = [
        migration.version
        for migration in MigrationRunner().pending(module_info(tmp), '1.1.0')
      ]
      self.assertEqual(pending, ['1.2.0'])


class RunTests(unittest.TestCase):
  def test_phases_and_versions_run_in_order(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      root = Path(tmp)
      write_script(
        root / 'migrations' / '1.1.0', 'pre-a.py', recorder('pre', '1.1.0')
      )
      write_script(
        root / 'migrations' / '1.1.0', 'post-a.py', recorder('post', '1.1.0')
      )
      write_script(
        root / 'migrations' / '1.2.0', 'pre-b.py', recorder('pre', '1.2.0')
      )

      change = SimpleNamespace(
        name='demo', previous='1.0.0', info=module_info(root, '1.2.0')
      )
      runner = MigrationRunner()
      connection = FakeConnection()

      self.assertEqual(
        runner.run(connection, [change], 'pre'),
        ['demo:1.1.0/pre-a.py', 'demo:1.2.0/pre-b.py'],
      )
      self.assertEqual(
        runner.run(connection, [change], 'post'), ['demo:1.1.0/post-a.py']
      )
      self.assertEqual(
        connection.calls,
        [
          ('pre', '1.1.0', '1.0.0'),
          ('pre', '1.2.0', '1.0.0'),
          ('post', '1.1.0', '1.0.0'),
        ],
      )

  def test_scripts_without_the_phase_prefix_are_ignored(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      root = Path(tmp)
      write_script(root / 'migrations' / '1.1.0', 'notes.py', 'value = 1\n')
      change = SimpleNamespace(
        name='demo', previous='1.0.0', info=module_info(root, '1.2.0')
      )
      self.assertEqual(MigrationRunner().run(FakeConnection(), [change], 'pre'), [])

  def test_script_must_define_migrate(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      root = Path(tmp)
      write_script(root / 'migrations' / '1.1.0', 'pre-a.py', 'value = 1\n')
      change = SimpleNamespace(
        name='demo', previous='1.0.0', info=module_info(root, '1.2.0')
      )
      with self.assertRaises(ValueError):
        MigrationRunner().run(FakeConnection(), [change], 'pre')

  def test_failure_names_the_module_and_rolls_up(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      root = Path(tmp)
      write_script(
        root / 'migrations' / '1.1.0',
        'pre-a.py',
        'def migrate(cr, version):\n  raise RuntimeError("boom")\n',
      )
      change = SimpleNamespace(
        name='demo', previous='1.0.0', info=module_info(root, '1.2.0')
      )
      with self.assertRaises(RuntimeError) as caught:
        MigrationRunner().run(FakeConnection(), [change], 'pre')
      self.assertIn('pre-a.py', str(caught.exception))
      self.assertIn('demo', str(caught.exception))
      self.assertIn('boom', str(caught.exception))

  def test_unknown_phase_is_rejected(self) -> None:
    with self.assertRaises(ValueError):
      MigrationRunner().run(FakeConnection(), [], 'end')


if __name__ == '__main__':
  unittest.main()
