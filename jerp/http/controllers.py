"""Controller discovery.

Importing a module's ``controller`` package registers its routes as *unbound*
functions (the decorator runs at class-definition time). This loader then
instantiates each ``Controller`` subclass and re-registers its methods as bound
handlers, so ``def index(self)`` receives its instance when dispatched.
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path

from jerp.http.controller import Controller


def _subclasses(base) -> list[type]:
  found: list[type] = []
  for child in base.__subclasses__():
    found.append(child)
    found.extend(_subclasses(child))
  return found


def _register_bound(controller_cls, environment) -> int:
  try:
    instance = controller_cls()
  except Exception:
    instance = None

  count = 0
  for name in dir(controller_cls):
    try:
      attr = getattr(controller_cls, name)
    except Exception:
      continue
    routes = getattr(attr, '_jerp_routes', None)
    if not routes:
      continue
    handler = getattr(instance, name) if instance is not None else attr
    for method, endpoint, auth in routes:
      environment.router.add_route(method, endpoint, handler, auth=auth)
      count += 1
  return count


def load_controllers(modules_dir: str | Path, environment) -> list[str]:
  """Import every module's controllers and register bound handlers."""

  modules_dir = Path(modules_dir)
  package = modules_dir.name
  imported: list[str] = []

  if modules_dir.is_dir():
    for path in sorted(modules_dir.iterdir()):
      if not (path / 'configure.json').exists():
        continue
      controller_pkg = f'{package}.{path.name}.controller'
      try:
        package_module = importlib.import_module(controller_pkg)
      except ModuleNotFoundError:
        continue
      imported.append(controller_pkg)

      if hasattr(package_module, '__path__'):
        for info in pkgutil.iter_modules(package_module.__path__):
          importlib.import_module(f'{controller_pkg}.{info.name}')

  for controller_cls in _subclasses(Controller):
    _register_bound(controller_cls, environment)

  return imported
