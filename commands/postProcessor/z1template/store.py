# Z1 Post, by jimmyvegas29, 2026-11-16. GPL v2 (see LICENSE).
"""The Z1 template: the machine, post processor and changed post settings of one NC Program, saved so
Z1 Post can create an NC Program in any document (template_program.py).

Saved per computer in the user data folder as template.json. Plain data, no Fusion objects:

    {"machine":  {"vendor", "model", "description"},
     "post":     {"vendor", "description", "version", "extension"},
     "post_settings": {internal name: expression},   # only those changed from the post's defaults
     "output_folder": str,                           # where the source NC Program wrote its files
     "saved": {"date", "program", "document"}}
"""
from __future__ import annotations

import json
from typing import Any, Optional

from ..z1send import userdata

FILE_NAME = "template.json"
NC_PROGRAM_NAME = "Z1 Post"


def _path():
    return userdata.data_file(FILE_NAME)


def load() -> Optional[dict]:
    try:
        data = json.loads(_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if is_valid(data) else None


def save(template: dict) -> bool:
    if not is_valid(template):
        raise ValueError("a template needs a machine model and a post description")
    return userdata.write_text(_path(), json.dumps(template, indent=4, sort_keys=True))


def clear() -> None:
    try:
        _path().unlink()
    except OSError:
        pass


def is_valid(data: Any) -> bool:
    return (isinstance(data, dict)
            and bool((data.get("machine") or {}).get("model"))
            and bool((data.get("post") or {}).get("description"))
            and isinstance(data.get("post_settings", {}), dict))


def summary(template: dict, machine_found: bool = True, post_found: bool = True) -> list[tuple[str, str]]:
    """Rows for the More tab: (label, value)."""
    m, p = template["machine"], template["post"]
    machine = m.get("model", "")
    post = p.get("description", "")
    if not machine_found:
        machine += " · not found in this computer's machine libraries"
    if not post_found:
        post += " · not found in this computer's post libraries"
    n = len(template.get("post_settings") or {})
    settings = "the post's defaults" if n == 0 else f"{n} changed from the post's defaults"
    saved = template.get("saved") or {}
    where = ", ".join(x for x in (saved.get("date", ""),
                                  f"from {saved['program']}" if saved.get("program") else "",
                                  f"in {saved['document']}" if saved.get("document") else "") if x)
    rows = [("Machine", machine), ("Post processor", post), ("Post settings", settings)]
    if where:
        rows.append(("Saved", where))
    return rows


def dropdown_label(document_has_programs: bool) -> str:
    return "Z1 template (new NC Program)" if document_has_programs else "Z1 template"
