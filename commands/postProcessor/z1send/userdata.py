# Z1 Post, by jimmyvegas29, 2026-11-16. GPL v2 (see LICENSE).
"""Where Z1 Post keeps per-computer data (send settings, the Z1 template).

Outside the add-in folder on purpose: updating the add-in replaces that folder, and anything saved in it
would go with it. Windows: %APPDATA%\\Z1 Post. Mac: ~/Library/Application Support/Z1 Post.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def data_dir() -> Path:
    override = os.environ.get("Z1POST_DATA_DIR")  # tests
    if override:
        base = Path(override)
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "Z1 Post"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support" / "Z1 Post"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "z1-post"
    return base


def data_file(name: str) -> Path:
    return data_dir() / name


def write_text(path: Path, text: str) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return True
    except OSError:
        return False
