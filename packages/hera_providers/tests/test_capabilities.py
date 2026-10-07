"""What a local endpoint says about itself, and what to do when it says nothing.

A self-hosted server is under no obligation to publish anything, and the two that do disagree in
useful ways. ``llama.cpp`` serves ``/props`` with both a ``chat_template_caps`` object and the
Jinja ``chat_template`` itself; for MiniCPM5-2B the caps say
``"supports_reasoning_effort": false`` and the template mentions ``enable_thinking`` three times
and ``reasoning_effort`` not at all. Two independent signals from the same server, agreeing.

Everything uncertain here answers ``False``, because both flags mean *draw a control that would
work* and a control that does nothing is worse than an absent one.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
from hera_providers.capabilities import (
    NOTHING,
    UNKNOWN,
    Capabilities,
    EndpointCapabilities,
    props_url,
    template_capabilities,
    tool_call_shape,
)

from hera_providers import capabilities as _capabilities

Handler = Callable[[httpx.Request], httpx.Response]

MINICPM_TEMPLATE = (
    "{%- if messages[0].role == 'system' %}"
    "{{- '<|im_start|>system\\n' + messages[0].content + '<|im_end|>\\n' }}"
    "{%- endif %}"
    "{%- if add_generation_prompt %}"
    "{%- if enable_thinking is defined %}"
    "{%- if enable_thinking is false %}"
    "{{- '<think>\\n\\n</think>\\n\\n' }}"
    "{%- elif enable_thinking is true %}"
    "{{- '<think>\\n' }}"
    "{%- endif %}"
    "{%- endif %}"
)

QWEN_TEMPLATE = (
    "{%- if enable_thinking is undefined or enable_thinking is true %}"
    "{%- set resolved_reasoning_effort = reasoning_effort|default('xhigh') %}"
    "{%- if resolved_reasoning_effort not in ('xhigh', 'medium', 'low') %}"
    "{{- raise_exception('Unexpected reasoning effort') }}"
    "{%- endif %}"
)


QWEN_TOOLS_TEMPLATE = (
    "{%- if tools %}"
    "{{- '<|im_start|>system\n' + '<tools>' + (tools | tojson) + '</tools>\n' }}"
    "{%- endif %}"
    "{%- if message.tool_calls %}"
    "{{- '<|im_start|>assistant\n<tool_call>' }}"
)
"""A Hermes-style template: it loops over ``tools`` to render the catalogue and renders
``tool_calls`` back out of history. Trimmed, but the two names are the whole of the question."""


MIMO_TOOL_MACROS = (
    # Verbatim from XiaomiMiMo/MiMo-V2.6-Distill-Qwen-9B `chat_template.jinja`, the parts that
    # answer the question. Taken from the model rather than written here on purpose: a fixture
    # invented to match the implementation proves only that the implementation agrees with
    # itself, and this detector is a substring test whose failure mode is a wrong idea about what
    # a tools path looks like.
    "{%- macro render_tools(tools) -%}"
    "{{- 'You are provided with the following tools:\\n\\n<tools>' -}}"
    "{%- for tool in tools -%}"
    "{{- '\\n' ~ (tool | tojson(ensure_ascii=False)) -}}"
    "{%- endfor -%}"
    "{{- '\\n</tools>' -}}"
    "{%- endmacro -%}"
    "{%- macro render_tool_calls(tool_calls) -%}"
    "{%- for tool_call in tool_calls -%}"
    "{{- '<\\u200btool_call><function=' ~ tool_call.name ~ '>' -}}"
    "{%- for args_name, args_value in tool_call.arguments | items -%}"
    "{{- '<parameter=' ~ args_name ~ '>' ~ render_value(args_value) ~ '</parameter>' -}}"
    "{%- endfor -%}"
    "{{- '</function></\\u200btool_call>' -}}"
    "{%- endfor -%}"
    "{%- endmacro -%}"
    "{%- if tools is defined and tools is iterable and tools | length > 0 -%}"
    "{{- 'system\\n' ~ render_tools(tools) ~ '' -}}"
    "{%- endif -%}"
)

#: The generation-prompt branch of the same template, which is where the thinking switch lives:
#: ``{%- if add_generation_prompt -%}`` ... ``{%- if enable_thinking is false -%}``. Kept apart
#: from the tool macros so a test can ask the two questions separately.
ENABLE_THINKING = (
    "{%- if add_generation_prompt -%}"
    "{{- 'assistant\\n' -}}"
    "{%- if enable_thinking is false -%}"
    "{{- '<think></think>' -}}"
    "{%- endif -%}"
    "{%- endif -%}"
)


def props(**extra: object) -> dict[str, object]:
    """A `/props` body. Flat, because that is what llama.cpp serves -- the template and the
    capability object are top-level keys, not entries under a `data` envelope."""
    return dict(extra)


@pytest.fixture(autouse=True)
def _no_shared_cache() -> None:
    EndpointCapabilities.forget()


def _client(handler: Handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


class TestPropsUrl:
    def test_the_openai_compatible_suffix_is_dropped(self) -> None:
        # `/props` hangs off the server's root, and a base_url of `.../v1` is a routes prefix
        # rather than a prefix of the server.
        assert props_url("http://127.0.0.1:8080/v1") == "http://127.0.0.1:8080"
        assert props_url("http://host/api/v1") == "http://host/api"
        assert props_url("http://host/openai/v1/") == "http://host/openai"

    def test_a_bare_root_is_left_alone(self) -> None:
        assert props_url("http://127.0.0.1:8080") == "http://127.0.0.1:8080"

    def test_an_unrecognised_path_is_not_guessed_at(self) -> None:
        # A server on a path prefix is unusual, and rearranging its base_url to find `/props`
        # would be the kind of guessing this whole arrangement exists to avoid.
        assert props_url("https://gw.example/team-a/llm/v1beta") == (
            "https://gw.example/team-a/llm/v1beta"
        )


class TestTemplateCapabilities:
    def test_a_declared_capability_is_taken_at_face_value(self) -> None:
        # MiniCPM5, verbatim: the server says the field is not honoured, and the template agrees.
        found = template_capabilities(
            props(
                chat_template=MINICPM_TEMPLATE,
                chat_template_caps={"supports_reasoning_effort": False, "supports_tools": True},
            )
        )

        assert found == Capabilities(
            supports_reasoning_effort=False, thinking_toggle=True, tool_call_shape="none"
        )

    def test_a_capability_the_server_omits_falls_back_to_the_template(self) -> None:
        # No caps object at all. A template that *reads* reasoning_effort is one that honours it.
        found = template_capabilities(props(chat_template=QWEN_TEMPLATE))

        assert found.supports_reasoning_effort is True
        assert found.thinking_toggle is True

    def test_a_template_with_neither_means_neither_control(self) -> None:
        found = template_capabilities(props(chat_template="{{ messages[0].content }}"))

        # `NO_TOOLS` and not `NOTHING`: a template *was* published and it has no tools path, which
        # is evidence. `NOTHING` is an endpoint that said nothing, which is silence.
        assert found == NO_TOOLS

    def test_a_whole_word_is_required(self) -> None:
        # `supports_reasoning_effort` in a comment is not a declaration, and a longer name
        # containing the field is a different name.
        template = "{# supports_reasoning_effort is not read #} {{ my_reasoning_effort_setting }}"
        assert template_capabilities(props(chat_template=template)) == NO_TOOLS

    def test_an_empty_template_is_not_a_template(self) -> None:
        assert template_capabilities(props(chat_template="")) == NOTHING
        assert template_capabilities(props(chat_template=None)) == NOTHING

    def test_rubbish_is_nothing_rather_than_an_exception(self) -> None:
        rubbish: list[object] = [{}, {"data": "nonsense"}, [], "nonsense", None, 7]
        for payload in rubbish:
            assert template_capabilities(payload) == NOTHING

    def test_a_caps_flag_of_the_wrong_type_is_ignored(self) -> None:
        found = template_capabilities(
            props(
                chat_template=QWEN_TEMPLATE,
                chat_template_caps={"supports_reasoning_effort": "yes"},
            )
        )

        assert found.supports_reasoning_effort is True, "falls through to the template"


MINICPM5_TOOLS_TEMPLATE = (
    # The tools branch of openbmb/MiniCPM5-2B's real `chat_template.jinja`, trimmed. It renders
    # function signatures inside <tools></tools> and then inlines its own usage guidelines,
    # telling the model the shape to answer in: `<function name=...><param name=...>`.
    "{{- bos_token }}{%- if tools %}"
    "{%- set tool_definitions %}"
    "{{- '# Tools\\n\\nYou are provided with function signatures within "
    "<tools></tools> XML tags:\\n<tools>' }}"
    "{%- for tool in tools %}"
    "{{- tool | tojson(ensure_ascii=False) }}"
    "{{- '\\n</tools>\\n\\nTool usage guidelines:\\n"
    "- When calling a function, return an XML object within "
    "<function ... </function> using:\\n"
    '<function name="function-name">'
    '<param name="param-name">param-value</param></function>\' }}'
)
"""Real, and the reason this module says less than it might. MiniCPM5-2B has an unambiguous tools
path, so this reads ``template``. It does **not** follow that calls will come back: SGLang converts
this dialect natively, vLLM has no parser for it yet (vllm#43175), Ollama returns
``tool_calls: null`` with the markup left in ``content`` (ollama#18483), and llama.cpp does not
support it. Four engines, one template, three different outcomes -- which is why the field records
the template and stops there (#145)."""

#: A published template with no tools path. Distinct from :data:`NOTHING`, which is an endpoint that
#: published nothing at all: the first is evidence and the second is silence.
NO_TOOLS = Capabilities(tool_call_shape="none")


class TestToolCallShape:
    """Whether this endpoint's *template* can render a tool declaration.

    The name is deliberately not ``native``. ``native`` read as "tool calls will work here", and for
    MiniCPM5-2B -- which this class has a fixture for -- that is false on three of the four engines
    it runs on. The gap between "the template offers tools" and "a call comes back" is the engine's
    dialect parser, and no endpoint publishes it. So this answers the half that can be answered,
    under a name that does not overclaim the other half.
    """

    def test_a_template_that_loops_over_tools_is_template(self) -> None:
        assert tool_call_shape(props(chat_template=QWEN_TOOLS_TEMPLATE)) == "template"

    def test_a_render_tools_macro_counts(self) -> None:
        assert tool_call_shape(props(chat_template="{{ render_tools(tools) }}")) == "template"

    def test_minicpm5_is_template_which_is_not_a_claim_about_calls(self) -> None:
        # The case that forced the rename. Its template is unambiguous, and every engine but
        # SGLang either has no parser for its dialect or is waiting on one.
        assert tool_call_shape(props(chat_template=MINICPM5_TOOLS_TEMPLATE)) == "template"

    def test_the_mimo_template_is_template(self) -> None:
        assert tool_call_shape(props(chat_template=MIMO_TOOL_MACROS)) == "template"

    def test_a_published_template_with_no_tools_path_is_none(self) -> None:
        # Evidence, not silence: this template was served to us and it cannot offer a tool.
        assert tool_call_shape(props(chat_template="{{ messages[0].content }}")) == "none"

    def test_no_template_at_all_is_unknown_not_none(self) -> None:
        # The distinction the whole thing turns on. Nothing published is not the same as something
        # published that has no tools, and collapsing them would report an absence of information
        # as an absence of capability.
        assert tool_call_shape(props()) == UNKNOWN
        assert tool_call_shape({}) == UNKNOWN
        assert tool_call_shape(None) == UNKNOWN
        assert NOTHING.tool_call_shape == UNKNOWN

    def test_an_empty_template_is_not_a_template(self) -> None:
        assert tool_call_shape(props(chat_template="")) == UNKNOWN
        assert tool_call_shape(props(chat_template=None)) == UNKNOWN

    def test_a_server_that_declares_no_is_none(self) -> None:
        assert tool_call_shape(props(chat_template_caps={"supports_tools": False})) == "none"

    def test_a_template_rendering_call_history_alone_is_not_a_declaration_path(self) -> None:
        # llama.cpp probes these separately: `supports_tools` from whether the template *uses* the
        # tools it was handed, `supports_tool_calls` from whether it uses `messages[1].tool_calls`
        # (common/jinja/caps.cpp). A template can render results without ever rendering a
        # declaration, so `tool_calls` cannot stand in for one -- and this field means "can be
        # offered a tool", not "can render tool history".
        history_only = (
            "{{ messages[0].content }}{% for m in messages %}{{ m.tool_calls }}{% endfor %}"
        )

        assert tool_call_shape(props(chat_template=history_only)) == "none"

    def test_a_failed_string_argument_render_does_not_hide_a_declaration_path(self) -> None:
        # Upstream, a template taking string arguments fails its probe and clears *both* flags
        # (`if (!success) { supports_tool_calls = false; supports_tools = false; }`) without saying
        # anything about a declaration path. Believing the flags before the template would report
        # `none` here and hide a working tools path behind a probe artefact.
        found = tool_call_shape(
            props(
                chat_template=MINICPM5_TOOLS_TEMPLATE,
                chat_template_caps={"supports_tools": False, "supports_tool_calls": False},
            )
        )

        assert found == "template"

    def test_call_history_flag_false_alone_does_not_claim_a_declaration_is_absent(self) -> None:
        # The other half of the same mistake: `supports_tool_calls: false` is about history, so it
        # must not suppress a declaration path on its own.
        found = tool_call_shape(
            props(
                chat_template=MINICPM5_TOOLS_TEMPLATE,
                chat_template_caps={"supports_tool_calls": False},
            )
        )

        assert found == "template"

    def test_an_omitted_flag_falls_through_to_the_template(self) -> None:
        # `True` says nothing useful -- not whether the engine has a parser -- so it is no reason to
        # believe anything a template has not also said.
        found = tool_call_shape(props(chat_template="{{ m.content }}", chat_template_caps={}))

        assert found == "none"

    def test_a_whole_word_is_required(self) -> None:
        found = tool_call_shape(props(chat_template="{{ some_tool_settings_v2 and tools_legacy }}"))

        assert found == "none"

    def test_a_tools_path_named_only_in_a_prose_comment_is_not_one(self) -> None:
        # The false positive this exists for: a template whose header explains what it does has no
        # tools path, and reporting `template` for it would put a control up that does nothing.
        assert (
            tool_call_shape(props(chat_template="{# see render_tools #} {{ m.content }}")) == "none"
        )

    def test_rubbish_is_unknown_rather_than_an_exception(self) -> None:
        rubbish: list[object] = [[], "nonsense", None, 7]
        for payload in rubbish:
            assert tool_call_shape(payload) == UNKNOWN

    def test_it_travels_with_the_capabilities(self) -> None:
        found = template_capabilities(props(chat_template=QWEN_TOOLS_TEMPLATE))

        assert found.tool_call_shape == "template"
        assert template_capabilities(props(chat_template="{{ m.content }}")) == NO_TOOLS
        assert template_capabilities({}) == NOTHING

    def test_the_mimo_template_also_declares_its_thinking_switch(self) -> None:
        caps = template_capabilities(props(chat_template=MIMO_TOOL_MACROS + ENABLE_THINKING))

        assert caps.thinking_toggle is True
        assert caps.supports_reasoning_effort is False

    def test_minicpm5_agrees_with_what_the_module_already_claimed(self) -> None:
        # `capabilities.py` has asserted these two about a real server since before this field
        # existed. Checking them against the model's own template is a free second opinion.
        caps = template_capabilities(props(chat_template=MINICPM5_TOOLS_TEMPLATE + ENABLE_THINKING))

        assert caps.thinking_toggle is True
        assert caps.supports_reasoning_effort is False

    def test_the_detector_survives_a_large_real_template(self) -> None:
        assert tool_call_shape(props(chat_template=MINICPM5_TOOLS_TEMPLATE * 40)) == "template"


class TestLoading:
    async def test_an_endpoint_that_answers_is_asked_once(self) -> None:
        calls = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(
                200,
                json=props(chat_template=MINICPM_TEMPLATE, chat_template_caps={}),
            )

        async with _client(handler) as client:
            first = await EndpointCapabilities.load("http://h:1/v1", client=client)
            second = await EndpointCapabilities.load("http://h:1/v1", client=client)

        assert first.thinking_toggle is True
        assert second == first
        assert calls == 1

    async def test_it_asks_at_the_root_not_under_the_api_prefix(self) -> None:
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request.url.path)
            return httpx.Response(200, json=props(chat_template=MINICPM_TEMPLATE))

        async with _client(handler) as client:
            await EndpointCapabilities.load("http://h:1/v1", client=client)

        assert seen == ["/props"]

    async def test_a_404_is_an_answer_and_is_cached(self) -> None:
        # vLLM, LM Studio, a proxy: no `/props`. That is a whole answer, not a failure to retry.
        calls = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(404)

        async with _client(handler) as client:
            assert await EndpointCapabilities.load("http://h:1/v1", client=client) == NOTHING
            assert await EndpointCapabilities.load("http://h:1/v1", client=client) == NOTHING

        assert calls == 1

    async def test_an_unreachable_endpoint_is_nothing_and_is_cached(self) -> None:
        calls = 0

        def handler(_request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            raise httpx.ConnectError("refused")

        async with _client(handler) as client:
            assert (
                await EndpointCapabilities.load("http://127.0.0.1:9/v1", client=client) == NOTHING
            )
            assert (
                await EndpointCapabilities.load("http://127.0.0.1:9/v1", client=client) == NOTHING
            )

        assert calls == 1

    async def test_a_body_that_is_not_json_is_nothing(self) -> None:
        def handler(_request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="<html>hello</html>")

        async with _client(handler) as client:
            assert await EndpointCapabilities.load("http://h:1/v1", client=client) == NOTHING

    async def test_two_endpoints_are_answered_separately(self) -> None:
        # The cache is per base_url: a llama.cpp on loopback and a vLLM on the LAN are different
        # servers and one of them answering says nothing about the other.
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.host == "local":
                return httpx.Response(200, json=props(chat_template=MINICPM_TEMPLATE))
            return httpx.Response(404)

        async with _client(handler) as client:
            local = await EndpointCapabilities.load("http://local:8080/v1", client=client)
            remote = await EndpointCapabilities.load("http://remote:8000/v1", client=client)

        assert local.thinking_toggle is True
        assert remote == NOTHING

    def test_peek_never_asks(self) -> None:
        assert EndpointCapabilities.peek("http://h:1/v1") == NOTHING


class TestCommentStripping:
    """``{# ... #}`` removal, which used to be a quadratic regex.

    The bug is not observable in the answers -- every case below had the right answer before --
    only in the cost. So these are mostly about the edges a rewrite would get wrong, and the
    linear-time property is asserted structurally rather than by timing, which would be flaky.
    """

    def test_an_unterminated_comment_ends_the_scan(self) -> None:
        """The quadratic case. ``{#.*?#}`` restarts a lazy match at every ``{#`` and scans to the
        end of the string for a ``#}`` that never comes, so 4x the input was 16x the work:
        measured 0.04s / 0.56s / 9.0s at 2k / 8k / 32k unclosed comments.
        """
        hostile = "{#" * 50_000 + "tools"

        found, done = _capabilities._strip_jinja_comments(hostile), False
        try:
            assert "tools" not in found
            done = True
        finally:
            assert done, "stripping did not finish"

    def test_an_unterminated_comment_is_removed_not_kept(self) -> None:
        # What Jinja does with it, and what makes the fast path legal: everything from an
        # unterminated ``{#`` to the end is comment.
        # The comment is replaced by its space and the unterminated tail adds nothing, so
        # two spaces: harmless here, and the same thing a closed comment leaves behind.
        assert _capabilities._strip_jinja_comments("before {# after") == "before  "

    def test_several_comments_in_one_template(self) -> None:
        assert _capabilities._strip_jinja_comments("{#a#}keep{#b#}this{#c#}") == " keep this "

    def test_a_template_with_no_comments_is_returned_unchanged(self) -> None:
        plain = "{% for m in messages %}{{ m.content }}{% endfor %}"

        assert _capabilities._strip_jinja_comments(plain) == plain

    def test_words_either_side_do_not_join(self) -> None:
        """The reason a space replaces the comment rather than nothing.

        Without it ``a{# note #}tools`` became ``atools``, which is not a field name anyone
        declares -- so the whole-word rule would have passed on a string it should have failed.
        """
        assert _capabilities._strip_jinja_comments("a{# note #}tools") == "a tools"

    def test_a_nested_looking_open_is_not_special(self) -> None:
        """Jinja comments do not nest, so neither does this: the first ``#}`` closes it."""
        assert _capabilities._strip_jinja_comments("{# outer {# inner #} tail") == "  tail"

    def test_a_template_is_stripped_once_per_props_not_once_per_lookup(self) -> None:
        """Three capabilities are read out of one template, and each was re-running the strip.

        On the event loop, inside the capabilities cache lock, four or five times per ``/props``.
        Counted here rather than timed, because the count is the property and a clock is not.
        """
        calls: list[str] = []
        original = _capabilities._strip_jinja_comments

        def counted(template: str) -> str:
            calls.append(template)
            return original(template)

        _capabilities._strip_jinja_comments = counted
        try:
            template_capabilities({"chat_template": MINICPM5_TOOLS_TEMPLATE})
        finally:
            _capabilities._strip_jinja_comments = original

        assert len(calls) == 1, calls

    @pytest.mark.parametrize(
        ("props", "expected"),
        [
            # The flag cannot override a declared path, whatever it says.
            (
                {
                    "chat_template": "{% for t in tools %}x{% endfor %}",
                    "chat_template_caps": {"supports_tools": False},
                },
                "template",
            ),
            # No path, flag agrees with the template: none either way.
            (
                {
                    "chat_template": "{{ m.content }}",
                    "chat_template_caps": {"supports_tools": False},
                },
                "none",
            ),
            ({"chat_template": "{{ m.content }}"}, "none"),
            # Silence is unknown -- except when the server says otherwise, which is the one
            # answer the flag actually moves.
            ({"chat_template_caps": {"supports_tools": False}}, "none"),
            ({}, "unknown"),
            ({"chat_template_caps": {"supports_tools": True}}, "unknown"),
        ],
    )
    def test_what_decides_none(self, props: object, expected: str) -> None:
        """The whole of the decision table, so the docstring describing it cannot drift.

        Written as a table because the interesting part is not any single row -- it is which rows
        the flag can move, and the answer is exactly one: no template *and* an explicit false.
        Everything else it agrees with. ``supports_tools: true`` moves nothing at all, because
        ``true`` says nothing about the engine parser, which is the half nothing publishes.
        """
        assert tool_call_shape(props) == expected
