"""Session tokens, expiry and login throttling (no database required)."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from jerp import security, sessions


class TokenTests(unittest.TestCase):
  def test_tokens_are_random_and_long_enough(self) -> None:
    first = sessions.new_token()
    second = sessions.new_token()
    self.assertNotEqual(first, second)
    self.assertGreaterEqual(len(first), 40)

  def test_hash_is_deterministic_and_hides_the_token(self) -> None:
    token = 'abc123'
    digest = sessions.hash_token(token)
    self.assertEqual(digest, sessions.hash_token(token))
    self.assertNotIn(token, digest)
    self.assertEqual(len(digest), 64)

  def test_empty_token_hashes_without_error(self) -> None:
    self.assertEqual(len(sessions.hash_token(None)), 64)


class ExpiryTests(unittest.TestCase):
  def test_past_is_expired(self) -> None:
    self.assertTrue(
      sessions.is_expired(datetime.now(timezone.utc) - timedelta(seconds=1))
    )

  def test_future_is_not_expired(self) -> None:
    self.assertFalse(
      sessions.is_expired(datetime.now(timezone.utc) + timedelta(hours=1))
    )

  def test_missing_expiry_is_expired(self) -> None:
    self.assertTrue(sessions.is_expired(None))

  def test_naive_datetimes_are_read_as_utc(self) -> None:
    naive = datetime.now(timezone.utc).replace(tzinfo=None)
    self.assertTrue(sessions.is_expired(naive - timedelta(minutes=1)))
    self.assertFalse(sessions.is_expired(naive + timedelta(minutes=1)))


class CookieTests(unittest.TestCase):
  def test_session_cookie_is_http_only_and_lax(self) -> None:
    header = sessions.cookie_header('token')
    self.assertIn('jerp_session=token', header)
    self.assertIn('HttpOnly', header)
    self.assertIn('SameSite=Lax', header)
    self.assertIn('Path=/', header)
    self.assertNotIn('Secure', header)

  def test_secure_flag_for_https(self) -> None:
    self.assertIn('Secure', sessions.cookie_header('token', secure=True))

  def test_clear_cookie_expires_immediately(self) -> None:
    header = sessions.clear_cookie_header()
    self.assertIn('Max-Age=0', header)
    self.assertIn('HttpOnly', header)


class OutsideRequestTests(unittest.TestCase):
  def test_no_session_outside_a_request(self) -> None:
    self.assertIsNone(sessions.current())
    self.assertFalse(sessions.is_bound())
    self.assertIsNone(sessions.require_user())
    self.assertIsNone(sessions.require_admin())


class LoginThrottleTests(unittest.TestCase):
  def setUp(self) -> None:
    security.reset_login_failures()

  def tearDown(self) -> None:
    security.reset_login_failures()

  def test_failures_block_after_the_limit(self) -> None:
    key = 'admin'
    for _ in range(security.LOGIN_MAX_FAILURES - 1):
      security.record_login_failure(key)
    self.assertFalse(security.login_blocked(key))
    security.record_login_failure(key)
    self.assertTrue(security.login_blocked(key))

  def test_success_clears_the_counter(self) -> None:
    for _ in range(security.LOGIN_MAX_FAILURES):
      security.record_login_failure('admin')
    self.assertTrue(security.login_blocked('admin'))
    security.clear_login_failures('admin')
    self.assertFalse(security.login_blocked('admin'))

  def test_keys_are_independent(self) -> None:
    for _ in range(security.LOGIN_MAX_FAILURES):
      security.record_login_failure('alice')
    self.assertTrue(security.login_blocked('alice'))
    self.assertFalse(security.login_blocked('bob'))


if __name__ == '__main__':
  unittest.main()
