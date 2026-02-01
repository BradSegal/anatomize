from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from anatomize.cli import app

pytestmark = pytest.mark.e2e


def test_cli_pack_hybrid_defaults_to_markdown_when_output_is_markdown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "a.py").write_text("def f() -> None:\n    pass\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "out.md"

    res = CliRunner().invoke(app, ["pack", ".", "--mode", "hybrid", "--output", str(out)])
    assert res.exit_code == 0, res.output
    text = out.read_text(encoding="utf-8")
    assert "# Code Pack" in text
    assert "representation: summary" in text


def test_cli_pack_hybrid_allows_markdown_if_format_specified(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("def f() -> None:\n    pass\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "out.md"

    res = CliRunner().invoke(app, ["pack", ".", "--mode", "hybrid", "--format", "markdown", "--output", str(out)])
    assert res.exit_code == 0, res.output
    assert out.read_text(encoding="utf-8").startswith("# Code Pack")


def test_cli_pack_hybrid_fit_requires_max_output(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("def f() -> None:\n    pass\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    res = CliRunner().invoke(app, ["pack", ".", "--mode", "hybrid", "--fit-to-max-output"])
    assert res.exit_code != 0
    assert "only supported" in res.output


def test_cli_pack_hybrid_allows_jsonl_output(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("def f() -> None:\n    pass\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    out = tmp_path / "out.jsonl"
    res = CliRunner().invoke(app, ["pack", ".", "--mode", "hybrid", "--output", str(out)])
    assert res.exit_code == 0, res.output
    first = out.read_text(encoding="utf-8").splitlines()[0]
    meta = json.loads(first)
    assert meta["type"] == "meta"
    assert meta["mode"] == "hybrid"


def test_cli_pack_hybrid_rejects_json_format(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("def f() -> None:\n    pass\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    res = CliRunner().invoke(app, ["pack", ".", "--mode", "hybrid", "--format", "json"])
    assert res.exit_code != 0
    assert "supports only markdown, plain, or jsonl" in res.output
