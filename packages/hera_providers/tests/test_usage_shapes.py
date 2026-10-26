"""Every server says what a turn cost in its own shape; `Usage.from_wire` reads them all (#111)."""

from __future__ import annotations

from typing import Any

import pytest

from hera_providers import QwenAdapter, TurnEnd, Usage


def end_of(*chunks: dict[str, Any]) -> TurnEnd:
    adapter = QwenAdapter()
    events = [event for item in chunks for event in adapter.feed(item)]
    events.extend(adapter.finish())
    end = events[-1]
    assert isinstance(end, TurnEnd)
    return end


BASE = {"prompt_tokens": 1000, "completion_tokens": 50, "total_tokens": 1050}


class TestTheExtras:
    def test_openai_shaped_details(self) -> None:
        """OpenAI, OpenRouter, vLLM and Anthropic's compatible layer."""
        usage = Usage.from_wire(
            {
                **BASE,
                "prompt_tokens_details": {"cached_tokens": 800},
                "completion_tokens_details": {"reasoning_tokens": 30},
            }
        )
        assert usage is not None
        assert (usage.cached_tokens, usage.reasoning_tokens) == (800, 30)

    def test_deepseek_names_its_cache_hits(self) -> None:
        usage = Usage.from_wire(
            {**BASE, "prompt_cache_hit_tokens": 640, "prompt_cache_miss_tokens": 360}
        )
        assert usage is not None and usage.cached_tokens == 640

    def test_moonshot_puts_cached_tokens_at_the_top(self) -> None:
        usage = Usage.from_wire({**BASE, "cached_tokens": 512})
        assert usage is not None and usage.cached_tokens == 512

    def test_llama_cpp_timings_beside_usage(self) -> None:
        usage = Usage.from_wire(
            BASE,
            {"cache_n": 900, "prompt_n": 100, "prompt_ms": 120.5, "predicted_ms": 980.0},
        )
        assert usage is not None
        assert usage.cached_tokens == 900
        assert (usage.server_prompt_ms, usage.server_generation_ms) == (120.5, 980.0)

    def test_llama_cpp_timings_without_usage_still_count(self) -> None:
        usage = Usage.from_wire(None, {"cache_n": 10, "prompt_n": 90, "predicted_n": 40})
        assert usage is not None
        assert (usage.prompt_tokens, usage.completion_tokens, usage.total_tokens) == (100, 40, 140)

    def test_a_server_that_says_nothing_extra_leaves_the_extras_unknown(self) -> None:
        """Unknown, not zero: a 0% cache rate is a claim, and this server made none."""
        usage = Usage.from_wire(BASE)
        assert usage is not None
        assert usage.cached_tokens is None
        assert usage.reasoning_tokens is None
        assert usage.server_generation_ms is None

    def test_a_reported_zero_is_kept_as_zero(self) -> None:
        usage = Usage.from_wire({**BASE, "prompt_tokens_details": {"cached_tokens": 0}})
        assert usage is not None and usage.cached_tokens == 0

    @pytest.mark.parametrize("total", [None, 0])
    def test_a_missing_total_is_prompt_plus_completion(self, total: int | None) -> None:
        wire: dict[str, Any] = {"prompt_tokens": 7, "completion_tokens": 3}
        if total is not None:
            wire["total_tokens"] = total
        usage = Usage.from_wire(wire)
        assert usage is not None and usage.total_tokens == 10

    def test_nothing_at_all_is_no_usage(self) -> None:
        assert Usage.from_wire(None) is None
        assert Usage.from_wire({}, {}) is None

    @pytest.mark.parametrize("junk", [True, -5, "12", None])
    def test_a_value_that_is_not_a_count_is_not_read_as_one(self, junk: object) -> None:
        usage = Usage.from_wire({**BASE, "prompt_tokens_details": {"cached_tokens": junk}})
        assert usage is not None and usage.cached_tokens is None


class TestThroughTheAdapter:
    def test_a_trailing_chunk_with_details_reaches_the_end(self) -> None:
        end = end_of(
            {"choices": [{"index": 0, "delta": {"content": "hi"}, "finish_reason": "stop"}]},
            {
                "choices": [],
                "usage": {**BASE, "prompt_tokens_details": {"cached_tokens": 600}},
                "timings": {"predicted_ms": 500.0},
            },
        )
        assert end.usage is not None
        assert end.usage.cached_tokens == 600
        assert end.usage.server_generation_ms == 500.0

    def test_a_chunk_without_usage_does_not_erase_one_that_had_it(self) -> None:
        end = end_of(
            {"choices": [], "usage": BASE},
            {"choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}]},
        )
        assert end.usage is not None and end.usage.prompt_tokens == 1000
