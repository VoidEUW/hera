"""Reading ``mcp.json``: the Claude-Desktop shape, and what a bad file does."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from hera_tools.config import (
    HttpServer,
    McpConfig,
    StdioServer,
    expand_variables,
    parse_server,
)
from hera_tools.errors import InvalidToolConfig, InvalidToolName

CLAUDE_DESKTOP_BLOCK = {
    "mcpServers": {
        "filesystem": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
            "env": {"LOG": "debug"},
        },
        "remote": {"url": "https://example.test/mcp", "headers": {"Authorization": "Bearer x"}},
    }
}


def test_a_claude_desktop_block_parses_unchanged() -> None:
    """The compatibility promise of ADR 4, as a test."""
    config = McpConfig.parse(CLAUDE_DESKTOP_BLOCK)

    filesystem = config.servers["filesystem"]
    assert isinstance(filesystem, StdioServer)
    assert filesystem.command == "npx"
    assert filesystem.args[0] == "-y"
    assert filesystem.env == {"LOG": "debug"}

    remote = config.servers["remote"]
    assert isinstance(remote, HttpServer)
    assert remote.headers == {"Authorization": "Bearer x"}


def test_unknown_keys_are_ignored() -> None:
    """A block written for another client has to keep working, or it cannot be copied."""
    server = parse_server("fs", {"command": "npx", "alwaysAllow": ["read"], "type": "stdio"})
    assert isinstance(server, StdioServer)


def test_a_server_needs_a_command_or_a_url() -> None:
    with pytest.raises(InvalidToolConfig, match="neither"):
        parse_server("fs", {"args": ["-y"]})


def test_a_server_may_not_have_both() -> None:
    with pytest.raises(InvalidToolConfig, match="both"):
        parse_server("fs", {"command": "npx", "url": "https://example.test/mcp"})


def test_a_server_name_is_validated_at_load() -> None:
    with pytest.raises(InvalidToolName):
        parse_server("my.server", {"command": "npx"})


def test_an_entry_must_be_an_object() -> None:
    with pytest.raises(InvalidToolConfig, match="must be an object"):
        McpConfig.parse({"mcpServers": {"fs": "npx"}})


def test_mcp_servers_must_be_an_object() -> None:
    with pytest.raises(InvalidToolConfig, match="must be an object"):
        McpConfig.parse({"mcpServers": []})


def test_a_document_without_servers_is_empty() -> None:
    assert McpConfig.parse({}).servers == {}


class TestVariables:
    def test_expansion(self) -> None:
        assert expand_variables("${TOKEN}", {"TOKEN": "secret"}) == "secret"

    def test_default(self) -> None:
        assert expand_variables("${TOKEN:-none}", {}) == "none"

    def test_a_missing_variable_is_an_error(self) -> None:
        """An empty credential fails minutes later, somewhere unrelated. Say it now."""
        with pytest.raises(InvalidToolConfig, match="TOKEN"):
            expand_variables("${TOKEN}", {})

    def test_expansion_reaches_into_nested_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TOKEN", "secret")
        server = parse_server(
            "remote", {"url": "https://${HOST:-example.test}/mcp", "headers": {"K": "${TOKEN}"}}
        )
        assert isinstance(server, HttpServer)
        assert server.url == "https://example.test/mcp"
        assert server.headers == {"K": "secret"}


class TestLoading:
    def test_a_missing_file_is_an_empty_configuration(self, tmp_path: Path) -> None:
        """A fresh ``~/.hera`` has no ``mcp.json``, and that is a working installation."""
        assert McpConfig.load(tmp_path / "mcp.json").servers == {}

    def test_a_file(self, tmp_path: Path) -> None:
        path = tmp_path / "mcp.json"
        path.write_text(json.dumps(CLAUDE_DESKTOP_BLOCK), encoding="utf-8")
        assert set(McpConfig.load(path).servers) == {"filesystem", "remote"}

    def test_broken_json_names_the_file(self, tmp_path: Path) -> None:
        path = tmp_path / "mcp.json"
        path.write_text("{not json", encoding="utf-8")
        with pytest.raises(InvalidToolConfig, match="not valid JSON"):
            McpConfig.load(path)

    def test_a_document_must_be_an_object(self, tmp_path: Path) -> None:
        path = tmp_path / "mcp.json"
        path.write_text("[]", encoding="utf-8")
        with pytest.raises(InvalidToolConfig, match="JSON object"):
            McpConfig.load(path)

    def test_a_directory_is_reported_rather_than_raised_raw(self, tmp_path: Path) -> None:
        with pytest.raises(InvalidToolConfig, match="cannot read"):
            McpConfig.load(tmp_path)


def test_disabled_servers_are_kept_but_not_started() -> None:
    config = McpConfig.parse(
        {"mcpServers": {"fs": {"command": "npx"}, "off": {"command": "npx", "enabled": False}}}
    )
    assert set(config.servers) == {"fs", "off"}
    assert set(config.enabled()) == {"fs"}
