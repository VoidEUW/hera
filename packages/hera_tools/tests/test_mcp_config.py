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


class TestWriting:
    """The file is edited as JSON, so what the file says that this client does not read survives."""

    def test_a_server_is_added_beside_the_others(self, tmp_path: Path) -> None:
        from hera_tools.config import put_server, raw_servers

        path = tmp_path / "mcp.json"
        path.write_text(json.dumps(CLAUDE_DESKTOP_BLOCK), encoding="utf-8")

        existed = put_server(path, "fresh", {"command": "uvx", "args": ["thing"]})

        assert existed is False
        assert set(raw_servers(path)) == {"filesystem", "remote", "fresh"}
        assert raw_servers(path)["remote"] == CLAUDE_DESKTOP_BLOCK["mcpServers"]["remote"]

    def test_the_rest_of_the_document_is_left_alone(self, tmp_path: Path) -> None:
        from hera_tools.config import put_server, read_raw

        path = tmp_path / "mcp.json"
        path.write_text(
            json.dumps(
                {"note": "mine", "mcpServers": {"a": {"command": "x", "alwaysAllow": ["r"]}}}
            ),
            encoding="utf-8",
        )

        put_server(path, "b", {"command": "y"})

        document = read_raw(path)
        assert document["note"] == "mine"
        assert document["mcpServers"]["a"]["alwaysAllow"] == ["r"]

    def test_a_variable_reference_is_written_as_a_reference(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The reason the file is not saved back from the parsed model, which holds the secret."""
        from hera_tools.config import put_server

        monkeypatch.setenv("HERA_TEST_TOKEN", "s3cret")
        path = tmp_path / "mcp.json"

        put_server(path, "gh", {"command": "x", "env": {"TOKEN": "${HERA_TEST_TOKEN}"}})

        assert "s3cret" not in path.read_text(encoding="utf-8")
        assert "${HERA_TEST_TOKEN}" in path.read_text(encoding="utf-8")

    def test_a_bad_entry_is_refused_and_nothing_is_written(self, tmp_path: Path) -> None:
        from hera_tools.config import put_server

        path = tmp_path / "mcp.json"
        with pytest.raises(InvalidToolConfig):
            put_server(path, "bad", {"args": ["-y"]})
        with pytest.raises(InvalidToolConfig, match="not set"):
            put_server(path, "bad", {"command": "x", "env": {"A": "${HERA_NOT_SET_ANYWHERE}"}})
        with pytest.raises(InvalidToolName):
            put_server(path, "has__two", {"command": "x"})

        assert not path.exists()

    def test_a_file_nobody_can_parse_is_not_written_over(self, tmp_path: Path) -> None:
        from hera_tools.config import put_server, remove_server

        path = tmp_path / "mcp.json"
        path.write_text("{ not json", encoding="utf-8")

        with pytest.raises(InvalidToolConfig, match="not valid JSON"):
            put_server(path, "a", {"command": "x"})
        with pytest.raises(InvalidToolConfig):
            remove_server(path, "a")

        assert path.read_text(encoding="utf-8") == "{ not json"

    def test_replacing_says_the_server_existed(self, tmp_path: Path) -> None:
        from hera_tools.config import put_server

        path = tmp_path / "mcp.json"
        put_server(path, "a", {"command": "x"})
        assert put_server(path, "a", {"command": "y"}) is True

    def test_removing_one_leaves_the_rest(self, tmp_path: Path) -> None:
        from hera_tools.config import raw_servers, remove_server

        path = tmp_path / "mcp.json"
        path.write_text(json.dumps(CLAUDE_DESKTOP_BLOCK), encoding="utf-8")

        assert remove_server(path, "remote") is True
        assert remove_server(path, "remote") is False
        assert set(raw_servers(path)) == {"filesystem"}

    def test_a_missing_file_reads_as_nothing(self, tmp_path: Path) -> None:
        from hera_tools.config import raw_servers, remove_server

        assert raw_servers(tmp_path / "mcp.json") == {}
        assert remove_server(tmp_path / "mcp.json", "a") is False


class TestSecrets:
    def test_a_literal_is_hidden_and_a_reference_is_shown(self) -> None:
        from hera_tools.config import mask

        shown = mask(
            {
                "command": "x",
                "env": {"TOKEN": "${GH}", "PLAIN": "hunter2", "MIXED": "Bearer ${GH}"},
                "headers": {"Authorization": "Bearer abc"},
            }
        )

        assert shown["env"] == {"TOKEN": "${GH}", "PLAIN": None, "MIXED": "Bearer ${GH}"}
        assert shown["headers"] == {"Authorization": None}
        assert shown["command"] == "x"

    def test_a_hidden_value_keeps_what_was_stored(self) -> None:
        from hera_tools.config import merge

        stored = {"command": "x", "env": {"A": "one", "B": "two"}, "alwaysAllow": ["r"]}
        written = merge(stored, {"command": "x", "env": {"A": None, "B": "changed", "C": "new"}})

        assert written["env"] == {"A": "one", "B": "changed", "C": "new"}
        assert written["alwaysAllow"] == ["r"]

    def test_a_key_the_form_dropped_is_gone(self) -> None:
        from hera_tools.config import merge

        written = merge(
            {"command": "x", "env": {"A": "one", "B": "two"}}, {"command": "x", "env": {"B": None}}
        )
        assert written["env"] == {"B": "two"}

    def test_a_hidden_value_with_nothing_stored_is_dropped_not_written_as_null(self) -> None:
        from hera_tools.config import merge

        assert merge(None, {"command": "x", "env": {"A": None}})["env"] == {}

    def test_switching_kind_does_not_keep_the_old_kinds_keys(self) -> None:
        from hera_tools.config import merge

        written = merge(
            {"command": "x", "args": ["a"], "env": {"A": "1"}}, {"url": "https://e.test/mcp"}
        )
        assert written == {"url": "https://e.test/mcp"}

    def test_the_timeouts_survive_a_save_from_a_form_that_has_no_field_for_them(self) -> None:
        from hera_tools.config import merge

        written = merge({"command": "x", "timeout_s": 5, "startup_timeout_s": 40}, {"command": "y"})
        assert written == {"command": "y", "timeout_s": 5, "startup_timeout_s": 40}
