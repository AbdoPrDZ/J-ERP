"""Command line interface for J-ERP database and module management.

Examples::

  python -m jerp.cli create --database jerp
  python -m jerp.cli init   --database jerp
  python -m jerp.cli install stock --database jerp
  python -m jerp.cli update --database jerp
  python -m jerp.cli modules --database jerp
"""

from __future__ import annotations

import argparse
import json
import sys

from jerp.config import Config
from jerp.db import DatabaseManager


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


def cmd_update(args) -> int:
  manager = _manager(args)
  registry = manager.registry(_database(args))
  synced = registry.update(args.module, force=not args.no_force)
  print(f'Synchronized: {", ".join(synced) if synced else "(nothing changed)"}')
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
  p.set_defaults(func=cmd_update)

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
