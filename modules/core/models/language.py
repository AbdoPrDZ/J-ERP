from jerp import fields, models


class Language(models.Model):
  """Available UI/content languages."""

  _name = 'sys.lang'
  _description = 'Available UI and content languages.'
  _label = 'name'

  def write(self, values) -> bool:
    """Reload a language's module strings when it becomes active."""

    was_active = bool(self.active)
    result = super().write(values)
    activating = bool(values.get('active')) and not was_active
    if result and activating and self.code:
      self._load_translations()
    return result

  def _load_translations(self) -> None:
    from pathlib import Path

    from jerp.env import Environment
    from jerp.i18n import I18nLoader, module_language_files

    try:
      registry = Environment.instance.registry()
      registry.ensure_loaded()
    except Exception:
      return

    loader = I18nLoader(registry.db, Path(registry.manager.config.modules_path))
    for module_name in registry.modules:
      files = module_language_files(
        Path(registry.manager.config.modules_path) / module_name
      )
      if self.code in files:
        loader.sync_module(module_name, language=self.code)

  name = fields.StringField(
    name='Name',
    required=True,
    help='Human-readable language name, for example English.',
  )
  code = fields.StringField(
    name='Code',
    size=10,
    required=True,
    unique=True,
    help='Language code, for example en, fr or ar.',
  )
  active = fields.BooleanField(
    name='Active',
    default=False,
    help='Inactive languages are hidden from translation pickers.',
  )
  is_default = fields.BooleanField(
    name='Default',
    help='Use this language as the default value of multi-language fields.',
  )
