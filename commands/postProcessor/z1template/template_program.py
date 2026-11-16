# Z1 Post, by jimmyvegas29, 2026-11-16. GPL v2 (see LICENSE).
"""The "Z1 template" entry in the NC Program list.

It answers the dialog's questions (machine, post, A axis, file name, folder) from the saved template, without
touching the document. Only when you post does it create the real NC Program ("Z1 Post") in the document and
hand over to it; from then on that NC Program is used like any other, and it stays in the document.
"""
from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Optional

from . import store


class _FusionTemplateAdapter:
    """Default adapter; the Fusion calls live in fusion_adapters/nc_program_template.py."""

    def _mod(self):
        from ..fusion_adapters import nc_program_template
        return nc_program_template

    def find_machine(self, template):
        return self._mod().find_machine(template)

    def find_post(self, template):
        return self._mod().find_post(template)

    def create_nc_program(self, cam_product, template, name, operations, machine=None, post=None):
        return self._mod().create_nc_program(cam_product, template, name, operations, machine, post)

    def program_adapter(self):
        from ..fusion_adapters.program import FusionProgramAdapter
        return FusionProgramAdapter()


class TemplateProgram:
    def __init__(self, template: dict, cam_product: Any, label: str, document_name: str = "",
                 adapter: Any = None, program_factory: Optional[Callable[[Any], Any]] = None,
                 on_created: Optional[Callable[[Any], None]] = None):
        self.template = template
        self._cam = cam_product
        self._label = label
        self._adapter = adapter or _FusionTemplateAdapter()
        if program_factory is None:
            from ..program import Program
            program_factory = Program
        self._program_factory = program_factory
        self._on_created = on_created
        self._machine = self._adapter.find_machine(template)
        self._post = self._adapter.find_post(template)
        self._file_name = re.sub(r"\s+v\d+$", "", document_name or "") or "job"
        self._output_folder = Path(template.get("output_folder") or Path.home())
        self.created = None          # the real Program once posted
        self.failed_settings: list[str] = []

    def reload(self, template: dict) -> None:
        """A new template was saved while the dialog is open."""
        self.template = template
        self._machine = self._adapter.find_machine(template)
        self._post = self._adapter.find_post(template)
        if template.get("output_folder"):
            self._output_folder = Path(template["output_folder"])

    # --- what the dialog asks -------------------------------------------------------------------
    is_template = True
    has_error = False
    is_empty = False
    is_suppressed = False
    is_selected = False
    has_warning = False
    warning = ""

    @property
    def name(self) -> str:
        return self._label

    @property
    def template_note(self) -> str:
        if self._machine is None or self._post is None:
            return "Z1 template: its machine or post isn't on this computer (More tab)"
        return f"from your Z1 template · posting creates the NC Program \"{store.NC_PROGRAM_NAME}\""

    @property
    def has_machine(self) -> bool:
        return self._machine is not None and self._post is not None

    @property
    def machine_name(self) -> str:
        return self.template["machine"].get("model", "")

    @property
    def has_post_processor(self) -> bool:
        return self._post is not None

    @property
    def post_processor_description(self) -> str:
        return self.template["post"].get("description", "")

    @property
    def file_extension(self):
        if self._post is not None:
            return self._post.extension
        return self.template["post"].get("extension")

    def _capabilities(self):
        return SimpleNamespace(machine=self._machine)

    @property
    def machine_has_a_axis(self) -> bool:
        return self._machine is not None and self._adapter.program_adapter().machine_has_a_axis(self._capabilities())

    @property
    def machine_has_atc(self) -> bool:
        return self._machine is not None and self._adapter.program_adapter().machine_has_atc(self._capabilities())

    @property
    def machine_tool_slots(self) -> int:
        if self._machine is None:
            return 1
        return self._adapter.program_adapter().machine_tool_slots(self._capabilities())

    @property
    def file_name(self) -> str:
        return self._file_name

    def set_file_name(self, file_name: str) -> None:
        self._file_name = file_name

    def get_output_folder(self) -> Path:
        return self._output_folder

    def set_output_folder(self, folder: Path) -> None:
        self._output_folder = Path(folder)

    # --- posting: create the NC Program, then hand over ------------------------------------------
    def materialize(self, operations: list):
        if self.created is not None:
            return self.created
        if not self.has_machine:
            raise ValueError("The Z1 template's machine or post processor isn't on this computer.")
        nc_program, self.failed_settings = self._adapter.create_nc_program(
            self._cam, self.template, store.NC_PROGRAM_NAME, operations, self._machine, self._post)
        program = self._program_factory(nc_program)
        program.set_output_folder(self._output_folder)
        program.set_file_name(self._file_name)
        self.created = program
        if self._on_created is not None:
            self._on_created(program)
        return program

    def process(self, ctx: Any, tmp_path: Path):
        from ..setups.setup_source import raw_setup
        operations = [raw_setup(setup.ctx.setup) for setup in getattr(ctx, "selected", [])]
        if not operations and self._cam is not None:
            operations = list(self._cam.setups)
        return self.materialize(operations).process(ctx, tmp_path)

    def write_output(self, ctx: Any):
        if self.created is None:
            raise ValueError("Nothing posted yet.")
        return self.created.write_output(ctx)

    def __getattr__(self, name):
        # anything else (post_process, disable_open_in_editor, parameters...) goes to the created NC Program
        created = self.__dict__.get("created")
        if created is None:
            raise AttributeError(name)
        return getattr(created, name)
