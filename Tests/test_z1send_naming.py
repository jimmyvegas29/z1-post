# Z1 Post, by jimmyvegas29, 2026-11-16. GPL v2 (see LICENSE).
from pathlib import Path
from types import SimpleNamespace

from addin_import import import_addin_module

naming = import_addin_module("commands.postProcessor.z1send.naming")
send = import_addin_module("commands.postProcessor.z1send.send")
Constants = import_addin_module("commands.postProcessor.settings.constants").Constants
G = Constants.OperationsGroupings


def plan(path, *setups):
    return SimpleNamespace(path=Path(path), setups=[SimpleNamespace(name=n) for n in setups])


def names(plans, grouping, job="Bracket", numeric=False):
    return [w.send_name for w in naming.written_files(plans, job, grouping, numeric, lambda s: s)]


def test_every_grouping_gives_file_name_then_setup():
    assert names([plan("out/Bracket.cnc", "Setup1")], G.SINGLE_FILE) == ["Bracket_Setup1.cnc"]
    assert names([plan("out/Bracket.cnc", "Setup1", "Setup2")], G.SINGLE_FILE) == ["Bracket_Setup1-Setup2.cnc"]
    assert names([plan("out/Bracket/Setup1.cnc", "Setup1"), plan("out/Bracket/Setup2.cnc", "Setup2")],
                 G.SETUP) == ["Bracket_Setup1.cnc", "Bracket_Setup2.cnc"]
    assert names([plan("out/Bracket/Setup1/Setup1_T3.cnc", "Setup1")], G.SETUP_AND_TOOL) == ["Bracket_Setup1_T3.cnc"]
    assert names([plan("out/Bracket/Setup1/Pocket1.cnc", "Setup1")], G.PER_OPERATION) == ["Bracket_Setup1_Pocket1.cnc"]


def test_numeric_names_are_kept():
    assert names([plan("out/1001.cnc", "Setup1")], G.SETUP, job="1001", numeric=True) == ["1001.cnc"]


def test_machine_names_have_no_spaces_or_unsafe_characters():
    assert send.machine_name("My Job_Top Side.cnc") == "My_Job_Top_Side.cnc"
    assert send.machine_name("a?b*c!.cnc") == "a_b_c_.cnc"
    assert send.remote_path("sd/gcodes", "x.cnc") == "/sd/gcodes/x.cnc"


def test_two_files_with_the_same_machine_name_are_refused():
    import pytest
    clash = [naming.WrittenFile(Path("a/x.cnc"), "X.cnc"), naming.WrittenFile(Path("b/x.cnc"), "X.cnc")]
    with pytest.raises(ValueError, match="same name on the machine"):
        send.send_files(clash, "127.0.0.1")
