# Modified for Z1 Post by jimmyvegas29, 2026-11-16 (GPL v2; see CHANGELOG.md). Original: Makera Community Fusion plugin by Moinois.
from pathlib import Path
from typing import Any

from .output_plan import plan_output_files
from .output_renderer import render_output_files
from .program_output import (
    ProgramOutputSettings,
    plan_program_output,
    prepare_output_folder,
)


def render_program_output(
    context: Any,
    output_path: Path,
    output_file_name: str | None,
    file_extension: str,
) -> tuple["WrittenFile", ...]:
    """Plan and stream every result file for one processing context. Returns the files written, each with
    the name it should get on the Z1 (z1send/naming.py)."""
    from .z1send.naming import written_files
    settings = context.processingSettings or context.capture_processing_settings()
    output_settings = ProgramOutputSettings(
        operationsGrouping=settings.operationsGrouping,
        flatFileStructure=settings.flatFileStructure,
        numericName=settings.numericName,
        clearFolder=settings.clearFolder,
    )
    prepare_output_folder(output_path, output_settings.clearFolder)

    context.set_file_extension(file_extension)
    layout = plan_program_output(output_path, output_file_name, output_settings)
    context.set_path(layout.path)
    context.set_file_name(layout.fileName)

    plans = plan_output_files(context, settings, context.sanitize_filename)
    render_output_files(plans, settings.overwriteFiles)
    return written_files(plans, output_file_name, settings.operationsGrouping, settings.numericName,
                         context.sanitize_filename)
