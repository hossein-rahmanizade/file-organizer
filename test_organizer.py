from pathlib import Path

import pytest

from file_organizer import build_plan, execute_plan, print_summary, PlanEntry


@pytest.fixture
def messy_dir(tmp_path):
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.jpg").write_text("b")
    (tmp_path / ".hidden").write_text("h")
    (tmp_path / "noext").write_text("n")
    (tmp_path / "broken.jpg").symlink_to(tmp_path / "nowhere")
    return tmp_path


def test_plan_classifies(messy_dir):
    plan = build_plan(messy_dir, "organized")
    by_name = {e.source.name: e for e in plan}
    assert by_name["a.txt"].action == "move"
    assert by_name[".hidden"].reason == "hidden"
    assert by_name["noext"].reason == "no_ext"
    assert by_name["broken.jpg"].reason == "symlink"


def test_execute_moves(messy_dir):
    plan = build_plan(messy_dir, "organized")
    results = execute_plan(plan)
    assert all(r.status == "moved" for r in results)
    assert (messy_dir / "organized_txt" / "a.txt").exists()
    assert not (messy_dir / "a.txt").exists()


def test_failure_recorded():
    bogus = [PlanEntry(
        source=Path("/nonexistent/foo.txt"),
        target=Path("/tmp/organized_txt/foo.txt"),
        action="move",
        reason=None,
    )]
    (r,) = execute_plan(bogus)
    assert r.status == "failed"
    assert "FileNotFoundError" in r.error


def test_summary_format(capsys, messy_dir):
    plan = build_plan(messy_dir, "organized")
    results = execute_plan(plan)
    print_summary(plan, results)
    out, _ = capsys.readouterr()
    # parse the line, assert the counts
    assert "Moved: 2" in out
    assert "Skipped: 3" in out
    assert "Failed: 0" in out
    assert "hidden: 1" in out
    assert "no_ext: 1" in out
    assert "symlink: 1" in out


def test_collision_detected(messy_dir):
    # pre-create the destination so the target "already exists"
    (messy_dir / "organized_txt").mkdir()
    (messy_dir / "organized_txt" / "a.txt").write_text("existing")

    plan = build_plan(messy_dir, "organized")
    by_name = {e.source.name: e for e in plan}

    entry = by_name["a.txt"]
    assert entry.action == "skip"
    assert entry.reason == "collision"
    assert entry.target is None

    # other files are unaffected
    assert by_name["b.jpg"].action == "move"
