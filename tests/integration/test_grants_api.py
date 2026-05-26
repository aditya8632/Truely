from __future__ import annotations

from datetime import timedelta
from uuid import UUID

import pytest

from tests.factories import (
    ALICE_ID,
    BOB_ID,
    CAROL_ID,
    Q1_REPORT_ID,
    future_expires_at,
    now_utc,
    to_iso_z,
)


@pytest.mark.asyncio
async def test_grant_create_list_get_check_and_revoke(client) -> None:
    now = now_utc()
    expires_at = now + timedelta(minutes=3)

    create_payload = {
        "document_id": str(Q1_REPORT_ID),
        "granted_to_user_id": str(BOB_ID),
        "permission": "view",
        "expires_at": to_iso_z(expires_at),
    }

    resp = await client.post(
        "/grants",
        json=create_payload,
        headers={"X-User-Id": str(ALICE_ID)},
    )
    assert resp.status_code == 201, resp.text
    grant = resp.json()
    assert UUID(grant["id"]) == UUID(grant["id"])
    grant_id = grant["id"]

    # List
    resp = await client.get(
        "/grants",
        params={"granted_to_user_id": str(BOB_ID), "active_only": True},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] >= 1
    assert any(item["id"] == grant_id for item in body["items"])

    # Get
    resp = await client.get(f"/grants/{grant_id}")
    assert resp.status_code == 200, resp.text

    # Check
    resp = await client.get(f"/grants/{grant_id}/check")
    assert resp.status_code == 200, resp.text
    assert resp.json()["active"] is True

    # Revoke (authorized)
    resp = await client.delete(f"/grants/{grant_id}", headers={"X-User-Id": str(ALICE_ID)})
    assert resp.status_code == 204

    # Check now inactive
    resp = await client.get(f"/grants/{grant_id}/check")
    assert resp.status_code == 200
    assert resp.json()["active"] is False


@pytest.mark.asyncio
async def test_duplicate_active_grant_prevention_returns_409(client) -> None:
    expires_at = future_expires_at(300)
    payload = {
        "document_id": str(Q1_REPORT_ID),
        "granted_to_user_id": str(BOB_ID),
        "permission": "view",
        "expires_at": to_iso_z(expires_at),
    }

    resp = await client.post("/grants", json=payload, headers={"X-User-Id": str(ALICE_ID)})
    assert resp.status_code == 201, resp.text

    # Second grant for same pair while the first is still active should fail.
    resp = await client.post("/grants", json=payload, headers={"X-User-Id": str(ALICE_ID)})
    assert resp.status_code == 409, resp.text


@pytest.mark.asyncio
async def test_revoke_authorization_returns_403(client) -> None:
    expires_at = future_expires_at(300)
    payload = {
        "document_id": str(Q1_REPORT_ID),
        "granted_to_user_id": str(BOB_ID),
        "permission": "view",
        "expires_at": to_iso_z(expires_at),
    }

    resp = await client.post("/grants", json=payload, headers={"X-User-Id": str(ALICE_ID)})
    assert resp.status_code == 201, resp.text
    grant_id = resp.json()["id"]

    resp = await client.delete(f"/grants/{grant_id}", headers={"X-User-Id": str(CAROL_ID)})
    assert resp.status_code == 403, resp.text


@pytest.mark.asyncio
async def test_revoke_expired_grant_returns_400(client) -> None:
    # Create a grant that expires soon. It is still at least 1 minute in the future
    # for schema validation.
    real_now = now_utc()
    expires_at = real_now + timedelta(seconds=90)
    payload = {
        "document_id": str(Q1_REPORT_ID),
        "granted_to_user_id": str(BOB_ID),
        "permission": "view",
        "expires_at": to_iso_z(expires_at),
    }

    resp = await client.post("/grants", json=payload, headers={"X-User-Id": str(ALICE_ID)})
    assert resp.status_code == 201, resp.text
    grant_id = resp.json()["id"]

    # Fast-forward time beyond expires_at using X-Now.
    future_now = expires_at + timedelta(seconds=10)
    resp = await client.delete(
        f"/grants/{grant_id}",
        headers={"X-User-Id": str(ALICE_ID), "X-Now": to_iso_z(future_now)},
    )
    assert resp.status_code == 400, resp.text
