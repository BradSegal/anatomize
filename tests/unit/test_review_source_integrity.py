from __future__ import annotations

from pathlib import Path

import pytest

from anatomize.evidence import RepositoryEvidence
from anatomize.providers import ProviderEnvelope
from anatomize.review import ReviewApplication, ReviewApplicationError, application
from anatomize.review.imports import normalize_builtin_source_facts


@pytest.mark.parametrize("include_source", [False, True])
def test_review_rejects_source_changed_during_acquisition(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, include_source: bool,
) -> None:
    (tmp_path / "core.py").write_text("def before(): pass\n")
    original = normalize_builtin_source_facts

    def change_source(*, baseline: RepositoryEvidence, root: Path) -> ProviderEnvelope | None:
        result = original(baseline=baseline, root=root)
        (root / "core.py").write_text("def after(): pass\n")
        return result

    monkeypatch.setattr(application, "normalize_builtin_source_facts", change_source)
    with pytest.raises(ReviewApplicationError) as caught:
        ReviewApplication().start(tmp_path, source_paths=["core.py"] if include_source else [])
    assert caught.value.code == "source_state_changed"
    assert caught.value.remediation


def test_review_can_capture_unchanged_invalid_python(tmp_path: Path) -> None:
    (tmp_path / "invalid.py").write_text("def invalid(:\n")
    bundle = ReviewApplication().start(tmp_path)
    baseline = next(item for item in bundle.manifest.providers if item.provider_id == "anatomize.repository-index")
    assert baseline.status.value == "partial"
