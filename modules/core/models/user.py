from jerp import fields, models, security, sessions
from jerp.api import api_expose

HASH_PREFIX = 'pbkdf2_sha256$'


class User(models.Model):
  _name = 'sys.user'
  _description = 'Workspace user accounts and their preferences.'

  #: ``name`` is the display name; ``username`` is used to log in.
  name = fields.StringField(
    name='Name',
    required=True,
    help='Display name shown in the application.',
  )
  username = fields.StringField(
    name='Username',
    unique=True,
    help='Login name. Must be unique.',
  )
  password = fields.PasswordField(
    name='Password',
    required=True,
    hide=True,
    help='Stored as a PBKDF2 hash and never returned by the API.',
  )
  image = fields.ImageField(
    name='Avatar',
    help='Profile image for this user.',
  )
  lang_id = fields.Many2oneField(
    'sys.lang',
    name='Language',
    help='Preferred UI language. Empty uses the session or system default.',
  )
  is_admin = fields.BooleanField(
    name='Administrator',
    required=True,
    default=True,
    help=(
      'Administrators manage modules, users and technical settings. The '
      'default keeps existing accounts privileged when the column is added to '
      'an older database; new accounts are created without it.'
    ),
  )

  @staticmethod
  def _hash(value):
    """Hash a raw password; leave an existing hash untouched."""

    if value and not str(value).startswith(HASH_PREFIX):
      return security.hash_password(str(value))
    return value

  @classmethod
  def _visible_domain(cls, domain=None):
    """Restrict reads to the logged-in account for non-administrators."""

    if not sessions.is_bound() or sessions.is_admin():
      return domain
    user = sessions.current()
    if user is None:
      return domain
    return [('id', '=', int(user.id))] + list(domain or [])

  @classmethod
  @api_expose
  def all(cls, domain=None, fields=None, order=None, limit=None, offset=None):
    return super().all(
      domain=cls._visible_domain(domain),
      fields=fields,
      order=order,
      limit=limit,
      offset=offset,
    )

  @classmethod
  @api_expose
  def count(cls, domain=None):
    return super().count(domain=cls._visible_domain(domain))

  @classmethod
  @api_expose
  def find(cls, id, fields=None):
    records = cls.search(cls._visible_domain([('id', '=', id)]), limit=1)
    return cls._as_dict(records[0], fields) if records else None

  @classmethod
  def _check_create(cls):
    """Only administrators create accounts (the first account bootstraps)."""

    from jerp import sessions

    if not sessions.is_bound() or sessions.is_admin():
      return
    if cls.count():
      raise PermissionError('Administrator access is required to create users.')

  def _check_write(self, values):
    """Non-administrators may only edit their own non-privileged fields."""

    from jerp import sessions

    if not sessions.is_bound() or sessions.is_admin():
      return

    user = sessions.current()
    if user is None:
      raise sessions.AuthRequired('Authentication is required.')
    if int(self.id) != int(user.id):
      raise PermissionError('You can only modify your own account.')
    if 'is_admin' in values:
      raise PermissionError(
        'Only administrators can change administrator access.'
      )

  @classmethod
  def create(cls, values=None, **kwargs):
    payload = dict(values or {})
    payload.update(kwargs)
    payload.setdefault('is_admin', False)
    if 'password' in payload:
      payload['password'] = cls._hash(payload['password'])
    cls._check_create()
    return super().create(**payload)

  def write(self, values) -> bool:
    values = dict(values)
    self._check_write(values)
    if 'password' in values:
      values['password'] = type(self)._hash(values['password'])
    return super().write(values)

  def unlink(self) -> bool:
    from jerp import sessions

    if sessions.is_bound() and not sessions.is_admin():
      raise PermissionError('Administrator access is required to delete users.')
    return super().unlink()

  def set_password(self, raw: str) -> None:
    self.password = security.hash_password(raw)

  def check_password(self, raw: str) -> bool:
    return security.verify_password(raw, self.password or '')
