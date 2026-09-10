from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest

from anatomize.index import build_repository_index
from anatomize.index.intelligence import definition_fingerprints
from anatomize.index.models import OccurrenceKind, ProviderCompleteness


def test_relative_imports_cannot_escape_the_package(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__init__.py").write_text("from ..external import target\n")
    (tmp_path / "pkg" / "valid.py").write_text("from .local import target\ntarget()\n")
    (tmp_path / "pkg" / "invalid.py").write_text("from ..external import target\ntarget()\n")
    (tmp_path / "pkg" / "local.py").write_text("def target(): pass\n")
    (tmp_path / "script.py").write_text("from .external import target\ntarget()\n")
    (tmp_path / "external.py").write_text("def target(): pass\n")

    index = build_repository_index(tmp_path)
    assert [(edge.importer_path, edge.imported_path) for edge in index.import_edges] == [
        ("pkg/valid.py", "pkg/local.py")
    ]
    references = [item for item in index.occurrences if item.kind is OccurrenceKind.REFERENCE]
    assert [(item.path, item.symbol_id) for item in references] == [
        ("pkg/valid.py", "python:pkg.local.target@pkg/local.py")
    ]


@pytest.mark.parametrize(
    "body",
    [
        "return [target() for target in values]",
        "return {target() for target in values}",
        "return {target(): value for target, value in values}",
        "return (target() for target in values)",
        "try:\n        pass\n    except Exception as target:\n        target()",
        "match values:\n        case {'fn': target}:\n            target()",
        "match values:\n        case [*target]:\n            target()",
        "match values:\n        case {'fn': _, **target}:\n            target()",
        "return lambda *target: target()",
        "return lambda **target: target()",
        "return lambda: ((target := lambda: None), target())[1]",
        "import unrelated as target\n    return target()",
    ],
)
def test_local_bindings_do_not_create_false_imported_consumers(tmp_path: Path, body: str) -> None:
    (tmp_path / "core.py").write_text("def target(): pass\n")
    (tmp_path / "use.py").write_text(f"from core import target\ndef use(values):\n    {body}\n")
    index = build_repository_index(tmp_path)
    assert not [item for item in index.occurrences if item.kind is OccurrenceKind.REFERENCE]


def test_comprehension_preserves_outer_iterable_and_binding(tmp_path: Path) -> None:
    (tmp_path / "core.py").write_text("def target(): pass\n")
    (tmp_path / "use.py").write_text(
        "from core import target\n"
        "def use():\n"
        "    values = [target() for target in target()]\n"
        "    return target()\n"
    )
    index = build_repository_index(tmp_path)
    references = [item for item in index.occurrences if item.kind is OccurrenceKind.REFERENCE]
    assert [(item.line, item.column) for item in references] == [(3, 37), (4, 11)]


def test_ambiguous_module_roots_do_not_choose_arbitrary_symbols(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    for path in (tmp_path / "core.py", tmp_path / "src" / "core.py"):
        path.write_text("def target(): pass\n")
    (tmp_path / "use.py").write_text("from core import target\ntarget()\n")
    index = build_repository_index(tmp_path)
    assert len(index.symbols) == 2
    assert not index.import_edges
    assert not [item for item in index.occurrences if item.kind is not OccurrenceKind.DEFINITION]


def test_definition_expressions_record_real_consumers(tmp_path: Path) -> None:
    (tmp_path / "core.py").write_text("def target(value=None): pass\n")
    (tmp_path / "use.py").write_text(
        "from core import target\n@target\ndef use(value=target()): pass\n"
        "class Child(target): pass\ncallback = lambda value=target(): value\n"
    )
    index = build_repository_index(tmp_path)
    references = [item for item in index.occurrences if item.kind is OccurrenceKind.REFERENCE]
    assert [item.line for item in references] == [2, 3, 4, 5]


def test_fingerprinting_normalizes_only_outer_name_without_mutating_ast() -> None:
    node = ast.parse("def first(x):\n    def nested(): return x\n    return nested()\n").body[0]
    renamed = ast.parse("def second(x):\n    def nested(): return x\n    return nested()\n").body[0]
    assert isinstance(node, ast.FunctionDef) and isinstance(renamed, ast.FunctionDef)
    original = ast.dump(node, include_attributes=True)
    fingerprints = definition_fingerprints(node)
    other = definition_fingerprints(renamed)
    assert ast.dump(node, include_attributes=True) == original
    assert fingerprints.structural_digest == other.structural_digest
    assert fingerprints.exact_digest != other.exact_digest
    assert fingerprints.exact_digest == hashlib.sha256(ast.dump(node).encode()).hexdigest()


def test_invalid_python_is_partial_and_portable(tmp_path: Path) -> None:
    for name in ("first", "second"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "invalid.py").write_text("def broken(:\n")
    before = build_repository_index(tmp_path / "first")
    after = build_repository_index(tmp_path / "second")
    assert before.limitations == after.limitations
    assert str(tmp_path) not in str(before.limitations)
    assert any(provider.completeness is ProviderCompleteness.PARTIAL for provider in before.providers)


def test_deep_python_syntax_retains_inventory_with_explicit_limitation(tmp_path: Path) -> None:
    (tmp_path / "deep.py").write_text("def expression():\n    return " + "+".join(["1"] * 3000) + "\n")
    index = build_repository_index(tmp_path)
    assert [item.path for item in index.files] == ["deep.py"]
    assert any("recursion limit" in item for item in index.limitations)


def test_method_receivers_are_resolved_only_while_the_original_binding_survives(tmp_path: Path) -> None:
    (tmp_path / "core.py").write_text(
        "class Example:\n"
        "    def target(self): pass\n"
        "    def real(self): return self.target()\n"
        "    def closed(self): return lambda: self.target()\n"
        "    def shadowed(self, items): return [self.target() for self in items]\n"
        "    def rebound(self, other):\n"
        "        self = other\n"
        "        return self.target()\n"
        "    def lambda_arg(self): return lambda self: self.target()\n"
        "    @staticmethod\n"
        "    def static(self): return self.target()\n"
    )
    index = build_repository_index(tmp_path)
    references = [item for item in index.occurrences if item.kind is OccurrenceKind.REFERENCE]
    assert [(item.line, item.symbol_id) for item in references] == [
        (3, "python:core.Example.target@core.py"), (4, "python:core.Example.target@core.py"),
    ]
