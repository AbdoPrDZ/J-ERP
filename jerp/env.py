"""Application environment.

The environment holds the :class:`~jerp.db.DatabaseManager` and the HTTP router.
The *active database* is tracked in a :class:`contextvars.ContextVar` so that a
request (or any scoped block) can select which database the ORM talks to.
"""

from __future__ import annotations

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

  def __init__(self, databases):
    self.databases = databases
    self.router = Router()

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

  @contextmanager
  def using(self, name: str):
    """Temporarily switch the active database."""

    token = _active_database.set(name)
    try:
      yield self
    finally:
      _active_database.reset(token)
