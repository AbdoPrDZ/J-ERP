"""Upload storage.

Files first land in ``data/uploads/tmp``; when the record is confirmed they are
moved to ``data/uploads/files``. The stored file name is a generated id (uuid +
extension); the original name and metadata live on the ``file`` model.
"""

from __future__ import annotations

import hashlib
import mimetypes
import uuid
from pathlib import Path


def _uploads_root() -> Path:
  try:
    from jerp.env import Environment

    return Path(Environment.instance.databases.config.uploads_dir)
  except Exception:
    from jerp.config import Config

    return Path(Config.load().uploads_dir)


def dirs(root: Path | None = None) -> tuple[Path, Path]:
  base = root or _uploads_root()
  return base / 'tmp', base / 'files'


def checksum(data: bytes) -> str:
  return hashlib.sha256(data).hexdigest()


def guess_mimetype(name: str, fallback: str | None = None) -> str:
  guessed, _ = mimetypes.guess_type(name)
  return guessed or fallback or 'application/octet-stream'


def safe_token(token: str) -> str:
  if not token or token.startswith('.') or '/' in token or '\\' in token:
    raise ValueError(f'Invalid upload token: {token!r}')
  return token


def generate_name(original_name: str) -> str:
  return f'{uuid.uuid4().hex}{Path(original_name).suffix}'


def save_temp(data: bytes, name: str, mimetype: str | None = None) -> dict:
  """Store an uploaded file in ``tmp`` and return its metadata/token."""

  tmp, _ = dirs()
  tmp.mkdir(parents=True, exist_ok=True)

  token = generate_name(name)
  (tmp / token).write_bytes(data)

  return {
    'token': token,
    'name': name,
    'mimetype': mimetype or guess_mimetype(name),
    'checksum': checksum(data),
    'size': len(data),
  }


def confirm(token: str) -> Path:
  """Move a file from ``tmp`` to ``files`` and return its final path."""

  token = safe_token(token)
  tmp, files = dirs()
  files.mkdir(parents=True, exist_ok=True)

  source = tmp / token
  if not source.is_file():
    raise FileNotFoundError(f'Upload not found: {token}')

  target = files / token
  source.replace(target)
  return target


def path_of(token: str) -> Path:
  _, files = dirs()
  return files / safe_token(token)
