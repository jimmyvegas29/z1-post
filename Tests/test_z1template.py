# Z1 Post, by jimmyvegas29, 2026-11-16. GPL v2 (see LICENSE).
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from addin_import import import_addin_module

store = import_addin_module("commands.postProcessor.z1template.store")
tp = import_addin_module("commands.postProcessor.z1template.template_program")
prefs = import_addin_module("commands.postProcessor.z1send.prefs")

TEMPLATE = {
    "machine": {"vendor": "Makera", "model": "Makera Z1 3 axis", "description": ""},
    "post": {"vendor": "Makera", "description": "Makera Carvera Community Post v1.4.6", "version": "1.4.6",
             "extension": "cnc"},
    "post_settings": {"useCoolant": "false", "safeRetract": "'G28'"},
    "output_folder": "C:/cam",
    "saved": {"date": "2026-11-16", "program": "NCProgram11", "document": "can_lid"},
}


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("Z1POST_DATA_DIR", str(tmp_path / "data"))
    prefs._items.clear()
    return tmp_path / "data"


def test_store_round_trip_and_clear(data_dir):
    assert store.load() is None
    assert store.save(TEMPLATE)
    assert (data_dir / "template.json").exists()
    assert store.load() == TEMPLATE
    store.clear()
    assert store.load() is None


def test_store_rejects_incomplete_templates():
    with pytest.raises(ValueError):
        store.save({"machine": {"model": "X"}, "post": {}})


def test_summary_rows_and_missing_pieces():
    rows = dict(store.summary(TEMPLATE))
    assert rows["Machine"] == "Makera Z1 3 axis"
    assert rows["Post settings"] == "2 changed from the post's defaults"
    assert rows["Saved"] == "2026-11-16, from NCProgram11, in can_lid"
    missing = dict(store.summary(TEMPLATE, machine_found=False, post_found=True))
    assert "not found" in missing["Machine"]


def test_dropdown_label():
    assert store.dropdown_label(False) == "Z1 template"
    assert store.dropdown_label(True) == "Z1 template (new NC Program)"


class FakeCapabilities:
    def machine_has_a_axis(self, program):
        return program.machine.has_a

    def machine_has_atc(self, program):
        return False

    def machine_tool_slots(self, program):
        return 1


class FakeAdapter:
    def __init__(self, machine=True, post=True, failed=()):
        self.machine = SimpleNamespace(model="Makera Z1 3 axis", has_a=False) if machine else None
        self.post = SimpleNamespace(extension="cnc") if post else None
        self.failed = list(failed)
        self.created = []

    def find_machine(self, template):
        return self.machine

    def find_post(self, template):
        return self.post

    def create_nc_program(self, cam, template, name, operations, machine=None, post=None):
        assert machine is self.machine and post is self.post   # found once, when the dialog opened
        nc = SimpleNamespace(name=name, operations=operations)
        self.created.append(nc)
        return nc, self.failed

    def program_adapter(self):
        return FakeCapabilities()


class FakeProgram:
    def __init__(self, nc):
        self.nc, self.name, self.calls = nc, nc.name, []

    def set_output_folder(self, folder):
        self.folder = folder

    def set_file_name(self, name):
        self.file = name

    def process(self, ctx, tmp):
        self.calls.append("process")

    def write_output(self, ctx):
        self.calls.append("write")
        return ("files",)

    def disable_open_in_editor(self):
        self.calls.append("no editor")


def make(adapter, created=None):
    return tp.TemplateProgram(TEMPLATE, SimpleNamespace(setups=["S1", "S2"]), "Z1 template", "can_lid v22",
                              adapter=adapter, program_factory=FakeProgram,
                              on_created=(created.append if created is not None else None))


def test_template_answers_the_dialog_without_touching_the_document():
    adapter = FakeAdapter()
    entry = make(adapter)
    assert entry.name == "Z1 template"
    assert entry.has_machine and entry.has_post_processor
    assert entry.machine_name == "Makera Z1 3 axis"
    assert entry.post_processor_description.startswith("Makera Carvera")
    assert entry.file_extension == "cnc"
    assert entry.machine_has_a_axis is False
    assert entry.file_name == "can_lid"            # document name without " v22"
    assert entry.get_output_folder() == Path("C:/cam")
    assert "Z1 Post" in entry.template_note
    assert adapter.created == []                   # nothing created yet


def test_posting_creates_the_nc_program_once_and_hands_over():
    adapter, created = FakeAdapter(), []
    entry = make(adapter, created)
    entry.set_file_name("bracket")
    setup = SimpleNamespace(ctx=SimpleNamespace(setup="raw-setup"))
    ctx = SimpleNamespace(selected=[setup])
    entry.process(ctx, Path("tmp"))
    assert len(adapter.created) == 1 and adapter.created[0].name == "Z1 Post"
    assert adapter.created[0].operations == ["raw-setup"]
    program = entry.created
    assert created == [program]
    assert program.file == "bracket" and program.folder == Path("C:/cam")
    assert entry.write_output(ctx) == ("files",)
    entry.disable_open_in_editor()                  # forwarded to the created program
    entry.process(ctx, Path("tmp"))                 # a second post reuses it
    assert len(adapter.created) == 1
    assert program.calls == ["process", "write", "no editor", "process"]


def test_missing_machine_disables_posting():
    entry = make(FakeAdapter(machine=False))
    assert not entry.has_machine
    assert "isn't on this computer" in entry.template_note
    with pytest.raises(ValueError):
        entry.process(SimpleNamespace(selected=[]), Path("tmp"))


def test_failed_post_settings_are_reported():
    entry = make(FakeAdapter(failed=["safeRetract"]))
    entry.process(SimpleNamespace(selected=[]), Path("tmp"))
    assert entry.failed_settings == ["safeRetract"]


def test_send_prefs_live_in_the_user_data_folder(data_dir):
    prefs.set("host", "192.168.1.100")
    saved = json.loads((data_dir / "send.json").read_text(encoding="utf-8"))
    assert saved["host"] == "192.168.1.100"
