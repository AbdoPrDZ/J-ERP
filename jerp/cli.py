"""Command line interface for J-ERP database and module management.

Examples::

  python -m jerp.cli create --database jerp
  python -m jerp.cli init   --database jerp
  python -m jerp.cli install stock --database jerp
  python -m jerp.cli update --database jerp
  python -m jerp.cli update --database jerp --dry-run
  python -m jerp.cli doctor --database jerp
  python -m jerp.cli modules --database jerp
"""

from __future__ import annotations

import argparse
import json
import sys

from jerp.config import Config
from jerp.db import DatabaseManager
from jerp.dialect import quote_ident, quote_table
from jerp.schema import SchemaBlocked


def _manager(args) -> DatabaseManager:
  manager = DatabaseManager(Config.load(args.config))
  _MANAGERS.append(manager)
  return manager


_MANAGERS: list[DatabaseManager] = []


def _database(args) -> str:
  name = getattr(args, 'database', None)
  if not name:
    raise SystemExit('A database is required: pass --database <name>.')
  return name


def cmd_create(args) -> int:
  manager = _manager(args)
  name = _database(args)
  manager.create(name)
  print(f'Database ready: {name}')
  return 0


def cmd_drop(args) -> int:
  manager = _manager(args)
  name = _database(args)
  manager.drop(name)
  print(f'Database dropped: {name}')
  return 0


def cmd_databases(args) -> int:
  manager = _manager(args)
  for name in manager.list_databases():
    print(name)
  return 0


def cmd_install(args) -> int:
  manager = _manager(args)
  registry = manager.registry(_database(args))
  for module in args.modules:
    order = registry.install(module, force=args.force)
    print(f'Installed {" -> ".join(order)}')
  return 0


def _describe_change(change: dict) -> str:
  """One human-readable line for a plan change (or a blocked entry)."""

  op = change.get('op', '?')
  table = change.get('table')
  column = change.get('column')
  field = change.get('field')
  target = '.'.join(part for part in (table, column) if part) or field or ''

  if op == 'create_table':
    detail = str(table or '')
  elif op == 'rename_table':
    detail = f"{change.get('old')} -> {table}"
  elif op == 'rename_column':
    detail = f"{target} (from {change.get('old')})"
  elif op == 'alter_type':
    detail = f"{target} ({change.get('from')} -> {change.get('to')})"
  elif op == 'add_column':
    detail = f"{target}{' (required)' if change.get('required') else ''}"
  elif op == 'set_nullable':
    detail = f"{target} ({'nullable' if change.get('nullable') else 'not null'})"
  elif op == 'retire_column':
    detail = f'{target} (kept)'
  elif op == 'drop_column':
    detail = f'{target} (destructive)'
  elif op == 'create_index':
    detail = f"{change.get('index')}{' (unique)' if change.get('unique') else ''}"
  elif op == 'rename_index':
    detail = f"{change.get('old')} -> {change.get('index')}"
  elif op == 'drop_index':
    detail = str(change.get('index') or '')
  else:
    detail = target

  return f'  {op:<15} {detail}'.rstrip()


def _format_plan(plan, database: str | None = None) -> str:
  """Render a ``SchemaPlan`` as text for the CLI."""

  title = f'Schema plan for {database or "(database)"}'
  title += ' (dry run)' if plan.mode == 'plan' else ' (applied)'
  lines = [title]

  if plan.allow_drop:
    lines.append(
      '  allow-drop is ON for the whole database: retired columns may be dropped.'
    )

  if plan.changes:
    lines.extend(_describe_change(change) for change in plan.changes)
  else:
    lines.append('  no changes')

  if plan.blocked:
    lines.append(f'Blocked ({len(plan.blocked)}):')
    for item in plan.blocked:
      lines.append(f'{_describe_change(item)}: {item.get("reason", "")}')

  for warning in plan.warnings:
    lines.append(f'Warning: {warning}')

  if plan.destructive:
    lines.append('This plan drops columns; the data cannot be recovered.')
  return '\n'.join(lines)


def cmd_update(args) -> int:
  manager = _manager(args)
  name = _database(args)
  registry = manager.registry(name)
  allow_drop = bool(getattr(args, 'allow_drop', False))

  if getattr(args, 'dry_run', False):
    try:
      plan = registry.preview(args.module, allow_drop=allow_drop)
    except ValueError as exc:
      print(str(exc), file=sys.stderr)
      return 1
    print(_format_plan(plan, name))
    return 1 if plan.blocked else 0

  try:
    synced = registry.update(
      args.module, force=not args.no_force, allow_drop=allow_drop
    )
  except SchemaBlocked as exc:
    print(_format_plan(exc.plan, name), file=sys.stderr)
    print(
      'The safe changes were applied; blocked changes were skipped. '
      'Resolve them and run update again.',
      file=sys.stderr,
    )
    return 1

  print(f'Synchronized: {", ".join(synced) if synced else "(nothing changed)"}')
  plan = registry.last_schema_plan
  if plan is not None and (plan.changes or plan.blocked or plan.warnings):
    print(_format_plan(plan, name))
  if allow_drop:
    print('Retired columns were dropped where possible (database-wide).')
  return 0


def cmd_doctor(args) -> int:
  manager = _manager(args)
  name = _database(args)
  registry = manager.registry(name)
  try:
    retired = registry.retired_fields()
  except RuntimeError as exc:
    print(f'Cannot inspect retired columns: {exc}', file=sys.stderr)
    return 1

  statements = [
    f'ALTER TABLE {quote_table(row["table_name"])} '
    f'DROP COLUMN {quote_ident(row["column_name"])};'
    for row in retired
  ]

  if args.sql:
    if not statements:
      print('-- No retired columns.')
    for statement in statements:
      print(statement)
    return 0

  if not retired:
    print(f'{name}: no retired columns.')
    return 0

  print(
    f'{name}: {len(retired)} retired column(s) kept in the database '
    f'(an update --allow-drop removes them):'
  )
  for row in retired:
    print(
      f'  {row["table_name"]}.{row["column_name"]}  '
      f'(field {row["model"]}.{row["field_name"]}, {row["ttype"]})'
    )
  print('SQL:')
  for statement in statements:
    print(f'  {statement}')
  return 0


def cmd_uninstall(args) -> int:
  manager = _manager(args)
  registry = manager.registry(_database(args))
  registry.uninstall(args.module)
  print(f'Uninstalled: {args.module}')
  return 0


def cmd_init(args) -> int:
  manager = _manager(args)
  registry = manager.registry(_database(args))
  registry.load()
  discovered = registry.module_manager.discover()
  for name in discovered:
    registry.install(name)
  print(f'Initialized {registry.db.name} with modules: {", ".join(registry.list_modules())}')
  return 0


def cmd_modules(args) -> int:
  manager = _manager(args)
  registry = manager.registry(_database(args)).load()
  for name in registry.list_modules():
    info = registry.modules[name]
    print(f'{name:<14} {info.version:<10} models={len(info.models)}')
  return 0


def cmd_build(args) -> int:
  manager = _manager(args)
  name = _database(args)
  registry = manager.registry(name)
  registry.rebuild(force=args.force)

  print(f'Built {len(registry.models)} model(s) for {name}:')
  for model_name in sorted(registry.models):
    detail = registry.describe(model_name) or {}
    sources = ', '.join(detail.get('sources', []))
    print(f'  {model_name:<20} <- {sources}')

  if registry.build_result is not None:
    changed = sorted(registry.build_result.changed)
    if changed:
      print(f'Rebuilt: {", ".join(changed)}')
    else:
      print('No model source changed.')
  return 0


def cmd_describe(args) -> int:
  manager = _manager(args)
  registry = manager.registry(_database(args)).load()
  detail = registry.describe(args.model)
  if detail is None:
    print(f"Model '{args.model}' is not built in this database.")
    return 1
  print(json.dumps(detail, indent=2, default=str))
  return 0


def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(prog='jerp', description='J-ERP manager')
  parser.add_argument('--config', help='Path to jerp.config.json')
  parser.add_argument('--database', help='Target database name')

  sub = parser.add_subparsers(dest='command', required=True)

  p = sub.add_parser('create', help='Create the database if missing')
  p.set_defaults(func=cmd_create)

  p = sub.add_parser('drop', help='Drop the database')
  p.set_defaults(func=cmd_drop)

  p = sub.add_parser('databases', help='List databases')
  p.set_defaults(func=cmd_databases)

  p = sub.add_parser('install', help='Install one or more modules')
  p.add_argument('modules', nargs='+')
  p.add_argument('--force', action='store_true')
  p.set_defaults(func=cmd_install)

  p = sub.add_parser('update', help='Synchronize installed modules')
  p.add_argument('module', nargs='?', default=None)
  p.add_argument('--no-force', action='store_true')
  p.add_argument(
    '--dry-run',
    action='store_true',
    help='Print the plan without changing the database',
  )
  p.add_argument(
    '--allow-drop',
    action='store_true',
    help='Drop retired columns across the whole database (destructive)',
  )
  p.set_defaults(func=cmd_update)

  p = sub.add_parser('doctor', help='List retired columns kept in the database')
  p.add_argument('--sql', action='store_true', help='Print only the DROP COLUMN SQL')
  p.set_defaults(func=cmd_doctor)

  p = sub.add_parser('uninstall', help='Uninstall a module')
  p.add_argument('module')
  p.set_defaults(func=cmd_uninstall)

  p = sub.add_parser('init', help='Create/refresh every discovered module')
  p.set_defaults(func=cmd_init)

  p = sub.add_parser('modules', help='List installed modules')
  p.set_defaults(func=cmd_modules)

  p = sub.add_parser('build', help='Rebuild and synchronize the database models')
  p.add_argument('--force', action='store_true', help='Synchronize every model')
  p.set_defaults(func=cmd_build)

  p = sub.add_parser('describe', help='Show how a built model was composed')
  p.add_argument('model')
  p.set_defaults(func=cmd_describe)

  return parser


def main(argv=None) -> int:
  parser = build_parser()
  args = parser.parse_args(argv)
  try:
    return args.func(args)
  finally:
    for manager in _MANAGERS:
      manager.close_all()
    _MANAGERS.clear()


if __name__ == '__main__':
  sys.exit(main())
