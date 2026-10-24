from jerp import fields, models


class TempModel(models.Model):
  """Temporary records used by form-embedded tables before the parent exists.

  ``data`` is a JSON object with the target model's field values. ``token``
  groups every temporary record belonging to one unsaved parent form.
  """

  _name = 'temp.model'
  _description = 'Server-side drafts for forms and tables.'
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
    help='Model of the record being temporarily stored.',
  )
  record_id = fields.BigIntField(
    name='Record ID',
    help='Existing record being edited, or empty for a new record.',
  )
  state = fields.SelectionField(
    [('create', 'Create'), ('update', 'Update'), ('delete', 'Delete')],
    name='State',
    help='Draft state: create, update or delete.',
    default='create',
  )
  data = fields.TextField(
    name='Data',
    required=True,
    help='JSON object containing the temporary record field values.',
  )
  dirty = fields.JsonField(
    name='Dirty',
    help='JSON object containing the fields changed from the original record.',
  )
  version = fields.IntegerField(
    name='Version',
    help='Incremented on every server-side draft change.',
  )
  base_stamp = fields.DateTimeField(
    name='Base Stamp',
    use_tz=True,
    help='Updated-at value of the real record when the draft was created.',
  )
