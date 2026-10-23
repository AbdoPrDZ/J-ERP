"""Request-scoped middleware helpers."""

from __future__ import annotations

from contextlib import contextmanager


@contextmanager
def database_scope(request=None):
  """Select the database for the duration of a request.

  The database name comes from the ``jerp_db`` cookie or the ``X-JERP-DB``
  header. When neither is present, or no environment is initialized, whatever
  database is currently active (if any) stays active.
  """

  from jerp.env import Environment

  try:
    environment = Environment.instance
  except RuntimeError:
    yield
    return

  name = request.database() if request is not None else None
  if name and name != environment.active_database:
    with environment.using(name):
      yield
  else:
    yield
