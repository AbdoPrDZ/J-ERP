"""Translation file scaffolding and validation."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

from jerp.i18n import (
  KEY_PATTERN,
  LANG_SUFFIX,
  LangFormatError,
  module_language_files,
  parse_lang_file,
)
from jerp.menus import iter_menu_entries
from jerp.modules import ModuleManager

T_CALL = re.compile(r"\bt\(\s*(['\"])([^'\"]+)\1\s*[,)]", re.S)
LANG_PATTERN = re.compile(r'^[a-zA-Z]{2,8}(?:[_-][a-zA-Z0-9]+)?$')
SKIP_FIELDS = {'id', 'created_at', 'updated_at'}

#: Keys referenced through variables rather than a literal ``t('...')`` call.
CORE_EXTRA_KEYS = {
  'app.actions': 'Actions',
  'app.add': 'Add',
  'app.additional_fields': 'Additional fields',
  'app.cancel': 'Cancel',
  'app.create': 'Create',
  'app.delete': 'Delete',
  'app.deleting': 'Deleting…',
  'app.discard': 'Discard',
  'app.first_page': 'First page',
  'app.language': 'Language',
  'app.last_page': 'Last page',
  'app.loading': 'Loading',
  'app.loading_text': 'Loading…',
  'app.logout': 'Logout',
  'app.menu': 'Menu',
  'app.navigation': 'Navigation',
  'app.new': 'New',
  'app.next': 'Next',
  'app.next_page': 'Next page',
  'app.no_records': 'No records',
  'app.not_available': 'Not available',
  'app.page_of': 'Page {page} of {count}',
  'app.previous': 'Prev',
  'app.previous_page': 'Previous page',
  'app.profile': 'Profile',
  'app.rows_per_page': 'Rows per page',
  'app.rows_range': '{first}–{last} of {total}',
  'app.save': 'Save',
  'app.saving': 'Saving…',
  'app.search': 'Search…',
  'app.select_all': 'Select all rows on this page',
  'app.selected': '{count} selected',
  'app.view.list': 'List',
  'app.view.cards': 'Cards',
  'app.view.form': 'Form',
  'search.aria': 'Search menus and records',
  'search.change': 'Change',
  'search.matching': 'matching',
  'search.menus': 'Menus',
  'search.models': 'Models',
  'search.no_menus': 'No menus match.',
  'search.no_models': 'No models match.',
  'search.no_records': 'No records found.',
  'search.open': 'Open',
  'search.placeholder.all': 'Search menus or models…',
  'search.placeholder.menu': 'Search menus…',
  'search.placeholder.model': 'Search models…',
  'search.placeholder.record': 'Search {model} records…',
  'search.record_empty': 'Type a name to search records.',
  'search.record_hint': 'Matching records by name.',
  'search.record_type': 'Type a name to search {model} records.',
  'search.records': 'Records',
  'search.search': 'Search',
  'search.searching': 'Searching…',
  'search.select': 'Select',
}

CORE_EXTRA_KEYS.update({
  'app.draft_suffix': '(draft)',
  'app.drafts': 'Drafts',
  'app.form_table_missing_relation': (
    'No relation field to "{parent}" was found on {child}.'
  ),
  'app.form_table_requires_form': 'FormTable must be used inside a Form.',
  'app.group': 'Group',
  'app.hide': 'Hide',
  'app.image_field.uploading': 'Uploading…',
  'app.missing_view_component': 'No component registered for view type "{type}".',
  'app.missing_view_descriptor': 'Missing view descriptor.',
  'app.missing_widget': 'No widget registered for type "{type}".',
  'app.multi_lang_panel.close_button': 'Close',
  'app.multi_lang_panel.default': 'default',
  'app.multi_lang_panel.dialog_aria_label': '{title} translations',
  'app.multi_lang_panel.no_languages_message': 'No languages configured.',
  'app.multi_lang_panel.no_record_message': (
    'Save the record first to edit translations.'
  ),
  'app.multi_lang_panel.title': '{title} translations',
  'app.parent_model': 'the parent model',
  'app.private': 'private',
  'app.public': 'public',
  'app.refresh': 'Refresh',
  'app.show': 'Show',
  'app.uploading': 'Uploading…',
  'home.overview': 'Workspace overview',
  'home.subtitle': (
    'Everything important in one place — contacts, sales, stock and your '
    'workspace configuration.'
  ),
  'home.welcome': 'Welcome back',
  'home.stats.contacts.label': 'Contacts',
  'home.stats.contacts.description': 'People and organisations',
  'home.stats.orders.label': 'Sales orders',
  'home.stats.orders.description': 'Quotes and confirmations',
  'home.stats.products.label': 'Products',
  'home.stats.products.description': 'Items in the catalogue',
  'home.stats.users.label': 'Users',
  'home.stats.users.description': 'Workspace accounts',
  'plan.applying': 'Applying…',
  'plan.apply': 'Apply',
  'plan.blocked': 'Blocked ({count}) — these will be skipped:',
  'plan.confirm_destructive': (
    'I understand the columns listed above will be permanently deleted.'
  ),
  'plan.drop_retired': (
    'Drop retired columns for the whole database. Columns are currently kept; '
    'dropping them permanently deletes their data.'
  ),
  'plan.intro': (
    'Updating {label} synchronizes the database schema. Nothing is changed '
    'until you apply.'
  ),
  'plan.loading': 'Loading plan…',
  'plan.no_changes': 'No schema changes.',
  'plan.review': 'Review schema changes',
  'plan.the_module': 'the module',
  'plan.title': 'Schema plan',
  'validation.date': '{label} must be a valid date.',
  'validation.email': '{label} must be a valid email address.',
  'validation.integer': '{label} must be a whole number.',
  'validation.invalid_option': '{label} has an invalid option.',
  'validation.max_length': '{label} must be at most {size} characters.',
  'validation.number': '{label} must be a number.',
  'validation.required': '{label} is required.',
  'view.core.contacts.empty_message': 'No contacts found.',
  'view.core.contacts.form_title': 'Contact',
  'view.core.contacts.group_address': 'Address',
  'view.core.contacts.group_contact_info': 'Contact Info',
  'view.core.contacts.title': 'Contacts',
  'view.core.countries.empty_message': 'No countries found.',
  'view.core.countries.form_title': 'Country',
  'view.core.countries.title': 'Countries',
  'view.core.data.empty_message': 'No external identifiers found.',
  'view.core.data.form_title': 'External Identifier',
  'view.core.data.group_reference': 'Reference',
  'view.core.data.title': 'Data',
  'view.core.db_manager.active': 'Active',
  'view.core.db_manager.admin_password': 'Admin password',
  'view.core.db_manager.admin_password_required': 'An admin password is required.',
  'view.core.db_manager.admin_username': 'Admin username',
  'view.core.db_manager.attention': 'Attention needed',
  'view.core.db_manager.available': 'Available databases',
  'view.core.db_manager.available_hint': (
    'Select a card to continue, or remove a workspace you no longer need.'
  ),
  'view.core.db_manager.confirm_name_error': 'Type "{name}" to confirm deletion.',
  'view.core.db_manager.connected': 'Connected',
  'view.core.db_manager.create_database': 'Create database',
  'view.core.db_manager.create_subtitle': 'A new isolated workspace.',
  'view.core.db_manager.create_title': 'Create database',
  'view.core.db_manager.creating': 'Creating…',
  'view.core.db_manager.current_hint': 'Currently selected — click to sign in.',
  'view.core.db_manager.database_name': 'Database name',
  'view.core.db_manager.database_name_hint': (
    'Case and spaces are preserved. Up to 63 bytes.'
  ),
  'view.core.db_manager.database_name_required': 'A database name is required.',
  'view.core.db_manager.delete_active_warning': (
    'This is the active database. You will be returned to the database manager '
    'after it is deleted.'
  ),
  'view.core.db_manager.delete_body': (
    'This permanently deletes {name}, including every module, table and record '
    'in it.'
  ),
  'view.core.db_manager.delete_subtitle': 'This action cannot be undone.',
  'view.core.db_manager.delete_title': 'Delete database',
  'view.core.db_manager.deleting': 'Deleting…',
  'view.core.db_manager.description': (
    'Choose an isolated workspace to sign in, or create a new one. Modules, '
    'data and users are kept separate per database.'
  ),
  'view.core.db_manager.empty_hint': 'Create your first workspace to get started.',
  'view.core.db_manager.empty_title': 'No databases yet',
  'view.core.db_manager.loading': 'Loading databases…',
  'view.core.db_manager.master_key': 'Master key',
  'view.core.db_manager.master_key_hint': (
    'Required to create or delete databases.'
  ),
  'view.core.db_manager.master_key_required': 'The master key is required.',
  'view.core.db_manager.new_database': 'New database',
  'view.core.db_manager.none': 'None',
  'view.core.db_manager.open_database': 'Open database {name}',
  'view.core.db_manager.select_hint': (
    'Click to select this workspace and sign in.'
  ),
  'view.core.db_manager.stat_active': 'Active',
  'view.core.db_manager.stat_databases': 'Databases',
  'view.core.db_manager.stat_server': 'Server',
  'view.core.db_manager.title': 'Databases',
  'view.core.db_manager.total': '{count} total',
  'view.core.db_manager.type_to_confirm': 'Type {name} to confirm',
  'view.core.db_manager.workspace': 'Workspace',
  'view.core.fields.empty_message': 'No fields found.',
  'view.core.fields.form_title': 'Field',
  'view.core.fields.group_field': 'Field',
  'view.core.fields.title': 'Fields',
  'view.core.languages.empty_message': 'No languages found.',
  'view.core.languages.form_title': 'Language',
  'view.core.languages.title': 'Languages',
  'view.core.login.badge_fast': 'Fast',
  'view.core.login.badge_modular': 'Modular',
  'view.core.login.badge_secure': 'Secure',
  'view.core.login.contact_admin': (
    'Need access? Contact your workspace administrator.'
  ),
  'view.core.login.hero_eyebrow': 'Modular ERP platform',
  'view.core.login.hero_subtitle': (
    'Sales, inventory, contacts and configuration — connected by design, ready '
    'to grow with you.'
  ),
  'view.core.login.hero_title': 'One workspace for your whole business.',
  'view.core.login.password': 'Password',
  'view.core.login.sign_in': 'Sign in',
  'view.core.login.signing_in': 'Signing in…',
  'view.core.login.subtitle': 'Use your workspace credentials to continue.',
  'view.core.login.title': 'Sign in to J-ERP',
  'view.core.login.username': 'Username',
  'view.core.menus.column_access': 'Access',
  'view.core.menus.column_label': 'Label',
  'view.core.menus.column_sequence': 'Sequence',
  'view.core.menus.column_target': 'View / endpoint',
  'view.core.menus.description': (
    "Menu entries are stored in sys.menu and synchronized from each installed "
    "module's configure.json when it is installed or updated. Groups have no "
    'target; pages link to their view or endpoint.'
  ),
  'view.core.menus.empty_message': 'No menus are configured.',
  'view.core.menus.title': 'Menus',
  'view.core.models.empty_message': 'No models found.',
  'view.core.models.form_title': 'Model',
  'view.core.models.group_model': 'Model',
  'view.core.models.title': 'Models',
  'view.core.modules.empty_message': 'No modules found.',
  'view.core.modules.group_details': 'Details',
  'view.core.modules.group_general': 'General',
  'view.core.modules.title': 'Modules',
  'view.core.profile.form_title': 'Profile',
  'view.core.profile.group_profile': 'Profile',
  'view.core.profile.title': 'Profile',
  'view.core.states.empty_message': 'No states found.',
  'view.core.states.form_title': 'State',
  'view.core.states.title': 'States',
  'view.core.users.change_password': 'Change Password',
  'view.core.users.empty_message': 'No users found.',
  'view.core.users.form_title': 'User',
  'view.core.users.new_password': 'New password',
  'view.core.users.title': 'Users',
})


MODULE_EXTRA_KEYS = {
  'sale': {
    'view.sale.order_lines.empty_message': 'No order lines found.',
    'view.sale.order_lines.form.group_line': 'Line',
    'view.sale.order_lines.form.title': 'Order Line',
    'view.sale.order_lines.title': 'Order Lines',
    'view.sale.orders.empty_message': 'No sales orders found.',
    'view.sale.orders.form.group_general': 'General',
    'view.sale.orders.form.tabs.lines.empty_message': 'No lines.',
    'view.sale.orders.form.tabs.lines.label': 'Lines',
    'view.sale.orders.form.tabs.notes.label': 'Notes',
    'view.sale.orders.form.title': 'Sales Order',
    'view.sale.orders.title': 'Sales Orders',
  },
  'stock': {
    'view.stock.products.empty_message': 'No products found.',
    'view.stock.products.form.title': 'Product',
    'view.stock.products.title': 'Products',
  },
}


def discover_modules(modules_dir: str | Path) -> dict:
  return ModuleManager(None, Path(modules_dir)).discover()


def _add(keys: dict[str, str], key: str, source: str = '') -> None:
  if not key or not KEY_PATTERN.match(key):
    return
  if key not in keys or (not keys[key] and source):
    keys[key] = source


def _view_keys(views_dir: Path, keys: dict[str, str]) -> None:
  if not views_dir.is_dir():
    return
  for path in sorted(views_dir.rglob('*.ts*')):
    if path.suffix not in ('.ts', '.tsx'):
      continue
    try:
      source = path.read_text(encoding='utf-8')
    except OSError:
      continue
    for match in T_CALL.finditer(source):
      _add(keys, match.group(2).strip())


def _python_keys(root: Path, keys: dict[str, str]) -> None:
  if not root.is_dir():
    return
  for path in sorted(root.rglob('*.py')):
    if '__pycache__' in path.parts:
      continue
    try:
      source = path.read_text(encoding='utf-8')
      tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError):
      continue

    for node in ast.walk(tree):
      if not isinstance(node, ast.Call) or not node.args:
        continue
      func = node.func
      name = (
        func.id if isinstance(func, ast.Name)
        else func.attr if isinstance(func, ast.Attribute)
        else None
      )
      if name != '_t':
        continue
      key = node.args[0]
      if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
        continue
      fallback = ''
      if len(node.args) > 1:
        value = node.args[1]
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
          fallback = value.value
      _add(keys, key.value.strip(), fallback.strip())


def module_keys(info) -> dict[str, str]:
  """Translation key -> English source for one module."""

  keys: dict[str, str] = {}
  _add(keys, f'module.{info.name}.summary', info.summary)

  for model in info.models:
    model_name = model._name
    _add(
      keys,
      f'model.{model_name}.title',
      model_name.replace('.', ' ').replace('_', ' ').title(),
    )
    description = getattr(model, '_description', None)
    if description:
      _add(keys, f'model.{model_name}.description', description)

    for field_name, field in model._fields.items():
      if field.auto_increment or field_name in SKIP_FIELDS:
        continue
      prefix = f'model.{model_name}.field.{field_name}'
      _add(keys, f'{prefix}.label', field.name or field_name)
      if field.help:
        _add(keys, f'{prefix}.help', field.help)
      for value, label in getattr(field, 'selection', None) or []:
        _add(keys, f'{prefix}.selection.{value}', str(label))

  configure = info.path / 'configure.json'
  if configure.is_file():
    try:
      data = json.loads(configure.read_text(encoding='utf-8'))
    except (OSError, ValueError):
      data = {}
    for code, item, _parent in iter_menu_entries(
      data.get('routes') or data.get('pages') or [], info.name
    ):
      _add(keys, f'menu.{code}.label', item.get('label') or '')
      if item.get('description'):
        _add(keys, f'menu.{code}.description', item['description'])

  for key, source in MODULE_EXTRA_KEYS.get(info.name, {}).items():
    _add(keys, key, source)

  _python_keys(info.path, keys)
  _view_keys(info.path / 'ui' / 'src' / 'views', keys)
  if info.name == 'core':
    _python_keys(Path(__file__).resolve().parent, keys)
    _view_keys(Path(__file__).resolve().parent / 'ui' / 'src' / 'core', keys)
    for key, source in CORE_EXTRA_KEYS.items():
      _add(keys, key, source)
  return keys


def scaffold(
  modules_dir: str | Path,
  modules: list[str] | None,
  languages: list[str],
) -> list[Path]:
  discovered = discover_modules(modules_dir)
  selected = modules or sorted(discovered)
  paths: list[Path] = []

  for module_name in selected:
    info = discovered.get(module_name)
    if info is None:
      raise ValueError(f"Unknown module '{module_name}'.")
    keys = module_keys(info)
    directory = info.path / 'i18n'
    directory.mkdir(parents=True, exist_ok=True)

    for language in languages:
      if not LANG_PATTERN.match(language):
        raise ValueError(f'Invalid language code {language!r}.')
      path = directory / f'{language}{LANG_SUFFIX}'
      existing = parse_lang_file(path) if path.is_file() else {}
      lines = [
        f'# {module_name} translations ({language})',
        '# Generated by: python -m jerp.cli i18n scaffold',
        '',
      ]
      for key in sorted(keys):
        source = keys[key]
        if source:
          lines.append(f'# English: {source}')
        value = (
          (source or existing.get(key, ''))
          if language == 'en'
          else existing.get(key, '')
        )
        lines.append(f'{key} = {value}'.rstrip())
        lines.append('')
      path.write_text(
        '\n'.join(lines).rstrip() + '\n',
        encoding='utf-8',
        newline='\n',
      )
      paths.append(path)

  return paths


def check(modules_dir: str | Path, modules: list[str] | None) -> int:
  discovered = discover_modules(modules_dir)
  selected = modules or sorted(discovered)
  problems = 0

  for module_name in selected:
    info = discovered.get(module_name)
    if info is None:
      print(f'{module_name}: unknown module')
      problems += 1
      continue
    expected = set(module_keys(info))
    for language, path in module_language_files(info.path).items():
      try:
        values = parse_lang_file(path)
      except LangFormatError as exc:
        print(str(exc))
        problems += 1
        continue

      missing = sorted(expected - set(values))
      extra = sorted(set(values) - expected)
      if missing:
        problems += len(missing)
        print(f'{path}: {len(missing)} missing key(s)')
        for key in missing:
          print(f'  + {key}')
      if extra:
        problems += len(extra)
        print(f'{path}: {len(extra)} stale key(s)')
        for key in extra:
          print(f'  - {key}')
  return problems


def translate_modules(
  modules_dir: str | Path,
  modules: list[str] | None,
  languages: list[str],
  source: str = 'en',
  api_key: str | None = None,
  delay: float = 0.2,
  overwrite: bool = False,
  dry_run: bool = False,
  limit: int | None = None,
) -> int:
  """Translate empty values from ``source`` with Google Translate."""

  from jerp.translate import GoogleTranslator

  discovered = discover_modules(modules_dir)
  selected = modules or sorted(discovered)
  translator = GoogleTranslator(api_key=api_key, delay=delay)
  total = 0

  for module_name in selected:
    info = discovered.get(module_name)
    if info is None:
      raise ValueError(f"Unknown module '{module_name}'.")
    source_path = info.path / 'i18n' / f'{source}{LANG_SUFFIX}'
    derived = {
      key: value for key, value in module_keys(info).items() if value
    }

    if source_path.is_file():
      source_messages = {
        key: value
        for key, value in parse_lang_file(source_path).items()
        if value
      }
      for key, value in derived.items():
        source_messages.setdefault(key, value)
    else:
      if not dry_run:
        scaffold(modules_dir, [module_name], [source])
        print(f'{module_name}: created {source_path.name}.')
      source_messages = derived

    if not source_messages:
      print(f'{module_name}: no source strings; skipped.')
      continue

    for language in languages:
      if not LANG_PATTERN.match(language):
        raise ValueError(f'Invalid language code {language!r}.')
      if language == source:
        continue

      if not dry_run:
        scaffold(modules_dir, [module_name], [language])

      target_path = info.path / 'i18n' / f'{language}{LANG_SUFFIX}'
      target = parse_lang_file(target_path) if target_path.is_file() else {}
      keys = [
        key
        for key, value in source_messages.items()
        if value and (overwrite or not target.get(key))
      ]
      if limit is not None:
        keys = keys[:max(0, limit)]
      if not keys:
        print(f'{module_name}:{language}: nothing to translate.')
        continue

      translations = translator.translate(
        [source_messages[key] for key in keys],
        language,
        source,
      )
      values = dict(zip(keys, translations))

      if dry_run:
        for key, value in values.items():
          print(f'{module_name}:{language} {key} = {value}')
      else:
        _patch_lang_values(target_path, values, overwrite=overwrite)
        print(f'{module_name}:{language}: translated {len(values)} value(s).')
      total += len(values)

  return total


def _patch_lang_values(
  path: Path, values: dict[str, str], overwrite: bool = False
) -> None:
  lines = path.read_text(encoding='utf-8').splitlines()
  for index, line in enumerate(lines):
    stripped = line.strip()
    if not stripped or stripped.startswith('#') or '=' not in line:
      continue
    key, current = line.split('=', 1)
    key = key.strip()
    if key not in values:
      continue
    if overwrite or not current.strip():
      lines[index] = f'{key} = {values[key]}'
  path.write_text(
    '\n'.join(lines).rstrip() + '\n',
    encoding='utf-8',
    newline='\n',
  )


def sync_database(
  registry,
  modules: list[str] | None,
  languages: list[str] | None = None,
) -> int:
  from jerp.i18n import I18nLoader

  registry.ensure_loaded()
  selected = modules or list(registry.modules)
  loader = I18nLoader(registry.db, registry.manager.config.modules_path)
  count = 0
  if languages:
    for module_name in selected:
      for language in languages:
        count += loader.sync_module(module_name, language=language)
  else:
    for module_name in selected:
      count += loader.sync_module(module_name)
  return count
