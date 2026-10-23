from jerp import fields, models


class TempModel(models.Model):
  """Temporary records used by form-embedded tables before the parent exists.

  ``data`` is a JSON object with the target model's field values. ``token``
  groups every temporary record belonging to one unsaved parent form.
  """

  _name = 'temp.model'
  _label = 'model'
  _temporary = True
  _track_refs = False

  token = fields.StringField(
    name='Token',
    required=True,
    help='Random identifier grouping temporary records of one form.',
  )
  model = fields.StringField(
    name='Model',
    required=True,
    help='Target model that will receive these records on commit.',
  )
  data = fields.TextField(
    name='Data',
    required=True,
    help='JSON object containing the temporary record field values.',
  )
