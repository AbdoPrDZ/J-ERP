from jerp import i18n, security, sessions
from jerp.env import Environment
from jerp.http import controller, request, response, router


class AuthController(controller.Controller):

  @router.post('/login', auth=False)
  def login(self):
    """Verify credentials against the selected database's users."""

    req = request.current()
    payload = req.json() if req else {}
    username = str(payload.get('username') or '').strip()
    password = str(payload.get('password') or '')
    attempt = username.lower()

    if attempt and security.login_blocked(attempt):
      return response.json(
        {
          'error': 'too_many_attempts',
          'message': i18n._t(
            'error.too_many_attempts',
            'Too many failed attempts. Try again later.',
          ),
        },
        status=429,
      )

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
      if attempt:
        security.record_login_failure(attempt)
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

    security.clear_login_failures(attempt)
    user = users[0]
    lang_id = user.read(['lang_id']).get('lang_id')
    language = None
    Language = registry.get('sys.lang')
    if lang_id and Language is not None:
      rows = Language.browse(lang_id)
      if rows and rows[0].active:
        language = rows[0].code

    if not language:
      cookie = req.cookies.get('jerp_lang') if req else None
      if cookie and i18n.find_language(cookie):
        language = cookie
        if not lang_id:
          i18n.save_user_language(user.username, cookie)
    if not language:
      language = i18n.current_language()

    token = sessions.create(
      user, user_agent=req.headers.get('user-agent') if req else None
    )

    result = response.json({
      'user': user.name or user.username,
      'lang': language,
    })
    result.headers['Set-Cookie'] = sessions.cookie_header(
      token, secure=sessions.request_is_secure(req)
    )
    result.headers['Cache-Control'] = 'no-store'
    return result

  @router.post('/logout', auth=False)
  def logout(self):
    req = request.current()
    token = req.cookies.get(sessions.COOKIE) if req else None
    try:
      sessions.revoke(token)
    except Exception:
      # A missing database or session table must not make logout fail.
      pass

    result = response.json({'ok': True})
    result.headers['Set-Cookie'] = sessions.clear_cookie_header()
    result.headers['Cache-Control'] = 'no-store'
    return result
