from jerp import i18n
from jerp.env import Environment
from jerp.http import controller, request, response, router


class AuthController(controller.Controller):

  @router.post('/login')
  def login(self):
    """Verify credentials against the selected database's users."""

    payload = request.current().json() if request.current() else {}
    username = str(payload.get('username') or '').strip()
    password = str(payload.get('password') or '')

    environment = Environment.instance
    if not environment.active_database:
      return response.json(
        {'error': 'no_database', 'message': 'No database is selected.'},
        status=400,
      )

    registry = environment.registry()
    registry.ensure_loaded()
    User = registry.get('sys.user')
    if User is None:
      return response.json(
        {'error': 'missing_model', 'message': 'The user model is not installed.'},
        status=500,
      )

    users = User.search([('username', '=', username)], limit=1) if username else []
    if not users or not users[0].check_password(password):
      return response.json(
        {
          'error': 'invalid_credentials',
          'message': i18n._t(
            'error.invalid_credentials',
            'Invalid username or password.',
          ),
        },
        status=401,
      )

    user = users[0]
    lang_id = user.read(['lang_id']).get('lang_id')
    language = None
    Language = registry.get('sys.lang')
    if lang_id and Language is not None:
      rows = Language.browse(lang_id)
      if rows and rows[0].active:
        language = rows[0].code

    if not language:
      req = request.current()
      cookie = req.cookies.get('jerp_lang') if req else None
      if cookie and i18n.find_language(cookie):
        language = cookie
        if not lang_id:
          i18n.save_user_language(user.username, cookie)
    if not language:
      language = i18n.current_language()

    result = response.json({
      'user': user.name or user.username,
      'lang': language,
    })
    result.headers['Set-Cookie'] = (
      f'jerp_user={user.username}; Path=/; SameSite=Lax'
    )
    result.headers['Cache-Control'] = 'no-store'
    return result

  @router.post('/logout')
  def logout(self):
    result = response.json({'ok': True})
    result.headers['Set-Cookie'] = 'jerp_user=; Path=/; Max-Age=0; SameSite=Lax'
    return result
