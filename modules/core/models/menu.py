from jerp import fields, models


class SysMenu(models.Model):
  """Navigation entries synchronized from the installed modules."""

  _name = 'sys.menu'
  _label = 'label'
  _track_refs = False

  code = fields.StringField(
    name='Code',
    required=True,
    unique=True,
    index=True,
    help='Stable declaration path, for example core.2.1.',
  )
  module = fields.StringField(
    name='Module',
    required=True,
    index=True,
    help='Module that owns this menu entry.',
  )
  parent_id = fields.Many2oneField(
    'sys.menu',
    name='Parent',
    index=True,
    help='Parent group, if this entry is nested.',
  )
  label = fields.StringField(
    name='Label',
    required=True,
    help='Text shown in the navigation.',
  )
  view = fields.StringField(
    name='View',
    help='View key rendered by this entry.',
  )
  href = fields.StringField(
    name='Link',
    help='Resolved URL of the entry.',
  )
  sequence = fields.IntegerField(
    name='Sequence',
    default=0,
    help='Sort order among sibling entries.',
  )
  auth = fields.BooleanField(
    name='Requires Login',
    default=True,
    help='Whether the entry is only shown to logged-in users.',
  )
  description = fields.TextField(
    name='Description',
    help='Short description of the destination.',
  )
  img = fields.StringField(
    name='Image',
    help='Optional icon URL.',
  )
