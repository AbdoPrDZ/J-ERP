"""Language file parsing and direction tests (no database required)."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from jerp.i18n import LangFormatError, language_direction, parse_lang_file, parse_lang_text
from jerp.i18n_cli import _patch_lang_values
from jerp.translate import (
  GoogleTranslator,
  protect_placeholders,
  restore_placeholders,
)


class LangParserTest(unittest.TestCase):

  def test_parses_comments_keys_and_values(self):
    messages = parse_lang_text(
      '# English: Modules\n'
      'view.core.modules.title = الوحدات\n'
      '\n'
      '  model.sys.module.field.name.label  =  Nom  \n'
    )

    self.assertEqual(messages['view.core.modules.title'], 'الوحدات')
    self.assertEqual(messages['model.sys.module.field.name.label'], 'Nom')

  def test_parses_quoted_values(self):
    messages = parse_lang_text('app.message = "Hello = world"')
    self.assertEqual(messages['app.message'], 'Hello = world')

  def test_rejects_duplicate_keys(self):
    with self.assertRaises(LangFormatError):
      parse_lang_text('app.a = one\napp.a = two\n')

  def test_rejects_lines_without_equal_sign(self):
    with self.assertRaises(LangFormatError):
      parse_lang_text('app.a one\n')

  def test_direction(self):
    self.assertEqual(language_direction('ar'), 'rtl')
    self.assertEqual(language_direction('fr'), 'ltr')

  def test_placeholders_roundtrip(self):
    text = 'Page {page} of {count}: {name}'
    protected, tokens = protect_placeholders(text)

    self.assertNotIn('{page}', protected)
    self.assertIn('__JERP_PH_0__', protected)
    self.assertEqual(restore_placeholders(protected, tokens), text)

  def test_same_language_is_not_translated(self):
    translator = GoogleTranslator()
    self.assertEqual(
      translator.translate(['Hello', 'World'], 'en', 'en'),
      ['Hello', 'World'],
    )

  def test_patch_lang_values_only_fills_blanks_by_default(self):
    with tempfile.TemporaryDirectory() as directory:
      path = Path(directory) / 'fr.lang'
      path.write_text(
        '# comment\napp.a =\napp.b = Existing\n',
        encoding='utf-8',
      )
      _patch_lang_values(path, {'app.a': 'Un', 'app.b': 'Deux'})
      values = parse_lang_file(path)

      self.assertEqual(values['app.a'], 'Un')
      self.assertEqual(values['app.b'], 'Existing')


if __name__ == '__main__':
  unittest.main()
