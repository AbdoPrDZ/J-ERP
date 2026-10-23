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


def on_change(*fields):
  """Declare a method as an on-change handler for one or more fields.

  Usage::

      @on_change(['quantity', 'price_unit'])
      def _on_change_amount(self):
          ...

  The handler may be an instance method (``self`` is a pseudo-record whose
  assignments are collected as changed values) or a classmethod returning a
  values dictionary. The decorator can be applied above or below
  ``@classmethod``.
  """

  if len(fields) == 1 and isinstance(fields[0], (list, tuple, set)):
    fields = tuple(fields[0])
  selected = tuple(str(field) for field in fields)
  if not selected:
    raise ValueError('on_change requires at least one field name.')

  def decorator(func):
    target = getattr(func, '__func__', func)
    try:
      target._jerp_on_change_fields = selected
    except (AttributeError, TypeError):
      pass
    return func

  return decorator


def depends_on(*fields):
  """Declare the field dependencies of a computed field's method.

  Usage::

      @depends_on(['quantity', 'price_unit'])
      def _compute_subtotal(self):
          ...

      @depends_on('lines.subtotal')
      def _compute_amount_total(self):
          ...

  Both a single list/tuple and variadic arguments are accepted. Dotted paths
  describe fields reached through relational fields.
  """

  if len(fields) == 1 and isinstance(fields[0], (list, tuple, set)):
    fields = tuple(fields[0])
  selected = tuple(str(field) for field in fields)
  if not selected:
    raise ValueError('depends_on requires at least one field name.')

  def decorator(func):
    target = getattr(func, '__func__', func)
    try:
      target._jerp_depends = selected
    except (AttributeError, TypeError):
      pass
    return func

  return decorator
