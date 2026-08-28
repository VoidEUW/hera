"""What she is told about the time, and what happens when nobody said where the person is.

The reason this exists at all: a model that does not know the date answers "what is current"
from its training data, confidently and a year late, and nothing on screen distinguishes that
from an answer that is merely wrong.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from core_support import API
from httpx import AsyncClient

from hera_core.clock import is_known, render

MOMENT = datetime(2026, 8, 28, 12, 7, tzinfo=UTC)


class TestRendering:
    def test_utc_is_always_there(self) -> None:
        line = render("", now=MOMENT)
        assert "28 August 2026" in line
        assert "12:07" in line
        assert "UTC" in line

    def test_the_weekday_is_spelled_out(self) -> None:
        """A model cannot derive it reliably from a date, and it is free here — "next Tuesday"
        is a thing people say and a thing she otherwise has to guess at."""
        assert "Friday" in render("", now=MOMENT)

    def test_a_zone_adds_the_persons_local_time(self) -> None:
        line = render("Europe/Berlin", now=MOMENT)
        assert "12:07" in line
        assert "14:07" in line
        assert "Europe/Berlin" in line

    def test_utc_is_not_said_twice(self) -> None:
        """Configuring UTC explicitly is the same state as configuring nothing."""
        assert render("UTC", now=MOMENT) == render("", now=MOMENT)

    def test_an_unusable_zone_degrades_to_utc(self) -> None:
        """This runs on every turn. A typo in a settings file is not a reason to stop
        answering, and the person can see it is UTC and go and fix it."""
        line = render("Mars/Olympus_Mons", now=MOMENT)
        assert "12:07" in line
        assert "Mars" not in line

    def test_a_zone_is_a_name_rather_than_an_offset(self) -> None:
        """The whole reason for storing IANA names: an offset is wrong twice a year. Berlin is
        +2 in August and +1 in January, and the same stored value has to cover both."""
        winter = datetime(2026, 1, 28, 12, 7, tzinfo=UTC)
        assert "13:07" in render("Europe/Berlin", now=winter)
        assert "14:07" in render("Europe/Berlin", now=MOMENT)


class TestNaming:
    def test_a_known_zone_passes(self) -> None:
        assert is_known("Europe/Berlin")

    def test_empty_passes(self) -> None:
        """Clearing the setting back to UTC alone is a thing a person may do."""
        assert is_known("")

    def test_nonsense_is_refused(self) -> None:
        assert not is_known("Somewhere/Else")


class TestThePreferencesScreen:
    async def test_it_starts_at_utc_alone(self, client: AsyncClient) -> None:
        body = (await client.get(f"{API}/preferences")).json()
        assert body["timezone"] == ""
        assert "UTC" in body["now"]

    async def test_setting_a_zone_changes_what_she_is_told(self, client: AsyncClient) -> None:
        """The response carries the real sentence rather than the setting alone, so picking a
        zone and reading what she will read are the same action."""
        body = (await client.patch(f"{API}/preferences", json={"timezone": "Asia/Tokyo"})).json()

        assert body["timezone"] == "Asia/Tokyo"
        assert "Asia/Tokyo" in body["now"]
        assert (await client.get(f"{API}/preferences")).json()["timezone"] == "Asia/Tokyo"

    async def test_a_bad_zone_is_refused_here_rather_than_degraded(
        self, client: AsyncClient
    ) -> None:
        """The opposite of what `render` does with the same value, and deliberately: a person
        typing into a screen should be told now, a turn already running should not fail."""
        response = await client.patch(f"{API}/preferences", json={"timezone": "Nowhere/Real"})

        assert response.status_code == 422
        assert (await client.get(f"{API}/preferences")).json()["timezone"] == ""

    async def test_it_can_be_cleared(self, client: AsyncClient) -> None:
        await client.patch(f"{API}/preferences", json={"timezone": "Asia/Tokyo"})
        body = (await client.patch(f"{API}/preferences", json={"timezone": ""})).json()
        assert body["timezone"] == ""

    async def test_changing_the_endpoint_does_not_lose_it(self, client: AsyncClient) -> None:
        """Both live in `config.toml`, and every constructor of `HeraConfig` has to carry the
        other through — which is exactly the kind of thing nobody notices until it is gone."""
        await client.patch(f"{API}/preferences", json={"timezone": "Asia/Tokyo"})

        await client.post(
            f"{API}/providers",
            json={"name": "second", "base_url": "http://localhost:9/v1", "model": "m"},
        )
        await client.post(f"{API}/providers/second/activate")

        assert (await client.get(f"{API}/preferences")).json()["timezone"] == "Asia/Tokyo"


@pytest.mark.usefixtures("client")
class TestItReachesTheModel:
    async def test_the_date_is_in_the_prompt(self, client: AsyncClient, services: object) -> None:
        """The point of the whole thing: implicit, with no tool call to spend a round trip on,
        and there before she decides whether she needs to look something up."""
        chat_id = (await client.post(f"{API}/chats", json={})).json()["id"]
        await client.post(f"{API}/chats/{chat_id}/messages", json={"text": "what is going on"})

        provider = services.provider  # type: ignore[attr-defined]
        system = provider.requests[0].messages[0].content
        assert str(datetime.now(UTC).year) in system
        assert "UTC" in system
