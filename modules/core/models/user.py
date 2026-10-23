from jerp import fields, models, security

HASH_PREFIX = 'pbkdf2_sha256$'


class User(models.Model):
  _name = 'sys.user'

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

  @staticmethod
  def _hash(value):
    """Hash a raw password; leave an existing hash untouched."""

    if value and not str(value).startswith(HASH_PREFIX):
      return security.hash_password(str(value))
    return value

  @classmethod
  def create(cls, **values):
    if 'password' in values:
      values['password'] = cls._hash(values['password'])
    return super().create(**values)

  def write(self, values) -> bool:
    values = dict(values)
    if 'password' in values:
      values['password'] = type(self)._hash(values['password'])
    return super().write(values)

  def set_password(self, raw: str) -> None:
    self.password = security.hash_password(raw)

  def check_password(self, raw: str) -> bool:
    return security.verify_password(raw, self.password or '')
