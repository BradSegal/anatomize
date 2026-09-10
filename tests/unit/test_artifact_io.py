from __future__ import annotations

import io
import os
from collections.abc import Callable
from pathlib import Path

import pytest

from anatomize._artifacts import BoundedJsonError, read_bounded_bytes
from anatomize._errors import AnatomizeError
from anatomize.diagnostics import SarifArtifactLimits, load_sarif_log
from anatomize.dossiers import load_dossier, load_dossier_request
from anatomize.evidence import load_evidence
from anatomize.providers import ProviderArtifactLimits, load_provider_envelope
from anatomize.review.io import json_object, load_review_artifact
from anatomize.semantic import LspSemanticArtifactLimits, load_lsp_semantic_artifact
from anatomize.sessions import load_session_bundle
from anatomize.temporal import load_comparison


@pytest.mark.parametrize(
    ("loader", "kwargs", "code"),
    [
        (load_evidence, {"max_bytes": 16}, "artifact_too_large"),
        (load_comparison, {"max_bytes": 16}, "comparison_artifact_too_large"),
        (load_session_bundle, {"max_bytes": 16}, "session_bundle_too_large"),
        (load_review_artifact, {"max_bytes": 16}, "review_artifact_too_large"),
        (load_dossier, {"max_bytes": 16}, "dossier_too_large"),
        (load_dossier_request, {"max_bytes": 16}, "dossier_request_too_large"),
        (load_provider_envelope, {"limits": ProviderArtifactLimits(max_bytes=16)}, "provider_artifact_too_large"),
        (load_sarif_log, {"limits": SarifArtifactLimits(max_bytes=16)}, "sarif_artifact_too_large"),
        (
            load_lsp_semantic_artifact,
            {"limits": LspSemanticArtifactLimits(max_bytes=16)},
            "semantic_artifact_too_large",
        ),
        (json_object, {"max_bytes": 16}, "review_input_invalid"),
    ],
)
def test_artifact_loaders_bound_reads_when_file_size_underreports_content(
    loader: Callable[..., object],
    kwargs: dict[str, object],
    code: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "growing.json"
    path.write_bytes(b"{")
    reads: list[int] = []

    class GrowingFile(io.BytesIO):
        def fileno(self) -> int:
            return 0

        def read(self, size: int | None = -1) -> bytes:
            assert size is not None and 0 <= size <= 17, "artifact content was read without its allocation bound"
            reads.append(size)
            return super().read(size)

    monkeypatch.setattr(Path, "open", lambda *args, **kwargs: GrowingFile(b"x" * 1_000))
    monkeypatch.setattr(os, "fstat", lambda descriptor: os.stat_result((0,) * 10))
    with pytest.raises(AnatomizeError) as error:
        loader(path, **kwargs)
    assert error.value.code == code
    assert reads == [17]


def test_bounded_file_reader_preserves_exact_limit_and_rejects_larger_files(tmp_path: Path) -> None:
    path = tmp_path / "artifact.json"
    raw = b'{"value":true}'
    path.write_bytes(raw)
    assert read_bounded_bytes(path, max_bytes=len(raw)) == raw
    with pytest.raises(BoundedJsonError) as error:
        read_bounded_bytes(path, max_bytes=len(raw) - 1)
    assert error.value.code == "too_large"
    with pytest.raises(ValueError, match="positive"):
        read_bounded_bytes(path, max_bytes=0)
