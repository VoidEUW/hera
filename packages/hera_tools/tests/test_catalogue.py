"""The catalogue: namespacing, and the shape a request wants."""

from __future__ import annotations

from hera_tools.catalogue import Catalogue, Tool
from mcp.types import Tool as McpTool

SCHEMA = {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}


def _tool(server: str, name: str, description: str = "") -> Tool:
    return Tool.from_mcp(
        server, McpTool(name=name, description=description, inputSchema=dict(SCHEMA))
    )


def test_a_protocol_tool_becomes_a_namespaced_one() -> None:
    tool = _tool("fs", "read_file", "Read a file.")
    assert tool.name == "fs__read_file"
    assert tool.server == "fs"
    assert tool.local_name == "read_file"
    assert tool.description == "Read a file."
    assert tool.input_schema == SCHEMA


def test_a_tool_without_a_schema_still_has_one() -> None:
    """An endpoint given ``parameters: null`` rejects the whole request."""
    tool = Tool.from_mcp("fs", McpTool(name="ping", inputSchema={}))
    assert tool.input_schema == {"type": "object", "properties": {}}
    assert tool.as_function_spec()["parameters"] == {"type": "object", "properties": {}}


def test_the_function_spec_falls_back_to_the_title() -> None:
    tool = Tool.from_mcp("fs", McpTool(name="ping", title="Ping", inputSchema={}))
    assert tool.as_function_spec()["description"] == "Ping"


def test_the_function_spec_has_the_keys_tool_spec_wants() -> None:
    """``hera_providers.ToolSpec(**spec)`` is the whole mapping, and it stays that way."""
    assert set(_tool("fs", "read_file").as_function_spec()) == {
        "name",
        "description",
        "parameters",
    }


class TestCatalogue:
    def test_it_is_sorted_by_name(self) -> None:
        catalogue = Catalogue.of([_tool("fs", "write"), _tool("fs", "read"), _tool("db", "query")])
        assert catalogue.names() == ("db__query", "fs__read", "fs__write")

    def test_lookup(self) -> None:
        catalogue = Catalogue.of([_tool("fs", "read")])
        assert catalogue.get("fs__read") is not None
        assert catalogue.get("fs__nope") is None
        assert "fs__read" in catalogue
        assert "fs__nope" not in catalogue
        assert 7 not in catalogue
        assert len(catalogue) == 1

    def test_narrowing_to_one_server(self) -> None:
        catalogue = Catalogue.of([_tool("fs", "read"), _tool("db", "query")])
        assert catalogue.for_server("fs").names() == ("fs__read",)

    def test_the_whole_catalogue_as_function_specs(self) -> None:
        catalogue = Catalogue.of([_tool("fs", "read"), _tool("db", "query")])
        assert [spec["name"] for spec in catalogue.as_function_specs()] == [
            "db__query",
            "fs__read",
        ]

    def test_two_catalogues_over_the_same_tools_are_equal(self) -> None:
        """Sorting on construction is what makes this true whatever order servers answered in."""
        one = Catalogue.of([_tool("fs", "read"), _tool("db", "query")])
        other = Catalogue.of([_tool("db", "query"), _tool("fs", "read")])
        assert one == other
