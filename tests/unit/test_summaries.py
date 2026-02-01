"""Unit tests for summary generation."""

from __future__ import annotations

import pytest

from anatomize.pack.summaries import (
    SummaryConfig,
    _outline_paths,
    json_summary,
    markdown_summary,
    summary_for_text,
    toml_summary,
    yaml_summary,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def default_config() -> SummaryConfig:
    """Create default summary config."""
    return SummaryConfig()


class TestSummaryConfig:
    """Tests for SummaryConfig validation."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        cfg = SummaryConfig()
        assert cfg.max_depth == 3
        assert cfg.max_keys == 200
        assert cfg.max_items == 200
        assert cfg.max_headings == 200

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        cfg = SummaryConfig(max_depth=5, max_keys=50)
        assert cfg.max_depth == 5
        assert cfg.max_keys == 50

    def test_min_value_constraint(self) -> None:
        """Test that values must be >= 1."""
        with pytest.raises(ValueError):
            SummaryConfig(max_depth=0)


class TestJsonSummary:
    """Tests for json_summary function."""

    def test_simple_object(self, default_config: SummaryConfig) -> None:
        """Test summary of a simple JSON object."""
        text = '{"a": 1, "b": 2}'
        result = json_summary(text, cfg=default_config)
        assert result["type"] == "json"
        assert "a" in result["paths"]
        assert "b" in result["paths"]

    def test_nested_object(self, default_config: SummaryConfig) -> None:
        """Test summary of nested JSON objects."""
        text = '{"outer": {"inner": 1}}'
        result = json_summary(text, cfg=default_config)
        assert "outer" in result["paths"]
        assert "outer.inner" in result["paths"]

    def test_array_elements(self, default_config: SummaryConfig) -> None:
        """Test summary of JSON arrays."""
        text = '[{"a": 1}, {"b": 2}]'
        result = json_summary(text, cfg=default_config)
        assert "[0]" in result["paths"]
        assert "[0].a" in result["paths"]
        assert "[1]" in result["paths"]
        assert "[1].b" in result["paths"]

    def test_invalid_json_raises(self, default_config: SummaryConfig) -> None:
        """Test that invalid JSON raises ValueError."""
        with pytest.raises(ValueError, match="Failed to parse JSON"):
            json_summary("{invalid", cfg=default_config)

    def test_respects_max_depth(self) -> None:
        """Test that max_depth limits traversal."""
        cfg = SummaryConfig(max_depth=1)
        text = '{"a": {"b": {"c": 1}}}'
        result = json_summary(text, cfg=cfg)
        assert "a" in result["paths"]
        assert "a.b" not in result["paths"]

    def test_empty_object(self, default_config: SummaryConfig) -> None:
        """Test summary of empty JSON object."""
        text = "{}"
        result = json_summary(text, cfg=default_config)
        assert result["type"] == "json"
        assert result["paths"] == []

    def test_empty_array(self, default_config: SummaryConfig) -> None:
        """Test summary of empty JSON array."""
        text = "[]"
        result = json_summary(text, cfg=default_config)
        assert result["type"] == "json"
        assert result["paths"] == []


class TestYamlSummary:
    """Tests for yaml_summary function."""

    def test_simple_mapping(self, default_config: SummaryConfig) -> None:
        """Test summary of a simple YAML mapping."""
        text = "a: 1\nb: 2"
        result = yaml_summary(text, cfg=default_config)
        assert result["type"] == "yaml"
        assert "a" in result["paths"]
        assert "b" in result["paths"]

    def test_nested_mapping(self, default_config: SummaryConfig) -> None:
        """Test summary of nested YAML mappings."""
        text = "outer:\n  inner: 1"
        result = yaml_summary(text, cfg=default_config)
        assert "outer" in result["paths"]
        assert "outer.inner" in result["paths"]

    def test_invalid_yaml_raises(self, default_config: SummaryConfig) -> None:
        """Test that invalid YAML raises ValueError."""
        with pytest.raises(ValueError, match="Failed to parse YAML"):
            yaml_summary("key: [invalid", cfg=default_config)

    def test_null_yaml(self, default_config: SummaryConfig) -> None:
        """Test summary of null YAML document."""
        text = "~"
        result = yaml_summary(text, cfg=default_config)
        assert result["type"] == "yaml"
        assert result["paths"] == []


class TestTomlSummary:
    """Tests for toml_summary function."""

    def test_simple_table(self, default_config: SummaryConfig) -> None:
        """Test summary of a simple TOML table."""
        text = 'key = "value"\nnum = 42'
        result = toml_summary(text, cfg=default_config)
        assert result["type"] == "toml"
        assert "key" in result["paths"]
        assert "num" in result["paths"]

    def test_nested_table(self, default_config: SummaryConfig) -> None:
        """Test summary of nested TOML tables."""
        text = "[section]\nkey = 1"
        result = toml_summary(text, cfg=default_config)
        assert "section" in result["paths"]
        assert "section.key" in result["paths"]

    def test_invalid_toml_raises(self, default_config: SummaryConfig) -> None:
        """Test that invalid TOML raises ValueError."""
        with pytest.raises(ValueError, match="Failed to parse TOML"):
            toml_summary("key = [invalid", cfg=default_config)


class TestMarkdownSummary:
    """Tests for markdown_summary function."""

    def test_extracts_headings(self, default_config: SummaryConfig) -> None:
        """Test extraction of Markdown headings."""
        text = "# H1\n## H2\n### H3"
        result = markdown_summary(text, cfg=default_config)
        assert result["type"] == "markdown"
        assert len(result["headings"]) == 3
        assert result["headings"][0]["level"] == 1
        assert result["headings"][0]["text"] == "H1"
        assert result["headings"][1]["level"] == 2
        assert result["headings"][2]["level"] == 3

    def test_respects_max_headings(self) -> None:
        """Test that max_headings limits extraction."""
        cfg = SummaryConfig(max_headings=2)
        text = "# H1\n## H2\n### H3\n#### H4"
        result = markdown_summary(text, cfg=cfg)
        assert len(result["headings"]) == 2

    def test_no_headings(self, default_config: SummaryConfig) -> None:
        """Test document with no headings."""
        text = "Just some text without headings."
        result = markdown_summary(text, cfg=default_config)
        assert result["type"] == "markdown"
        assert result["headings"] == []

    def test_heading_with_leading_spaces(self, default_config: SummaryConfig) -> None:
        """Test that headings must start at line beginning."""
        text = "  # Not a heading\n# Real heading"
        result = markdown_summary(text, cfg=default_config)
        assert len(result["headings"]) == 1
        assert result["headings"][0]["text"] == "Real heading"


class TestSummaryForText:
    """Tests for summary_for_text router function."""

    def test_routes_json(self, default_config: SummaryConfig) -> None:
        """Test routing to JSON summary."""
        result = summary_for_text(suffix=".json", text="{}", rel_posix="test.json", cfg=default_config)
        assert result["type"] == "json"

    def test_routes_yaml(self, default_config: SummaryConfig) -> None:
        """Test routing to YAML summary."""
        result = summary_for_text(suffix=".yaml", text="key: 1", rel_posix="test.yaml", cfg=default_config)
        assert result["type"] == "yaml"

    def test_routes_yml(self, default_config: SummaryConfig) -> None:
        """Test routing .yml extension to YAML summary."""
        result = summary_for_text(suffix=".yml", text="key: 1", rel_posix="test.yml", cfg=default_config)
        assert result["type"] == "yaml"

    def test_routes_toml(self, default_config: SummaryConfig) -> None:
        """Test routing to TOML summary."""
        result = summary_for_text(suffix=".toml", text='key = "val"', rel_posix="test.toml", cfg=default_config)
        assert result["type"] == "toml"

    def test_routes_markdown(self, default_config: SummaryConfig) -> None:
        """Test routing to Markdown summary."""
        result = summary_for_text(suffix=".md", text="# H1", rel_posix="test.md", cfg=default_config)
        assert result["type"] == "markdown"

    def test_unsupported_raises(self, default_config: SummaryConfig) -> None:
        """Test that unsupported suffix raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported summary type"):
            summary_for_text(suffix=".txt", text="hello", rel_posix="test.txt", cfg=default_config)


class TestOutlinePaths:
    """Tests for _outline_paths helper function."""

    def test_dict_keys(self) -> None:
        """Test extraction of dictionary keys."""
        paths = _outline_paths({"a": 1, "b": 2}, max_depth=3, max_items=100, max_keys=100)
        assert paths == ["a", "b"]

    def test_sorted_keys(self) -> None:
        """Test that keys are sorted."""
        paths = _outline_paths({"z": 1, "a": 2, "m": 3}, max_depth=3, max_items=100, max_keys=100)
        assert paths == ["a", "m", "z"]

    def test_max_keys_limit(self) -> None:
        """Test max_keys constraint."""
        obj = {f"key{i}": i for i in range(10)}
        paths = _outline_paths(obj, max_depth=3, max_items=100, max_keys=3)
        assert len(paths) == 3

    def test_max_items_limit(self) -> None:
        """Test max_items constraint."""
        obj = {"a": [1, 2, 3, 4, 5]}
        paths = _outline_paths(obj, max_depth=3, max_items=3, max_keys=100)
        assert len(paths) == 3

    def test_max_depth_limit(self) -> None:
        """Test max_depth constraint."""
        obj = {"a": {"b": {"c": {"d": 1}}}}
        paths = _outline_paths(obj, max_depth=2, max_items=100, max_keys=100)
        assert "a" in paths
        assert "a.b" in paths
        assert "a.b.c" not in paths

    def test_list_indices(self) -> None:
        """Test list index formatting."""
        obj = [1, 2, 3]
        paths = _outline_paths(obj, max_depth=3, max_items=100, max_keys=100)
        assert "[0]" in paths
        assert "[1]" in paths
        assert "[2]" in paths

    def test_nested_path_format(self) -> None:
        """Test nested path formatting."""
        obj = {"a": {"b": [{"c": 1}]}}
        paths = _outline_paths(obj, max_depth=5, max_items=100, max_keys=100)
        assert "a" in paths
        assert "a.b" in paths
        assert "a.b[0]" in paths
        assert "a.b[0].c" in paths
