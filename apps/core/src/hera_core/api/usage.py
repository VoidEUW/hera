"""What the turns cost (#111): Settings → Usage.

One route over the ledger ``hera_chats`` keeps (ADR 25). The days are cut in the reader's time
zone — the browser sends its own — falling back to the one set on Settings → General, then UTC.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, status

from hera_chats import UsageRepository, summarise, window_start
from hera_core.clock import is_known
from hera_core.config import load as load_config
from hera_core.deps import Db, Owner
from hera_core.schemas import UsageOut

router = APIRouter(tags=["usage"])

MAX_DAYS = 366


@router.get("/usage", response_model=UsageOut)
def usage(
    owner: Owner,
    db: Db,
    days: Annotated[int, Query(ge=1, le=MAX_DAYS)] = 30,
    tz: str = "",
) -> UsageOut:
    """A bar per day for the last ``days`` days, and the last 24 hours, 7 and 30 days."""
    zone_name = tz or load_config().timezone or "UTC"
    if not is_known(zone_name):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"{zone_name!r} is not a time zone this system knows about",
        )
    zone = ZoneInfo(zone_name)
    now = datetime.now(UTC)
    rows = UsageRepository(db).since(owner, window_start(now=now, zone=zone, days=days))
    return UsageOut.of(summarise(rows, now=now, zone=zone, days=days), zone_name)
