"""What Lumen remembers between logins, and the one secret it holds.

`lumen.json` is ordinary settings (names of the PC's headers, groups the owner made, the last
scene, screen-sync preferences). `lumen-hue.json` holds the Hue bridge's application key and
client key: like the Home Assistant token beside it in ~/.config/mo-dot, it is 0600, never
logged, never sent anywhere but the bridge, and never shown.
"""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

CONFIG_DIR = Path(os.environ.get('MIRA_CONFIG_DIR') or (Path.home() / '.config' / 'mo-dot'))


def _write_private(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.tmp')
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)
    os.chmod(path, 0o600)


class Store:
    def __init__(self, directory: Path | None = None):
        self.dir = Path(directory) if directory else CONFIG_DIR
        self.path = self.dir / 'lumen.json'
        self.secret_path = self.dir / 'lumen-hue.json'
        self._lock = threading.Lock()
        self._data = self._read(self.path)

    @staticmethod
    def _read(path: Path) -> dict:
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def get(self, key, default=None):
        with self._lock:
            return self._data.get(key, default)

    def set(self, key, value) -> None:
        with self._lock:
            if value is None:
                self._data.pop(key, None)
            else:
                self._data[key] = value
            _write_private(self.path, self._data)

    # ── the Hue bridge's keys ────────────────────────────────────────
    def hue(self) -> dict:
        data = self._read(self.secret_path)
        return data if data.get('host') and data.get('app_key') else {}

    def save_hue(self, creds: dict) -> None:
        keep = {k: creds[k] for k in ('host', 'app_key', 'client_key', 'bridge_id', 'cert_sha256') if creds.get(k)}
        _write_private(self.secret_path, keep)

    def forget_hue(self) -> None:
        try:
            self.secret_path.unlink()
        except FileNotFoundError:
            pass
