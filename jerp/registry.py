"""Per-database registry.

A ``Registry`` is the runtime view of a single PostgreSQL database: which modules
are installed and which models they contribute. Each database is built
independently, so databases can have different modules installed and therefore
different table/field sets.

Model sources are combined by :class:`jerp.builder.ModelBuilder`; the resulting
built classes are what the API, views and schema syncer use.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from jerp.builder import BuildResult, ModelBuilder
from jerp.modules import ModuleManager
from jerp.schema import SchemaBlocked, SchemaSyncer
from jerp.seeds import SeedLoader
from jerp.refs import backfill

logger = logging.getLogger('jerp.registry')


class Registry:
  def __init__(self, db, manager):
    self.db = db
    self.manager = manager
    self.module_manager = ModuleManager(db, Path(manager.config.modules_path))
    self.builder = ModelBuilder()
    self.seed_loader = SeedLoader(self)
    self.modules: dict = {}
    self.models: dict = {}
    self._result: BuildResult | None = None
    self._lock = threading.RLock()
    self._schema_synced = False
    self._seeded_modules: set[str] = set()
    self._refs_ready = False
    self._menus_ready = False
    #: Last plan produced by a schema sync (see ``jerp.schema.SchemaPlan``).
    self.last_schema_plan = None
    self.ready = False

  # --- loading ------------------------------------------------------------

  def load(self) -> 'Registry':
    """Discover installed modules and rebuild the models for this database."""

    with self._lock:
      discovered = self.module_manager.discover()
      installed = self.module_manager.installed()
      order = self._installed_order(discovered, installed)

      self.modules = {}
      module_sources: dict[str, list] = {}
      for name in order:
        info = discovered.get(name)
        if info is None:
          continue
        self.modules[name] = info
        module_sources[name] = list(info.models)

      # Dependencies are needed for validation even when a dependency is not
      # installed (the builder then reports the missing module clearly).
      depends = {
        name: list(info.depends) for name, info in discovered.items()
      }

      self._result = self.builder.build(module_sources, depends)
      self.models = self._result.models
      if self._result.changed:
        self._schema_synced = False
      self._seeded_modules &= set(self.modules)
      self._menus_ready = False
      self.ready = True
      return self

  def ensure_loaded(self) -> 'Registry':
    with self._lock:
      if not self.ready:
        self.load()
      if not self._schema_synced:
        self.sync_dirty()
      self._apply_seeds()
      self._ensure_refs()
      return self

  @property
  def build_result(self) -> BuildResult | None:
    return self._result

  def rebuild(self, force: bool = False) -> 'Registry':
    """Rebuild this database's models and synchronize their schema."""

    with self._lock:
      self.load()
      if force:
        self.init_models()
      else:
        self.sync_dirty()
      self._apply_seeds()
      self._ensure_refs()
      return self

  # --- schema -------------------------------------------------------------

  def _apply_seeds(self) -> None:
    if not self.modules:
      return

    from jerp.env import Environment

    try:
      environment = Environment.instance
    except RuntimeError:
      environment = Environment.init_instance(self.manager)

    with environment.using(self.db.name):
      for name, info in self.modules.items():
        if name in self._seeded_modules:
          continue
        if info.seed:
          self.seed_loader.apply(info)
        self._seeded_modules.add(name)

  def _ensure_refs(self) -> None:
    if self._refs_ready:
      return

    from jerp.env import Environment

    try:
      environment = Environment.instance
    except RuntimeError:
      environment = Environment.init_instance(self.manager)

    with environment.using(self.db.name):
      backfill(self)
    self._refs_ready = True

  # --- menus --------------------------------------------------------------

  def ensure_menus(self) -> None:
    """Backfill modules that have no menu rows yet (existing databases)."""

    with self._lock:
      if self._menus_ready:
        return
      from jerp.menus import MenuSyncer

      MenuSyncer(self.db, Path(self.manager.config.modules_path)).sync_missing(
        self.modules
      )
      self._menus_ready = True

  def _sync_menus(self, module_names) -> None:
    from jerp.menus import MenuSyncer

    MenuSyncer(self.db, Path(self.manager.config.modules_path)).sync_modules(
      module_names
    )
    self._menus_ready = True

  def _remove_menus(self, module_name: str) -> None:
    from jerp.menus import MenuSyncer

    MenuSyncer(self.db, Path(self.manager.config.modules_path)).remove_module(
      module_name
    )
    self._menus_ready = True

  # --- translations -------------------------------------------------------

  def _sync_i18n(self, module_names) -> None:
    from jerp.i18n import I18nLoader

    I18nLoader(self.db, Path(self.manager.config.modules_path)).sync_modules(
      module_names, active_only=True
    )

  def _remove_i18n(self, module_name: str) -> None:
    from jerp.i18n import I18nLoader

    I18nLoader(self.db, Path(self.manager.config.modules_path)).remove_module(
      module_name
    )

  def init_models(self, allow_drop: bool = False):
    """Synchronize the schema of every built model."""

    with self._lock:
      self.last_schema_plan = SchemaSyncer(self.db).sync_models(
        self.models.values(), allow_drop=allow_drop
      )
      self._schema_synced = True
      self._refs_ready = False
      return self.last_schema_plan

  def preview(self, name: str | None = None, allow_drop: bool = False):
    """Return the plan for a full sync, without changing the database.

    ``name`` only validates that the module is known; like an update, the plan
    covers every model of the database.
    """

    with self._lock:
      self.load()
      if name and name not in self.modules:
        raise ValueError(f"Module '{name}' is not installed in {self.db.name}.")
      return SchemaSyncer(self.db).plan(
        self.models.values(), allow_drop=allow_drop
      )

  def retired_fields(self) -> list[dict]:
    """Retired columns still present in the database (read-only)."""

    with self._lock:
      self.load()
      return SchemaSyncer(self.db).retired_fields(self.models.values())

  def sync_dirty(self) -> set[str]:
    """Synchronize only models whose build fingerprint changed.

    Request handlers reach this through :meth:`ensure_loaded`, so it must never
    take the process down: safe changes are applied, blocked ones are logged and
    kept in ``last_schema_plan``. Declared renames are applied (they are
    explicit and lossless), while type changes and drops are left to an explicit
    update. Explicit install/update calls :meth:`init_models` instead, which
    propagates :class:`SchemaBlocked`.
    """

    with self._lock:
      if self._result is None:
        return set()

      names = set(self._result.changed)
      models = [
        self.models[name]
        for name in names
        if name in self.models and not getattr(self.models[name], '_virtual', False)
      ]
      if models:
        try:
          self.last_schema_plan = SchemaSyncer(self.db).sync_models(
            models, allow_type_change=False
          )
        except SchemaBlocked as exc:
          self.last_schema_plan = exc.plan
          logger.warning('%s (database %s)', exc, self.db.name)
      self._schema_synced = True
      self._refs_ready = False
      return names

  # --- lifecycle (delegated to the module manager) ------------------------

  def install(self, name: str, force: bool = False) -> list[str]:
    with self._lock:
      before = set(self.module_manager.installed())

      try:
        order = self.module_manager.install(name, force=force)
        self.load()
        self.init_models()
        for module_name in order:
          self._seeded_modules.discard(module_name)
        self._apply_seeds()
        self._ensure_refs()
        self._sync_menus(order)
        self._sync_i18n(order)
        return order
      except Exception:
        # Do not leave newly recorded modules behind if the build/sync fails.
        try:
          after = set(self.module_manager.installed())
          for module_name in after - before:
            self.db.execute(
              'DELETE FROM sys_module WHERE name = %s', [module_name]
            )
            try:
              self._remove_menus(module_name)
            except Exception:
              pass
            try:
              self._remove_i18n(module_name)
            except Exception:
              pass
        except Exception:
          pass
        self.ready = False
        raise

  def update(
    self, name: str | None = None, force: bool = True, allow_drop: bool = False
  ) -> list[str]:
    with self._lock:
      synced = self.module_manager.update(name, force=force)
      self.load()
      self.init_models(allow_drop=allow_drop)
      targets = [name] if name else list(self.modules)
      for module_name in targets:
        self._seeded_modules.discard(module_name)
      self._apply_seeds()
      self._ensure_refs()
      self._sync_menus(targets)
      self._sync_i18n(targets)
      return synced

  def uninstall(self, name: str) -> None:
    with self._lock:
      self.module_manager.uninstall(name)
      self._seeded_modules.discard(name)
      self._refs_ready = False
      self.load()
      self.init_models()
      self._remove_menus(name)
      self._remove_i18n(name)

  # --- accessors ----------------------------------------------------------

  def get(self, model_name: str):
    model = self.models.get(model_name)
    if model is None and '_' in model_name:
      # Accept ``sys_module`` as an alias for ``sys.module``.
      model = self.models.get(model_name.replace('_', '.'))
    return model

  def describe(self, model_name: str) -> dict | None:
    self.ensure_loaded()
    return self.builder.describe(model_name)

  def list_models(self) -> list[str]:
    return list(self.models)

  def list_modules(self) -> list[str]:
    return list(self.modules)

  # --- internals ----------------------------------------------------------

  @staticmethod
  def _installed_order(discovered, installed) -> list[str]:
    """Installed modules in dependency order (stably sorted by name)."""

    order: list[str] = []
    seen: set[str] = set()

    def visit(name: str) -> None:
      if name in seen:
        return
      seen.add(name)
      info = discovered.get(name)
      if info is None:
        return
      for dependency in info.depends:
        visit(dependency)
      if name in installed:
        order.append(name)

    for name in sorted(installed):
      visit(name)

    return order
