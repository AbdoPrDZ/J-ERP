"""API exposure for model methods.

Decorate a model method with :func:`api_expose` to make it callable through the
model API endpoint (``POST /api/model/<model>/<func>``).

Works whether applied above or below ``@classmethod`` / ``@staticmethod``.
"""

from __future__ import annotations


def api_expose(func):
  target = getattr(func, '__func__', func)
  try:
    target._jerp_exposed = True
  except (AttributeError, TypeError):
    pass
  return func


def is_exposed(value) -> bool:
  if getattr(value, '_jerp_exposed', False):
    return True
  inner = getattr(value, '__func__', None)
  return bool(inner is not None and getattr(inner, '_jerp_exposed', False))
