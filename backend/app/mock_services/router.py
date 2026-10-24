"""Mock external HTTP routes under /mock/*.

@author jiaolin
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    MockCrmContact,
    MockOrder,
    MockReturn,
    MockShipment,
    MockSlot,
)
from app.db.session import get_async_session
from app.mock_services.chaos import apply_chaos
from app.mock_services.runtime import get_mock_runtime, set_mock_runtime
from app.mock_services.schemas import (
    BookingCreate,
    CrmContactUpsert,
    MockConfigResponse,
    MockConfigUpdate,
    OrderResponse,
    ReturnCreate,
)

router = APIRouter(prefix="/mock", tags=["mock"])

_RETURN_WINDOW_DAYS = 30


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"code": "NOT_FOUND", "message": "Not found"},
    )


@router.get("/config", response_model=MockConfigResponse)
async def get_config() -> MockConfigResponse:
    """Return current mock latency and failure rate.

    Returns:
        MockConfigResponse: Runtime chaos settings.
    """
    config = get_mock_runtime()
    return MockConfigResponse(
        latency_ms=config.latency_ms,
        failure_rate=config.failure_rate,
    )


@router.put("/config", response_model=MockConfigResponse)
async def update_config(body: MockConfigUpdate) -> MockConfigResponse:
    """Update mock latency and/or failure rate at runtime.

    Args:
        body: Partial update of chaos settings.

    Returns:
        MockConfigResponse: Updated settings.
    """
    config = set_mock_runtime(
        latency_ms=body.latency_ms,
        failure_rate=body.failure_rate,
    )
    return MockConfigResponse(
        latency_ms=config.latency_ms,
        failure_rate=config.failure_rate,
    )


@router.get("/orders/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: str,
    email: str = Query(..., min_length=3),
    session: AsyncSession = Depends(get_async_session),
) -> OrderResponse:
    """Look up an order; requires matching email (404 on any mismatch).

    Args:
        order_id: Store order id.
        email: Email used on the order.
        session: Database session.

    Returns:
        OrderResponse: Order details when verified.
    """
    await apply_chaos()
    result = await session.execute(
        select(MockOrder).where(MockOrder.order_id == order_id)
    )
    order = result.scalar_one_or_none()
    if order is None or order.email.lower() != email.strip().lower():
        raise _not_found()
    return OrderResponse(
        order_id=order.order_id,
        email=order.email,
        status=order.status,
        ordered_at=order.ordered_at,
        delivered_at=order.delivered_at,
        cancelled_at=order.cancelled_at,
        tracking_number=order.tracking_number,
        items=list(order.items),
        shipping_address=order.shipping_address,
        total_cents=order.total_cents,
        currency=order.currency,
    )


@router.get("/shipping/{tracking_no}")
async def get_shipment(
    tracking_no: str,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Return carrier tracking events for a tracking number.

    Args:
        tracking_no: Carrier tracking number.
        session: Database session.

    Returns:
        dict[str, Any]: Shipment payload.
    """
    await apply_chaos()
    result = await session.execute(
        select(MockShipment).where(MockShipment.tracking_number == tracking_no)
    )
    shipment = result.scalar_one_or_none()
    if shipment is None:
        raise _not_found()
    return {
        "tracking_number": shipment.tracking_number,
        "order_id": shipment.order_id,
        "carrier": shipment.carrier,
        "status": shipment.status,
        "events": list(shipment.events),
    }


@router.get("/calendar/slots")
async def list_slots(
    date_from: date = Query(...),
    date_to: date = Query(...),
    timezone: str = Query(default="UTC"),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """List open (unbooked) call-back slots in a date range.

    Args:
        date_from: Inclusive start date (UTC day).
        date_to: Inclusive end date (UTC day).
        timezone: Customer IANA timezone (echoed; slots stored in UTC).
        session: Database session.

    Returns:
        dict[str, Any]: Available slots list.
    """
    await apply_chaos()
    if date_to < date_from:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_RANGE", "message": "date_to must be >= date_from"},
        )
    start_dt = datetime(date_from.year, date_from.month, date_from.day, tzinfo=UTC)
    end_dt = datetime(
        date_to.year, date_to.month, date_to.day, 23, 59, 59, tzinfo=UTC
    )
    result = await session.execute(
        select(MockSlot)
        .where(
            MockSlot.slot_start >= start_dt,
            MockSlot.slot_start <= end_dt,
            MockSlot.is_booked.is_(False),
        )
        .order_by(MockSlot.slot_start)
    )
    slots = result.scalars().all()
    return {
        "timezone": timezone,
        "slots": [
            {
                "slot_id": slot.slot_id,
                "slot_start": slot.slot_start.isoformat(),
                "slot_end": slot.slot_end.isoformat(),
                "timezone": slot.timezone,
            }
            for slot in slots
        ],
    }


@router.post("/calendar/bookings", status_code=201)
async def create_booking(
    body: BookingCreate,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Book an open calendar slot.

    Args:
        body: Booking request.
        session: Database session.

    Returns:
        dict[str, Any]: Booking confirmation.
    """
    await apply_chaos()
    result = await session.execute(
        select(MockSlot).where(MockSlot.slot_id == body.slot_id)
    )
    slot = result.scalar_one_or_none()
    if slot is None:
        raise _not_found()
    if slot.is_booked:
        raise HTTPException(
            status_code=409,
            detail={"code": "SLOT_TAKEN", "message": "Slot already booked"},
        )
    slot.is_booked = True
    booking_id = f"BK-{hashlib.sha256(body.slot_id.encode()).hexdigest()[:10].upper()}"
    await session.commit()
    return {
        "booking_id": booking_id,
        "slot_id": slot.slot_id,
        "slot_start": slot.slot_start.isoformat(),
        "name": body.name,
        "email": str(body.email),
        "topic": body.topic,
    }


@router.get("/crm/contacts")
async def get_crm_contact(
    email: str = Query(..., min_length=3),
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Fetch a CRM contact by email.

    Args:
        email: Contact email.
        session: Database session.

    Returns:
        dict[str, Any]: Contact payload.
    """
    await apply_chaos()
    result = await session.execute(
        select(MockCrmContact).where(MockCrmContact.email == email.strip().lower())
    )
    contact = result.scalar_one_or_none()
    if contact is None:
        # Also try exact match for legacy seed casing.
        result = await session.execute(
            select(MockCrmContact).where(MockCrmContact.email == email.strip())
        )
        contact = result.scalar_one_or_none()
    if contact is None:
        raise _not_found()
    return {
        "email": contact.email,
        "name": contact.name,
        "phone": contact.phone,
        "tags": contact.tags,
        "notes": contact.notes,
        "updated_at": contact.updated_at.isoformat() if contact.updated_at else None,
    }


@router.put("/crm/contacts")
async def upsert_crm_contact(
    body: CrmContactUpsert,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Create or update a CRM contact.

    Args:
        body: Contact fields.
        session: Database session.

    Returns:
        dict[str, Any]: Upserted contact.
    """
    await apply_chaos()
    email = str(body.email).strip().lower()
    result = await session.execute(
        select(MockCrmContact).where(MockCrmContact.email == email)
    )
    contact = result.scalar_one_or_none()
    now = datetime.now(UTC)
    if contact is None:
        contact = MockCrmContact(
            email=email,
            name=body.name,
            phone=body.phone,
            tags=body.tags,
            notes=body.notes,
            updated_at=now,
        )
        session.add(contact)
    else:
        if body.name is not None:
            contact.name = body.name
        if body.phone is not None:
            contact.phone = body.phone
        if body.tags is not None:
            contact.tags = body.tags
        if body.notes is not None:
            contact.notes = body.notes
        contact.updated_at = now
    await session.commit()
    await session.refresh(contact)
    return {
        "email": contact.email,
        "name": contact.name,
        "phone": contact.phone,
        "tags": contact.tags,
        "notes": contact.notes,
        "updated_at": contact.updated_at.isoformat(),
    }


@router.post("/returns", status_code=201)
async def create_return(
    body: ReturnCreate,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """Create a return / RMA when order+email match and within return window.

    Args:
        body: Return request.
        session: Database session.

    Returns:
        dict[str, Any]: Created RMA payload.
    """
    await apply_chaos()
    result = await session.execute(
        select(MockOrder).where(MockOrder.order_id == body.order_id)
    )
    order = result.scalar_one_or_none()
    if order is None or order.email.lower() != str(body.email).strip().lower():
        raise _not_found()

    if order.status == "cancelled":
        raise HTTPException(
            status_code=400,
            detail={
                "code": "ORDER_CANCELLED",
                "message": "Cancelled orders cannot be returned",
            },
        )

    anchor = order.delivered_at or order.ordered_at
    age_days = (datetime.now(UTC) - anchor).days
    if age_days > _RETURN_WINDOW_DAYS:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "OUT_OF_RETURN_WINDOW",
                "message": f"Return window is {_RETURN_WINDOW_DAYS} days",
            },
        )

    order_skus = {item.get("sku") for item in order.items if isinstance(item, dict)}
    unknown = [sku for sku in body.item_skus if sku not in order_skus]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_SKU",
                "message": f"SKUs not on order: {unknown}",
            },
        )

    if body.idempotency_key:
        existing = await session.execute(
            select(MockReturn).where(
                MockReturn.order_id == body.order_id,
                MockReturn.rma_id == f"RMA-{body.idempotency_key[:12].upper()}",
            )
        )
        prior = existing.scalar_one_or_none()
        if prior is not None:
            return {
                "rma_id": prior.rma_id,
                "order_id": prior.order_id,
                "item_skus": list(prior.item_skus),
                "reason": prior.reason,
                "note": prior.note,
                "status": prior.status,
                "idempotent": True,
            }
        rma_id = f"RMA-{body.idempotency_key[:12].upper()}"
    else:
        rma_id = f"RMA-{uuid.uuid4().hex[:10].upper()}"

    record = MockReturn(
        rma_id=rma_id,
        order_id=body.order_id,
        item_skus=list(body.item_skus),
        reason=body.reason,
        note=body.note,
        status="open",
    )
    session.add(record)
    await session.commit()
    return {
        "rma_id": record.rma_id,
        "order_id": record.order_id,
        "item_skus": list(record.item_skus),
        "reason": record.reason,
        "note": record.note,
        "status": record.status,
        "idempotent": False,
    }


@router.get("/returns")
async def list_returns(
    order_id: str | None = None,
    session: AsyncSession = Depends(get_async_session),
) -> dict[str, Any]:
    """List mock returns, optionally filtered by order_id.

    Args:
        order_id: Optional order filter.
        session: Database session.

    Returns:
        dict[str, Any]: Returns list.
    """
    await apply_chaos()
    statement = select(MockReturn).order_by(MockReturn.created_at.desc())
    if order_id:
        statement = statement.where(MockReturn.order_id == order_id)
    result = await session.execute(statement)
    rows = result.scalars().all()
    return {
        "returns": [
            {
                "rma_id": row.rma_id,
                "order_id": row.order_id,
                "item_skus": list(row.item_skus),
                "reason": row.reason,
                "note": row.note,
                "status": row.status,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]
    }
