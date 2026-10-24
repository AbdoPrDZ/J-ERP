"""Configuration loading for J-ERP.

Connection settings live in ``jerp.config.json`` at the project root and can be
overridden through ``JERP_DB_*`` environment variables.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from psycopg.conninfo import make_conninfo

DEFAULT_CONFIG_NAME = 'jerp.config.json'


class DatabaseConfig:
  """Connection settings shared by every database managed by J-ERP."""

  def __init__(self, data: dict | None = None):
    data = data or {}
    self.host = os.environ.get('JERP_DB_HOST', data.get('host', 'localhost'))
    self.port = int(os.environ.get('JERP_DB_PORT', data.get('port', 5432)))
    self.user = os.environ.get('JERP_DB_USER', data.get('user', 'postgres'))
    self.password = os.environ.get('JERP_DB_PASSWORD', data.get('password', ''))
    self.sslmode = os.environ.get('JERP_DB_SSLMODE', data.get('sslmode'))
    self.connect_timeout = int(data.get('connect_timeout', 10))
    #: Restrict the database list to databases owned by this role (defaults to
    #: the connected role when unset).
    self.owner = os.environ.get('JERP_DB_OWNER', data.get('owner'))
    #: Optional superuser role used only to force-drop databases.
    self.admin_user = os.environ.get(
      'JERP_DB_ADMIN_USER', data.get('admin_user')
    )
    self.admin_password = os.environ.get(
      'JERP_DB_ADMIN_PASSWORD', data.get('admin_password')
    )

  def dsn(self, database: str, user: str | None = None, password: str | None = None) -> str:
    params = {
      'host': self.host,
      'port': str(self.port),
      'user': user or self.user,
      'dbname': database,
      'connect_timeout': str(self.connect_timeout),
    }
    secret = self.password if password is None else password
    if secret:
      params['password'] = secret
    if self.sslmode:
      params['sslmode'] = self.sslmode
    return make_conninfo(**params)

  @property
  def has_admin(self) -> bool:
    return bool(self.admin_user)

  def admin_dsn(self, database: str) -> str:
    return self.dsn(
      database,
      user=self.admin_user,
      password=self.admin_password,
    )


class Config:
  """Top level J-ERP configuration."""

  def __init__(self, data: dict | None = None, path: Path | None = None):
    data = data or {}
    self.path = path
    self.databases = DatabaseConfig(data.get('databases'))
    app = data.get('app') or {}
    self.app_host = os.environ.get('JERP_APP_HOST', app.get('host', '127.0.0.1'))
    self.app_port = int(os.environ.get('JERP_APP_PORT', app.get('port', 1347)))
    security = data.get('security') or {}
    self.master_key = os.environ.get(
      'JERP_MASTER_KEY', security.get('master_key', '')
    )
    self.modules_path = data.get('modules_path', 'modules')
    self.schema = data.get('schema', 'public')
    self.database = os.environ.get('JERP_DATABASE', data.get('database'))
    self.ui_dist = data.get('ui_dist', 'data/ui')
    self.views_dir = data.get('views_dir', 'data/view')
    self.uploads_dir = data.get('uploads_dir', 'data/uploads')

  @classmethod
  def load(cls, path: str | Path | None = None) -> 'Config':
    if path is None:
      candidate = Path.cwd() / DEFAULT_CONFIG_NAME
      path = candidate if candidate.exists() else None
    else:
      path = Path(path)

    data = {}
    if path is not None and Path(path).exists():
      data = json.loads(Path(path).read_text(encoding='utf-8'))

    return cls(data, path)

  def dsn(self, database: str) -> str:
    return self.databases.dsn(database)
