"""Password hashing utilities (PBKDF2-SHA256, standard library only)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import threading
import time

ALGORITHM = 'pbkdf2_sha256'
ITERATIONS = 260_000

#: Failed logins allowed per account inside :data:`LOGIN_WINDOW` seconds.
LOGIN_MAX_FAILURES = 5
LOGIN_WINDOW = 300.0

_failures: dict[str, list[float]] = {}
_failures_lock = threading.Lock()


def hash_password(password: str, *, iterations: int = ITERATIONS) -> str:
  salt = os.urandom(16)
  digest = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, iterations)
  return '$'.join([
    ALGORITHM,
    str(iterations),
    base64.b64encode(salt).decode('ascii'),
    base64.b64encode(digest).decode('ascii'),
  ])


def verify_password(password: str, stored: str | None) -> bool:
  if not stored:
    return False
  try:
    algorithm, iterations, salt_b64, digest_b64 = stored.split('$')
    if algorithm != ALGORITHM:
      return False
    salt = base64.b64decode(salt_b64)
    expected = base64.b64decode(digest_b64)
    digest = hashlib.pbkdf2_hmac(
      'sha256', password.encode('utf-8'), salt, int(iterations)
    )
  except (ValueError, TypeError):
    return False
  return hmac.compare_digest(digest, expected)


def verify_secret(supplied: str | None, expected: str | None) -> bool:
  """Constant-time comparison for manager secrets (e.g. the master key)."""

  if not expected:
    return False
  return hmac.compare_digest(str(supplied or ''), str(expected))


def _recent_failures(key: str, now: float) -> list[float]:
  return [
    stamp for stamp in _failures.get(key, []) if now - stamp < LOGIN_WINDOW
  ]


def login_blocked(key: str) -> bool:
  """Whether ``key`` failed too often inside the current window."""

  now = time.monotonic()
  with _failures_lock:
    recent = _recent_failures(key, now)
    if recent:
      _failures[key] = recent
    else:
      _failures.pop(key, None)
    return len(recent) >= LOGIN_MAX_FAILURES


def record_login_failure(key: str) -> None:
  now = time.monotonic()
  with _failures_lock:
    recent = _recent_failures(key, now) + [now]
    _failures[key] = recent
    # Keep the table bounded even under a username-spraying attack.
    if len(_failures) > 10_000:
      for stale in [
        name for name, stamps in _failures.items() if not _recent_failures(name, now)
      ]:
        _failures.pop(stale, None)


def clear_login_failures(key: str) -> None:
  with _failures_lock:
    _failures.pop(key, None)


def reset_login_failures() -> None:
  """Clear the in-memory failure table (tests)."""

  with _failures_lock:
    _failures.clear()
