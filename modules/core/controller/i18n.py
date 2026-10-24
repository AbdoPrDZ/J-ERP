"""UI language endpoints.

``GET /api/i18n`` returns the active catalog and available languages.
``POST /api/lang`` stores the selected language for the current user and sets
the ``jerp_lang`` session cookie.
"""

from __future__ import annotations

from urllib.parse import quote

from jerp import i18n
from jerp.env import Environment
from jerp.http import controller, request, response, router


class I18nController(controller.Controller):

  @router.get('/i18n')
  def index(self):
    result = response.json(i18n.payload())
    result.headers['Cache-Control'] = 'no-store'
    return result

  @router.post('/lang')
  def set_language(self):
    req = request.current()
    payload = req.json() if req else {}
    code = str(payload.get('code') or '').strip()

    environment = Environment.instance
    if not environment.active_database:
      return response.json(
        {'error': 'no_database', 'message': 'No database is selected.'},
        status=400,
      )

    language = i18n.find_language(code)
    if language is None:
      return response.json(
        {'error': 'unknown_language', 'message': f'Unknown language "{code}".'},
        status=400,
      )

    username = req.cookies.get('jerp_user') if req else None
    saved = i18n.save_user_language(username, language.code) if username else False

    result = response.json({
      'lang': language.code,
      'dir': i18n.language_direction(language.code),
      'saved': saved,
    })
    result.headers['Set-Cookie'] = (
      f'jerp_lang={quote(language.code, safe="")}; Path=/; SameSite=Lax'
    )
    result.headers['Cache-Control'] = 'no-store'
    return result
