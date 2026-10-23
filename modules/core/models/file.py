from jerp import fields, models


class File(models.Model):
  """Metadata for an uploaded/stored file."""

  _name = 'sys.file'

  name = fields.StringField(
    name='Name',
    required=True,
    help='Original name of the uploaded file.',
  )
  mimetype = fields.StringField(
    name='Mimetype',
    help='MIME type reported for this file.',
  )
  checksum = fields.StringField(
    name='Checksum',
    help='SHA-256 checksum of the stored file content.',
  )
  path = fields.StringField(
    name='Path',
    required=True,
    help='Generated storage token used to serve the file.',
  )
