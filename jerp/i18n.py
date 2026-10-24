"""Translation catalogs and language resolution.

Translations live in flat ``key = value`` files under
``modules/<module>/i18n/<lang>.lang`` and are synchronized into
``sys.translation`` on module install/update. Runtime reads the database and
falls back to the source strings when a key is missing.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from jerp.dialect import quote_ident, quote_table

logger = logging.getLogger('jerp.i18n')

LANG_SUFFIX = '.lang'
DEFAULT_LANGUAGE = 'en'
RTL_LANGUAGES = {'ar', 'fa', 'he', 'ur'}
KEY_PATTERN = re.compile(r'^[A-Za-z0-9_.:-]+$')

TRANSLATION_TABLE = 'sys_translation'
LANGUAGE_TABLE = 'sys_lang'


class LangFormatError(ValueError):
  """A ``.lang`` file is not valid."""


# --- file parsing ---------------------------------------------------------


def parse_lang_text(text: str, source: str = '<lang>') -> dict[str, str]:
  """Parse a flat ``key = value`` language file."""

  result: dict[str, str] = {}
  for number, raw in enumerate(text.splitlines(), 1):
    line = raw.strip()
    if not line or line.startswith('#'):
      continue
    if '=' not in line:
      raise LangFormatError(
        f'{source}:{number}: expected "key = value", got {raw!r}'
      )

    key, value = line.split('=', 1)
    key = key.strip()
    value = value.strip()
    if not key or not KEY_PATTERN.match(key):
      raise LangFormatError(
        f'{source}:{number}: invalid translation key {key!r}'
      )
    if key in result:
      raise LangFormatError(
        f'{source}:{number}: duplicate translation key {key!r}'
      )

    if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
      try:
        value = json.loads(value)
      except ValueError as exc:
        raise LangFormatError(
          f'{source}:{number}: invalid quoted value: {exc}'
        ) from exc
    elif len(value) >= 2 and value.startswith("'") and value.endswith("'"):
      value = value[1:-1]
    result[key] = value
  return result


def parse_lang_file(path: str | Path) -> dict[str, str]:
  path = Path(path)
  return parse_lang_text(path.read_text(encoding='utf-8'), str(path))


def module_language_files(module_dir: str | Path) -> dict[str, Path]:
  directory = Path(module_dir) / 'i18n'
  if not directory.is_dir():
    return {}
  return {
    path.stem: path
    for path in sorted(directory.glob(f'*{LANG_SUFFIX}'))
    if path.is_file()
  }


def load_module_messages(module_dir: str | Path) -> dict[str, dict[str, str]]:
  return {
    language: parse_lang_file(path)
    for language, path in module_language_files(module_dir).items()
  }


# --- database synchronization --------------------------------------------


class I18nLoader:
  """Write module ``.lang`` files into ``sys.translation``."""

  def __init__(self, db, modules_dir: str | Path):
    self.db = db
    self.modules_dir = Path(modules_dir)

  def sync_modules(
    self,
    module_names,
    language: str | None = None,
    active_only: bool = False,
  ) -> None:
    for module_name in dict.fromkeys(module_names):
      self.sync_module(
        module_name, language=language, active_only=active_only
      )

  def sync_module(
    self,
    module_name: str,
    language: str | None = None,
    active_only: bool = False,
  ) -> int:
    all_messages = load_module_messages(self.modules_dir / module_name)
    if language is not None:
      all_messages = {
        name: messages
        for name, messages in all_messages.items()
        if name == language
      }
      if not all_messages:
        raise ValueError(
          f'No {language} language file for module {module_name}.'
        )

    language_ids = self._language_ids(active_only=active_only)
    if active_only:
      all_messages = {
        name: messages
        for name, messages in all_messages.items()
        if name in language_ids
      }

    rows: list[tuple] = []
    language_id = None

    for name, messages in all_messages.items():
      lang_id = language_ids.get(name)
      if lang_id is None:
        if language is not None:
          raise ValueError(f'Language {name!r} is not in sys.lang.')
        if active_only:
          continue
        logger.warning(
          'Skipping %s translation file: language %r is not in sys.lang.',
          module_name,
          name,
        )
        continue
      if language is not None:
        language_id = lang_id
      for key, value in messages.items():
        if not value:
          continue
        rows.append([
          lang_id,
          module_name,
          key,
          f'{name}:{key}',
          value,
          'file',
        ])

    with self.db.transaction():
      if language_id is not None:
        self.db.execute(
          f'DELETE FROM {quote_table(TRANSLATION_TABLE)} '
          f'WHERE {quote_ident("module")} = %s '
          f'AND {quote_ident("lang_id")} = %s',
          [module_name, language_id],
        )
      else:
        self.db.execute(
          f'DELETE FROM {quote_table(TRANSLATION_TABLE)} '
          f'WHERE {quote_ident("module")} = %s',
          [module_name],
        )
      for row in rows:
        self.db.execute(
          f'INSERT INTO {quote_table(TRANSLATION_TABLE)} '
          f'({quote_ident("lang_id")}, {quote_ident("module")}, '
          f'{quote_ident("key")}, {quote_ident("code")}, '
          f'{quote_ident("value")}, {quote_ident("source")}, '
          f'{quote_ident("active")}, {quote_ident("created_at")}, '
          f'{quote_ident("updated_at")}) '
          f'VALUES (%s, %s, %s, %s, %s, %s, TRUE, NOW(), NOW())',
          row,
        )
    return len(rows)

  def remove_module(self, module_name: str) -> None:
    if not self.db.table_exists(TRANSLATION_TABLE):
      return
    self.db.execute(
      f'DELETE FROM {quote_table(TRANSLATION_TABLE)} '
      f'WHERE {quote_ident("module")} = %s',
      [module_name],
    )

  def _language_ids(self, active_only: bool = False) -> dict[str, int]:
    where = f' WHERE {quote_ident("active")} = TRUE' if active_only else ''
    rows = self.db.fetchall(
      f'SELECT {quote_ident("id")}, {quote_ident("code")} '
      f'FROM {quote_table(LANGUAGE_TABLE)}{where}'
    )
    return {row['code']: int(row['id']) for row in rows}


# --- runtime --------------------------------------------------------------


def _registry():
  from jerp.env import Environment

  try:
    return Environment.instance.registry()
  except Exception:
    return None


def _request():
  from jerp.http.request import current

  return current()


def _language_model():
  registry = _registry()
  if registry is None:
    return None
  try:
    registry.ensure_loaded()
  except Exception:
    return None
  return registry.get(LANGUAGE_TABLE)


def _active_language(code):
  Language = _language_model()
  if Language is None or not code:
    return None
  try:
    rows = Language.search(
      [('code', '=', str(code)), ('active', '=', True)], limit=1
    )
  except Exception:
    return None
  return rows[0] if rows else None


def _user_language(username):
  registry = _registry()
  if registry is None or not username:
    return None
  try:
    registry.ensure_loaded()
  except Exception:
    return None

  User = registry.get('sys.user')
  if User is None:
    return None
  try:
    users = User.search([('username', '=', username)], limit=1)
  except Exception:
    return None
  if not users:
    return None

  language_id = users[0].read(['lang_id']).get('lang_id')
  if not language_id:
    return None

  Language = registry.get('sys.lang')
  if Language is None:
    return None
  languages = Language.browse(language_id)
  if not languages or not languages[0].active:
    return None
  return languages[0].code


def _default_language() -> str:
  Language = _language_model()
  if Language is None:
    return DEFAULT_LANGUAGE
  try:
    rows = Language.search(
      [('is_default', '=', True), ('active', '=', True)], limit=1
    )
    if rows:
      return rows[0].code or DEFAULT_LANGUAGE
  except Exception:
    pass
  return DEFAULT_LANGUAGE


def current_language(request=None) -> str:
  """User preference, then ``jerp_lang`` cookie, then the system default."""

  req = request or _request()
  if req is not None:
    cached = getattr(req, '_jerp_lang_code', None)
    if cached:
      return cached

  code = None
  if req is not None:
    username = req.cookies.get('jerp_user')
    if username:
      code = _user_language(username)
    if not code:
      cookie = req.cookies.get('jerp_lang')
      if cookie and _active_language(cookie):
        code = cookie
  if not code:
    code = _default_language()

  if req is not None:
    req._jerp_lang_code = code
  return code


def language_direction(code: str | None = None) -> str:
  return 'rtl' if (code or current_language()) in RTL_LANGUAGES else 'ltr'


def _catalog(code: str) -> dict[str, str]:
  req = _request()
  if req is not None:
    catalogs = getattr(req, '_jerp_catalogs', None)
    if catalogs is None:
      catalogs = {}
      req._jerp_catalogs = catalogs
    if code in catalogs:
      return catalogs[code]
  else:
    catalogs = None

  messages: dict[str, str] = {}
  registry = _registry()
  if registry is not None:
    try:
      registry.ensure_loaded()
      rows = registry.db.fetchall(
        f'SELECT t.{quote_ident("key")} AS translation_key, '
        f't.{quote_ident("value")} AS translation_value '
        f'FROM {quote_table(TRANSLATION_TABLE)} t '
        f'JOIN {quote_table(LANGUAGE_TABLE)} l '
        f'ON l.{quote_ident("id")} = t.{quote_ident("lang_id")} '
        f'WHERE l.{quote_ident("code")} = %s '
        f'AND t.{quote_ident("active")} = TRUE',
        [code],
      )
      messages = {
        row['translation_key']: row['translation_value']
        for row in rows
        if row.get('translation_value')
      }
    except Exception:
      logger.exception('Could not load translations for %s', code)
      messages = {}

  if catalogs is not None:
    catalogs[code] = messages
  return messages


def catalog(code: str | None = None) -> dict[str, str]:
  return _catalog(code or current_language())


def translate(key: str, default: str | None = None, code: str | None = None) -> str:
  value = catalog(code).get(key)
  if value:
    return value
  return default if default is not None else key


def _t(key: str, default: str | None = None, **params) -> str:
  """Translate a Python-side message, with ``{name}`` interpolation."""

  value = translate(key, default)
  for name, replacement in params.items():
    value = value.replace(f'{{{name}}}', str(replacement))
  return value


def available_languages() -> list[dict]:
  Language = _language_model()
  if Language is None:
    return []
  try:
    rows = Language.search([('active', '=', True)], order='name')
  except Exception:
    return []
  languages = [
    {
      'code': row.code,
      'name': row.name,
      'is_default': bool(row.is_default),
    }
    for row in rows
    if row.code
  ]
  languages.sort(key=lambda item: (not item['is_default'], item['name'] or ''))
  return languages


def payload() -> dict:
  code = current_language()
  default = _default_language()
  return {
    'lang': code,
    'dir': language_direction(code),
    'messages': catalog(code),
    'fallback': catalog(default) if default != code else {},
    'languages': available_languages(),
  }


# --- language preference --------------------------------------------------


def find_language(code: str):
  return _active_language(code)


def save_user_language(username: str, code: str) -> bool:
  registry = _registry()
  if registry is None or not username:
    return False
  try:
    registry.ensure_loaded()
  except Exception:
    return False

  User = registry.get('sys.user')
  language = _active_language(code)
  if User is None or language is None:
    return False
  try:
    users = User.search([('username', '=', username)], limit=1)
    if not users:
      return False
    users[0].write({'lang_id': language.id})
    return True
  except Exception:
    logger.exception('Could not save language %s for %s', code, username)
    return False
