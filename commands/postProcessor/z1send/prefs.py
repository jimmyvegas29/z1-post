# Z1 Post, by jimmyvegas29, 2026-11-16. GPL v2 (see LICENSE).
"""Send-to-Z1 settings. Kept for this computer (not per Fusion document): the machine's address doesn't change
from one design to the next. Stored in the user data folder (userdata.py), so updating the add-in keeps them."""
from __future__ import annotations

import json
from pathlib import Path

from . import userdata
from .send import DEFAULT_FOLDER

_OLD_PATH = Path(__file__).with_name("z1send.settings")  # 0.1.0 kept them in the add-in folder
_DEFAULTS = {"enabled": False, "host": "", "folder": DEFAULT_FOLDER, "last": ""}
_items: dict = {}


def _path() -> Path:
    return userdata.data_file("send.json")


def _load() -> dict:
    global _items
    if not _items:
        _items = dict(_DEFAULTS)
        for source in (_path(), _OLD_PATH):
            try:
                _items.update(json.loads(source.read_text(encoding="utf-8")))
                break
            except (OSError, ValueError):
                continue
    return _items


def get(key: str):
    return _load().get(key, _DEFAULTS.get(key))


def set(key: str, value) -> None:  # noqa: A001 - mirrors Settings.set
    _load()[key] = value
    userdata.write_text(_path(), json.dumps(_items, indent=4, sort_keys=True))
