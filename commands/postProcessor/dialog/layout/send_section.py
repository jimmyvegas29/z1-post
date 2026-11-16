# Z1 Post, by jimmyvegas29, 2026-11-16. GPL v2 (see LICENSE).
"""Post tab: the "Send to the Z1" group. Its settings live in z1send/prefs.py (one copy for this computer)."""
from __future__ import annotations

import html

from adsk.core import (
    Application,
    BoolValueCommandInput,
    StringValueCommandInput,
    TextBoxCommandInput,
)

from ...strings import Strings
from ...z1send import prefs
from ..event_registry import EventRegistry

SEND_GROUP_ID = "z1SendGroup"
SEND_ENABLED_ID = "z1SendEnabled"
SEND_HOST_ID = "z1SendHost"
SEND_FIND_ID = "z1SendFind"
SEND_FOLDER_ID = "z1SendFolder"
SEND_STATUS_ID = "z1SendStatus"


def ok_button_text() -> str:
    return Strings("Post and send") if prefs.get("enabled") else Strings("Post")


def _status(inputs, text: str) -> None:
    box = TextBoxCommandInput.cast(inputs.itemById(SEND_STATUS_ID))
    if box is not None:
        box.formattedText = f'<span style="color:#808080">{html.escape(text)}</span>' if text else ""


def create(post_tab) -> None:
    group = post_tab.children.addGroupCommandInput(SEND_GROUP_ID, Strings("Send to the Z1"))
    group.isExpanded = True
    kids = group.children

    enabled = kids.addBoolValueInput(SEND_ENABLED_ID, Strings("Send after posting"),
                                     True, "", bool(prefs.get("enabled")))
    enabled.tooltip = Strings("Send the files to the machine after posting")
    enabled.tooltipDescription = Strings("TOOLTIP TEXT: Send to the Z1")

    host = kids.addStringValueInput(SEND_HOST_ID, Strings("Machine (IP address)"), str(prefs.get("host") or ""))
    host.tooltip = Strings("Machine (IP address)")
    host.tooltipDescription = Strings("TOOLTIP TEXT: Z1 address")

    find = kids.addBoolValueInput(SEND_FIND_ID, "   " + Strings("Find the Z1 on the network") + "   ", False)
    find.isFullWidth = True
    find.tooltip = Strings("Find the Z1 on the network")
    find.tooltipDescription = Strings("TOOLTIP TEXT: Find the Z1")

    folder = kids.addStringValueInput(SEND_FOLDER_ID, Strings("Folder on the machine"), str(prefs.get("folder")))
    folder.tooltip = Strings("Folder on the machine")
    folder.tooltipDescription = Strings("TOOLTIP TEXT: Folder on the machine")

    status = kids.addTextBoxCommandInput(SEND_STATUS_ID, "", "", 2, True)
    status.isFullWidth = True
    last = prefs.get("last")
    _status(post_tab.parentCommand.commandInputs, Strings("Last sent: {what}").format(what=last) if last else "")

    def set_enabled_state(inputs) -> None:
        on = BoolValueCommandInput.cast(inputs.itemById(SEND_ENABLED_ID)).value
        for i in (SEND_HOST_ID, SEND_FIND_ID, SEND_FOLDER_ID):
            item = inputs.itemById(i)
            if item is not None:
                item.isEnabled = on

    def on_enabled(checkbox) -> None:
        prefs.set("enabled", bool(checkbox.value))
        inputs = checkbox.parentCommand.commandInputs
        set_enabled_state(inputs)
        try:
            checkbox.parentCommand.okButtonText = ok_button_text()
        except Exception:
            pass  # if Fusion won't relabel it while open, the next opening shows the new text

    def on_host(text) -> None:
        prefs.set("host", StringValueCommandInput.cast(text).value.strip())

    def on_folder(text) -> None:
        value = StringValueCommandInput.cast(text).value.strip() or "/sd/gcodes/"
        if not value.startswith("/"):
            value = "/" + value
        prefs.set("folder", value)

    def on_find(button) -> None:
        from ...z1send.send import find_machines
        inputs = button.parentCommand.commandInputs
        _status(inputs, Strings("Looking for the Z1…"))
        machines = find_machines(3.0)
        if not machines:
            _status(inputs, Strings("No Z1 found. Check it's on and on this network, or type its IP address."))
            return
        first = machines[0]
        StringValueCommandInput.cast(inputs.itemById(SEND_HOST_ID)).value = first["ip"]
        prefs.set("host", first["ip"])
        found = ", ".join(f'{m.get("name", "?")} ({m["ip"]})' for m in machines)
        text = Strings("Found: {found}").format(found=found)
        if len(machines) > 1:
            text += " · " + Strings("using the first; type another IP to change it.")
        if first.get("how") == "probe":
            text += " · " + Strings("by asking each address")
        _status(inputs, text)

    EventRegistry.register(SEND_ENABLED_ID, on_enabled)
    EventRegistry.register(SEND_HOST_ID, on_host)
    EventRegistry.register(SEND_FOLDER_ID, on_folder)
    EventRegistry.register(SEND_FIND_ID, on_find)
    set_enabled_state(post_tab.parentCommand.commandInputs)


def send_after_post(ui, written) -> None:
    """Called by the dialog after the files are written. Shows one message with the outcome."""
    from adsk.core import MessageBoxButtonTypes, MessageBoxIconTypes
    from ...z1send.send import send_with_fusion_progress
    import time

    if not prefs.get("enabled") or not written:
        return
    title = Strings("Send to the Z1")
    host = str(prefs.get("host") or "").strip()
    if not host:
        ui.messageBox(Strings("The files are saved on this computer. They weren't sent: no machine is set. "
                              "Use \"Find the Z1 on the network\" on the Post tab, or type its IP address."),
                      title, MessageBoxButtonTypes.OKButtonType, MessageBoxIconTypes.WarningIconType)
        return
    try:
        report = send_with_fusion_progress(ui, written, host, prefs.get("folder"))
    except ValueError as e:      # two files would get the same name on the machine
        ui.messageBox(str(e) + "\n" + Strings("The files are saved on this computer either way."), title,
                      MessageBoxButtonTypes.OKButtonType, MessageBoxIconTypes.WarningIconType)
        return
    if report.sent:
        names = ", ".join(r.remote_path.rsplit("/", 1)[-1] for r in report.sent)
        prefs.set("last", f"{names}, {time.strftime('%H:%M')}" + (" · " + Strings("checked")
                                                                  if all(r.verified for r in report.sent) else ""))
    ui.messageBox(report.summary(), title, MessageBoxButtonTypes.OKButtonType,
                  MessageBoxIconTypes.InformationIconType if report.ok else MessageBoxIconTypes.WarningIconType)
