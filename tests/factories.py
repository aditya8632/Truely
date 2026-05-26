from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

ALICE_ID = UUID("11111111-1111-1111-1111-111111111111")
BOB_ID = UUID("22222222-2222-2222-2222-222222222222")
CAROL_ID = UUID("33333333-3333-3333-3333-333333333333")

Q1_REPORT_ID = UUID("44444444-4444-4444-4444-444444444444")
PRODUCT_ROADMAP_ID = UUID("55555555-5555-5555-5555-555555555555")
BUDGET_2026_ID = UUID("66666666-6666-6666-6666-666666666666")


def now_utc() -> datetime:
    return datetime.now(UTC)


def future_expires_at(seconds: int = 180) -> datetime:
    return now_utc() + timedelta(seconds=seconds)


def to_iso_z(dt: datetime) -> str:
    # Keep timezone information; dependencies accept ISO 8601, including `Z`.
    if dt.tzinfo is None:
        raise ValueError("dt must be timezone-aware")
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")
