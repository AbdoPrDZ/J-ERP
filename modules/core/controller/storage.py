"""Serve stored files.

A file is only served if it is registered in the active database's ``sys_file``
table (matched by ``path``); otherwise 404. This prevents serving arbitrary
files that just happen to be on disk.
"""

from __future__ import annotations

from pathlib import Path

from jerp.env import Environment
from jerp.http import controller, response, router
from jerp.http.response import Response


class StorageController(controller.Controller):

  @router.route('/__storage/<name>')
  def get(self, name):
    if not Environment.instance.active_database:
      return response.not_found('Not Found')

    registry = Environment.instance.registry()
    registry.ensure_loaded()
    File = registry.get('sys.file')
    if File is None:
      return response.not_found('Not Found')

    records = File.search([('path', '=', name)], limit=1)
    if not records:
      return response.not_found('Not Found')

    config = Environment.instance.databases.config
    file = Path(config.uploads_dir) / 'files' / name
    if not file.is_file():
      return response.not_found('Not Found')

    record = records[0]
    return Response(
      file.read_bytes(),
      status=200,
      headers={
        'Content-Type': record.mimetype or 'application/octet-stream',
        'Cache-Control': 'no-cache',
      },
    )
