"""Per-database registry.

A ``Registry`` is the runtime view of a single PostgreSQL database: which modules
are installed and which model classes they contribute. Each database is built
independently, so databases can have different modules installed and therefore
different table/field sets.
"""

from __future__ import annotations

from pathlib import Path

from jerp.modules import ModuleManager
from jerp.schema import SchemaSyncer


class Registry:
  def __init__(self, db, manager):
    self.db = db
    self.manager = manager
    self.module_manager = ModuleManager(db, Path(manager.config.modules_path))
    self.modules: dict = {}
    self.models: dict = {}
    self.ready = False

  # --- loading ------------------------------------------------------------

  def load(self) -> 'Registry':
    discovered = self.module_manager.discover()
    installed = self.module_manager.installed()

    self.modules = {}
    self.models = {}
    for name in installed:
      info = discovered.get(name)
      if info is None:
        continue
      self.modules[name] = info
      for model in info.models:
        self.models[model._name] = model

    self.ready = True
    return self

  def ensure_loaded(self) -> 'Registry':
    if not self.ready:
      self.load()
    return self

  def init_models(self) -> None:
    """Synchronize the schema of every installed model."""

    SchemaSyncer(self.db).sync_models(self.models.values())

  # --- lifecycle (delegated to the module manager) ------------------------

  def install(self, name: str, force: bool = False) -> list[str]:
    order = self.module_manager.install(name, force=force)
    self.load()
    return order

  def update(self, name: str | None = None, force: bool = True) -> list[str]:
    synced = self.module_manager.update(name, force=force)
    self.load()
    return synced

  def uninstall(self, name: str) -> None:
    self.module_manager.uninstall(name)
    self.load()

  # --- accessors ----------------------------------------------------------

  def get(self, model_name: str):
    model = self.models.get(model_name)
    if model is None and '_' in model_name:
      # Accept ``sys_module`` as an alias for ``sys.module``.
      model = self.models.get(model_name.replace('_', '.'))
    return model

  def list_models(self) -> list[str]:
    return list(self.models)

  def list_modules(self) -> list[str]:
    return list(self.modules)
