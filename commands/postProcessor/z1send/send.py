"""Send posted files to a Makera Z1 over Wi-Fi, from inside Fusion.

The transfer itself is z1upload.py (a copy of pendant/python/z1upload.py in the Makera Z1 Upgrades
project; see reference/upload_protocol_notes.md there). This module adds what Fusion needs: a progress
dialog with Cancel, machine-safe names, and one summary for the message box.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Optional

from . import z1upload as Z

DEFAULT_FOLDER = "/sd/gcodes/"


def machine_name(name) -> str:
    """Make a name safe for the machine: spaces become _ (Studio doesn't show spaces), and characters the
    machine can't take are replaced too. Takes a Path (uses its name) or a plain file name."""
    out = []
    for c in (name.name if isinstance(name, Path) else str(name)):
        if c == " ":
            out.append("_")
        elif c in "?*!~\\" or ord(c) < 0x20 or ord(c) > 0x7E:
            out.append("_")
        else:
            out.append(c)
    return "".join(out)


def remote_path(folder: str, name) -> str:
    folder = (folder or DEFAULT_FOLDER).strip()
    if not folder.startswith("/"):
        folder = "/" + folder
    return folder.rstrip("/") + "/" + machine_name(name)


def _split(item) -> tuple[Path, str]:
    """A WrittenFile (naming.py: path + send_name) or a plain path (sent under its own name)."""
    if hasattr(item, "send_name"):
        return Path(item.path), item.send_name
    return Path(item), Path(item).name


@dataclass
class SendReport:
    sent: list = field(default_factory=list)          # Z.Result, ok
    failed: Optional[object] = None                    # Z.Result of the first failure
    skipped: list = field(default_factory=list)        # machine names of files not tried after a failure
    cancelled: bool = False
    seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return self.failed is None and not self.cancelled and not self.skipped

    def summary(self) -> str:
        lines = []
        for r in self.sent:
            lines.append(f"Sent {r.remote_path} ({_kb(r.size)}{', checked' if r.verified else ''})")
        if self.cancelled:
            lines.append("Cancelled.")
        elif self.failed is not None:
            lines.append(f"Not sent: {self.failed.remote_path}\n{self.failed.message}")
        if self.skipped:
            lines.append("Not tried: " + ", ".join(self.skipped))
        if not self.ok:
            lines.append("The files are saved on this computer either way.")
        return "\n".join(lines)


def _kb(n: int) -> str:
    return f"{n} bytes" if n < 1024 else f"{n / 1024:.0f} KB"


def send_files(paths: Iterable, host: str, folder: str = DEFAULT_FOLDER, *, verify: bool = False,
               on_progress: Optional[Callable[[str, int, int], bool]] = None) -> SendReport:
    """Send each file in turn (WrittenFile items get their send_name; plain paths keep their name).
    on_progress(file name, bytes done over all files, total bytes) returns False to cancel. Stops at the
    first file that fails. Two files that end up with the same machine name are refused up front."""
    items = [_split(p) for p in paths]
    paths = [p for p, _ in items]
    remotes = [remote_path(folder, n) for _, n in items]
    dup = {r for r in remotes if remotes.count(r) > 1}
    if dup:
        raise ValueError("Two files would get the same name on the machine: " + ", ".join(sorted(dup)))
    report = SendReport()
    t0 = time.monotonic()
    total = sum(p.stat().st_size for p in paths if p.exists()) or 1
    done = 0

    class _Cancel(Z.TransferError):
        pass

    for i, p in enumerate(paths):
        def prog(d, _t, _name=remotes[i].rsplit("/", 1)[-1], _base=done):
            if on_progress is not None and on_progress(_name, _base + d, total) is False:
                raise _Cancel("cancelled")

        r = Z.upload(host, str(p), remotes[i], verify=verify, progress=prog)
        if r.ok:
            report.sent.append(r)
            done += r.size
            continue
        if r.message == "cancelled":
            report.cancelled = True
        else:
            report.failed = r
        report.skipped = [r.rsplit("/", 1)[-1] for r in remotes[i + 1:]]
        break
    report.seconds = time.monotonic() - t0
    return report


def send_with_fusion_progress(ui, paths: Iterable, host: str, folder: str = DEFAULT_FOLDER) -> SendReport:
    """send_files() behind a Fusion progress dialog with a Cancel button."""
    import adsk.core

    dlg = ui.createProgressDialog()
    dlg.isCancelButtonShown = True
    dlg.cancelButtonText = "Cancel"
    dlg.isBackgroundTranslucent = False
    dlg.show("Sending to the Z1", "Connecting…", 0, 100, 0)

    def on_progress(name: str, done: int, total: int) -> bool:
        dlg.progressValue = int(100 * done / total)
        dlg.message = f"{name}: %p%"
        adsk.doEvents()
        return not dlg.wasCancelled

    try:
        return send_files(paths, host, folder, on_progress=on_progress)
    finally:
        dlg.hide()


def find_machines(timeout: float = 3.0) -> list[dict]:
    """Z1s on this network: [{'name', 'ip', 'port', 'busy', 'how'}]. Listens for their broadcasts first;
    if none arrive (Windows Firewall can block inbound traffic to Fusion), asks each address on the local
    network over TCP instead, which only needs outgoing connections."""
    try:
        found = Z.discover(timeout)
    except OSError:
        found = []
    for m in found:
        m["how"] = "broadcast"
    if found:
        return found
    found = Z.probe()
    for m in found:
        m["how"] = "probe"
    return found
