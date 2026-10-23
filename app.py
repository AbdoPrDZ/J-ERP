"""J-ERP application entrypoint.

Serves the built UI (``data/ui``) and the ``/api`` router.

No database is assumed: nothing is created at startup. If no database is
selected, use the UI (``/`` → Databases) to create or choose one.

Usage::

  python app.py                    # http://127.0.0.1:1347 (from config)
  python app.py --port 9000        # override app.port
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from jerp.config import Config
from jerp.db import DatabaseManager
from jerp.env import Environment
from jerp.http.controllers import load_controllers
from jerp.server import serve


def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(prog='jerp', description='Serve the J-ERP app')
  parser.add_argument('--host', default=None, help='Override app.host from config')
  parser.add_argument('--port', type=int, default=None, help='Override app.port from config')
  parser.add_argument('--config', help='Path to jerp.config.json')
  parser.add_argument('--static', default='data/ui', help='Built UI directory')
  parser.add_argument('--api-prefix', default='/api')
  parser.add_argument('-v', '--verbose', action='store_true')
  return parser


def main(argv=None) -> int:
  args = build_parser().parse_args(argv)

  logging.basicConfig(
    level=logging.DEBUG if args.verbose else logging.INFO,
    format='%(levelname)s %(name)s: %(message)s',
  )

  config = Config.load(args.config)
  host = args.host or config.app_host
  port = args.port if args.port is not None else config.app_port

  environment = Environment.init_instance(DatabaseManager(config))

  # Import module controllers and bind their routes.
  load_controllers(config.modules_path, environment)

  # Bind declared `path -> view` routes (no controller needed).
  from jerp.routes import register_view_routes

  register_view_routes(environment, config.modules_path)

  static_dir = Path(args.static)
  if not static_dir.is_dir():
    print(f'WARNING: UI build not found at "{static_dir}". Run "npm run build".')

  serve(
    environment,
    host=host,
    port=port,
    static_dir=static_dir,
    modules_dir=config.modules_path,
    views_dir=config.views_dir,
    api_prefix=args.api_prefix,
  )
  return 0


if __name__ == '__main__':
  sys.exit(main())
