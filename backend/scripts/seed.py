"""Idempotent database seed for mock store data and KB documents.

@author jiaolin
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    KbDocument,
    MockCrmContact,
    MockOrder,
    MockReturn,
    MockShipment,
    MockSlot,
)
from app.db.session import get_session_factory, reset_engine
from app.rag.embedder import build_embedder
from app.rag.service import ingest_seed_kb

logger = logging.getLogger(__name__)

SEED_KB_DIR = Path(__file__).resolve().parent.parent / "seed_kb"

# Stable UUIDs so kb_documents upserts stay idempotent across runs.
KB_DOCUMENT_IDS: dict[str, uuid.UUID] = {
    "return-policy.md": uuid.UUID("11111111-1111-4111-8111-111111111111"),
    "shipping.md": uuid.UUID("22222222-2222-4222-8222-222222222222"),
    "size-guide.md": uuid.UUID("33333333-3333-4333-8333-333333333333"),
    "warranty.md": uuid.UUID("44444444-4444-4444-8444-444444444444"),
    "faq.md": uuid.UUID("55555555-5555-4555-8555-555555555555"),
}


def _now() -> datetime:
    return datetime.now(UTC)


def _build_orders(now: datetime) -> list[dict[str, Any]]:
    """Build the 10 seed orders covering required boundary statuses.

    Args:
        now: Current UTC timestamp used for relative dates.

    Returns:
        list[dict[str, Any]]: Order row payloads keyed for upsert.
    """
    address = {
        "name": "Jane Customer",
        "line1": "100 Market St",
        "city": "San Francisco",
        "state": "CA",
        "postal": "94105",
        "country": "US",
    }
    tee = [{"sku": "TEE-BLK-M", "name": "Black Tee M", "qty": 1, "price_cents": 2900}]
    hoodie = [
        {"sku": "HD-GRY-L", "name": "Gray Hoodie L", "qty": 1, "price_cents": 6900}
    ]
    shoes = [
        {"sku": "SHOE-WHT-9", "name": "White Runner 9", "qty": 1, "price_cents": 8900}
    ]

    return [
        {
            "order_id": "A1001",
            "email": "jane@example.com",
            "status": "in_transit",
            "ordered_at": now - timedelta(days=3),
            "delivered_at": None,
            "cancelled_at": None,
            "tracking_number": "TRK1001",
            "items": tee,
            "shipping_address": address,
            "total_cents": 2900,
            "currency": "USD",
        },
        {
            "order_id": "A1002",
            "email": "alex@example.com",
            "status": "in_transit",
            "ordered_at": now - timedelta(days=2),
            "delivered_at": None,
            "cancelled_at": None,
            "tracking_number": "TRK1002",
            "items": hoodie,
            "shipping_address": address,
            "total_cents": 6900,
            "currency": "USD",
        },
        {
            "order_id": "A1003",
            "email": "sam@example.com",
            "status": "delivered",
            "ordered_at": now - timedelta(days=8),
            "delivered_at": now - timedelta(days=5),
            "cancelled_at": None,
            "tracking_number": "TRK1003",
            "items": shoes,
            "shipping_address": address,
            "total_cents": 8900,
            "currency": "USD",
        },
        {
            "order_id": "A1004",
            "email": "riley@example.com",
            "status": "delivered",
            "ordered_at": now - timedelta(days=12),
            "delivered_at": now - timedelta(days=9),
            "cancelled_at": None,
            "tracking_number": "TRK1004",
            "items": tee + hoodie,
            "shipping_address": address,
            "total_cents": 9800,
            "currency": "USD",
        },
        {
            "order_id": "A1005",
            "email": "casey@example.com",
            "status": "delivered",
            "ordered_at": now - timedelta(days=45),
            "delivered_at": now - timedelta(days=40),
            "cancelled_at": None,
            "tracking_number": "TRK1005",
            "items": shoes,
            "shipping_address": address,
            "total_cents": 8900,
            "currency": "USD",
        },
        {
            "order_id": "A1006",
            "email": "jordan@example.com",
            "status": "delivered",
            "ordered_at": now - timedelta(days=60),
            "delivered_at": now - timedelta(days=55),
            "cancelled_at": None,
            "tracking_number": "TRK1006",
            "items": hoodie,
            "shipping_address": address,
            "total_cents": 6900,
            "currency": "USD",
        },
        {
            "order_id": "A1007",
            "email": "taylor@example.com",
            "status": "cancelled",
            "ordered_at": now - timedelta(days=4),
            "delivered_at": None,
            "cancelled_at": now - timedelta(days=3),
            "tracking_number": None,
            "items": tee,
            "shipping_address": address,
            "total_cents": 2900,
            "currency": "USD",
        },
        {
            "order_id": "A1008",
            "email": "morgan@example.com",
            "status": "cancelled",
            "ordered_at": now - timedelta(days=10),
            "delivered_at": None,
            "cancelled_at": now - timedelta(days=9),
            "tracking_number": None,
            "items": shoes,
            "shipping_address": address,
            "total_cents": 8900,
            "currency": "USD",
        },
        {
            "order_id": "A1009",
            "email": "avery@example.com",
            "status": "delivered",
            "ordered_at": now - timedelta(days=7),
            "delivered_at": now - timedelta(days=2),
            "cancelled_at": None,
            "tracking_number": "TRK1009",
            "items": tee,
            "shipping_address": address,
            "total_cents": 2900,
            "currency": "USD",
        },
        {
            "order_id": "A1010",
            "email": "quinn@example.com",
            "status": "in_transit",
            "ordered_at": now - timedelta(days=1),
            "delivered_at": None,
            "cancelled_at": None,
            "tracking_number": "TRK1010",
            "items": hoodie + shoes,
            "shipping_address": address,
            "total_cents": 15800,
            "currency": "USD",
        },
    ]


def _build_shipments(
    orders: list[dict[str, Any]], now: datetime
) -> list[dict[str, Any]]:
    """Build shipment rows and tracking events for orders that have tracking.

    Args:
        orders: Seed order payloads.
        now: Current UTC timestamp.

    Returns:
        list[dict[str, Any]]: Shipment row payloads.
    """
    shipments: list[dict[str, Any]] = []
    for order in orders:
        tracking = order.get("tracking_number")
        if not tracking:
            continue
        ordered_at: datetime = order["ordered_at"]
        events: list[dict[str, Any]] = [
            {
                "status": "label_created",
                "description": "Shipping label created",
                "at": (ordered_at + timedelta(hours=2)).isoformat(),
                "location": "Warehouse",
            },
            {
                "status": "picked_up",
                "description": "Picked up by carrier",
                "at": (ordered_at + timedelta(days=1)).isoformat(),
                "location": "Origin facility",
            },
        ]
        status = "in_transit"
        if order["status"] == "delivered" and order.get("delivered_at") is not None:
            delivered_at: datetime = order["delivered_at"]
            events.append(
                {
                    "status": "out_for_delivery",
                    "description": "Out for delivery",
                    "at": (delivered_at - timedelta(hours=6)).isoformat(),
                    "location": "Local hub",
                }
            )
            events.append(
                {
                    "status": "delivered",
                    "description": "Delivered",
                    "at": delivered_at.isoformat(),
                    "location": "Destination",
                }
            )
            status = "delivered"
        else:
            events.append(
                {
                    "status": "in_transit",
                    "description": "In transit to destination",
                    "at": (now - timedelta(hours=12)).isoformat(),
                    "location": "Regional hub",
                }
            )
        shipments.append(
            {
                "tracking_number": tracking,
                "order_id": order["order_id"],
                "carrier": "MockParcel",
                "status": status,
                "events": events,
            }
        )
    return shipments


def _build_slots(now: datetime) -> list[dict[str, Any]]:
    """Build 7 days × 4 call-back slots starting tomorrow UTC.

    Args:
        now: Current UTC timestamp.

    Returns:
        list[dict[str, Any]]: Slot row payloads.
    """
    slots: list[dict[str, Any]] = []
    start_day = (now + timedelta(days=1)).date()
    hours = (10, 12, 14, 16)
    for day_offset in range(7):
        day = start_day + timedelta(days=day_offset)
        for hour in hours:
            slot_start = datetime(day.year, day.month, day.day, hour, 0, tzinfo=UTC)
            slot_end = slot_start + timedelta(minutes=30)
            slot_id = f"SLOT-{day.isoformat()}-{hour:02d}"
            slots.append(
                {
                    "slot_id": slot_id,
                    "slot_start": slot_start,
                    "slot_end": slot_end,
                    "timezone": "UTC",
                    "is_booked": False,
                }
            )
    return slots


async def _upsert_orders(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    """Upsert mock orders by primary key.

    Args:
        session: Async database session.
        rows: Order payloads.
    """
    statement = insert(MockOrder).values(rows)
    excluded = statement.excluded
    statement = statement.on_conflict_do_update(
        index_elements=[MockOrder.order_id],
        set_={
            "email": excluded.email,
            "status": excluded.status,
            "ordered_at": excluded.ordered_at,
            "delivered_at": excluded.delivered_at,
            "cancelled_at": excluded.cancelled_at,
            "tracking_number": excluded.tracking_number,
            "items": excluded["items"],
            "shipping_address": excluded.shipping_address,
            "total_cents": excluded.total_cents,
            "currency": excluded.currency,
        },
    )
    await session.execute(statement)


async def _upsert_shipments(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    """Upsert mock shipments by tracking number.

    Args:
        session: Async database session.
        rows: Shipment payloads.
    """
    if not rows:
        return
    statement = insert(MockShipment).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=[MockShipment.tracking_number],
        set_={
            "order_id": statement.excluded.order_id,
            "carrier": statement.excluded.carrier,
            "status": statement.excluded.status,
            "events": statement.excluded.events,
        },
    )
    await session.execute(statement)


async def _upsert_slots(session: AsyncSession, rows: list[dict[str, Any]]) -> None:
    """Upsert mock calendar slots without clearing bookings.

    Args:
        session: Async database session.
        rows: Slot payloads.
    """
    statement = insert(MockSlot).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=[MockSlot.slot_id],
        set_={
            "slot_start": statement.excluded.slot_start,
            "slot_end": statement.excluded.slot_end,
            "timezone": statement.excluded.timezone,
            # is_booked intentionally omitted to preserve bookings.
        },
    )
    await session.execute(statement)


async def _upsert_kb_documents(session: AsyncSession) -> None:
    """Register seed markdown files as kb_documents rows.

    Args:
        session: Async database session.
    """
    if not SEED_KB_DIR.is_dir():
        msg = f"seed_kb directory not found: {SEED_KB_DIR}"
        raise FileNotFoundError(msg)

    rows: list[dict[str, Any]] = []
    for filename, document_id in KB_DOCUMENT_IDS.items():
        path = SEED_KB_DIR / filename
        if not path.is_file():
            msg = f"Missing seed KB file: {path}"
            raise FileNotFoundError(msg)
        title = filename.removesuffix(".md").replace("-", " ").title()
        rows.append(
            {
                "id": document_id,
                "title": title,
                "source_type": "md",
                "source_uri": str(path),
                "status": "pending",
                "chunk_count": 0,
                "error": None,
            }
        )

    statement = insert(KbDocument).values(rows)
    statement = statement.on_conflict_do_update(
        index_elements=[KbDocument.id],
        set_={
            "title": statement.excluded.title,
            "source_type": statement.excluded.source_type,
            "source_uri": statement.excluded.source_uri,
            # status/chunk_count/error omitted to preserve processing progress.
        },
    )
    await session.execute(statement)


async def _ensure_sample_crm_and_returns(session: AsyncSession) -> None:
    """Seed a sample CRM contact and leave returns empty baseline.

    Args:
        session: Async database session.
    """
    statement = insert(MockCrmContact).values(
        {
            "email": "jane@example.com",
            "name": "Jane Customer",
            "phone": "+1-555-0100",
            "tags": ["seed", "vip"],
            "notes": "Seed contact for demo flows",
        }
    )
    statement = statement.on_conflict_do_update(
        index_elements=[MockCrmContact.email],
        set_={
            "name": statement.excluded.name,
            "phone": statement.excluded.phone,
            "tags": statement.excluded.tags,
            "notes": statement.excluded.notes,
            "updated_at": _now(),
        },
    )
    await session.execute(statement)

    # Ensure table is queryable; no default returns — created by tools later.
    _ = MockReturn


async def seed_all(session: AsyncSession) -> dict[str, int]:
    """Seed all mock tables and KB document metadata.

    Args:
        session: Async database session.

    Returns:
        dict[str, int]: Row counts after seeding for key tables.
    """
    now = _now()
    orders = _build_orders(now)
    # Fix accidental whitespace email if any
    for order in orders:
        order["email"] = str(order["email"]).strip()

    await _upsert_orders(session, orders)
    await _upsert_shipments(session, _build_shipments(orders, now))
    await _upsert_slots(session, _build_slots(now))
    await _upsert_kb_documents(session)
    await _ensure_sample_crm_and_returns(session)
    await session.commit()

    # Embed seed markdown with deterministic fake vectors for offline demos/tests.
    await ingest_seed_kb(session, embedder=build_embedder(fake=True))

    counts = {
        "mock_orders": int(
            await session.scalar(select(func.count()).select_from(MockOrder)) or 0
        ),
        "mock_shipments": int(
            await session.scalar(select(func.count()).select_from(MockShipment)) or 0
        ),
        "mock_slots": int(
            await session.scalar(select(func.count()).select_from(MockSlot)) or 0
        ),
        "kb_documents": int(
            await session.scalar(select(func.count()).select_from(KbDocument)) or 0
        ),
        "mock_crm_contacts": int(
            await session.scalar(select(func.count()).select_from(MockCrmContact)) or 0
        ),
    }
    logger.info("Seed complete: %s", counts)
    return counts


async def async_main() -> dict[str, int]:
    """Run seeding with a fresh session factory.

    Returns:
        dict[str, int]: Seeded table counts.
    """
    reset_engine()
    session_factory = get_session_factory()
    async with session_factory() as session:
        return await seed_all(session)


def main() -> None:
    """CLI entrypoint for `python -m scripts.seed`."""
    logging.basicConfig(level=logging.INFO)
    counts = asyncio.run(async_main())
    print(counts)


if __name__ == "__main__":
    main()
