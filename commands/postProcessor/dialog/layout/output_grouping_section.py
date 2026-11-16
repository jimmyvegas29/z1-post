# Modified for Z1 Post by jimmyvegas29, 2026-11-16 (GPL v2; see CHANGELOG.md). Original: Makera Community Fusion plugin by Moinois.
from adsk.core import BoolValueCommandInput, DropDownCommandInput, DropDownStyles

from ...settings.settings import Settings
from ...strings import Strings
from ..event_registry import EventRegistry
from ..state import can_combine_tools


def _grouping_values() -> dict:
    return {
        Strings("One file"): Settings.OperationsGroupings.SINGLE_FILE,
        Strings("One per setup"): Settings.OperationsGroupings.SETUP,
        Strings("One per setup and tool"): Settings.OperationsGroupings.SETUP_AND_TOOL,
        Strings("One per operation"): Settings.OperationsGroupings.PER_OPERATION,
    }


def create_files_and_replace(post_tab, constants) -> None:
    """Post tab: the "Files" dropdown (operations grouping) and "Replace files that already exist"."""
    grouping_values = _grouping_values()
    grouping_input = post_tab.children.addDropDownCommandInput(
        constants.OPERATIONS_GROUPING_ID,
        Strings("Files"),
        DropDownStyles.TextListDropDownStyle,
    )
    grouping_input.tooltip = Strings("TOOLTIP: Operations grouping")
    grouping_input.tooltipDescription = Strings("TOOLTIP TEXT: Files")
    for label, value in grouping_values.items():
        grouping_input.listItems.add(
            label,
            value == Settings(Settings.OPERATIONS_GROUPING),
        )
    EventRegistry.register(
        constants.OPERATIONS_GROUPING_ID,
        lambda dropdown: Settings.set(
            Settings.OPERATIONS_GROUPING,
            grouping_values[dropdown.selectedItem.name],
        ),
    )

    overwrite = post_tab.children.addBoolValueInput(
        constants.OVERWRITE_EXISTING_FILES_ID,
        Strings("Replace files that already exist"),
        True,
        "",
        bool(Settings(Settings.OVERWRITE_FILES)),
    )
    overwrite.tooltip = Strings("TOOLTIP: Overwrite existing files")
    overwrite.tooltipDescription = Strings("TOOLTIP TEXT: Overwrite existing files")
    overwrite.isEnabled = True
    EventRegistry.register(
        constants.OVERWRITE_EXISTING_FILES_ID,
        lambda checkbox: Settings.set(Settings.OVERWRITE_FILES, checkbox.value),
    )


def create_name_options(names_tab, constants) -> None:
    """File names tab: combine same-tool operations, no subfolders, empty the output folder first.
    The "Files" dropdown and the Replace checkbox they depend on are on the Post tab (built first)."""
    grouping_values = _grouping_values()

    combine_tools = names_tab.children.addBoolValueInput(
        constants.COMBINE_TOOLS_ID,
        Strings("Combine operations that use the same tool"),
        True,
        "",
        Settings(Settings.COMBINE_TOOL),
    )
    combine_tools.tooltip = Strings("TOOLTIP: Combine operations using same tool")
    combine_tools.tooltipDescription = Strings("TOOLTIP TEXT: Combine operations using same tool")
    EventRegistry.register(
        constants.COMBINE_TOOLS_ID,
        lambda checkbox: Settings(Settings.COMBINE_TOOL, checkbox.value),
    )

    def update_combine_tools(dropdown) -> None:
        dropdown = DropDownCommandInput.cast(dropdown)
        combine = BoolValueCommandInput.cast(
            dropdown.parentCommand.commandInputs.itemById(constants.COMBINE_TOOLS_ID)
        )
        if dropdown.selectedItem is None or combine is None:
            return
        grouping = grouping_values[dropdown.selectedItem.name]
        enabled = can_combine_tools(grouping, Settings.OperationsGroupings)
        combine.isEnabled = enabled
        if not enabled:
            combine.value = False
            Settings(Settings.COMBINE_TOOL, False)

    grouping_input = names_tab.parentCommand.commandInputs.itemById(constants.OPERATIONS_GROUPING_ID)
    EventRegistry.register(constants.OPERATIONS_GROUPING_ID, update_combine_tools)
    update_combine_tools(grouping_input)

    flat_structure = names_tab.children.addBoolValueInput(
        constants.FLAT_FILE_STRUCTURE_ID,
        Strings("No subfolders (flat)"),
        True,
        "",
        Settings(Settings.FLAT_FILE_STRUCTURE),
    )
    flat_structure.tooltip = Strings("TOOLTIP: Flatten the file structure")
    flat_structure.tooltipDescription = Strings("TOOLTIP TEXT: Flatten the file structure")
    EventRegistry.register(
        constants.FLAT_FILE_STRUCTURE_ID,
        lambda checkbox: Settings.set(Settings.FLAT_FILE_STRUCTURE, checkbox.value),
    )

    clear_folder = names_tab.children.addBoolValueInput(
        constants.CLEAR_OUTPUT_FOLDER_ID,
        Strings("Empty the output folder first"),
        True,
        "",
        bool(Settings(Settings.CLEAR_FOLDER)),
    )
    clear_folder.tooltip = Strings("TOOLTIP: Clear output folder")
    clear_folder.tooltipDescription = Strings("TOOLTIP TEXT: Clear output folder")

    def update_clear_folder(checkbox) -> None:
        inputs = checkbox.parentCommand.commandInputs
        replace = BoolValueCommandInput.cast(inputs.itemById(constants.OVERWRITE_EXISTING_FILES_ID))
        clear_input = BoolValueCommandInput.cast(inputs.itemById(constants.CLEAR_OUTPUT_FOLDER_ID))
        if replace is None or clear_input is None:
            return
        clear_input.isEnabled = replace.value
        if not replace.value:
            Settings(Settings.CLEAR_FOLDER, False)
            clear_input.value = False

    EventRegistry.register(
        constants.CLEAR_OUTPUT_FOLDER_ID,
        lambda checkbox: Settings.set(Settings.CLEAR_FOLDER, checkbox.value),
    )
    EventRegistry.register(constants.OVERWRITE_EXISTING_FILES_ID, update_clear_folder)
    update_clear_folder(clear_folder)
