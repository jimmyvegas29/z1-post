"""The name a posted file gets on the Z1's SD card.

Rule: always `<File name>_<Setup>.cnc`, flat in the send folder, whatever the grouping does
on this computer. Locally "Group on setup" makes `<File name>/<Setup>.cnc`; the machine gets one flat name
that still says both the job and the setup, so different jobs' `Setup1` files never overwrite each other.

- Single file, one setup:          Job_Setup1.cnc
- Single file, several setups:     Job_Setup1-Setup2.cnc
- Group on setup:                  Job_Setup1.cnc, Job_Setup2.cnc
- Group on setup and tool:         Job_Setup1_T3.cnc  (local stem already starts with the setup)
- One file per operation:          Job_Setup1_Pocket1.cnc
- Numeric names: kept as they are (they are numbers on purpose).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable


@dataclass(frozen=True)
class WrittenFile:
    path: Path          # where the plugin wrote it on this computer
    send_name: str      # file name (with extension) to use on the machine


def send_name(job_name: str | None, setup_names: Iterable[str], local_path: Path, mode: str = "setup", *,
              sanitize: Callable[[str], str] = lambda s: s) -> str:
    """mode: "single", "setup", "tool", "op" or "numeric" (from the Operations grouping setting)."""
    if mode == "numeric":
        return local_path.name
    stem = local_path.stem
    setups = "-".join(sanitize(n) for n in setup_names if n) or stem
    if mode == "tool":
        tail = stem if setups in stem else f"{setups}_{stem}"   # local stem is "<Setup>_T3"
    elif mode == "op":
        tail = f"{setups}_{stem}"
    else:
        tail = setups
    job = (job_name or "").strip()
    if job and job != "None":
        tail = f"{sanitize(job)}_{tail}"
    return tail + local_path.suffix


def written_files(plans: Iterable[Any], job_name: str | None, grouping: Any, numeric: bool,
                  sanitize: Callable[[str], str]) -> tuple[WrittenFile, ...]:
    """One WrittenFile per rendered plan (ResultFilePlan: .path, .setups with .name)."""
    from ..settings.constants import Constants
    G = Constants.OperationsGroupings
    mode = "numeric" if numeric else {G.SINGLE_FILE: "single", G.SETUP: "setup",
                                      G.SETUP_AND_TOOL: "tool"}.get(grouping, "op")
    return tuple(
        WrittenFile(p.path, send_name(job_name, [s.name for s in p.setups], p.path, mode, sanitize=sanitize))
        for p in plans
    )
