"""Database access layer.

``Database`` wraps a pooled PostgreSQL connection and exposes small helpers used
by the rest of the framework. ``DatabaseManager`` keeps one ``Database`` (and one
model registry) per J-ERP database.
"""

from __future__ import annotations

import time
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from jerp.config import Config
from jerp.dialect import PostgresDialect, quote_ident, quote_table

#: PostgreSQL identifiers are limited to NAMEDATALEN - 1 bytes.
MAX_DATABASE_NAME_BYTES = 63


def is_valid_database_name(name: str) -> bool:
  """Whether ``name`` can be used as a quoted PostgreSQL database name.

  PostgreSQL supports mixed case, spaces and most printable characters in a
  quoted identifier. We only reject empty/whitespace-only names, NUL/control
  characters, and names longer than 63 bytes.
  """

  if not isinstance(name, str) or not name.strip():
    return False
  if '\x00' in name:
    return False
  if any(ord(char) < 32 or ord(char) == 127 for char in name):
    return False
  return len(name.encode('utf-8')) <= MAX_DATABASE_NAME_BYTES


class Database:
  """A single PostgreSQL database plus its connection pool."""

  def __init__(self, name: str, dsn: str, schema: str = 'public'):
    self.name = name
    self.dsn = dsn
    self.schema = schema
    self.dialect = PostgresDialect(schema)
    self._pool: ConnectionPool | None = None

  # --- lifecycle ----------------------------------------------------------

  def start(self) -> None:
    if self._pool is None:
      self._pool = ConnectionPool(
        conninfo=self.dsn,
        min_size=1,
        max_size=10,
        open=False,
        timeout=5,
        kwargs={'row_factory': dict_row},
      )
      self._pool.open(wait=True)

  def close(self) -> None:
    if self._pool is not None:
      self._pool.close()
      self._pool = None

  @contextmanager
  def connection(self):
    self.start()
    with self._pool.connection() as conn:
      yield conn

  @contextmanager
  def transaction(self):
    """Run a block inside a single transaction (committed on success)."""

    self.start()
    with self._pool.connection() as conn:
      with conn.transaction():
        yield conn

  # --- query helpers ------------------------------------------------------

  def execute(self, sql: str, params=None) -> int:
    """Execute a statement and return the affected row count."""

    with self.connection() as conn:
      with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.rowcount

  def fetchall(self, sql: str, params=None) -> list[dict]:
    with self.connection() as conn:
      with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall() or []

  def fetchone(self, sql: str, params=None) -> dict | None:
    with self.connection() as conn:
      with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()

  # --- introspection ------------------------------------------------------

  def table_exists(self, table: str) -> bool:
    row = self.fetchone(
      "SELECT 1 FROM information_schema.tables "
      "WHERE table_schema = %s AND table_name = %s AND table_type = 'BASE TABLE'",
      [self.schema, table],
    )
    return row is not None

  def list_tables(self) -> list[str]:
    rows = self.fetchall(self.dialect.tables_query(), [self.schema])
    return [r['table_name'] for r in rows]

  def get_columns(self, table: str) -> dict:
    rows = self.fetchall(self.dialect.columns_query(), [self.schema, table])
    return {r['column_name']: r for r in rows}

  def get_primary_key(self, table: str) -> list[str]:
    rows = self.fetchall(self.dialect.primary_key_query(), [self.schema, table])
    return [r['column_name'] for r in rows]

  def get_indexes(self, table: str) -> dict:
    rows = self.fetchall(self.dialect.indexes_query(), [self.schema, table])
    return {r['indexname']: r['indexdef'] for r in rows}

  def drop_table(self, table: str) -> None:
    self.execute(self.dialect.drop_table_sql(table))


class DatabaseManager:
  """Creates, caches and hands out :class:`Database` objects."""

  def __init__(self, config: Config | None = None):
    self.config = config or Config.load()
    self._databases: dict[str, Database] = {}
    self._registries: dict = {}
    self._catalog: set[str] | None = None
    self._catalog_at = 0.0

  # --- database handles ---------------------------------------------------

  def get(self, name: str | None = None) -> Database:
    if not name:
      raise RuntimeError('No database is selected. Create or choose one first.')
    if name not in self._databases:
      self._databases[name] = Database(
        name=name, dsn=self.config.dsn(name), schema=self.config.schema
      )
    return self._databases[name]

  # --- administration -----------------------------------------------------

  def _admin_connection(self, database: str = 'postgres'):
    return psycopg.connect(
      self.config.dsn(database), autocommit=True, row_factory=dict_row
    )

  def list_databases(self, owner: str | None = None) -> list[str]:
    """Databases owned by ``owner``.

    Defaults to ``databases.owner`` from the config, or the connected role when
    that is unset, so only the current user's databases are listed.
    """

    owner = owner if owner is not None else (
      self.config.databases.owner or self.config.databases.user
    )
    query = (
      'SELECT d.datname FROM pg_database d '
      'JOIN pg_roles r ON r.oid = d.datdba '
      'WHERE d.datistemplate = false AND r.rolname = %s '
      'ORDER BY d.datname'
    )
    with self._admin_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(query, [owner])
        return [row['datname'] for row in cur.fetchall()]

  def exists(self, name: str) -> bool:
    """Whether a database exists (cached briefly to avoid a query per request)."""

    try:
      if self._catalog is None or (time.monotonic() - self._catalog_at) > 5.0:
        with self._admin_connection() as conn:
          with conn.cursor() as cur:
            cur.execute('SELECT datname FROM pg_database WHERE datistemplate = false')
            self._catalog = {row['datname'] for row in cur.fetchall()}
        self._catalog_at = time.monotonic()
      return name in self._catalog
    except Exception:
      with self._admin_connection() as conn:
        with conn.cursor() as cur:
          cur.execute('SELECT 1 FROM pg_database WHERE datname = %s', [name])
          return cur.fetchone() is not None

  def invalidate_catalog(self) -> None:
    self._catalog = None
    self._catalog_at = 0.0

  def create(self, name: str, owner: str | None = None, template: str = 'template1') -> str:
    if self.exists(name):
      return name
    owner = owner or self.config.databases.owner or self.config.databases.user
    with self._admin_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(
          f'CREATE DATABASE {quote_ident(name)} '
          f'OWNER {quote_ident(owner)} TEMPLATE {quote_ident(template)}'
        )
    self.invalidate_catalog()
    return name

  def drop(self, name: str) -> None:
    database = self._databases.pop(name, None)
    if database is not None:
      database.close()
    self._registries.pop(name, None)
    with self._admin_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(
          f'DROP DATABASE IF EXISTS {quote_ident(name)} WITH (FORCE)'
        )
    self.invalidate_catalog()

  def duplicate(self, source: str, target: str) -> str:
    """Clone ``source`` into a new database ``target`` (Postgres TEMPLATE)."""

    if self.exists(target):
      return target
    with self._admin_connection() as conn:
      with conn.cursor() as cur:
        cur.execute(
          f'CREATE DATABASE {quote_ident(target)} TEMPLATE {quote_ident(source)}'
        )
    self.invalidate_catalog()
    return target

  # --- registries ---------------------------------------------------------

  def registry(self, name: str | None = None):
    from jerp.registry import Registry

    if not name:
      raise RuntimeError('No database is selected. Create or choose one first.')
    if name not in self._registries:
      self._registries[name] = Registry(self.get(name), self)
    return self._registries[name]

  def drop_registry(self, name: str) -> None:
    self._registries.pop(name, None)

  def close_all(self) -> None:
    for db in self._databases.values():
      db.close()
