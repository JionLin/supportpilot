"""Idempotency tests for the seed script."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from alembic import command
from alembic.config import Config
from scripts.seed import SEED_KB_DIR, seed_all
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.models import KbDocument, MockOrder, MockShipment, MockSlot

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _run_migrations(database_url: str) -> None:
    os.environ["DATABASE_URL"] = database_url
    get_settings.cache_clear()
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "app/db/migrations"))
    config.set_main_option("path_separator", "os")
    command.upgrade(config, "head")


async def test_seed_twice_is_idempotent(
    db_session: AsyncSession,
    database_url: str,
) -> None:
    """Seeding twice must not duplicate orders, shipments, slots, or KB docs."""
    _run_migrations(database_url)

    assert SEED_KB_DIR.is_dir()
    kb_files = sorted(path.name for path in SEED_KB_DIR.glob("*.md"))
    assert kb_files == [
        "faq.md",
        "return-policy.md",
        "shipping.md",
        "size-guide.md",
        "warranty.md",
    ]

    first = await seed_all(db_session)
    second = await seed_all(db_session)

    assert first == second
    assert first["mock_orders"] == 10
    assert first["mock_shipments"] == 8
    assert first["mock_slots"] == 28
    assert first["kb_documents"] == 5

    order_count = await db_session.scalar(select(func.count()).select_from(MockOrder))
    shipment_count = await db_session.scalar(
        select(func.count()).select_from(MockShipment)
    )
    slot_count = await db_session.scalar(select(func.count()).select_from(MockSlot))
    kb_count = await db_session.scalar(select(func.count()).select_from(KbDocument))

    assert order_count == 10
    assert shipment_count == 8
    assert slot_count == 28
    assert kb_count == 5

    statuses = {
        row[0]
        for row in (await db_session.execute(select(MockOrder.status).distinct())).all()
    }
    assert {"in_transit", "delivered", "cancelled"}.issubset(statuses)

    delivered_orders = (
        await db_session.execute(
            select(MockOrder).where(MockOrder.status == "delivered")
        )
    ).scalars().all()
    now = datetime.now(UTC)
    has_recent_delivery = any(
        order.delivered_at is not None
        and (now - order.delivered_at) <= timedelta(days=10)
        for order in delivered_orders
    )
    has_old_delivery = any(
        order.delivered_at is not None
        and (now - order.delivered_at) > timedelta(days=30)
        for order in delivered_orders
    )
    assert has_recent_delivery
    assert has_old_delivery
