from adsk.core import Command

from ...setups.setups_context import SetupsContext

from ..event_registry import EventRegistry

from ...strings import Strings

from ..constants import Constants
from .input_tab import InputTab
from .gcode_tab import GCodeTab
from .output_tab import OutputTab
from .file_names_tab import FileNamesTab
from .misc_tab import MiscTab
from . import send_section

class PostDialogLayout(Constants):
    """Four tabs (2026-11-16 layout, see fusion_addins/mockups/post_dialog_mock.html in the Z1 project):
    Post (everything a normal post needs, plus Send to the Z1), File names, G-code, More.

    The tabs are created first and filled afterwards, because inputs on one tab refer to inputs on
    another (the File names tab reads the Post tab's file name, "Files" and "Replace" inputs)."""

    @classmethod
    def createLayout(cls, command: Command, ctx: SetupsContext):

        EventRegistry.clear()  # drop handlers left from earlier openings of the dialog

        command.setDialogMinimumSize(420, 560)
        command.setDialogInitialSize(420, 640)
        command.okButtonText = send_section.ok_button_text()
        command.cancelButtonText = Strings("Close")

        # https://help.autodesk.com/view/fusion360/ENU/?contextId=CommandInputs
        inputs = command.commandInputs

        postTab = inputs.addTabCommandInput(cls.INPUT_SELECTION_TAB_ID, Strings("Post"))
        namesTab = inputs.addTabCommandInput(cls.OUTPUT_GROUP_ID, Strings("File names"))
        gcodeTab = inputs.addTabCommandInput(cls.GCODE_OPTIONS_GROUP_ID, Strings("G-code"))
        moreTab = inputs.addTabCommandInput(cls.RENAME_SETUPS_GROUP_ID, Strings("More"))
        postTab.activate()

        InputTab.create(postTab, inputs, ctx)          # NC program, machine line, setups
        OutputTab.create_post_part(postTab, inputs)    # Save to, File name, Files, Replace
        send_section.create(postTab)                   # Send to the Z1
        GCodeTab.create(gcodeTab)                      # holds Rotate A, which the setups table reads
        FileNamesTab.create(namesTab, inputs)
        MiscTab.create(moreTab, inputs, ctx)

        InputTab._updateSetups(inputs.itemById(cls.PROGRAM_DROPDOWN_ID), ctx) # initialize table state based on current program selection
