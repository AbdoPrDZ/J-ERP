"""Versioned per-module data migrations.

A module may ship scripts under ``migrations/<version>/``::

  modules/sale/migrations/1.1.0/pre-backfill_price.py
  modules/sale/migrations/1.1.0/post-rename_currency.py

``pre-*`` scripts run before the schema sync (old columns still exist) and
``post-*`` scripts after it (new columns available). Both run inside the same
transaction as the schema sync and the ``sys_module`` version row, so a failing
script rolls everything back and the installed version stays unchanged.

Each script defines ``migrate(cr, version)``, where ``cr`` is the psycopg
connection (raw SQL only: the ORM still describes the old schema during ``pre``)
and ``version`` is the previously installed module version.

Migrations only run when the module version moves forward. A fresh install, a
re-sync at the same version, and ``update(force=True)`` never run them.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path

#: Folder under a module directory that holds versioned migration scripts.
MIGRATIONS_DIR = 'migrations'

#: Phases, in execution order, and the filename prefix of their scripts.
PHASES = ('pre', 'post')


def version_tuple(value: str | None) -> tuple[int, ...]:
  """Comparable numeric version, ignoring trailing zeros and suffixes.

  ``'1.10.0'`` -> ``(1, 10)``, ``'1.9'`` -> ``(1, 9)``, ``'1.1'`` == ``'1.1.0'``.
  Values without digits produce ``()``.
  """

  if not value:
    return ()

  parts: list[int] = []
  for token in str(value).strip().lstrip('vV').split('.'):
    digits = ''
    for char in token:
      if not char.isdigit():
        break
      digits += char
    if not digits:
      break
    parts.append(int(digits))

  while parts and parts[-1] == 0:
    parts.pop()
  return tuple(parts)


@dataclass(frozen=True)
class Migration:
  """One ``migrations/<version>/`` folder."""

  version: str
  key: tuple[int, ...]
  path: Path

  def scripts(self, phase: str) -> list[Path]:
    if phase not in PHASES:
      raise ValueError(f"Unknown migration phase '{phase}'")
    return sorted(
      path for path in self.path.glob(f'{phase}-*.py') if path.is_file()
    )


def discover(module_path: str | Path) -> list[Migration]:
  """Migration folders of a module, in ascending version order."""

  root = Path(module_path) / MIGRATIONS_DIR
  if not root.is_dir():
    return []

  migrations: list[Migration] = []
  for path in root.iterdir():
    if not path.is_dir():
      continue
    key = version_tuple(path.name)
    if not key:
      raise ValueError(
        f"Migration folder '{path}' must be named after a version, "
        f'for example 1.1.0.'
      )
    migrations.append(Migration(version=path.name, key=key, path=path))

  migrations.sort(key=lambda migration: (migration.key, migration.version))
  return migrations


class MigrationRunner:
  """Selects and executes the migrations of a module lifecycle plan."""

  def __init__(self, db=None):
    self.db = db

  def pending(self, info, previous: str | None) -> list[Migration]:
    """Folders to run when going from ``previous`` to ``info.version``."""

    if previous is None:
      # Fresh install: the schema is created at the current version and there
      # is no data to transform.
      return []

    previous_key = version_tuple(previous)
    target_key = version_tuple(info.version)
    if not target_key or previous_key >= target_key:
      return []

    return [
      migration
      for migration in discover(info.path)
      if previous_key < migration.key <= target_key
    ]

  def run(self, conn, changes, phase: str) -> list[str]:
    """Run ``phase`` for every pending module change, in plan order."""

    if phase not in PHASES:
      raise ValueError(f"Unknown migration phase '{phase}'")

    executed: list[str] = []
    for change in changes:
      for migration in self.pending(change.info, change.previous):
        for script in migration.scripts(phase):
          self._execute(conn, change, migration, script)
          executed.append(f'{change.name}:{migration.version}/{script.name}')
    return executed

  def _execute(self, conn, change, migration: Migration, script: Path) -> None:
    label = (
      f"jerp_migration_{change.name}_{migration.version}_{script.stem}"
    ).replace('.', '_').replace('-', '_')

    spec = importlib.util.spec_from_file_location(label, script)
    if spec is None or spec.loader is None:
      raise RuntimeError(f'Cannot load migration script {script}.')

    module = importlib.util.module_from_spec(spec)
    try:
      spec.loader.exec_module(module)
    except Exception as exc:
      raise RuntimeError(
        f"Migration script {script} for module '{change.name}' failed to "
        f'load: {exc}'
      ) from exc

    migrate = getattr(module, 'migrate', None)
    if not callable(migrate):
      raise ValueError(
        f"Migration script {script} must define migrate(cr, version)."
      )

    try:
      migrate(conn, change.previous or '0.0.0')
    except Exception as exc:
      raise RuntimeError(
        f"Migration script {script} for module '{change.name}' failed: {exc}"
      ) from exc
