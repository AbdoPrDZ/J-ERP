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
from jerp.migrations import MigrationRunner
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

  def load(self, installed=None) -> 'Registry':
    """Discover installed modules and rebuild the models for this database.

    ``installed`` overrides the ``sys_module`` lookup; the lifecycle uses it to
    build the target model set before the version rows are written.
    """

    with self._lock:
      discovered = self.module_manager.discover()
      if installed is None:
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
      plan = self.module_manager.prepare_install(name, force=force)
      try:
        self._apply_lifecycle(plan)
        for module_name in plan.order:
          self._seeded_modules.discard(module_name)
        self._apply_seeds()
        self._ensure_refs()
        self._sync_menus(plan.order)
        self._sync_i18n(plan.order)
        return plan.order
      except Exception:
        # A failed transaction leaves no module row behind; make sure the next
        # request rebuilds from the database instead of the partial in-memory
        # state produced while planning.
        self.ready = False
        raise

  def update(
    self, name: str | None = None, force: bool = True, allow_drop: bool = False
  ) -> list[str]:
    with self._lock:
      plan = self.module_manager.prepare_update(name, force=force)
      try:
        self._apply_lifecycle(plan, allow_drop=allow_drop)
        for module_name in plan.order:
          self._seeded_modules.discard(module_name)
        self._apply_seeds()
        self._ensure_refs()
        self._sync_menus(plan.order)
        self._sync_i18n(plan.order)
        return plan.names
      except Exception:
        self.ready = False
        raise

  def uninstall(self, name: str) -> None:
    with self._lock:
      info = self.module_manager.prepare_uninstall(name)
      try:
        with self.db.transaction():
          self.module_manager.drop_module(info)
          self.module_manager.forget(name)
          self.load()
          self.last_schema_plan = SchemaSyncer(self.db).sync_models(
            self.models.values()
          )
          self._remove_menus(name)
          self._remove_i18n(name)
      except Exception:
        self.ready = False
        raise

      self._schema_synced = True
      self._refs_ready = False
      self._seeded_modules.discard(name)

  def _apply_lifecycle(self, plan, *, allow_drop: bool = False) -> None:
    """Apply migrations, schema and version rows in one transaction.

    Order matters: ``pre`` scripts see the old schema, the sync creates the new
    one, ``post`` scripts see it, and the version rows are written last. A
    blocked or failing step rolls the whole lifecycle back, so the installed
    version never advances past a schema that was not applied.
    """

    runner = MigrationRunner(self.db)
    with self.db.transaction() as conn:
      self.module_manager.ensure_registry_tables(plan.modules)

      installed = set(self.module_manager.installed())
      installed.update(change.name for change in plan.changes)
      self.load(installed=installed)

      runner.run(conn, plan.changes, 'pre')
      self.last_schema_plan = SchemaSyncer(self.db).sync_models(
        self.models.values(), allow_drop=allow_drop
      )
      runner.run(conn, plan.changes, 'post')

      for change in plan.changes:
        self.module_manager.record(change.info)

    self._schema_synced = True
    self._refs_ready = False

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
    """Installed modules in dependency order (stably sorted by name).

    Raises ``ValueError`` when the discovered dependencies contain a cycle, so a
    broken manifest fails loudly instead of producing a partial order.
    """

    order: list[str] = []
    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(name: str) -> None:
      status = state.get(name)
      if status == 2:
        return
      if status == 1:
        start = stack.index(name)
        cycle = ' -> '.join(stack[start:] + [name])
        raise ValueError(f'Circular module dependency: {cycle}')

      state[name] = 1
      stack.append(name)
      info = discovered.get(name)
      if info is not None:
        for dependency in info.depends:
          visit(dependency)
      stack.pop()
      state[name] = 2

      if name in installed:
        order.append(name)

    for name in sorted(installed):
      visit(name)

    return order
