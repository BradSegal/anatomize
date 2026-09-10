from __future__ import annotations

import json
from pathlib import Path

import pytest

from anatomize.dossiers import DossierContext
from anatomize.evidence import FileEntity, SymbolEntity
from anatomize.review import ReviewApplication


@pytest.mark.parametrize("cell_type", [[], {}, None, 1])
def test_review_retains_malformed_notebook_as_partial_inventory(tmp_path: Path, cell_type: object) -> None:
    (tmp_path / "bad.ipynb").write_text(
        json.dumps({"nbformat": 4, "cells": [{"cell_type": cell_type, "source": "x"}]}),
        encoding="utf-8",
    )

    bundle = ReviewApplication().start(tmp_path)
    context = DossierContext.from_bundle(bundle)
    assert any(
        isinstance(entity, FileEntity) and entity.path == "bad.ipynb"
        for evidence in context.evidence
        for entity in evidence.entities
    )
    assert any(
        limitation.code == "notebook_parse" and "notebook_cell_type_invalid" in limitation.summary
        for evidence in context.evidence
        for limitation in evidence.limitations
    )
    provider = next(item for item in bundle.manifest.providers if item.provider_id == "anatomize.source-inventory")
    assert provider.status.value == "partial"


def test_review_retains_deep_python_test_as_partial_inventory(tmp_path: Path) -> None:
    (tmp_path / "test_deep.py").write_text(
        "def test_expression():\n    assert " + "+".join(["1"] * 10_000) + "\n",
        encoding="utf-8",
    )

    bundle = ReviewApplication().start(tmp_path)
    context = DossierContext.from_bundle(bundle)
    assert any(
        isinstance(entity, FileEntity) and entity.path == "test_deep.py"
        for evidence in context.evidence
        for entity in evidence.entities
    )
    assert any(
        "recursion limit" in limitation.summary
        for evidence in context.evidence
        for limitation in evidence.limitations
    )
    provider = next(item for item in bundle.manifest.providers if item.provider_id == "anatomize.repository-index")
    assert provider.status.value == "partial"


@pytest.mark.parametrize("suffix", ["qmd", "rmd"])
def test_review_indexes_r_functions_only_in_executable_document_chunks(tmp_path: Path, suffix: str) -> None:
    path = f"analysis.{suffix}"
    (tmp_path / path).write_text(
        "Prose:\nphantom <- function() { 0 }\n\n"
        "```{python}\nother <- function() { 1 }\n```\n\n"
        "```{r}\nanswer <- function() { 42 }\n```\n",
        encoding="utf-8",
    )

    context = DossierContext.from_bundle(ReviewApplication().start(tmp_path))
    symbols = [
        entity
        for evidence in context.evidence
        for entity in evidence.entities
        if isinstance(entity, SymbolEntity)
    ]
    assert [(symbol.name, symbol.language) for symbol in symbols] == [("answer", "r")]
    locations = {
        location.location_id: location
        for evidence in context.evidence
        for location in evidence.locations
    }
    location = locations[symbols[0].location_ids[0]]
    assert location.path == path
    assert location.source_range is not None
    assert location.source_range.start.line == location.source_range.end.line == 9
