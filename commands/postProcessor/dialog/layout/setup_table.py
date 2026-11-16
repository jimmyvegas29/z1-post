from typing import Any

from ...strings import Strings
from ..state import is_setup_selectable


INDEX = "index"
ENABLED = "enabled"
SELECTED = "selected"
NAME = "name"
ORIGIN = "origin"
X_NORMAL = "xNormal"
ROTATION = "rotation"
CHECK = "check"


def get_row_state(
    setup: Any,
    *,
    has_reference: bool,
    valid_program: bool,
    same_origin: bool,
    parallel_x_axis: bool,
    can_rotate: bool,
    rotation: float,
    machine_has_a_axis: bool,
) -> dict[str, Any]:
    selectable = is_setup_selectable(
        has_reference=has_reference,
        valid_program=valid_program,
        same_origin=same_origin,
        parallel_x_axis=parallel_x_axis,
        can_rotate=can_rotate,
        required_rotation=rotation,
        machine_has_a_axis=machine_has_a_axis,
    )
    selected = setup.is_selected if selectable else False

    if has_reference:
        origin_text = Strings("Same") if same_origin else Strings("Different")
        x_normal_text = Strings("Aligned") if parallel_x_axis else Strings("Misaligned")
        rotation_text = f"{rotation}°" if parallel_x_axis else ""
    else:
        origin_text = x_normal_text = rotation_text = (
            Strings("(reference)") if selected else "-"
        )

    if not has_reference:
        check_text = Strings("reference") if selected else ""
    else:
        problems = []
        if not same_origin:
            problems.append(Strings("other origin"))
        if not parallel_x_axis:
            problems.append(Strings("X not parallel"))
        elif rotation != 0:
            problems.append(Strings("A {degrees}°").format(degrees=f"{rotation:g}"))
        if not problems:
            check_text = Strings("OK") if selectable else ""
        else:
            check_text = ", ".join(problems)

    return {
        CHECK: check_text,
        INDEX: setup.index,
        NAME: setup.name,
        ENABLED: selectable,
        SELECTED: selected,
        ORIGIN: origin_text,
        X_NORMAL: x_normal_text,
        ROTATION: rotation_text,
    }


def apply_row_state(inputs: Any, row_state: dict[str, Any]) -> None:
    from adsk.core import BoolValueCommandInput, StringValueCommandInput

    index = row_state[INDEX]
    checkbox = BoolValueCommandInput.cast(inputs.itemById(f"setupSelected_{index}"))
    name = StringValueCommandInput.cast(inputs.itemById(f"setupName_{index}"))
    check = StringValueCommandInput.cast(inputs.itemById(f"setupCheck_{index}"))

    checkbox.isEnabled = row_state[ENABLED]
    name.value = row_state[NAME]
    name.isEnabled = row_state[ENABLED]
    # The check stays readable on a greyed-out row: it says why the setup can't be picked.
    check.isEnabled = True

    checkbox.value = row_state[SELECTED]
    check.value = row_state[CHECK]
