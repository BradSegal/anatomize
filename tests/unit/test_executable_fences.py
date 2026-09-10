from __future__ import annotations

from anatomize.research import NotebookCellKind, parse_executable_document


def test_executable_fences_respect_length_character_and_literal_examples() -> None:
    artifact = parse_executable_document(
        "````markdown\n```{r}\nfiction()\n```\n````\n"
        "  ~~~{r real}\nactual()\n```\nstill_actual()\n  ~~~~\n"
        "````{python}\nvalue = 1\n```\nvalue = 2\n````\n",
        repository_id="repository:fixture", source_state_id="state:fixture", path="analysis.qmd",
    )
    cells = [item for item in artifact.cells if item.kind is NotebookCellKind.CODE]
    assert [item.language for item in cells] == ["r", "python"]
    assert cells[0].source_preview == "actual()\n```\nstill_actual()"
    assert cells[1].source_preview == "value = 1\n```\nvalue = 2"
    assert cells[0].locator.start_line == 7
    assert cells[0].locator.end_line == 9


def test_r_notebook_semantics_ignore_comments_and_raw_string_contents() -> None:
    artifact = parse_executable_document(
        '```{r}\n# phantom()\ntext <- r"---(\nghost <- function() fake()\n)---"\nreal()\n```\n',
        repository_id="repository:fixture", source_state_id="state:fixture", path="analysis.qmd",
    )
    cell = artifact.cells[0]
    assert cell.definitions == ["text"]
    assert cell.references == ["real"]
