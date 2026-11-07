from jerp import fields, models


class Session(models.Model):
  """Server-side login sessions.

  The cookie only carries an opaque token; this table stores its SHA-256 digest
  so a stolen database dump cannot be replayed as a session cookie. Sessions are
  deleted on logout and pruned after ``expires_at``.
  """

  _name = 'sys.session'
  _description = 'Active login sessions and their expiry.'
  _track_refs = False

  token_hash = fields.StringField(
    name='Token',
    required=True,
    unique=True,
    index=True,
    hide=True,
    help='SHA-256 digest of the session cookie token.',
  )
  user_id = fields.BigIntField(
    name='User',
    required=True,
    index=True,
    help='Identifier of the user that owns the session.',
  )
  user_agent = fields.StringField(
    name='Client',
    help='User agent reported when the session was created.',
  )
  expires_at = fields.DateTimeField(
    name='Expires',
    required=True,
    use_tz=True,
    help='Moment after which the session is no longer valid.',
  )
