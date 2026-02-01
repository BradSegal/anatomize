from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from anatomize.cli import app

pytestmark = pytest.mark.e2e


def test_cli_pack_explain_selection_reports_ignored_dirs(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / ".runtime").mkdir()
    (tmp_path / ".runtime" / "index.log").write_text("nope\n", encoding="utf-8")
    (tmp_path / "kept.txt").write_text("ok\n", encoding="utf-8")

    out = tmp_path / "out.json"
    report = tmp_path / "selection.json"

    monkeypatch.chdir(tmp_path)
    res = CliRunner().invoke(
        app,
        [
            "pack",
            ".",
            "--format",
            "json",
            "--output",
            str(out),
            "--no-files",
            "--explain-selection",
            "--explain-selection-output",
            str(report),
        ],
    )
    assert res.exit_code == 0, res.output

    data = json.loads(report.read_text(encoding="utf-8"))
    excluded_dirs = {d["path"] for d in data["excluded_directories"]}
    assert ".runtime" in excluded_dirs


def test_cli_pack_explain_selection_reports_include_allowlist_exclusions(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "a.txt").write_text("a\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("b\n", encoding="utf-8")

    out = tmp_path / "out.json"
    report = tmp_path / "selection.json"

    monkeypatch.chdir(tmp_path)
    res = CliRunner().invoke(
        app,
        [
            "pack",
            ".",
            "--format",
            "json",
            "--output",
            str(out),
            "--include",
            "a.txt",
            "--no-files",
            "--explain-selection",
            "--explain-selection-output",
            str(report),
        ],
    )
    assert res.exit_code == 0, res.output

    data = json.loads(report.read_text(encoding="utf-8"))
    by_path = {f["path"]: f for f in data["files"]}
    assert by_path["a.txt"]["decision"] == "included"
    assert by_path["b.txt"]["decision"] == "excluded"
    assert by_path["b.txt"]["reason"] == "include"


def test_cli_pack_explain_selection_reports_slice_exclusions(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("print('a')\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("print('b')\n", encoding="utf-8")

    out = tmp_path / "out.json"
    report = tmp_path / "selection.json"

    monkeypatch.chdir(tmp_path)
    res = CliRunner().invoke(
        app,
        [
            "pack",
            ".",
            "--format",
            "json",
            "--output",
            str(out),
            "--entry",
            "a.py",
            "--no-files",
            "--explain-selection",
            "--explain-selection-output",
            str(report),
        ],
    )
    assert res.exit_code == 0, res.output

    data = json.loads(report.read_text(encoding="utf-8"))
    by_path = {f["path"]: f for f in data["files"]}
    assert by_path["a.py"]["decision"] == "included"
    assert by_path["b.py"]["decision"] == "excluded"
    assert by_path["b.py"]["reason"] == "slice"

