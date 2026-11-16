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
from .output_grouping_section import create_name_options

class FileNamesTab(Constants):
    @classmethod
    def create(cls, outputTab, inputs):
        """File names tab: numeric names, numbering, combining, subfolders, emptying the folder.
        Built after the Post tab, which holds the file name, "Files" and "Replace" inputs it refers to."""
        programDropdown = inputs.itemById(cls.PROGRAM_DROPDOWN_ID)

        def setTabEnabled(dropdown: DropDownCommandInput):
            dropdown.parentCommand.commandInputs.itemById(cls.OUTPUT_GROUP_ID).isEnabled = Programs.Current is not None

        EventRegistry.register(cls.PROGRAM_DROPDOWN_ID, setTabEnabled)
        setTabEnabled(programDropdown)
        fileName = inputs.itemById(cls.FILE_NAME_ID)

        #region Numeric name checkbox
        numericName = outputTab.children.addBoolValueInput(cls.NUMERIC_NAME_ID, Strings("Name must be numeric"), True, "", Settings(Settings.NUMERIC_NAME))
        numericName.tooltip = Strings("TOOLTIP: Name must be numeric")
        numericName.tooltipDescription = Strings("TOOLTIP TEXT: Name must be numeric")

        EventRegistry.register(cls.NUMERIC_NAME_ID, lambda checkbox: Settings.set(Settings.NUMERIC_NAME, checkbox.value))

        def ensureNumericFileName(input: CommandInput):
            textbox = StringValueCommandInput.cast(input.parentCommand.commandInputs.itemById(cls.FILE_NAME_ID))
            numeric = BoolValueCommandInput.cast(
                textbox.parentCommand.commandInputs.itemById(cls.NUMERIC_NAME_ID)
            ).value
            textbox.isValueError = not is_output_name_valid(textbox.value, numeric)

        EventRegistry.register(cls.FILE_NAME_ID, ensureNumericFileName)
        EventRegistry.register(cls.NUMERIC_NAME_ID, ensureNumericFileName)
        ensureNumericFileName(fileName) # initialize state based on current value after file name input is created to ensure that the file name is valid if "Name must be numeric" is selected

        #endregion

        #region Prepend sequence number checkbox
        prependFileNumber = outputTab.children.addBoolValueInput(cls.FILE_SEQUENCE_ID, Strings("Number the files"), True, "", Settings(Settings.FILE_SEQUENCE))
        prependFileNumber.tooltip = Strings("TOOLTIP: Prepend file sequence number")
        prependFileNumber.tooltipDescription = Strings("TOOLTIP TEXT: Prepend file sequence number")

        EventRegistry.register(cls.FILE_SEQUENCE_ID, lambda checkbox: Settings.set(Settings.FILE_SEQUENCE, checkbox.value))
        #endregion

        #region Numbering digits spinner input
        numberingDigits = outputTab.children.addIntegerSliderListCommandInput(cls.FILE_SEQUENCE_DIGITS_ID, Strings("Number of digits"), [1, 2, 3, 4, 5, 6])
        numberingDigits.valueOne = Settings(Settings.FILE_SEQUENCE_DIGITS)
        numberingDigits.tooltip = Strings("TOOLTIP: Number of file digits")
        numberingDigits.tooltipDescription = Strings("TOOLTIP TEXT: Number of file digits")

        def setNumberingDigitsEnabled(checkbox: BoolValueCommandInput):
            checkbox.parentCommand.commandInputs.itemById(cls.FILE_SEQUENCE_DIGITS_ID).isEnabled = checkbox.value

        def setNumberingDigitsOnNumericFileName(checkbox: BoolValueCommandInput):
            input = IntegerSliderCommandInput.cast(checkbox.parentCommand.commandInputs.itemById(cls.FILE_SEQUENCE_DIGITS_ID))
            prependFileNumbers = BoolValueCommandInput.cast(checkbox.parentCommand.commandInputs.itemById(cls.FILE_SEQUENCE_ID))
            fileNameInput = StringValueCommandInput.cast(checkbox.parentCommand.commandInputs.itemById(cls.FILE_NAME_ID))
            digits = numeric_name_digits(fileNameInput.value)
            if checkbox.value:
                if digits is not None:
                    Settings.set(Settings.FILE_SEQUENCE_DIGITS, digits)
                    input.valueOne = Settings(Settings.FILE_SEQUENCE_DIGITS)
                input.isEnabled = False
                prependFileNumbers.isEnabled = False
            else:
                prependFileNumbers.isEnabled = True
                input.isEnabled = prependFileNumbers.value

        def setNumberingDigitsOnFileName(textbox: StringValueCommandInput):
            inputs = textbox.parentCommand.commandInputs
            digits = numeric_name_digits(textbox.value)
            if (digits is not None
                    and BoolValueCommandInput.cast(inputs.itemById(cls.NUMERIC_NAME_ID)).value):
                Settings.set(Settings.FILE_SEQUENCE_DIGITS, digits)
                IntegerSliderCommandInput.cast(inputs.itemById(cls.FILE_SEQUENCE_DIGITS_ID)).valueOne = Settings(Settings.FILE_SEQUENCE_DIGITS)
            setNumberingDigitsOnNumericFileName(BoolValueCommandInput.cast(inputs.itemById(cls.NUMERIC_NAME_ID)))

        EventRegistry.register(cls.FILE_SEQUENCE_DIGITS_ID, lambda spinner: Settings.set(Settings.FILE_SEQUENCE_DIGITS, spinner.valueOne))
        EventRegistry.register(cls.NUMERIC_NAME_ID, setNumberingDigitsOnNumericFileName) # Disable numbering digits when "Name must be numeric" is enabled, as it doesn't make sense in that context
        EventRegistry.register(cls.FILE_SEQUENCE_ID, setNumberingDigitsEnabled)
        EventRegistry.register(cls.FILE_NAME_ID, setNumberingDigitsOnFileName) # Disable numbering digits when "Prepend sequence number" is disabled, as it doesn't make sense in that context
        setNumberingDigitsEnabled(prependFileNumber) # initialize state based on current checkbox value
        setNumberingDigitsOnNumericFileName(numericName)
        #endregion

        create_name_options(outputTab, cls)

        hint = outputTab.children.addTextBoxCommandInput('fileNamesHint', '', '', 2, True)
        hint.isFullWidth = True
        hint.formattedText = '<span style="color:#808080">' + Strings("Files sent to the Z1 are named <i>File name</i>_<i>Setup</i>, with _ for spaces.") + '</span>'
