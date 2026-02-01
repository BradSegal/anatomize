"""Unit tests for Python compression."""

from __future__ import annotations

import pytest

from anatomize.core.types import AttributeInfo, ClassInfo, FunctionInfo, ModuleInfo
from anatomize.pack.compress import _render_class, _render_function, render_module

pytestmark = pytest.mark.unit


class TestRenderModule:
    """Tests for render_module function."""

    def test_includes_docstring(self) -> None:
        """Test that module docstring is included."""
        info = ModuleInfo(path="test.py", name="test", source=0, doc="Module doc")
        result = render_module(info)
        assert '""" Module doc """' in result

    def test_includes_imports(self) -> None:
        """Test that imports are included."""
        info = ModuleInfo(path="test.py", name="test", source=0, imports=["import os", "from typing import List"])
        result = render_module(info)
        assert "import os" in result
        assert "from typing import List" in result

    def test_renders_constants_with_annotation_and_default(self) -> None:
        """Test constant rendering with both annotation and default."""
        info = ModuleInfo(
            path="test.py",
            name="test",
            source=0,
            constants=[AttributeInfo(name="FOO", line=1, annotation="int", default="42")],
        )
        result = render_module(info)
        assert "FOO: int = 42" in result

    def test_renders_constants_with_annotation_only(self) -> None:
        """Test constant rendering with annotation only."""
        info = ModuleInfo(
            path="test.py",
            name="test",
            source=0,
            constants=[AttributeInfo(name="BAR", line=1, annotation="str")],
        )
        result = render_module(info)
        assert "BAR: str" in result

    def test_renders_constants_with_default_only(self) -> None:
        """Test constant rendering with default only."""
        info = ModuleInfo(
            path="test.py",
            name="test",
            source=0,
            constants=[AttributeInfo(name="BAZ", line=1, default='"value"')],
        )
        result = render_module(info)
        assert 'BAZ = "value"' in result

    def test_renders_functions(self) -> None:
        """Test function rendering."""
        fn = FunctionInfo(name="foo", line=1, signature="(x: int) -> int")
        info = ModuleInfo(path="test.py", name="test", source=0, functions=[fn])
        result = render_module(info)
        assert "def foo(x: int) -> int: ..." in result

    def test_renders_classes(self) -> None:
        """Test class rendering."""
        cls = ClassInfo(name="Foo", line=1)
        info = ModuleInfo(path="test.py", name="test", source=0, classes=[cls])
        result = render_module(info)
        assert "class Foo:" in result

    def test_output_ends_with_newline(self) -> None:
        """Test that output ends with newline."""
        info = ModuleInfo(path="test.py", name="test", source=0)
        result = render_module(info)
        assert result.endswith("\n")

    def test_empty_module(self) -> None:
        """Test rendering of empty module."""
        info = ModuleInfo(path="test.py", name="test", source=0)
        result = render_module(info)
        assert result == "\n"

    def test_sorts_by_line_number(self) -> None:
        """Test that elements are sorted by line number."""
        fn1 = FunctionInfo(name="zebra", line=10, signature="() -> None")
        fn2 = FunctionInfo(name="alpha", line=5, signature="() -> None")
        info = ModuleInfo(path="test.py", name="test", source=0, functions=[fn1, fn2])
        result = render_module(info)
        # alpha (line 5) should come before zebra (line 10)
        assert result.index("def alpha") < result.index("def zebra")


class TestRenderFunction:
    """Tests for _render_function helper."""

    def test_basic_function(self) -> None:
        """Test basic function rendering."""
        fn = FunctionInfo(name="foo", line=1, signature="() -> None")
        lines = _render_function(fn)
        assert any("def foo() -> None: ..." in line for line in lines)

    def test_async_function(self) -> None:
        """Test async function rendering."""
        fn = FunctionInfo(name="bar", line=1, signature="() -> None", is_async=True)
        lines = _render_function(fn)
        assert any("async def bar() -> None: ..." in line for line in lines)

    def test_with_decorators(self) -> None:
        """Test function with decorators."""
        fn = FunctionInfo(name="baz", line=1, signature="() -> None", decorators=["staticmethod", "cached"])
        lines = _render_function(fn)
        assert any("@staticmethod" in line for line in lines)
        assert any("@cached" in line for line in lines)

    def test_with_indent(self) -> None:
        """Test function rendering with indent (for methods)."""
        fn = FunctionInfo(name="method", line=1, signature="(self) -> None")
        lines = _render_function(fn, indent="    ")
        assert any("    def method(self) -> None: ..." in line for line in lines)

    def test_decorator_ordering(self) -> None:
        """Test that decorators come before def."""
        fn = FunctionInfo(name="func", line=1, signature="() -> None", decorators=["deco"])
        lines = _render_function(fn)
        deco_idx = next(i for i, line in enumerate(lines) if "@deco" in line)
        def_idx = next(i for i, line in enumerate(lines) if "def func" in line)
        assert deco_idx < def_idx


class TestRenderClass:
    """Tests for _render_class helper."""

    def test_basic_class(self) -> None:
        """Test basic class rendering."""
        cls = ClassInfo(name="Foo", line=1)
        lines = _render_class(cls)
        assert any("class Foo:" in line for line in lines)

    def test_with_bases(self) -> None:
        """Test class with base classes."""
        cls = ClassInfo(name="Foo", line=1, bases=["Bar", "Baz"])
        lines = _render_class(cls)
        assert any("class Foo(Bar, Baz):" in line for line in lines)

    def test_with_decorators(self) -> None:
        """Test class with decorators."""
        cls = ClassInfo(name="Foo", line=1, decorators=["dataclass"])
        lines = _render_class(cls)
        assert any("@dataclass" in line for line in lines)

    def test_empty_class_has_ellipsis(self) -> None:
        """Test that empty class body contains ellipsis."""
        cls = ClassInfo(name="Empty", line=1)
        lines = _render_class(cls)
        assert any("..." in line for line in lines)

    def test_with_attributes(self) -> None:
        """Test class with attributes."""
        cls = ClassInfo(
            name="Foo",
            line=1,
            attributes=[
                AttributeInfo(name="x", line=2, annotation="int"),
                AttributeInfo(name="y", line=3, annotation="str", default='"default"'),
            ],
        )
        lines = _render_class(cls)
        joined = "\n".join(lines)
        assert "x: int" in joined
        assert 'y: str = "default"' in joined

    def test_with_methods(self) -> None:
        """Test class with methods."""
        cls = ClassInfo(
            name="Foo",
            line=1,
            methods=[FunctionInfo(name="method", line=5, signature="(self) -> None")],
        )
        lines = _render_class(cls)
        joined = "\n".join(lines)
        assert "def method(self) -> None: ..." in joined

    def test_method_indentation(self) -> None:
        """Test that methods are properly indented."""
        cls = ClassInfo(
            name="Foo",
            line=1,
            methods=[FunctionInfo(name="method", line=5, signature="(self) -> None")],
        )
        lines = _render_class(cls)
        method_line = next(line for line in lines if "def method" in line)
        assert method_line.startswith("    ")

    def test_attribute_indentation(self) -> None:
        """Test that attributes are properly indented."""
        cls = ClassInfo(
            name="Foo",
            line=1,
            attributes=[AttributeInfo(name="x", line=2, annotation="int")],
        )
        lines = _render_class(cls)
        attr_line = next(line for line in lines if "x: int" in line)
        assert attr_line.startswith("    ")

    def test_class_with_no_bases_no_parens(self) -> None:
        """Test that class with no bases has no parentheses."""
        cls = ClassInfo(name="Foo", line=1)
        lines = _render_class(cls)
        class_line = next(line for line in lines if "class Foo" in line)
        assert "class Foo:" in class_line
        assert "class Foo():" not in class_line

    def test_sorts_methods_by_line(self) -> None:
        """Test that methods are sorted by line number."""
        cls = ClassInfo(
            name="Foo",
            line=1,
            methods=[
                FunctionInfo(name="zebra", line=20, signature="(self) -> None"),
                FunctionInfo(name="alpha", line=10, signature="(self) -> None"),
            ],
        )
        lines = _render_class(cls)
        joined = "\n".join(lines)
        assert joined.index("def alpha") < joined.index("def zebra")
