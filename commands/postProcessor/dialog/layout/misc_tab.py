# Modified for Z1 Post by jimmyvegas29, 2026-11-16 (GPL v2; see CHANGELOG.md). Original: Makera Community Fusion plugin by Moinois.
from typing import cast

from adsk.core import BoolValueCommandInput
from adsk.core import CommandInputs
from adsk.core import CommandInput
from adsk.core import DropDownStyles
from adsk.core import DropDownCommandInput
from adsk.core import StringValueCommandInput

from ...settings.settings import Settings
from ...strings import Strings
from ...programs import Programs

from ...setups.setups_context import SetupsContext

from ..event_registry import EventRegistry
from ..constants import Constants
from ..state import is_find_pattern_valid

from .input_tab import InputTab

class MiscTab(Constants):
    @classmethod
    def create(cls, miscTab, inputs: CommandInputs, ctx: SetupsContext):
        """More tab: language, rename setups (closed), and saving every setting as the defaults.
        Always enabled: none of it needs an NC program. (The old Misc tab's enable handler switched the
        Output tab by mistake.)"""

        #region Language dropdown
        languageDropdown = miscTab.children.addDropDownCommandInput(cls.LANGUAGE_ID, Strings("Language"), cast(DropDownStyles, DropDownStyles.TextListDropDownStyle))
        languageDropdown.tooltip = Strings("TOOLTIP: Language")
        languageDropdown.tooltipDescription = (Strings("TOOLTIP TEXT: Language {fileVersion}")).format(fileVersion = Strings.file_version)

        languageTexts = Strings.available_languages()

        for language in languageTexts:
            languageDropdown.listItems.add(languageTexts[language], language == Settings(Settings.LANGUAGE))

        EventRegistry.register(cls.LANGUAGE_ID, lambda dropdown: Settings(Settings.LANGUAGE, Strings.language_setting(dropdown.selectedItem.name)))
        #endregion


        from .template_section import create as create_template_group
        create_template_group(miscTab)  # "Z1 template" group

        group = miscTab.children.addGroupCommandInput("renameSetupsBox", Strings("Rename setups"))
        group.isExpanded = False

        #region Use regex checkbox
        useRegex = group.children.addBoolValueInput(cls.USE_REGEX_ID, Strings("Use Python regular expressions"), True, "", bool(Settings(Settings.USE_REGEX)))
        useRegex.tooltip = Strings("TOOLTIP: Use Python regular expressions")
        useRegex.tooltipDescription = Strings("TOOLTIP TEXT: Use Python regular expressions")

        EventRegistry.register(cls.USE_REGEX_ID, lambda input: Settings.set(Settings.USE_REGEX, input.value))
        #endregion

        #region Find string input
        findText = group.children.addStringValueInput(cls.FIND_STRING_ID, Strings("Find"), str(Settings(Settings.FIND_STRING)))
        findText.tooltip = Strings("TOOLTIP: Search for this string")
        findText.tooltipDescription = Strings("TOOLTIP TEXT: Search for this string")
        EventRegistry.register(cls.FIND_STRING_ID, lambda input: Settings.set(Settings.FIND_STRING, input.value))
        #endregion

        #region Replace string input
        replaceText = group.children.addStringValueInput(cls.REPLACE_STRING_ID, Strings("Replace with"), Settings(Settings.REPLACE_STRING))
        replaceText.tooltip = Strings("TOOLTIP: Replace with this string")
        replaceText.tooltipDescription = Strings("TOOLTIP TEXT: Replace with this string")
        EventRegistry.register(cls.REPLACE_STRING_ID, lambda input: Settings.set(Settings.REPLACE_STRING, input.value))
        #endregion

        #region Only selected Setups checkbox
        replaceOnlySelected = group.children.addBoolValueInput(cls.REPLACE_ONLY_SELECTED_ID, Strings("Only the selected setups"),  True, "", Settings(Settings.REPLACE_ONLY_SELECTED))
        replaceOnlySelected.tooltip = Strings("TOOLTIP: Only selected Setups")
        replaceOnlySelected.tooltipDescription = Strings("TOOLTIP TEXT: Only selected Setups")
        EventRegistry.register(cls.REPLACE_ONLY_SELECTED_ID, lambda input: Settings.set(Settings.REPLACE_ONLY_SELECTED, input.value))
        #endregion

        def validateFindPattern(input: CommandInput):
            values = input.parentCommand.commandInputs
            findInput = StringValueCommandInput.cast(values.itemById(cls.FIND_STRING_ID))
            regexInput = BoolValueCommandInput.cast(values.itemById(cls.USE_REGEX_ID))
            findInput.isValueError = not is_find_pattern_valid(findInput.value, regexInput.value)

        EventRegistry.register(cls.FIND_STRING_ID, validateFindPattern)
        EventRegistry.register(cls.USE_REGEX_ID, validateFindPattern)
        validateFindPattern(findText)

        #region Replace button
        replaceButton = group.children.addBoolValueInput(cls.REPLACE_ID, "   " + Strings("Rename") + "   ", False) #l-/rjust() to widen the button some
        replaceButton.isFullWidth = True
        replaceButton.tooltip = Strings("TOOLTIP: Search and replace")
        replaceButton.tooltipDescription = Strings("TOOLTIP TEXT: Search and replace")
        
        def replaceButtonHandler(input: BoolValueCommandInput):
            values = input.parentCommand.commandInputs
            if input.value:
                find = StringValueCommandInput.cast(values.itemById(cls.FIND_STRING_ID)).value
                useRegex = BoolValueCommandInput.cast(values.itemById(cls.USE_REGEX_ID)).value
                if not is_find_pattern_valid(find, useRegex):
                    validateFindPattern(input)
                    input.value = False
                    return
                ctx.rename_setups(
                    find,
                    StringValueCommandInput.cast(values.itemById(cls.REPLACE_STRING_ID)).value, 
                    useRegex,
                    BoolValueCommandInput.cast(values.itemById(cls.REPLACE_ONLY_SELECTED_ID)).value
                )
                input.value = False # reset button state after operation

        EventRegistry.register(cls.REPLACE_ID, replaceButtonHandler)
        EventRegistry.register(cls.REPLACE_ID, lambda input: InputTab._updateSetups(input, ctx))
        #endregion

        #region Save as default button (one, here, instead of under every tab)
        saveButton = miscTab.children.addBoolValueInput(cls.SAVE_ID, "   " + Strings("Save all settings as my defaults") + "   ", False)
        saveButton.tooltip = Strings("TOOLTIP: Save as default settings")
        saveButton.tooltipDescription = Strings("TOOLTIP TEXT: Save as default settings")
        saveButton.isFullWidth = True
        saveButton.isEnabled = False

        EventRegistry.register(cls.SAVE_ID, lambda input: Settings.save_default())

        def setSaveButtonEnabled(input: CommandInput):
            input.parentCommand.commandInputs.itemById(cls.SAVE_ID).isEnabled = Programs.Current is not None

        EventRegistry.register(cls.PROGRAM_DROPDOWN_ID, setSaveButtonEnabled)
        setSaveButtonEnabled(inputs.itemById(cls.PROGRAM_DROPDOWN_ID))

        hint = miscTab.children.addTextBoxCommandInput('moreHint', '', '', 2, True)
        hint.isFullWidth = True
        hint.formattedText = '<span style="color:#808080">' + Strings("Settings are also kept with each document, as before. The Send to the Z1 settings are kept for this computer.") + '</span>'
        #endregion
