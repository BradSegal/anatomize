from __future__ import annotations

import hashlib
import os
import tracemalloc
from collections.abc import Iterator
from pathlib import Path
from typing import NoReturn, TypeVar

import pytest

from anatomize._artifacts import canonical_ordered_json_bytes
from anatomize.dossiers import (
    BudgetCounter,
    Dossier,
    DossierContext,
    DossierEngine,
    DossierLocator,
    DossierProfile,
    TargetKind,
    TargetResolutionStatus,
    TargetSelector,
    build_dossier_request,
    canonical_dossier_bytes,
)
from anatomize.evidence import RepositoryEvidence, SymbolEntity
from anatomize.index import build_repository_index
from anatomize.index.git import git_bytes, git_text
from anatomize.review import ReviewApplication
from anatomize.review.imports import _SymbolLookup
from tests._git import run_git
from tests.unit.test_dossier_engine import _context

pytestmark = pytest.mark.unit
_Value = TypeVar("_Value")


class _LookupOnlyDict(dict[str, _Value]):
    def values(self) -> NoReturn:
        raise AssertionError("A symbol lookup must not scan all evidence records")


@pytest.mark.parametrize("initial_size", [9_995, 9_996, 9_997, 9_999, 10_000])
@pytest.mark.parametrize("prior_used", [0, 7, 54_321])
def test_payload_byte_accounting_preserves_exact_serialization_at_decimal_boundaries(
    initial_size: int, prior_used: int
) -> None:
    context = _context()
    engine = DossierEngine(context)

    def prepared(question_size: int) -> Dossier:
        dossier = engine.query(
            build_dossier_request(
                profile=DossierProfile.LOCALISATION,
                question="x" * question_size,
                session_id=context.session_id,
                session_manifest_digest=context.session_manifest_digest,
                targets=[TargetSelector(kind=TargetKind.SYMBOL, identity="entity:missing")],
            )
        )
        use = dossier.budget_use.model_copy(
            update={
                "payload_bytes": BudgetCounter(limit=dossier.budget_use.payload_bytes.limit, used=prior_used),
            }
        )
        return dossier.model_copy(update={"budget_use": use})

    base_size = len(canonical_dossier_bytes(prepared(1)))
    original = prepared(1 + initial_size - base_size)
    assert len(canonical_dossier_bytes(original)) == initial_size
    result = engine._with_payload_use(original, initial_size)
    encoded_size = len(canonical_dossier_bytes(result))
    assert result.budget_use.payload_bytes.used == encoded_size
    expected = original.model_dump(mode="json")
    measured = initial_size
    for _ in range(4):
        expected["budget_use"]["payload_bytes"]["used"] = measured
        actual_size = len(canonical_ordered_json_bytes(expected))
        if actual_size == measured:
            break
        measured = actual_size
    else:
        pytest.fail("The serialization reference did not converge")
    assert result.model_dump(mode="json") == expected
    assert Dossier.model_validate(expected) == result


def test_opaque_file_inventory_uses_bounded_memory_and_preserves_bytes(tmp_path: Path) -> None:
    content = bytes(range(256)) * 32_768
    (tmp_path / "opaque.bin").write_bytes(content)

    tracemalloc.start()
    try:
        index = build_repository_index(tmp_path)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert [(item.path, item.size, item.digest) for item in index.files] == [
        ("opaque.bin", len(content), hashlib.sha256(content).hexdigest())
    ]
    assert peak < 4 * 1024 * 1024


def test_non_git_inventory_does_not_enter_excluded_or_symlink_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    excluded = root / ".venv"
    excluded.mkdir()
    (excluded / "hidden.py").write_text("hidden = True\n", encoding="utf-8")
    external = tmp_path / "external"
    external.mkdir()
    (external / "outside.py").write_text("outside = True\n", encoding="utf-8")
    (root / "linked").symlink_to(external, target_is_directory=True)
    (root / "visible.py").write_text("visible = True\n", encoding="utf-8")
    original_scandir = os.scandir

    def guarded_scandir(path: str | os.PathLike[str]) -> Iterator[os.DirEntry[str]]:
        candidate = Path(path)
        assert candidate != excluded and excluded not in candidate.parents
        assert candidate != root / "linked"
        return original_scandir(path)

    monkeypatch.setattr(os, "scandir", guarded_scandir)
    index = build_repository_index(root)
    assert [item.path for item in index.files] == ["visible.py"]


def test_git_inventory_rejects_tracked_files_beneath_symlinked_parent(tmp_path: Path) -> None:
    root = tmp_path / "repository"
    root.mkdir()
    package = root / "pkg"
    package.mkdir()
    tracked = package / "hidden.py"
    tracked.write_text("original = True\n", encoding="utf-8")
    (root / "visible.py").write_text("visible = True\n", encoding="utf-8")
    run_git(root, "init", "-q")
    run_git(root, "add", ".")
    external = tmp_path / "external"
    external.mkdir()
    (external / "hidden.py").write_text("outside = True\n", encoding="utf-8")
    tracked.unlink()
    package.rmdir()
    package.symlink_to(external, target_is_directory=True)

    index = build_repository_index(root)
    assert [item.path for item in index.files] == ["visible.py"]
    assert [item.path for item in index.modules] == ["visible.py"]


def test_source_inventory_remains_available_without_git(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "source.py").write_text("def answer():\n    return 42\n", encoding="utf-8")
    monkeypatch.setenv("PATH", "")
    for helper in (git_text, git_bytes):
        with pytest.raises(ValueError, match="could not be executed") as caught:
            helper(tmp_path, ["status"])
        assert isinstance(caught.value.__cause__, FileNotFoundError)

    index = build_repository_index(tmp_path)
    assert [item.name for item in index.symbols] == ["answer"]
    assert index.source_state.commit is None


@pytest.mark.parametrize("by_qualified_name", [False, True])
@pytest.mark.parametrize("state", [None, "state:before", "state:after", "state:missing"])
def test_symbol_locator_uses_candidate_lookup_and_preserves_source_state_ambiguity(
    by_qualified_name: bool, state: str | None
) -> None:
    context = _context()
    engine = DossierEngine(context)
    engine._records = _LookupOnlyDict(engine._records)
    engine._entities = _LookupOnlyDict(engine._entities)
    dossier = engine.query(
        build_dossier_request(
            profile=DossierProfile.LOCALISATION,
            question="Locate answer in the requested source state.",
            session_id=context.session_id,
            session_manifest_digest=context.session_manifest_digest,
            targets=[
                TargetSelector(
                    kind=TargetKind.SYMBOL,
                    locator=(
                        DossierLocator(qualified_name="pkg.core.answer")
                        if by_qualified_name
                        else DossierLocator(name="answer")
                    ),
                    source_state_id=state,
                )
            ],
        )
    )
    target = dossier.boundary.targets[0]
    if state is None:
        assert target.status is TargetResolutionStatus.AMBIGUOUS
        assert target.resolved_ids == ["entity:symbol-after", "entity:symbol-before"]
    elif state == "state:missing":
        assert target.status is TargetResolutionStatus.UNRESOLVED
        assert target.resolved_ids == []
    else:
        assert target.status is TargetResolutionStatus.EXACT
        assert target.resolved_ids == [f"entity:symbol-{state.removeprefix('state:')}"]


def test_symbol_locator_path_disambiguates_definitions_and_rejects_mismatches(tmp_path: Path) -> None:
    for name in ("left", "right"):
        (tmp_path / f"{name}.py").write_text("def shared():\n    return 1\n", encoding="utf-8")
    bundle = ReviewApplication().start(tmp_path)
    context = DossierContext.from_bundle(bundle)
    engine = DossierEngine(context)
    engine._records = _LookupOnlyDict(engine._records)
    engine._entities = _LookupOnlyDict(engine._entities)
    for locator, expected, status in [
        (DossierLocator(name="shared"), {"left.shared", "right.shared"}, TargetResolutionStatus.AMBIGUOUS),
        (DossierLocator(name="shared", path="left.py"), {"left.shared"}, TargetResolutionStatus.EXACT),
        (DossierLocator(name="shared", path="right.py"), {"right.shared"}, TargetResolutionStatus.EXACT),
        (DossierLocator(name="left.shared"), {"left.shared"}, TargetResolutionStatus.EXACT),
        (DossierLocator(name="shared", path="missing.py"), set(), TargetResolutionStatus.UNRESOLVED),
        (
            DossierLocator(qualified_name="left.shared", path="right.py"),
            set(),
            TargetResolutionStatus.UNRESOLVED,
        ),
    ]:
        dossier = engine.query(
            build_dossier_request(
                profile=DossierProfile.LOCALISATION,
                question="Locate the definition in this file.",
                session_id=context.session_id,
                session_manifest_digest=context.session_manifest_digest,
                targets=[TargetSelector(kind=TargetKind.SYMBOL, locator=locator)],
            )
        )
        target = dossier.boundary.targets[0]
        assert target.status is status
        assert {engine._entities[identity].display_name for identity in target.resolved_ids} == expected


@pytest.mark.parametrize("path", ["src/pkg/core.py", "unrelated.py"])
def test_symbol_alias_fallback_respects_explicit_path(path: str) -> None:
    base = _context()
    payload = base.evidence[0].model_dump(mode="json")
    payload["aliases"][0]["value"] = "exported_answer"
    context = DossierContext.from_evidence(
        session_id=base.session_id,
        session_manifest_digest=base.session_manifest_digest,
        repository_id=base.repository_id,
        source_state_ids=list(base.source_state_ids),
        provider_run_ids=list(base.provider_run_ids),
        policy_digest=base.policy_digest,
        evidence=[RepositoryEvidence.model_validate(payload)],
    )
    dossier = DossierEngine(context).query(
        build_dossier_request(
            profile=DossierProfile.LOCALISATION,
            question="Locate the aliased definition in this file.",
            session_id=context.session_id,
            session_manifest_digest=context.session_manifest_digest,
            targets=[
                TargetSelector(
                    kind=TargetKind.SYMBOL,
                    locator=DossierLocator(name="exported_answer", path=path),
                )
            ],
        )
    )
    target = dossier.boundary.targets[0]
    if path == "src/pkg/core.py":
        assert target.status is TargetResolutionStatus.EXACT
        assert target.resolved_ids == ["entity:symbol-after"]
    else:
        assert target.status is TargetResolutionStatus.UNRESOLVED
        assert target.resolved_ids == []


@pytest.mark.parametrize(
    ("reference", "expected"),
    [
        ("single", {"single"}),
        ("module.single", {"single"}),
        ("package::single", {"single"}),
        ("renamed.location", {"aliased"}),
        ("module.shared", {"shared-left", "shared-right"}),
        ("package::shared", {"shared-left", "shared-right"}),
        ("prefix.dotted.name", {"dotted", "short"}),
        ("prefix::dotted.name", {"dotted", "short"}),
        ("package:::a", {"backticked"}),
        ("prefix.renamed.location", set()),
        ("unknown", set()),
    ],
)
def test_symbol_lookup_preserves_qualified_suffix_and_ambiguous_candidates(
    reference: str, expected: set[str]
) -> None:
    declarations = [
        ("single", "single", "module.single"),
        ("aliased", "alias", "renamed.location"),
        ("shared-left", "shared", "left.shared"),
        ("shared-right", "shared", "right.shared"),
        ("dotted", "dotted.name", "package.dotted.name"),
        ("short", "name", "other.name"),
        ("backticked", ":a", "package.:a"),
    ]
    symbols = [
        SymbolEntity(
            entity_id=identity,
            source_state_id="state:lookup",
            display_name=qualified,
            language="r",
            symbol_kind="function",
            name=name,
            qualified_name=qualified,
        )
        for identity, name, qualified in declarations
    ]
    lookup = _SymbolLookup([*symbols, symbols[0]])
    assert set(lookup.candidates(reference)) == expected
