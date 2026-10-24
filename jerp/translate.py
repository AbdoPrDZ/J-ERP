"""Google Translate helpers for ``.lang`` files.

Uses the official Cloud Translation API when an API key is available
(``GOOGLE_TRANSLATE_API_KEY`` or ``--api-key``), otherwise the public
``translate.googleapis.com`` endpoint. No third-party package is required.
"""

from __future__ import annotations

import html
import json
import os
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

PLACEHOLDER = re.compile(r'\{[A-Za-z_][A-Za-z0-9_]*\}')
TOKEN = re.compile(r'__\s*JERP\s*_?\s*PH\s*_?\s*(\d+)\s*__', re.I)
CLOUD_URL = 'https://translation.googleapis.com/language/translate/v2'
FREE_URL = 'https://translate.googleapis.com/translate_a/single'
MAX_BATCH = 50


class TranslationError(RuntimeError):
  """Google Translate could not translate a value."""


def protect_placeholders(text: str) -> tuple[str, list[str]]:
  values: list[str] = []

  def replace(match):
    values.append(match.group(0))
    return f'__JERP_PH_{len(values) - 1}__'

  return PLACEHOLDER.sub(replace, text), values


def restore_placeholders(text: str, values: list[str]) -> str:
  def replace(match):
    index = int(match.group(1))
    return values[index] if 0 <= index < len(values) else match.group(0)

  return TOKEN.sub(replace, text)


class GoogleTranslator:
  def __init__(
    self,
    api_key: str | None = None,
    delay: float = 0.2,
    timeout: int = 30,
  ):
    self.api_key = (
      api_key
      or os.environ.get('GOOGLE_TRANSLATE_API_KEY')
      or os.environ.get('GOOGLE_API_KEY')
    )
    self.delay = max(0.0, delay)
    self.timeout = timeout
    self._cache: dict[tuple[str, str, str], str] = {}

  def translate(self, texts: list[str], target: str, source: str = 'en') -> list[str]:
    if source == target:
      return list(texts)

    protected: list[str] = []
    placeholders: list[list[str]] = []
    for text in texts:
      value, tokens = protect_placeholders(text)
      protected.append(value)
      placeholders.append(tokens)

    raw = (
      self._translate_cloud(protected, target, source)
      if self.api_key
      else self._translate_free(protected, target, source)
    )

    result: list[str] = []
    for value, tokens in zip(raw, placeholders):
      translated = restore_placeholders(value, tokens)
      if re.search(r'__\s*JERP\s*_?\s*PH', translated, re.I):
        raise TranslationError(
          f'Google Translate dropped a placeholder in {value!r}.'
        )
      result.append(translated)
    return result

  # --- official API -------------------------------------------------------

  def _translate_cloud(self, texts: list[str], target: str, source: str) -> list[str]:
    result: list[str] = []
    for start in range(0, len(texts), MAX_BATCH):
      chunk = texts[start:start + MAX_BATCH]
      result.extend(self._cloud_chunk(chunk, target, source))
    return result

  def _cloud_chunk(self, texts: list[str], target: str, source: str) -> list[str]:
    body = json.dumps({
      'q': texts,
      'source': source,
      'target': target,
      'format': 'text',
    }).encode('utf-8')
    url = f'{CLOUD_URL}?key={quote(self.api_key or "", safe="")}'

    payload = self._request(url, body, content_type='application/json')
    translations = (
      payload.get('data', {}).get('translations', [])
      if isinstance(payload, dict)
      else []
    )
    if len(translations) != len(texts):
      raise TranslationError(
        f'Google Translate returned {len(translations)} result(s) '
        f'for {len(texts)} value(s).'
      )
    return [
      html.unescape(str(item.get('translatedText') or ''))
      for item in translations
    ]

  # --- public endpoint ----------------------------------------------------

  def _translate_free(self, texts: list[str], target: str, source: str) -> list[str]:
    result: list[str] = []
    for index, text in enumerate(texts):
      if not text.strip():
        result.append('')
        continue

      key = (source, target, text)
      if key in self._cache:
        result.append(self._cache[key])
        continue

      params = urlencode({
        'client': 'gtx',
        'sl': source,
        'tl': target,
        'dt': 't',
        'q': text,
      })
      payload = self._request(f'{FREE_URL}?{params}')
      translated = self._free_text(payload)
      self._cache[key] = translated
      result.append(translated)

      if self.delay and index < len(texts) - 1:
        time.sleep(self.delay)
    return result

  @staticmethod
  def _free_text(payload) -> str:
    if not isinstance(payload, list) or not payload or not isinstance(payload[0], list):
      raise TranslationError('Unexpected response from Google Translate.')
    parts = []
    for segment in payload[0]:
      if isinstance(segment, list) and segment:
        parts.append(str(segment[0]))
    return html.unescape(''.join(parts))

  # --- HTTP ---------------------------------------------------------------

  def _request(self, url: str, body: bytes | None = None, content_type=None):
    headers = {'User-Agent': 'J-ERP/1.0 (i18n tool)'}
    if content_type:
      headers['Content-Type'] = content_type

    last_error = None
    for attempt in range(3):
      try:
        request = Request(url, data=body, headers=headers)
        with urlopen(request, timeout=self.timeout) as response:
          return json.loads(response.read().decode('utf-8'))
      except HTTPError as exc:
        last_error = exc
        if exc.code not in (429, 500, 502, 503, 504):
          raise TranslationError(
            f'Google Translate HTTP {exc.code}: {exc.reason}'
          ) from exc
      except URLError as exc:
        last_error = exc
        if attempt == 2:
          raise TranslationError(
            f'Google Translate is unreachable: {exc.reason}'
          ) from exc
      except (ValueError, OSError) as exc:
        last_error = exc
        if attempt == 2:
          raise TranslationError(f'Google Translate failed: {exc}') from exc

      time.sleep(0.5 * (2 ** attempt))

    raise TranslationError(f'Google Translate failed: {last_error}')
