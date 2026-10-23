"""File upload endpoints.

* ``POST /api/upload?name=<filename>`` (raw body = file bytes) -> stores in tmp,
  returns ``{token, name, mimetype, checksum, size}``.
* ``POST /api/upload/confirm`` (``{token, name?, mimetype?, checksum?}``) -> moves
  the file to ``files`` and creates a ``sys.file`` record.
"""

from __future__ import annotations

from jerp import uploads
from jerp.env import Environment
from jerp.http import controller, request, response, router


class UploadController(controller.Controller):

  @router.post('/upload')
  def upload(self):
    req = request.current()
    data = req.body if isinstance(req.body, (bytes, bytearray)) else b''
    if not data:
      return response.json(
        {'error': 'empty', 'message': 'No file data received.'}, status=400
      )

    name = str(
      (req.query.get('name') if req else None)
      or req.headers.get('x-filename')
      or 'file'
    )
    mimetype = req.headers.get('content-type')
    return response.json(uploads.save_temp(bytes(data), name, mimetype))

  @router.post('/upload/confirm')
  def confirm(self):
    payload = request.current().json() if request.current() else {}
    token = str(payload.get('token') or '')
    if not token:
      return response.json(
        {'error': 'token_required', 'message': 'A token is required.'}, status=400
      )

    try:
      uploads.confirm(token)
    except Exception as exc:
      return response.json(
        {'error': 'confirm_failed', 'message': str(exc)}, status=400
      )

    environment = Environment.instance
    if not environment.active_database:
      return response.json(
        {'error': 'no_database', 'message': 'No database is selected.'},
        status=400,
      )

    registry = environment.registry()
    registry.ensure_loaded()
    File = registry.get('sys.file')
    if File is None:
      return response.json(
        {'error': 'missing_model', 'message': 'The sys.file model is not installed.'},
        status=500,
      )

    record = File.create(
      name=str(payload.get('name') or token),
      mimetype=str(payload.get('mimetype') or uploads.guess_mimetype(token)),
      checksum=str(payload.get('checksum') or ''),
      path=token,
    )
    return response.json({
      'id': record.id,
      'name': record.name,
      'mimetype': record.mimetype,
      'path': token,
    })
