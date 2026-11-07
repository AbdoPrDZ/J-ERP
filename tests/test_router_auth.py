"""Router-level authentication enforcement (no database required)."""

from __future__ import annotations

import inspect
import json
import unittest

from jerp.http import router as decorators
from jerp.http.request import Request
from jerp.http.router import Router


def request(path: str, *, accept: str = 'application/json') -> Request:
  return Request(method='GET', path=path, headers={'accept': accept})


class RouterAuthTests(unittest.TestCase):
  def setUp(self) -> None:
    self.router = Router()
    self.router.add_route('GET', '/open', lambda: {'ok': True}, auth=False)
    self.router.add_route('GET', '/closed', lambda: {'ok': True}, auth=True)

  def test_public_route_reaches_the_handler(self) -> None:
    self.assertEqual(
      self.router.dispatch('GET', '/open', request('/open')), {'ok': True}
    )

  def test_protected_api_route_returns_401(self) -> None:
    result = self.router.dispatch('GET', '/closed', request('/closed'))
    self.assertEqual(result.status, 401)
    payload = json.loads(result.body)
    self.assertEqual(payload['error'], 'auth_required')

  def test_protected_html_route_redirects_to_login(self) -> None:
    result = self.router.dispatch(
      'GET', '/closed', request('/closed', accept='text/html')
    )
    self.assertEqual(result.status, 302)
    self.assertEqual(result.headers['Location'], '/login')

  def test_routes_are_protected_by_default(self) -> None:
    self.assertIs(
      inspect.signature(decorators.route).parameters['auth'].default, True
    )
    self.assertIs(
      inspect.signature(decorators.get).parameters['auth'].default, True
    )
    self.assertIs(
      inspect.signature(decorators.post).parameters['auth'].default, True
    )


if __name__ == '__main__':
  unittest.main()
