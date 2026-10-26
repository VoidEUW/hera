"""Settings → Usage over HTTP (#111): the ledger a turn writes, and the days it is cut into."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from core_support import API
from httpx import AsyncClient

from hera_core.wiring import Services
from hera_providers import FakeProvider, Usage, text_turn


def spent(prompt: int, completion: int) -> Usage:
    return Usage(
        prompt_tokens=prompt, completion_tokens=completion, total_tokens=prompt + completion
    )


@pytest.fixture
def services(make_services: Any) -> Services:
    built: Services = make_services(
        FakeProvider(
            [
                text_turn("One.", usage=spent(1200, 40)),
                text_turn("Two.", usage=spent(1500, 60)),
                text_turn("Unreported."),
            ]
        )
    )
    return built


async def turn(client: AsyncClient, text: str = "hi", chat_id: str | None = None) -> str:
    if chat_id is None:
        chat_id = str((await client.post(f"{API}/chats", json={})).json()["id"])
    response = await client.post(f"{API}/chats/{chat_id}/messages", json={"text": text})
    assert response.status_code == 200
    return chat_id


def today_in(zone: str) -> str:
    return datetime.now(UTC).astimezone(ZoneInfo(zone)).date().isoformat()


class TestUsage:
    async def test_a_fresh_install_has_thirty_empty_days(self, client: AsyncClient) -> None:
        body = (await client.get(f"{API}/usage", params={"tz": "UTC"})).json()

        assert len(body["days"]) == 30
        assert body["days"][-1]["date"] == today_in("UTC")
        assert {d["prompt_tokens"] + d["completion_tokens"] for d in body["days"]} == {0}
        assert body["totals"]["month"] == {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            # Nothing measured is nothing to show, not a nought.
            "reasoning_tokens": None,
            "cache_rate": None,
            "tokens_per_second": None,
            "first_token_ms": None,
        }
        assert body["timezone"] == "UTC"

    async def test_a_turn_lands_on_today_and_in_every_total(self, client: AsyncClient) -> None:
        chat = await turn(client)
        await turn(client, "again", chat)
        await turn(client, "once more", chat)  # the endpoint reported nothing for this one

        body = (await client.get(f"{API}/usage", params={"tz": "UTC"})).json()
        today = body["days"][-1]
        assert (today["prompt_tokens"], today["completion_tokens"]) == (2700, 100)
        for window in ("day", "week", "month"):
            totals = body["totals"][window]
            assert (totals["prompt_tokens"], totals["completion_tokens"]) == (2700, 100)

    async def test_deleting_the_chat_does_not_unspend_it(self, client: AsyncClient) -> None:
        chat = await turn(client)
        assert (await client.delete(f"{API}/chats/{chat}")).status_code == 204

        body = (await client.get(f"{API}/usage", params={"tz": "UTC"})).json()
        assert body["totals"]["day"]["prompt_tokens"] == 1200

    async def test_asking_again_keeps_what_the_first_answer_cost(self, client: AsyncClient) -> None:
        chat = await turn(client)
        messages = (await client.get(f"{API}/chats/{chat}")).json()["messages"]
        asked = next(m for m in messages if m["role"] == "user")
        response = await client.post(f"{API}/chats/{chat}/messages/{asked['id']}/redo", json={})
        assert response.status_code == 200

        body = (await client.get(f"{API}/usage", params={"tz": "UTC"})).json()
        assert body["totals"]["day"]["prompt_tokens"] == 2700

    async def test_the_number_of_days_is_the_callers(self, client: AsyncClient) -> None:
        body = (await client.get(f"{API}/usage", params={"days": 7, "tz": "UTC"})).json()
        assert len(body["days"]) == 7
        first = datetime.fromisoformat(body["days"][0]["date"]).date()
        assert first == datetime.now(UTC).date() - timedelta(days=6)

    @pytest.mark.parametrize("days", [0, 367])
    async def test_a_number_of_days_out_of_range_is_refused(
        self, client: AsyncClient, days: int
    ) -> None:
        response = await client.get(f"{API}/usage", params={"days": days})
        assert response.status_code == 422

    async def test_an_unknown_zone_is_refused(self, client: AsyncClient) -> None:
        response = await client.get(f"{API}/usage", params={"tz": "Mars/Olympus"})
        assert response.status_code == 422
        assert "Mars/Olympus" in response.json()["detail"]

    async def test_the_days_are_cut_in_the_zone_asked_for(self, client: AsyncClient) -> None:
        body = (await client.get(f"{API}/usage", params={"tz": "Pacific/Kiritimati"})).json()
        assert body["timezone"] == "Pacific/Kiritimati"
        assert body["days"][-1]["date"] == today_in("Pacific/Kiritimati")

    async def test_without_a_zone_it_is_the_configured_one_then_utc(
        self, client: AsyncClient
    ) -> None:
        assert (await client.get(f"{API}/usage")).json()["timezone"] == "UTC"
        await client.patch(f"{API}/preferences", json={"timezone": "Asia/Tokyo"})
        assert (await client.get(f"{API}/usage")).json()["timezone"] == "Asia/Tokyo"


class TestWhatIsKnown:
    @pytest.fixture
    def services(self, make_services: Any) -> Services:
        built: Services = make_services(
            FakeProvider(
                [
                    text_turn(
                        "Cached.",
                        usage=Usage(
                            prompt_tokens=1000,
                            completion_tokens=40,
                            total_tokens=1040,
                            cached_tokens=750,
                            reasoning_tokens=12,
                        ),
                    )
                ]
            )
        )
        return built

    async def test_cache_reasoning_and_speed_reach_the_screen(self, client: AsyncClient) -> None:
        await turn(client)
        day = (await client.get(f"{API}/usage", params={"tz": "UTC"})).json()["totals"]["day"]

        assert day["cache_rate"] == 0.75
        assert day["reasoning_tokens"] == 12
        # Measured by Hera, so present for every endpoint; how fast depends on the machine.
        assert day["first_token_ms"] is not None and day["first_token_ms"] >= 0
