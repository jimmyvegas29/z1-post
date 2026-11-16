# Z1 Post, by jimmyvegas29, 2026-11-16. GPL v2 (see LICENSE).
"""The Z1 template in the dialog: the extra NC Program choice (Post tab) and the "Z1 template" group (More tab).
The template itself: z1template/store.py and z1template/template_program.py."""
from __future__ import annotations

import html

from adsk.core import Application, LogLevels, MessageBoxButtonTypes, MessageBoxIconTypes, TextBoxCommandInput

from .....lib.fusionAddInUtils.general_utils import Utils
from ...programs import Programs
from ...settings.settings import Settings
from ...strings import Strings
from ...z1template import store
from ..event_registry import EventRegistry

GROUP_ID = "z1TemplateGroup"
INFO_ID = "z1TemplateInfo"
SAVE_ID = "z1TemplateSave"
REMOVE_ID = "z1TemplateRemove"
STATUS_ID = "z1TemplateStatus"
PROGRAM_DROPDOWN_ID = "program"


def _entry():
    return next((p for p in Programs if getattr(p, "is_template", False)), None)


def _make_entry(template, cam, document_name, usable_programs: bool):
    from ...z1template.template_program import TemplateProgram
    return TemplateProgram(template, cam, store.dropdown_label(usable_programs), document_name,
                           on_created=_program_created)


def _usable():
    return [p for p in Programs if not getattr(p, "is_template", False)
            and not p.has_error and not p.is_empty and not p.is_suppressed]


def add_to_programs(cam, doc) -> None:
    """Add the saved template as the last NC Program choice. In a document with no usable NC Program it is
    selected straight away; it's also re-selected if it was the last choice."""
    template = store.load()
    if template is None:
        return
    try:
        entry = _make_entry(template, cam, doc.name if doc else "", bool(_usable()))
    except Exception as e:
        Utils.log(f"Z1 template skipped: {e}", LogLevels.WarningLogLevel)
        return
    Programs._items.append(entry)
    last = str(Settings(Settings.NC_PROGRAM) or "")
    if Programs.Current is None and (not _usable() or last.startswith("Z1 template")):
        Programs.Current = entry
        Settings(Settings.NC_PROGRAM, entry.name)


def _program_created(program) -> None:
    """The template just created a real NC Program in the document: use it from now on."""
    Programs._items.append(program)
    Programs.Current = program
    Settings(Settings.NC_PROGRAM, program.name)


def report_failed_settings(ui, entry) -> None:
    if entry is None or not entry.failed_settings:
        return
    ui.messageBox(Strings("Created the NC Program \"{name}\" from your Z1 template, but these post settings "
                          "couldn't be set and use the post's defaults:\n{names}").format(
                      name=entry.created.name if entry.created else store.NC_PROGRAM_NAME,
                      names=", ".join(entry.failed_settings)),
                  Strings("Z1 template"), MessageBoxButtonTypes.OKButtonType, MessageBoxIconTypes.WarningIconType)


def save_error_report() -> None:
    """Keep the full traceback of the last posting error in the user data folder (last_error.txt)."""
    import traceback
    from ...z1send import userdata
    userdata.write_text(userdata.data_file("last_error.txt"), traceback.format_exc())


# --- More tab ---------------------------------------------------------------------------------------
def _info_html(template) -> str:
    if template is None:
        return ('<span style="color:#9aa3b0">' + html.escape(Strings(
            "No template saved. Pick an NC Program on the Post tab that has the Z1 machine and post processor, "
            "then save it here. After that, any document can post without making an NC Program first.")) + "</span>")
    entry = _entry()
    machine_found = entry is None or entry._machine is not None
    post_found = entry is None or entry._post is not None
    rows = store.summary(template, machine_found, post_found)
    return "<br>".join(f'<span style="color:#9aa3b0">{html.escape(Strings(k))}:</span> {html.escape(v)}'
                       for k, v in rows)


def _status(inputs, text: str) -> None:
    box = TextBoxCommandInput.cast(inputs.itemById(STATUS_ID))
    if box is not None:
        box.formattedText = f'<span style="color:#9aa3b0">{html.escape(text)}</span>' if text else ""


def _refresh(inputs) -> None:
    info = TextBoxCommandInput.cast(inputs.itemById(INFO_ID))
    if info is not None:
        info.formattedText = _info_html(store.load())
    current = Programs.Current
    save = inputs.itemById(SAVE_ID)
    if save is not None:
        save.isEnabled = (current is not None and not getattr(current, "is_template", False)
                          and current.has_machine and current.has_post_processor)
    remove = inputs.itemById(REMOVE_ID)
    if remove is not None:
        remove.isEnabled = store.load() is not None


def create(more_tab) -> None:
    group = more_tab.children.addGroupCommandInput(GROUP_ID, Strings("Z1 template"))
    group.isExpanded = True
    kids = group.children
    info = kids.addTextBoxCommandInput(INFO_ID, "", "", 4, True)
    info.isFullWidth = True
    save = kids.addBoolValueInput(SAVE_ID, "   " + Strings("Save the selected NC Program as the Z1 template") + "   ", False)
    save.isFullWidth = True
    save.tooltip = Strings("Save the selected NC Program as the Z1 template")
    save.tooltipDescription = Strings("TOOLTIP TEXT: Save Z1 template")
    remove = kids.addBoolValueInput(REMOVE_ID, "   " + Strings("Remove the template") + "   ", False)
    remove.isFullWidth = True
    status = kids.addTextBoxCommandInput(STATUS_ID, "", "", 2, True)
    status.isFullWidth = True

    def on_save(button) -> None:
        from ...fusion_adapters.nc_program_template import capture
        inputs = button.parentCommand.commandInputs
        program = Programs.Current
        try:
            doc = Application.get().activeDocument
            template = capture(program._program, doc.name if doc else "")
            store.save(template)
        except Exception as e:
            _status(inputs, Strings("Couldn't save the template: {error}").format(error=e))
            return
        entry = _entry()
        if entry is not None:
            entry.reload(template)
            _status(inputs, Strings("Saved from {name}.").format(name=program.name))
        else:
            try:
                entry = _make_entry(template, Programs._cam, doc.name if doc else "", True)
                Programs._items.append(entry)
                dropdown = inputs.itemById(PROGRAM_DROPDOWN_ID)
                if dropdown is not None:
                    dropdown.listItems.add(entry.name, False)
            except Exception as e:
                Utils.log(f"Z1 template entry not added: {e}", LogLevels.WarningLogLevel)
            _status(inputs, Strings("Saved from {name}. \"{entry}\" is now the last choice in the NC Program list.")
                    .format(name=program.name, entry=store.dropdown_label(True)))
        _refresh(inputs)

    def on_remove(button) -> None:
        inputs = button.parentCommand.commandInputs
        if getattr(Programs.Current, "is_template", False):
            _status(inputs, Strings("Pick another NC Program on the Post tab first; the template is the one selected."))
            return
        store.clear()
        entry = _entry()
        if entry is not None:
            Programs._items.remove(entry)
            dropdown = inputs.itemById(PROGRAM_DROPDOWN_ID)
            if dropdown is not None:
                for i in range(dropdown.listItems.count):
                    if dropdown.listItems.item(i).name == entry.name:
                        dropdown.listItems.item(i).deleteMe()
                        break
        _status(inputs, Strings("Template removed."))
        _refresh(inputs)

    EventRegistry.register(SAVE_ID, on_save)
    EventRegistry.register(REMOVE_ID, on_remove)
    EventRegistry.register(PROGRAM_DROPDOWN_ID, lambda dropdown: _refresh(dropdown.parentCommand.commandInputs))
    _refresh(more_tab.parentCommand.commandInputs)
