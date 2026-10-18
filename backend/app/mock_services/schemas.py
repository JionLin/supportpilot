"""Pydantic schemas for mock external APIs.

@author jiaolin
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field


class MockConfigUpdate(BaseModel):
    """Runtime update payload for mock chaos settings."""

    latency_ms: int | None = Field(default=None, ge=0, le=30_000)
    failure_rate: float | None = Field(default=None, ge=0.0, le=1.0)


class MockConfigResponse(BaseModel):
    """Current mock chaos settings."""

    latency_ms: int
    failure_rate: float


class BookingCreate(BaseModel):
    """Create a calendar booking against an open slot."""

    slot_id: str
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    topic: str | None = Field(default=None, max_length=200)


class CrmContactUpsert(BaseModel):
    """Create or update a CRM contact."""

    email: EmailStr
    name: str | None = None
    phone: str | None = None
    tags: list[str] | None = None
    notes: str | None = Field(default=None, max_length=1000)


class ReturnCreate(BaseModel):
    """Create a mock return / RMA."""

    order_id: str = Field(pattern=r"^[A-Z]\d{4}$")
    email: EmailStr
    item_skus: list[str] = Field(min_length=1)
    reason: str = Field(
        pattern=r"^(damaged|wrong_item|not_as_described|changed_mind|other)$"
    )
    note: str | None = Field(default=None, max_length=500)
    idempotency_key: str | None = None


class OrderResponse(BaseModel):
    """Order payload returned by the mock store API."""

    order_id: str
    email: str
    status: str
    ordered_at: datetime
    delivered_at: datetime | None
    cancelled_at: datetime | None
    tracking_number: str | None
    items: list[dict[str, Any]]
    shipping_address: dict[str, Any] | None
    total_cents: int
    currency: str
