# Z1 Post, by jimmyvegas29, 2026-11-16. GPL v2 (see LICENSE).
"""Send-to-Z1 settings. Kept in one file for this computer (not per Fusion document): the machine's address
doesn't change from one design to the next."""
from __future__ import annotations

import json
from pathlib import Path

from .send import DEFAULT_FOLDER

_PATH = Path(__file__).with_name("z1send.settings")
_DEFAULTS = {"enabled": False, "host": "", "folder": DEFAULT_FOLDER, "last": ""}
_items: dict = {}


def _load() -> dict:
    global _items
    if not _items:
        _items = dict(_DEFAULTS)
        try:
            _items.update(json.loads(_PATH.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    return _items


def get(key: str):
    return _load().get(key, _DEFAULTS.get(key))


def set(key: str, value) -> None:  # noqa: A001 - mirrors Settings.set
    _load()[key] = value
    try:
        _PATH.write_text(json.dumps(_items, indent=4, sort_keys=True), encoding="utf-8")
    except OSError:
        pass
