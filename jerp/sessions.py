"""Server-side login sessions.

The browser only holds an opaque random token in the ``jerp_session`` cookie
(``HttpOnly`` and ``SameSite=Lax``). The database stores its SHA-256 digest in
``sys.session`` together with the user and an expiry, so a request is
authenticated only after the server validates that row. Never trust a
client-supplied username.

A session is resolved once per request by :func:`bind`; :func:`current` then
returns the user record, and :func:`require_admin` guards privileged actions.
Outside a web request (CLI, seeds, Python callers) there is no session, and the
guards are no-ops so trusted code keeps working.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone

logger = logging.getLogger('jerp.sessions')

#: Cookie that carries the opaque session token.
COOKIE = 'jerp_session'

#: Lifetime of a session created by a successful login.
DEFAULT_DAYS = 7

#: ``Secure`` is added when the request reached us over HTTPS.
_FORWARDED_PROTO = 'x-forwarded-proto'


class AuthRequired(PermissionError):
  """Raised when a web request has no valid session."""


class AdminRequired(PermissionError):
  """Raised when a web request is authenticated but not administrative."""


_user: ContextVar = ContextVar('jerp_session_user', default=None)
_bound: ContextVar = ContextVar('jerp_session_bound', default=False)


# --- tokens ---------------------------------------------------------------


def new_token() -> str:
  return secrets.token_urlsafe(32)


def hash_token(token: str | None) -> str:
  return hashlib.sha256(str(token or '').encode('utf-8')).hexdigest()


def is_expired(value: datetime | None, now: datetime | None = None) -> bool:
  if value is None:
    return True
  if value.tzinfo is None:
    value = value.replace(tzinfo=timezone.utc)
  return value <= (now or datetime.now(timezone.utc))


# --- cookies --------------------------------------------------------------


def cookie_header(token: str, *, secure: bool = False) -> str:
  parts = [
    f'{COOKIE}={token}',
    'Path=/',
    'HttpOnly',
    'SameSite=Lax',
    f'Max-Age={DEFAULT_DAYS * 24 * 60 * 60}',
  ]
  if secure:
    parts.append('Secure')
  return '; '.join(parts)


def clear_cookie_header() -> str:
  return f'{COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0'


def request_is_secure(request) -> bool:
  """Whether the client reached us over HTTPS (behind a reverse proxy too)."""

  if request is None:
    return False
  return request.headers.get(_FORWARDED_PROTO, '').lower() == 'https'


# --- database -------------------------------------------------------------


def _registry():
  from jerp.env import Environment

  return Environment.instance.registry()


def _session_model():
  registry = _registry()
  registry.ensure_loaded()
  return registry.get('sys.session')


def create(user, *, user_agent: str | None = None, days: int = DEFAULT_DAYS) -> str:
  """Create a session for ``user`` and return the raw cookie token."""

  Session = _session_model()
  if Session is None:
    raise RuntimeError('The sys.session model is not installed.')

  prune()

  token = new_token()
  Session.create({
    'token_hash': hash_token(token),
    'user_id': int(user.id),
    'user_agent': (user_agent or '')[:255],
    'expires_at': datetime.now(timezone.utc) + timedelta(days=days),
  })
  return token


def resolve(token: str | None):
  """Return the user for a valid token, deleting an expired session."""

  if not token:
    return None

  Session = _session_model()
  if Session is None:
    return None

  sessions = Session.search([('token_hash', '=', hash_token(token))], limit=1)
  if not sessions:
    return None

  session = sessions[0]
  if is_expired(session.expires_at):
    session.unlink()
    return None

  User = _registry().get('sys.user')
  if User is None:
    return None
  users = User.browse(int(session.user_id))
  return users[0] if users else None


def revoke(token: str | None) -> None:
  if not token:
    return
  Session = _session_model()
  if Session is None:
    return
  sessions = Session.search([('token_hash', '=', hash_token(token))])
  ids = [session.id for session in sessions]
  if ids:
    Session.delete_many(ids)


def prune() -> int:
  """Delete expired sessions (best effort)."""

  Session = _session_model()
  if Session is None:
    return 0
  try:
    expired = Session.search([
      ('expires_at', '<', datetime.now(timezone.utc)),
    ])
    ids = [session.id for session in expired]
    if ids:
      Session.delete_many(ids)
    return len(ids)
  except Exception:
    logger.exception('Could not prune expired sessions')
    return 0


# --- request scope --------------------------------------------------------


@contextmanager
def bind(request=None):
  """Resolve the session cookie for the current request.

  Runs after the database middleware, so the active database is known. Any
  failure to resolve (missing table during an upgrade, bad token) means "not
  logged in" rather than a 500.
  """

  token = None
  if request is not None:
    token = request.cookies.get(COOKIE)

  user = None
  try:
    user = resolve(token)
  except Exception:
    logger.exception('Could not resolve the session cookie')

  user_token = _user.set(user)
  bound_token = _bound.set(True)
  try:
    yield user
  finally:
    _user.reset(user_token)
    _bound.reset(bound_token)


def is_bound() -> bool:
  """Whether a web request scope is active (even if unauthenticated)."""

  return bool(_bound.get())


def current():
  """The authenticated user of the current request, if any."""

  return _user.get() if _bound.get() else None


def is_admin(user=None) -> bool:
  target = current() if user is None else user
  return bool(target is not None and getattr(target, 'is_admin', False))


def require_user():
  """Require an authenticated web user; no-op outside a request."""

  if not is_bound():
    return None
  user = current()
  if user is None:
    raise AuthRequired('Authentication is required.')
  return user


def require_admin():
  """Require an administrative web user; no-op outside a request."""

  if not is_bound():
    return None
  user = require_user()
  if not is_admin(user):
    raise AdminRequired('Administrator access is required.')
  return user
