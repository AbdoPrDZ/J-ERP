"""Password hashing utilities (PBKDF2-SHA256, standard library only)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

ALGORITHM = 'pbkdf2_sha256'
ITERATIONS = 260_000


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
