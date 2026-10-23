from jerp import fields, models


class File(models.Model):
  """Metadata for an uploaded/stored file."""

  _name = 'file'
  _table = 'files'

  name = fields.StringField(name='Name', required=True)
  mimetype = fields.StringField(name='Mimetype')
  checksum = fields.StringField(name='Checksum')
  path = fields.StringField(name='Path', required=True)
