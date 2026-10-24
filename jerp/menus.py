"""Database-backed navigation menus.

Menu declarations live in each module's ``configure.json`` and are synchronized
into ``sys.menu`` when the module is installed or updated. The API reads the
table back and rebuilds the nested tree returned to the client.
"""

from __future__ import annotations

from pathlib import Path

from jerp.dialect import quote_ident, quote_table
from jerp.views import menu_href, read_module_entries

TABLE = 'sys_menu'

#: Columns written for every menu row (``created_at``/``updated_at`` use NOW()).
COLUMNS = (
  'code',
  'module',
  'parent_id',
  'label',
  'view',
  'href',
  'sequence',
  'auth',
  'description',
  'img',
)

INSERT_SQL = (
  f'INSERT INTO {quote_table(TABLE)} '
  f'({", ".join(quote_ident(column) for column in COLUMNS)}, '
  f'{quote_ident("created_at")}, {quote_ident("updated_at")}) '
  f'VALUES ({", ".join(["%s"] * len(COLUMNS))}, NOW(), NOW()) '
  f'RETURNING {quote_ident("id")}'
)


class MenuSyncer:
  """Mirror a module's declared routes into ``sys.menu``."""

  def __init__(self, db, modules_dir: str | Path):
    self.db = db
    self.modules_dir = Path(modules_dir)

  # --- writes -------------------------------------------------------------

  def sync_modules(self, module_names) -> None:
    for module_name in dict.fromkeys(module_names):
      self.sync_module(module_name)

  def sync_module(self, module_name: str) -> None:
    """Replace one module's menu rows with its ``configure.json`` declaration."""

    entries: list[dict] = []
    for _name, routes in read_module_entries(self.modules_dir, [module_name]):
      entries = routes

    with self.db.transaction():
      self.db.execute(
        f'DELETE FROM {quote_table(TABLE)} WHERE {quote_ident("module")} = %s',
        [module_name],
      )
      self._insert_entries(module_name, entries, None, '')

  def sync_missing(self, module_names) -> None:
    """Populate modules that do not have menu rows yet (upgrade backfill)."""

    if not self.db.table_exists(TABLE):
      return

    rows = self.db.fetchall(f'SELECT DISTINCT {quote_ident("module")} FROM {quote_table(TABLE)}')
    present = {row['module'] for row in rows}
    for module_name in dict.fromkeys(module_names):
      if module_name not in present:
        self.sync_module(module_name)

  def remove_module(self, module_name: str) -> None:
    if not self.db.table_exists(TABLE):
      return
    self.db.execute(
      f'DELETE FROM {quote_table(TABLE)} WHERE {quote_ident("module")} = %s',
      [module_name],
    )

  # --- internals ----------------------------------------------------------

  def _insert_entries(
    self, module_name: str, entries, parent_id, code_prefix: str
  ) -> None:
    for index, item in enumerate(entries):
      if not isinstance(item, dict):
        continue

      label = item.get('label')
      # Hidden and unlabelled entries never appear in the navigation (and,
      # like the old in-memory tree, their children are not traversed).
      if not label or item.get('hide'):
        continue

      code = f'{code_prefix}.{index}' if code_prefix else f'{module_name}.{index}'
      page = None
      if item.get('view'):
        page = {
          'view': item['view'],
          'endpoint': item.get('endpoint') or item.get('path'),
          'params': dict(item.get('params') or {}),
        }

      row = self.db.fetchone(INSERT_SQL, [
        code,
        module_name,
        parent_id,
        label,
        item.get('view'),
        menu_href(page) if page else None,
        item.get('sequence', 0),
        bool(item.get('auth', True)),
        item.get('description'),
        item.get('img'),
      ])
      node_id = row['id'] if row else None
      if node_id is None:
        continue

      children = item.get('children') or []
      if children:
        self._insert_entries(module_name, children, node_id, code)


def load_rows(db) -> list[dict]:
  """All menu rows in declaration order."""

  return db.fetchall(
    f'SELECT * FROM {quote_table(TABLE)} '
    f'ORDER BY {quote_ident("sequence")}, {quote_ident("label")}, {quote_ident("id")}'
  )


def menu_tree(rows, installed_modules=None) -> list[dict]:
  """Build the nested menu payload from flat ``sys.menu`` rows."""

  installed = None if installed_modules is None else set(installed_modules)
  children_by_parent: dict = {}

  for row in rows:
    if installed is not None and row.get('module') not in installed:
      continue
    children_by_parent.setdefault(row.get('parent_id'), []).append(row)

  def build(parent_id):
    nodes: list[dict] = []
    for row in children_by_parent.get(parent_id, []):
      node: dict = {
        'label': row['label'],
        'sequence': row.get('sequence') or 0,
      }
      if row.get('href'):
        node['href'] = row['href']
        node['auth'] = bool(row.get('auth', True))
      if row.get('img'):
        node['img'] = row['img']
      if row.get('description'):
        node['description'] = row['description']

      children = build(row.get('id'))
      if children:
        node['children'] = children
      nodes.append(node)

    nodes.sort(key=lambda node: (node.get('sequence', 0), node['label']))
    return nodes

  return build(None)
