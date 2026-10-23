"""Module discovery and lifecycle (install / update / uninstall).

Each directory under ``modules/`` that contains a ``configure.json`` manifest is
a J-ERP module. Installing a module means synchronizing the tables of the models
it declares and recording it in the per-database ``sys_module`` registry.
"""

from __future__ import annotations

import importlib
import json
import shutil
import subprocess
from dataclasses import dataclass, field as dataclass_field
from pathlib import Path

from jerp.models import ModelRegistry
from jerp.schema import SchemaSyncer

#: The module that owns the system tables; always installed first.
BASE_MODULE = 'core'


@dataclass
class ModuleInfo:
  name: str
  version: str
  summary: str
  depends: list
  path: Path
  logo: str | None = None
  models: list = dataclass_field(default_factory=list)


class ModuleManager:
  def __init__(self, db, modules_dir: str | Path):
    self.db = db
    self.modules_dir = Path(modules_dir)
    self.package = self.modules_dir.name

  # --- discovery ----------------------------------------------------------

  def discover(self) -> dict[str, ModuleInfo]:
    result: dict[str, ModuleInfo] = {}
    if not self.modules_dir.is_dir():
      return result

    for path in sorted(self.modules_dir.iterdir()):
      manifest = path / 'configure.json'
      if not path.is_dir() or not manifest.exists():
        continue
      data = json.loads(manifest.read_text(encoding='utf-8'))
      name = data.get('name') or path.name
      result[name] = ModuleInfo(
        name=name,
        version=str(data.get('version', '0.0.0')),
        summary=data.get('summary', ''),
        depends=list(data.get('depends', [])),
        path=path,
        logo=data.get('logo'),
      )

    for info in result.values():
      self._load_models(info)

    return result

  def _load_models(self, info: ModuleInfo) -> None:
    package = f'{self.package}.{info.name}'
    for target in (package, f'{package}.models'):
      try:
        importlib.import_module(target)
      except ModuleNotFoundError:
        continue

    prefix = f'{package}.'
    info.models = [
      model
      for model in ModelRegistry.all().values()
      if getattr(model, '__module__', '').startswith(prefix)
    ]

  # --- registry helpers ---------------------------------------------------

  def installed(self) -> dict[str, dict]:
    if not self.db.table_exists('sys_module'):
      return {}
    rows = self.db.fetchall('SELECT name, version, state FROM sys_module')
    return {r['name']: r for r in rows}

  def ensure_core(self) -> None:
    if not self.db.table_exists('sys_module'):
      self.install(BASE_MODULE)

  def resolve_order(self, modules: dict[str, ModuleInfo], target: str) -> list[str]:
    order: list[str] = []
    seen: set[str] = set()

    def visit(name: str) -> None:
      if name in seen:
        return
      info = modules.get(name)
      if info is None:
        raise ValueError(f"Unknown module '{name}'")
      seen.add(name)
      for dependency in info.depends:
        visit(dependency)
      order.append(name)

    visit(target)
    return order

  # --- lifecycle ----------------------------------------------------------

  def install(self, name: str, force: bool = False) -> list[str]:
    modules = self.discover()
    order = self.resolve_order(modules, name)
    syncer = SchemaSyncer(self.db)

    for module_name in order:
      info = modules[module_name]
      existing = self.installed().get(module_name)
      if existing and existing['version'] == info.version and not force:
        continue
      syncer.sync_models(info.models)
      self._record(info)
      self.build_views(module_name)

    return order

  def update(self, name: str | None = None, force: bool = True) -> list[str]:
    modules = self.discover()
    if name:
      targets = [name]
    else:
      targets = list(self.installed().keys())

    syncer = SchemaSyncer(self.db)
    synced: list[str] = []

    for module_name in targets:
      info = modules.get(module_name)
      if info is None:
        continue
      existing = self.installed().get(module_name)
      if existing and not force and existing['version'] == info.version:
        continue
      syncer.sync_models(info.models)
      self._record(info)
      self.build_views(module_name)
      synced.append(module_name)

    return synced

  def uninstall(self, name: str) -> None:
    if name == BASE_MODULE:
      raise ValueError('The core module cannot be uninstalled.')

    modules = self.discover()
    info = modules.get(name)
    if info is None:
      raise ValueError(f"Unknown module '{name}'")

    installed = self.installed()
    dependents = [
      module_name
      for module_name, module in modules.items()
      if name in module.depends and module_name in installed
    ]
    if dependents:
      raise ValueError(
        f"Cannot uninstall '{name}'; required by: {', '.join(dependents)}"
      )

    syncer = SchemaSyncer(self.db)
    for model in reversed(info.models):
      syncer.drop_model(model)

    if self.db.table_exists('sys_module'):
      self.db.execute('DELETE FROM sys_module WHERE name = %s', [name])

  # --- views --------------------------------------------------------------

  def build_views(self, name: str) -> bool:
    """Compile a module's TS views to JS (esbuild) and refresh its manifest."""

    script = Path.cwd() / 'tools' / 'build-views.mjs'
    if not script.is_file() or shutil.which('node') is None:
      return False
    try:
      subprocess.run(
        ['node', str(script), name],
        cwd=str(Path.cwd()),
        check=True,
        capture_output=True,
        text=True,
      )
      return True
    except subprocess.CalledProcessError as exc:
      print(f'WARNING: view build failed for "{name}": {exc.stderr or exc}')
      return False

  # --- internals ----------------------------------------------------------

  def _record(self, info: ModuleInfo, state: str = 'installed') -> None:
    self.db.execute(
      'INSERT INTO sys_module (name, version, state, summary, created_at, updated_at) '
      'VALUES (%s, %s, %s, %s, NOW(), NOW()) '
      'ON CONFLICT (name) DO UPDATE SET '
      'version = EXCLUDED.version, state = EXCLUDED.state, '
      'summary = EXCLUDED.summary, updated_at = NOW()',
      [info.name, info.version, state, info.summary],
    )
