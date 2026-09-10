from __future__ import annotations

import json

import pytest

from anatomize._artifacts import sha256_digest
from anatomize.evidence import ContentClass, FileEntity, RepositoryEvidence
from anatomize.research import (
    CellDeltaKind,
    CellIdentityStrength,
    NotebookArtifact,
    NotebookArtifactError,
    NotebookCellKind,
    NotebookExecutionArtifact,
    OutputState,
    compare_notebooks,
    notebook_execution_provider_envelope,
    parse_executable_document,
    parse_jupyter_notebook,
    parse_notebook_execution,
)
from tests.unit.test_evidence_models import _known_truth_evidence


def _raw(cells: list[dict[str, object]], *, language: str = "python") -> bytes:
    return json.dumps(
        {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {"kernelspec": {"language": language}, "language_info": {"name": language}},
            "cells": cells,
        }
    ).encode()


def _parse(cells: list[dict[str, object]], state: str = "state:after"):  # type: ignore[no-untyped-def]
    return parse_jupyter_notebook(
        _raw(cells),
        repository_id="repository:fixture",
        source_state_id=state,
        path="analysis.ipynb",
    )


def _execution(notebook: NotebookArtifact, payload: dict[str, object]) -> NotebookExecutionArtifact:
    return parse_notebook_execution(
        json.dumps(payload).encode(),
        repository_id=notebook.repository_id,
        source_state_id=notebook.source_state_id,
        notebook_document_digest=notebook.document_digest,
        provider_run_id="run:nbclient",
        provider_id="nbclient",
        provider_version="1",
        environment_digest=sha256_digest(b"python-r-environment"),
    )


def _notebook_baseline(notebook: NotebookArtifact) -> RepositoryEvidence:
    baseline = _known_truth_evidence()
    notebook_file = FileEntity(
        entity_id="entity:notebook",
        source_state_id=notebook.source_state_id,
        display_name=notebook.path,
        path=notebook.path,
        language="jupyter",
        digest=notebook.document_digest,
        size_bytes=100,
        roles=["notebook"],
    )
    return baseline.model_copy(update={"entities": [*baseline.entities, notebook_file]})


def test_nbformat_cells_cover_identity_source_semantics_outputs_attachments_and_privacy() -> None:
    source = "def answer():\n    return input_value\n"
    source_digest = sha256_digest(source.encode())
    artifact = _parse(
        [
            {
                "id": "parameters",
                "cell_type": "code",
                "metadata": {
                    "tags": ["parameters"],
                    "jupyter": {"source_hidden": True, "outputs_hidden": True},
                    "anatomize_output_source_digest": source_digest,
                    "anatomize_sensitive": True,
                },
                "source": source,
                "execution_count": 2,
                "outputs": [
                    {
                        "output_type": "display_data",
                        "data": {"text/plain": "secret", "image/png": "A" * 70_000},
                        "metadata": {},
                    }
                ],
            },
            {
                "id": "notes",
                "cell_type": "markdown",
                "metadata": {},
                "source": "Use `pkg.answer()`.",
                "attachments": {"plot.png": {"image/png": "binary"}},
            },
            {"cell_type": "code", "metadata": {}, "source": "answer()", "execution_count": None, "outputs": []},
        ]
    )

    code, markdown, missing = artifact.cells
    assert code.identity_strength is CellIdentityStrength.EXACT
    assert code.parameter and code.hidden_source and code.hidden_outputs
    assert code.definitions == ["answer"] and "input_value" in code.references
    assert code.output_state is OutputState.CURRENT
    assert code.outputs[0].content_class is ContentClass.SENSITIVE
    assert code.outputs[0].byte_size > 65_536
    assert code.outputs[0].media_types == ["image/png", "text/plain"]
    assert code.outputs[0].content_included is False
    assert markdown.kind is NotebookCellKind.MARKDOWN
    assert markdown.references == ["pkg.answer"]
    assert markdown.attachments[0].content_class is ContentClass.BINARY
    assert missing.identity_strength is CellIdentityStrength.CANDIDATE
    assert missing.output_state is OutputState.CLEARED
    assert any("no valid stable id" in item for item in artifact.limitations)


def test_quarto_mixed_language_document_preserves_order_parameters_and_hidden_cells() -> None:
    artifact = parse_executable_document(
        """---
title: Trial
params:
  seed: 1
---
# Analysis
Use `trialtools::normalise`.

```{python fit-model}
#| parameters: true
def fit():
    return data
```

```{r}
#| label: summarise
#| echo: false
summary <- function(x) mean(x)
```
""",
        repository_id="repository:fixture",
        source_state_id="state:after",
        path="report.qmd",
    )

    assert artifact.document_format == "quarto"
    assert [item.kind for item in artifact.cells] == [
        NotebookCellKind.MARKDOWN,
        NotebookCellKind.CODE,
        NotebookCellKind.CODE,
    ]
    python, r = artifact.cells[1:]
    assert python.language == "python" and python.parameter
    assert python.native_cell_id == "fit-model" and python.definitions == ["fit"]
    assert r.language == "r" and r.native_cell_id == "summarise" and r.hidden_source
    assert r.definitions == ["summary"] and "mean" in r.references


def test_execution_artifact_is_separate_source_environment_and_error_evidence() -> None:
    notebook = _parse([{"id": "run", "cell_type": "code", "metadata": {}, "source": "1 / 0", "outputs": []}])
    raw = json.dumps(
        {
            "status": "failed",
            "cells": [
                {
                    "cell_key": notebook.cells[0].cell_key,
                    "status": "failed",
                    "execution_count": 1,
                    "output_digests": [sha256_digest(b"error-output")],
                    "error_type": "ZeroDivisionError",
                    "error_digest": sha256_digest(b"bounded-redacted-error"),
                }
            ],
        }
    ).encode()
    execution = parse_notebook_execution(
        raw,
        repository_id="repository:fixture",
        source_state_id="state:after",
        notebook_document_digest=notebook.document_digest,
        provider_run_id="run:nbclient",
        provider_id="nbclient",
        provider_version="1",
        environment_digest=sha256_digest(b"python-r-environment"),
    )

    assert execution.status == "failed"
    assert execution.observations[0].error_type == "ZeroDivisionError"
    assert execution.notebook_document_digest == notebook.document_digest
    assert execution.environment_digest != notebook.document_digest

    envelope = notebook_execution_provider_envelope(
        execution,
        notebook=notebook,
        baseline=_notebook_baseline(notebook),
        configuration_digest=sha256_digest(b"execution-configuration"),
        policy_digest=sha256_digest(b"artifact-only"),
    )
    assert envelope.payload.observations[0].record_type == "runtime_observation"
    assert envelope.payload.observations[0].metrics["environment_digest"] == execution.environment_digest
    assert envelope.payload.completeness[0].status.value == "partial"


@pytest.mark.parametrize(
    "record",
    [
        42,
        {},
        {"cell_key": "", "status": "passed"},
        {"cell_key": "cell", "status": "invalid"},
        {"cell_key": "cell", "status": "passed", "execution_count": True},
        {"cell_key": "cell", "status": "passed", "execution_count": "1"},
        {"cell_key": "cell", "status": "passed", "output_digests": None},
        {"cell_key": "cell", "status": "passed", "output_digests": "digest"},
        {"cell_key": "cell", "status": "passed", "output_digests": [123]},
        {"cell_key": "cell", "status": "passed", "output_digests": ["invalid"]},
    ],
)
def test_execution_summary_rejects_malformed_records_instead_of_omitting_them(record: object) -> None:
    notebook = _parse([])
    with pytest.raises(NotebookArtifactError) as error:
        _execution(notebook, {"status": "complete", "cells": [record]})
    assert error.value.code == "notebook_execution_invalid"


def test_execution_summary_rejects_duplicate_cells_and_malformed_status() -> None:
    notebook = _parse([])
    record = {"cell_key": "cell", "status": "passed"}
    with pytest.raises(NotebookArtifactError, match="failed validation"):
        _execution(notebook, {"status": "complete", "cells": [record, record]})
    with pytest.raises(NotebookArtifactError) as error:
        _execution(notebook, {"status": {}, "cells": []})
    assert error.value.code == "notebook_execution_shape_invalid"


@pytest.mark.parametrize("invalid", ["unknown_cell", "missing_cell", "wrong_digest", "wrong_state"])
def test_execution_projection_requires_exact_source_membership_and_complete_coverage(invalid: str) -> None:
    notebook = _parse([
        {"id": "a", "cell_type": "code", "metadata": {}, "source": "1", "outputs": []},
        {"id": "b", "cell_type": "code", "metadata": {}, "source": "2", "outputs": []},
    ])
    records = [{"cell_key": item.cell_key, "status": "passed"} for item in notebook.cells]
    baseline = _notebook_baseline(notebook)
    if invalid == "unknown_cell":
        records[0]["cell_key"] = "unknown-cell"
    elif invalid == "missing_cell":
        records.pop()
    elif invalid == "wrong_digest":
        baseline = baseline.model_copy(update={
            "entities": [
                entity.model_copy(update={"digest": sha256_digest(b"other notebook")})
                if entity.entity_id == "entity:notebook" else entity
                for entity in baseline.entities
            ]
        })
    else:
        baseline = baseline.model_copy(update={"states": []})
    execution = _execution(notebook, {"status": "complete", "cells": records})
    with pytest.raises(ValueError):
        notebook_execution_provider_envelope(
            execution, notebook=notebook, baseline=baseline,
            configuration_digest=sha256_digest(b"configuration"), policy_digest=sha256_digest(b"policy"),
        )


@pytest.mark.parametrize("status", ["complete", "partial"])
def test_execution_projection_preserves_complete_and_selected_partial_runs(status: str) -> None:
    notebook = _parse([
        {"id": "a", "cell_type": "code", "metadata": {}, "source": "1", "outputs": []},
        {"id": "b", "cell_type": "code", "metadata": {}, "source": "2", "outputs": []},
    ])
    cells = notebook.cells if status == "complete" else notebook.cells[:1]
    execution = _execution(notebook, {
        "status": status,
        "cells": [{"cell_key": item.cell_key, "status": "passed", "execution_count": 0} for item in cells],
    })
    envelope = notebook_execution_provider_envelope(
        execution, notebook=notebook, baseline=_notebook_baseline(notebook),
        configuration_digest=sha256_digest(b"configuration"), policy_digest=sha256_digest(b"policy"),
    )
    assert len(envelope.payload.observations) == len(cells)
    assert envelope.payload.completeness[0].status.value == status


def test_cell_delta_distinguishes_reorder_source_output_split_merge_and_add_remove() -> None:
    before = _parse(
        [
            {"id": "a", "cell_type": "code", "metadata": {}, "source": "x = 1", "outputs": []},
            {
                "id": "b",
                "cell_type": "code",
                "metadata": {},
                "source": "print(x)",
                "outputs": [{"output_type": "stream", "text": "1"}],
            },
        ],
        "state:before",
    )
    after = _parse(
        [
            {
                "id": "b",
                "cell_type": "code",
                "metadata": {},
                "source": "print(x)",
                "outputs": [{"output_type": "stream", "text": "2"}],
            },
            {"id": "a", "cell_type": "code", "metadata": {}, "source": "x = 2", "outputs": []},
        ]
    )
    kinds = [set(item.kinds) for item in compare_notebooks(before, after)]

    assert {CellDeltaKind.REORDERED, CellDeltaKind.OUTPUT_ONLY} in kinds
    assert {CellDeltaKind.REORDERED, CellDeltaKind.SOURCE_CHANGED} in kinds
    assert all(item.invalidates_execution for item in compare_notebooks(before, after))

    split_before = _parse(
        [{"cell_type": "code", "metadata": {}, "source": "a = 1\nb = 2", "outputs": []}],
        "state:before",
    )
    split_after = _parse(
        [
            {"cell_type": "code", "metadata": {}, "source": "a = 1", "outputs": []},
            {"cell_type": "code", "metadata": {}, "source": "b = 2", "outputs": []},
        ]
    )
    # Id-less cells are matched by exact ordinal and kind only. Anatomize does
    # not infer split/merge lineage from bounded source previews.
    assert {kind for item in compare_notebooks(split_before, split_after) for kind in item.kinds} == {
        CellDeltaKind.SOURCE_CHANGED,
        CellDeltaKind.ADDED,
    }
    assert {kind for item in compare_notebooks(split_after, split_before) for kind in item.kinds} == {
        CellDeltaKind.SOURCE_CHANGED,
        CellDeltaKind.REMOVED,
    }


def test_stale_output_and_bounded_corrupt_artifacts_fail_or_degrade_explicitly() -> None:
    stale = _parse(
        [
            {
                "id": "stale",
                "cell_type": "code",
                "metadata": {"anatomize_output_source_digest": sha256_digest(b"old")},
                "source": "new_value = 2",
                "outputs": [{"output_type": "execute_result", "data": {"text/plain": "1"}}],
            }
        ]
    )
    assert stale.cells[0].output_state is OutputState.STALE

    with pytest.raises(NotebookArtifactError):
        parse_jupyter_notebook(
            b"{invalid",
            repository_id="repository:fixture",
            source_state_id="state:after",
            path="bad.ipynb",
        )
    with pytest.raises(ValueError, match="repository-relative"):
        parse_jupyter_notebook(
            _raw([]),
            repository_id="repository:fixture",
            source_state_id="state:after",
            path="../private.ipynb",
        )
