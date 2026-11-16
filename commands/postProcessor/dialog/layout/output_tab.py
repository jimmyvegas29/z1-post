# Modified for Z1 Post by jimmyvegas29, 2026-11-16 (GPL v2; see CHANGELOG.md). Original: Makera Community Fusion plugin by Moinois.
from pathlib import Path
from adsk.core import Application
from adsk.core import BoolValueCommandInput
from adsk.core import CommandInput
from adsk.core import DialogResults
from adsk.core import DropDownCommandInput
from adsk.core import StringValueCommandInput
from adsk.core import TablePresentationStyles
from adsk.core import IntegerSliderCommandInput

from ...settings.settings import Settings
from ...strings import Strings

from ..event_registry import EventRegistry
from ..state import is_output_folder_valid, is_output_name_valid, numeric_name_digits
from ...programs import Programs

from ..constants import Constants
from .output_grouping_section import create_files_and_replace

class OutputTab(Constants):
    @classmethod
    def create_post_part(cls, outputTab, inputs):
        """Post tab: where the files go ("Save to"), the file name, how they are split ("Files") and
        "Replace files that already exist"."""
        programDropdown = inputs.itemById(cls.PROGRAM_DROPDOWN_ID)

        #region -- Output folder table --
        outputFolderTable = outputTab.children.addTableCommandInput(cls.OUTPUT_FOLDER_TABLE_ID, Strings('Output folder'), 2, '90:10')
        outputFolderTable.minimumVisibleRows = 2
        outputFolderTable.maximumVisibleRows = 2
        outputFolderTable.tablePresentationStyle = TablePresentationStyles.transparentBackgroundTablePresentationStyle

        #region Output folder label, spans 2 columns
        outputFolderLabel = inputs.addStringValueInput(cls.OUTPUT_FOLDER_LABEL_ID, '', Strings("Save to"))
        outputFolderLabel.tooltip = Strings("TOOLTIP: Output folder")
        outputFolderLabel.tooltipDescription = Strings("TOOLTIP TEXT: Output folder")
        outputFolderLabel.isReadOnly = True
        outputFolderTable.addCommandInput(outputFolderLabel, 0, 0, 0, 2)

        #endregion

        #region Output folder string input

        outputFolder = inputs.addStringValueInput(cls.OUTPUT_FOLDER_ID, Strings("Output folder"), Strings("<Select program>"))
        outputFolder.tooltip = Strings("TOOLTIP: Output folder")
        outputFolder.tooltipDescription = Strings("TOOLTIP TEXT: Output folder")
        outputFolder.isReadOnly = False

        def setoutputFolder(dropdown: DropDownCommandInput):
            input = StringValueCommandInput.cast(dropdown.parentCommand.commandInputs.itemById(cls.OUTPUT_FOLDER_ID))
            try:
                if input.isValid: # Apparently the input can become invalid when the program is changed, so we check if it's valid before trying to set the value
                    newValue =  str(Programs.Current.get_output_folder().resolve()) if Programs.Current else Strings("<Select program>")
                    if input.value != newValue:
                        input.value = newValue
            except RuntimeError:
                pass # Every now and then the setting of the value gets an error that the object is no longer valid. Ignore and move on for now.           

        EventRegistry.register(cls.PROGRAM_DROPDOWN_ID, setoutputFolder)
        setoutputFolder(programDropdown) # initialize state based on current program selection

        def applyOutputFolder(stringInput: StringValueCommandInput):
            valid = is_output_folder_valid(stringInput.value)
            stringInput.isValueError = not valid
            if valid and Programs.Current is not None:
                Programs.Current.set_output_folder(Path(stringInput.value).expanduser())

        # Fusion delivers StringValueCommandInput changes when editing is
        # committed (normally when focus leaves the field).
        EventRegistry.register(cls.OUTPUT_FOLDER_ID, applyOutputFolder)

        outputFolderTable.addCommandInput(outputFolder, 1, 0)
        #endregion

        #region Output folder browse button

        openFolderDialogButton = inputs.addBoolValueInput(cls.OUTPUT_FOLDER_BUTTON_ID, '  …  ', False, '', False)

        outputFolderTable.addCommandInput(openFolderDialogButton, 1, 1)

        def openFolderDialog(button: BoolValueCommandInput):
            inputs = button.parentCommand.commandInputs
            app: Application = Application.get()
            ui = app.userInterface
            dialog = ui.createFolderDialog()

            dialog.initialDirectory = StringValueCommandInput.cast(inputs.itemById(cls.OUTPUT_FOLDER_ID)).value
            dialog.title = Strings("Select Output Folder")
            if dialog.showDialog() != DialogResults.DialogOK:
                return
            folder = dialog.folder
            if folder and Programs.Current is not None:
                Programs.Current.set_output_folder(Path(folder))
                StringValueCommandInput.cast(inputs.itemById(cls.OUTPUT_FOLDER_ID)).value = folder

        EventRegistry.register(cls.OUTPUT_FOLDER_BUTTON_ID, openFolderDialog)

        #endregion
        #endregion

        #region File name string input
        fileName = outputTab.children.addStringValueInput(cls.FILE_NAME_ID, Strings("File name"), Strings("<Select program>"))
        fileName.tooltip = Strings("TOOLTIP: File name")
        fileName.tooltipDescription = Strings("TOOLTIP TEXT: File name")

        def setFilename(stringInput: StringValueCommandInput):
            if Programs.Current is not None:
                Programs.Current.set_file_name(stringInput.value)

        EventRegistry.register(cls.FILE_NAME_ID, setFilename)

        def getFileNameFromProgram(dropdown: DropDownCommandInput):
            fileName = Programs.Current.file_name if Programs.Current is not None and Programs.Current.file_name is not None else Strings("<Select program>")
            StringValueCommandInput.cast(dropdown.parentCommand.commandInputs.itemById(cls.FILE_NAME_ID)).value = fileName

        EventRegistry.register(cls.PROGRAM_DROPDOWN_ID, getFileNameFromProgram)
        getFileNameFromProgram(programDropdown) # initialize state based on current program selection

        #endregion

        create_files_and_replace(outputTab, cls)
