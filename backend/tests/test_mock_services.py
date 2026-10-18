"""Tests for /mock/* external API stubs.

@author jiaolin
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from datetime import date, timedelta
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from scripts.seed import seed_all
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import MockSlot
from app.db.session import reset_engine
from app.main import create_app
from app.mock_services.runtime import reset_mock_runtime


@pytest.fixture(autouse=True)
def _reset_mock_chaos() -> Iterator[None]:
    """Reset mock chaos settings around each test.

    Yields:
        None: Fixture lifespan.
    """
    reset_mock_runtime(latency_ms=0, failure_rate=0.0)
    get_settings.cache_clear()
    reset_engine()
    yield
    reset_mock_runtime(latency_ms=0, failure_rate=0.0)
    get_settings.cache_clear()
    reset_engine()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """ASGI client with seeded mock data.

    Args:
        db_session: Shared async session (ensures DB is reachable).

    Yields:
        AsyncClient: HTTP client bound to the app.
    """
    await seed_all(db_session)
    # Ensure open slots exist even if prior test runs booked them.
    await db_session.execute(update(MockSlot).values(is_booked=False))
    await db_session.commit()
    application = create_app()
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


@pytest.mark.asyncio
async def test_get_order_success(client: AsyncClient) -> None:
    """Verified order_id + email returns order payload."""
    response = await client.get(
        "/mock/orders/A1001",
        params={"email": "jane@example.com"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["order_id"] == "A1001"
    assert payload["email"] == "jane@example.com"
    assert payload["tracking_number"] == "TRK1001"


@pytest.mark.asyncio
async def test_get_order_wrong_email_returns_404(client: AsyncClient) -> None:
    """Wrong email must not distinguish from missing order."""
    response = await client.get(
        "/mock/orders/A1001",
        params={"email": "attacker@example.com"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_order_missing_returns_404(client: AsyncClient) -> None:
    """Unknown order_id returns 404."""
    response = await client.get(
        "/mock/orders/Z9999",
        params={"email": "jane@example.com"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_shipment(client: AsyncClient) -> None:
    """Tracking lookup returns carrier events."""
    response = await client.get("/mock/shipping/TRK1001")
    assert response.status_code == 200
    payload = response.json()
    assert payload["tracking_number"] == "TRK1001"
    assert payload["carrier"] == "MockParcel"
    assert isinstance(payload["events"], list)
    assert len(payload["events"]) >= 1


@pytest.mark.asyncio
async def test_get_shipment_not_found(client: AsyncClient) -> None:
    """Unknown tracking number returns 404."""
    response = await client.get("/mock/shipping/NOPE999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_calendar_slots(client: AsyncClient) -> None:
    """Open slots are returned for a future date window."""
    today = date.today()
    response = await client.get(
        "/mock/calendar/slots",
        params={
            "date_from": (today + timedelta(days=1)).isoformat(),
            "date_to": (today + timedelta(days=3)).isoformat(),
            "timezone": "UTC",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert "slots" in payload
    assert len(payload["slots"]) >= 1
    assert "slot_id" in payload["slots"][0]


@pytest.mark.asyncio
async def test_book_calendar_slot(client: AsyncClient) -> None:
    """Booking an open slot succeeds once and conflicts on retry."""
    today = date.today()
    slots_response = await client.get(
        "/mock/calendar/slots",
        params={
            "date_from": (today + timedelta(days=1)).isoformat(),
            "date_to": (today + timedelta(days=7)).isoformat(),
        },
    )
    open_slots = slots_response.json()["slots"]
    assert open_slots, "expected at least one open slot in the next 7 days"
    slot_id = open_slots[0]["slot_id"]
    create = await client.post(
        "/mock/calendar/bookings",
        json={
            "slot_id": slot_id,
            "name": "Jane",
            "email": "jane@example.com",
            "topic": "Order help",
        },
    )
    assert create.status_code == 201
    assert create.json()["slot_id"] == slot_id

    again = await client.post(
        "/mock/calendar/bookings",
        json={
            "slot_id": slot_id,
            "name": "Jane",
            "email": "jane@example.com",
        },
    )
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_crm_upsert_and_get(client: AsyncClient) -> None:
    """CRM contact can be upserted and fetched."""
    put = await client.put(
        "/mock/crm/contacts",
        json={
            "email": "newlead@example.com",
            "name": "New Lead",
            "phone": "+1-555-0199",
            "tags": ["lead"],
            "notes": "From chat",
        },
    )
    assert put.status_code == 200
    assert put.json()["email"] == "newlead@example.com"

    get = await client.get(
        "/mock/crm/contacts",
        params={"email": "newlead@example.com"},
    )
    assert get.status_code == 200
    assert get.json()["name"] == "New Lead"


@pytest.mark.asyncio
async def test_create_return_within_window(client: AsyncClient) -> None:
    """Delivered-within-window order can create an RMA."""
    response = await client.post(
        "/mock/returns",
        json={
            "order_id": "A1003",
            "email": "sam@example.com",
            "item_skus": ["SHOE-WHT-9"],
            "reason": "changed_mind",
            "note": "Too big",
        },
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["rma_id"].startswith("RMA-")
    assert payload["order_id"] == "A1003"


@pytest.mark.asyncio
async def test_create_return_out_of_window(client: AsyncClient) -> None:
    """Orders past the return window are rejected."""
    response = await client.post(
        "/mock/returns",
        json={
            "order_id": "A1005",
            "email": "casey@example.com",
            "item_skus": ["SHOE-WHT-9"],
            "reason": "changed_mind",
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "OUT_OF_RETURN_WINDOW"


@pytest.mark.asyncio
async def test_mock_config_get_and_put(client: AsyncClient) -> None:
    """Runtime mock config can be read and updated."""
    initial = await client.get("/mock/config")
    assert initial.status_code == 200
    assert initial.json()["latency_ms"] == 0

    updated = await client.put(
        "/mock/config",
        json={"latency_ms": 25, "failure_rate": 0.5},
    )
    assert updated.status_code == 200
    assert updated.json() == {"latency_ms": 25, "failure_rate": 0.5}

    again = await client.get("/mock/config")
    assert again.json()["failure_rate"] == 0.5


@pytest.mark.asyncio
async def test_mock_failure_rate_returns_5xx(client: AsyncClient) -> None:
    """failure_rate=1.0 forces 503 or 504 on mock routes."""
    await client.put("/mock/config", json={"failure_rate": 1.0})
    response = await client.get(
        "/mock/orders/A1001",
        params={"email": "jane@example.com"},
    )
    assert response.status_code in {503, 504}


@pytest.mark.asyncio
async def test_mock_latency_is_applied(client: AsyncClient) -> None:
    """Configured latency delays the response."""
    await client.put("/mock/config", json={"latency_ms": 50})
    with patch("app.mock_services.chaos.asyncio.sleep") as sleep_mock:
        sleep_mock.return_value = None
        response = await client.get("/mock/shipping/TRK1001")
        assert response.status_code == 200
        sleep_mock.assert_awaited()
        delay = sleep_mock.await_args.args[0]
        assert delay == pytest.approx(0.05)


@pytest.mark.asyncio
async def test_list_returns(client: AsyncClient) -> None:
    """Returns list includes created RMAs."""
    await client.post(
        "/mock/returns",
        json={
            "order_id": "A1009",
            "email": "avery@example.com",
            "item_skus": ["TEE-BLK-M"],
            "reason": "damaged",
        },
    )
    response = await client.get("/mock/returns", params={"order_id": "A1009"})
    assert response.status_code == 200
    assert len(response.json()["returns"]) >= 1
