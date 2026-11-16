from typing import cast
from adsk.core import DropDownStyles, TableCommandInput, TextBoxCommandInput
import html
from adsk.core import MessageBoxButtonTypes
from adsk.core import MessageBoxIconTypes
from adsk.core import DialogResults
from adsk.core import CommandInput
from adsk.core import TabCommandInput
from adsk.core import BoolValueCommandInput
from adsk.core import DropDownCommandInput
from adsk.core import Application

from .....lib.fusionAddInUtils.general_utils import Utils

from ...const import Const
from ...settings.settings import Settings

from ...programs import Programs
from ...setups.setups import a_axis_rotation_required
from ...setups.setups_context import SetupsContext
from ...setups.setup.setup import Setup
from ...strings import Strings

from ..constants import Constants
from ..event_registry import EventRegistry
from .setup_table import ENABLED, SELECTED, apply_row_state, get_row_state

class InputTab(Constants):

    previous = None

    @classmethod
    def create(cls, inputTab, inputs, ctx: SetupsContext):
        """Top of the Post tab: NC program, one line naming the machine and post, and the setups table."""

        # helper method to make the syntax a little easier for adding 
        # items to a table.
        def init(obj, **attrs):
            for k, v in attrs.items():
                setattr(obj, k, v)
            return obj

        #region Program dropdown
        programDropdown = inputTab.children.addDropDownCommandInput(cls.PROGRAM_DROPDOWN_ID, Strings('NC Program'), DropDownStyles.TextListDropDownStyle)
        programDropdown.tooltip = Strings("TOOLTIP: NC Program to Use")
        programDropdown.tooltipDescription = Strings("TOOLTIP TEXT: NC Program to Use")

        EventRegistry.register(cls.PROGRAM_DROPDOWN_ID, cls._onProgramChanged)

        # Populate the dropdown with available programs
        for program in Programs:
            if not program.has_error and not program.is_empty and not program.is_suppressed:
                programDropdown.listItems.add(program.name, Settings(Settings.NC_PROGRAM) == program.name)
        programDropdown.isEnabled = True
        #endregion

        #region Machine and post processor: one read-only line under the program
        machineLine = inputTab.children.addTextBoxCommandInput(cls.MACHINE_ID, '', '', 1, True)
        machineLine.isFullWidth = True
        machineLine.tooltip = Strings("TOOLTIP: Machine")
        machineLine.tooltipDescription = Strings("TOOLTIP TEXT: Machine")

        def setMachineLine(programDropdown):
            line = TextBoxCommandInput.cast(programDropdown.parentCommand.commandInputs.itemById(cls.MACHINE_ID))
            program = Programs.Current
            if program is None:
                text = Strings('<Select a program>')
            elif not program.has_machine:
                text = Strings('<Select a program with a machine configuration>')
            elif not program.has_post_processor:
                text = f"{program.machine_name} · " + Strings('<Select a program with a post processor>')
            else:
                text = f"{program.machine_name} · {program.post_processor_description}"
            line.formattedText = f'<span style="color:#808080">{html.escape(text)}</span>'

        EventRegistry.register(cls.PROGRAM_DROPDOWN_ID, setMachineLine)
        setMachineLine(programDropdown)
        #endregion

        #region Setups table
        setupsTable = TableCommandInput.cast(inputTab.children.addTableCommandInput('SetupsTable', '', 3, "8:52:40")) # checkbox, setup name, check
        setupsTable.minimumVisibleRows = 3
        setupsTable.maximumVisibleRows = min(10, max(3, len([setup for setup in ctx.valid]) + 1)) # +1 for the header row

        selectAllSetups = inputs.addBoolValueInput(cls.SELECT_ALL_SETUPS_ID, '', True, '', False)

        def setAllSetups(checkbox):
            for setup in ctx.valid:
                setup.select(checkbox.value)
            cls._updateSetups(checkbox, ctx) # Update the table to enable/disable inputs based on the new selection
            
        EventRegistry.registerWithOnlyChange(cls.SELECT_ALL_SETUPS_ID, setAllSetups) # For some reason the checkbox generates duplicate events, so we use a special registry method that ignores duplicates. See EventRegistry for details.

        row = 0
        # Add header row
        setupsTable.addCommandInput(selectAllSetups, row, 0)
        setupsTable.addCommandInput(
                init(inputs.addStringValueInput('', '', Strings('Setup')),
                isReadOnly = True
            ), row, 1)
        checkHeader = init(inputs.addStringValueInput('', '', Strings('Check')), isReadOnly = True)
        checkHeader.tooltip = Strings("TOOLTIP: Setup check")
        checkHeader.tooltipDescription = Strings("TOOLTIP TEXT: Setup check")
        setupsTable.addCommandInput(checkHeader, row, 2)
        
        # Creating callback for when a setup selection has changed and the table needs update.
        def onSetupChanged(checkbox):
            setupIndex = int(checkbox.id.replace("setupSelected_", ""))
            setup = next((s for s in ctx.valid if s.index == setupIndex), None)
            if setup and setup.is_selected != checkbox.value:
                Utils.log(f'Updating setup selection from dialog: {setup.name} selected={checkbox.value}')
                setup.select(checkbox.value)
                cls._updateSetups(checkbox, ctx) # Update the table to enable/disable inputs based on the new selection
                EventRegistry.setValue(cls.SELECT_ALL_SETUPS_ID, areAllSetupsSelected(checkbox.parentCommand.commandInputs))

        def areAllSetupsSelected(inputs) -> bool:
            for setup in ctx.valid:
                checkbox = inputs.itemById(f"setupSelected_{setup.index}")
                if checkbox is None: # Should not happen...
                    return False
                if not checkbox.isEnabled:
                    continue
                if not checkbox.value:
                    return False
            return True
        
        # Wiring up event so that when the A-axis option is changed, 
        # the checkbox enabling de-/selecting all enabled setups is 
        # updated to reflect the new state.
        EventRegistry.register(cls.ROTATE_A_AXIS_ID, lambda input: EventRegistry.setValue(cls.SELECT_ALL_SETUPS_ID, areAllSetupsSelected(input.parentCommand.commandInputs)))
        
        def updateSetupsWithNotice(input: BoolValueCommandInput):
            needsRotation, rotatedSetups = a_axis_rotation_required(ctx)
            if needsRotation and not input.value:
                TabCommandInput.cast(input.parentCommand.commandInputs.itemById(cls.INPUT_SELECTION_TAB_ID)).activate()
                app = Application.get()
                ui = app.userInterface
                if ui.messageBox(
                        Strings("Some setups will be deselected as they are rotated. <p>Rotated setups:<ul>{rotatedSetups}</ul><p>Do you want to continue?")
                            .format(rotatedSetups = ''.join([Strings("<li>{name}: {degrees}°</li>")
                                                            .format(name=name, degrees=degrees) for name, degrees in rotatedSetups])),
                        Const.CMD_NAME,
                        cast(MessageBoxButtonTypes, MessageBoxButtonTypes.OKCancelButtonType),
                        cast(MessageBoxIconTypes, MessageBoxIconTypes.InformationIconType)) != DialogResults.DialogOK:
                    input.value = not input.value # revert the change if user cancels
            cls._updateSetups(input, ctx)

        EventRegistry.register(cls.ROTATE_A_AXIS_ID, updateSetupsWithNotice) # If the Rotate A-Axis option is changed, some setups may become ineligible for selection and need to be updated in the table.

        # Add setup rows
        for setup in ctx.valid:
            row += 1
            id = f"setupSelected_{setup.index}"
            setupCheckbox = inputs.addBoolValueInput(id, '', True, '', setup.is_selected)
            EventRegistry.register(id, onSetupChanged)
            setupsTable.addCommandInput(setupCheckbox, row, 0)
            setupsTable.addCommandInput(
                init(inputs.addStringValueInput(f"setupName_{setup.index}", '', setup.name),
                    isReadOnly = True,
                    isEnabled = setup.is_selected
                ),row,1)
            setupsTable.addCommandInput(
                init(inputs.addStringValueInput(f"setupCheck_{setup.index}", '', ''),
                    isReadOnly = True
                ),row,2)

        def updateSetupswithoutNotice(input: DropDownCommandInput):
            cls._updateSetups(input, ctx)
        
        EventRegistry.register(cls.PROGRAM_DROPDOWN_ID, updateSetupswithoutNotice)
        #endregion

    @classmethod
    def _onProgramChanged(cls, dropdown: DropDownCommandInput):
        selectedItem = dropdown.selectedItem
        if selectedItem:
            program = next((prog for prog in Programs if prog.name == selectedItem.name), None)
            if program:
                if(program.has_error):
                    return

                Programs.Current = program
                Utils.log(f'Selected NC program: {program.name}')

                if Programs.Current.has_warning:
                    app = Application.get()
                    ui = app.userInterface
                    ui.messageBox(Strings("The selected NC Program has the following warning:\n{warning}").format(warning = Programs.Current.warning),
                                                    Const.CMD_NAME,
                                                    cast(MessageBoxButtonTypes, MessageBoxButtonTypes.OKButtonType))


                Settings(Settings.NC_PROGRAM, program.name)

    @classmethod
    def _updateSetups(cls, input: CommandInput, ctx: SetupsContext):
        """Updates the setups table in the dialog, enabling/disabling 
        rows and setting values based on the selected program and 
        settings."""
        inputs = input.parentCommand.commandInputs
        rotateAAxisCheckbox = BoolValueCommandInput.cast(inputs.itemById(cls.ROTATE_A_AXIS_ID))
        rotateAAxisCheckbox.isEnabled = False if Programs.Current is None else Programs.Current.machine_has_a_axis

        validProgram = Programs.Current is not None and Programs.Current.has_machine

        firstSetup: Setup | None = None
        allSelectableSelected = True
        for setup in ctx.valid:
            rotation = 0 if firstSetup is None else round(setup.rotation_relative_to_degrees(firstSetup), 3)
            rowState = get_row_state(
                setup,
                has_reference=firstSetup is not None,
                valid_program=validProgram,
                same_origin=setup.origin.isEqualTo(firstSetup.origin) if firstSetup is not None else True,
                parallel_x_axis=setup.x_normal.isParallelTo(firstSetup.x_normal) if firstSetup is not None else True,
                can_rotate=rotateAAxisCheckbox.value,
                rotation=rotation,
                machine_has_a_axis=Programs.Current is not None and Programs.Current.machine_has_a_axis,
            )

            apply_row_state(inputs, rowState)
            if rowState[ENABLED] and not rowState[SELECTED]:
                allSelectableSelected = False
            
            setup.select(rowState[SELECTED]) # Update the setup's selected state based on the value in the table, which may have been changed if the setup became ineligible for selection

            if firstSetup is None and setup.is_selected:
                firstSetup = setup

        selectAll = BoolValueCommandInput.cast(inputs.itemById(cls.SELECT_ALL_SETUPS_ID))
        if selectAll is not None and selectAll.value != allSelectableSelected:
            EventRegistry.setValue(cls.SELECT_ALL_SETUPS_ID, allSelectableSelected)
            selectAll.value = allSelectableSelected
