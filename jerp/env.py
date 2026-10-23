"""Application environment.

The environment holds the :class:`~jerp.db.DatabaseManager` and the HTTP router.
The *active database* is tracked in a :class:`contextvars.ContextVar` so that a
request (or any scoped block) can select which database the ORM talks to.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from contextvars import ContextVar

from jerp.http.router import Router

_active_database: ContextVar = ContextVar('jerp_active_database', default=None)


class _EnvironmentMeta(type):
  @property
  def instance(cls) -> 'Environment':
    if cls._instance is None:
      raise RuntimeError('Environment is not initialized. Call Environment.init_instance().')
    return cls._instance


class Environment(metaclass=_EnvironmentMeta):
  _instance: 'Environment | None' = None

  def __init__(self, databases=None, database: str | None = None):
    standalone = databases is None
    if standalone:
      from jerp.config import Config
      from jerp.db import DatabaseManager

      databases = DatabaseManager(Config.load())

    self.databases = databases
    self.router = Router()

    if standalone:
      database = database or self._default_database()
      if database:
        _active_database.set(database)
      type(self)._instance = self
    elif database:
      _active_database.set(database)

  def _default_database(self) -> str | None:
    """Choose a database for a standalone ``Environment()``."""

    configured = os.environ.get('JERP_DATABASE')
    if not configured:
      configured = getattr(self.databases.config, 'database', None)
    if configured:
      return configured
    names = self.databases.list_databases()
    if not names:
      raise RuntimeError(
        'No J-ERP database was found. Create one in the application first.'
      )
    for candidate in ('J-ERP', 'jerp'):
      if candidate in names:
        return candidate
    if len(names) == 1:
      return names[0]
    raise RuntimeError(
      'Several databases exist; set JERP_DATABASE to choose one.'
    )

  def __getitem__(self, model_name: str):
    registry = self.registry()
    registry.ensure_loaded()
    model = registry.get(model_name)
    if model is None:
      raise KeyError(f'Unknown model "{model_name}".')
    return model

  def __contains__(self, model_name: str) -> bool:
    registry = self.registry()
    registry.ensure_loaded()
    return registry.get(model_name) is not None

  # --- initialization -----------------------------------------------------

  @classmethod
  def init_instance(cls, databases) -> 'Environment':
    cls._instance = Environment(databases)
    return cls._instance

  @classmethod
  def init_from_config(cls, config=None) -> 'Environment':
    from jerp.config import Config
    from jerp.db import DatabaseManager

    config = config or Config.load()
    return cls.init_instance(DatabaseManager(config))

  # --- active database ----------------------------------------------------

  @property
  def active_database(self) -> str | None:
    return _active_database.get()

  @property
  def db(self):
    return self.databases.get(self.active_database)

  def registry(self, name: str | None = None):
    return self.databases.registry(name or self.active_database)

  def ref(self, key: str):
    """Return the record referenced by an external key (``sys.data.key``)."""

    registry = self.registry()
    registry.ensure_loaded()

    Data = registry.get('sys.data')
    if Data is None:
      raise RuntimeError("The 'sys.data' model is not installed.")

    rows = Data.search([('key', '=', str(key))], limit=1)
    if not rows:
      raise ValueError(f"External ID not found: {key}")

    data = rows[0]
    Model = registry.get(data.model)
    if Model is None:
      raise ValueError(
        f"External ID '{key}' points to an unknown model '{data.model}'."
      )

    records = Model.browse(data.res_id)
    if not records:
      raise ValueError(
        f"External ID '{key}' points to a missing {data.model}#{data.res_id}."
      )
    return records[0]

  @contextmanager
  def using(self, name: str):
    """Temporarily switch the active database."""

    token = _active_database.set(name)
    try:
      yield self
    finally:
      _active_database.reset(token)
