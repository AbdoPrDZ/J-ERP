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
        {'error': 'invalid_credentials', 'message': 'Invalid username or password.'},
        status=401,
      )

    user = users[0]
    result = response.json({'user': user.name or user.username})
    result.headers['Set-Cookie'] = (
      f'jerp_user={user.username}; Path=/; SameSite=Lax'
    )
    return result

  @router.post('/logout')
  def logout(self):
    result = response.json({'ok': True})
    result.headers['Set-Cookie'] = 'jerp_user=; Path=/; Max-Age=0; SameSite=Lax'
    return result
