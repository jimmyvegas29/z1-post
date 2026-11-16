from pathlib import Path
from types import SimpleNamespace

import pytest

from addin_import import import_addin_module


workflow = import_addin_module("commands.postProcessor.program_workflow")
Constants = import_addin_module(
    "commands.postProcessor.settings.constants"
).Constants


def make_context():
    settings = SimpleNamespace(
        operationsGrouping=Constants.OperationsGroupings.SINGLE_FILE,
        flatFileStructure=False,
        numericName=False,
        clearFolder=False,
        overwriteFiles=True,
    )
    context = SimpleNamespace(
        processingSettings=settings,
        selected=[],
        fileName=None,
        events=[],
        sanitize_filename=lambda name: name,
    )
    context.set_file_extension = lambda value: context.events.append(("extension", value))
    context.set_path = lambda value: context.events.append(("path", value))
    context.set_file_name = lambda value: context.events.append(("name", value))
    return context


def test_render_program_output_prepares_plans_and_renders(tmp_path, monkeypatch):
    context = make_context()
    rendered = []
    monkeypatch.setattr(workflow, "prepare_output_folder", lambda path, clear: True)
    plan = SimpleNamespace(path=tmp_path / "job" / "Setup 1.nc", setups=[SimpleNamespace(name="Setup 1")])
    monkeypatch.setattr(workflow, "plan_output_files", lambda *args: (plan,))
    monkeypatch.setattr(
        workflow,
        "render_output_files",
        lambda plans, overwrite: rendered.append((plans, overwrite)),
    )

    written = workflow.render_program_output(context, tmp_path, "job", ".nc")

    assert context.events == [
        ("extension", ".nc"),
        ("path", tmp_path),
        ("name", "job"),
    ]
    assert rendered == [((plan,), True)]
    # Z1 Post: each written file comes back with its name for the machine
    assert [(w.path, w.send_name) for w in written] == [(plan.path, "job_Setup 1.nc")]


def test_render_program_output_stops_when_folder_preparation_fails(
    tmp_path,
    monkeypatch,
):
    context = make_context()
    def fail_preparation(_path, _clear):
        raise PermissionError("protected")

    monkeypatch.setattr(workflow, "prepare_output_folder", fail_preparation)

    with pytest.raises(PermissionError, match="protected"):
        workflow.render_program_output(context, tmp_path, "job", ".nc")
    assert context.events == []
