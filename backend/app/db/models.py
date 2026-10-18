"""SQLAlchemy ORM models matching SPEC section 8."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import get_settings
from app.db.base import Base

_EMBEDDING_DIM = get_settings().embedding_dim


class Conversation(Base):
    """Customer support conversation."""

    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active','handed_off','closed')",
            name="ck_conversations_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="active")
    customer_email: Mapped[str | None] = mapped_column(Text)
    channel: Mapped[str | None] = mapped_column(Text, server_default="web")

    messages: Mapped[list[Message]] = relationship(back_populates="conversation")
    trace_steps: Mapped[list[TraceStep]] = relationship(back_populates="conversation")


class Message(Base):
    """Single message within a conversation."""

    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(
            "role IN ('user','assistant','tool','system')",
            name="ck_messages_role",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    structured: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class TraceStep(Base):
    """Agent execution trace step."""

    __tablename__ = "trace_steps"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    step_no: Mapped[int] = mapped_column(Integer, nullable=False)
    node: Mapped[str] = mapped_column(Text, nullable=False)
    tool_name: Mapped[str | None] = mapped_column(Text)
    input: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    attempt: Mapped[int | None] = mapped_column(Integer, server_default=text("1"))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    conversation: Mapped[Conversation] = relationship(back_populates="trace_steps")


class KbDocument(Base):
    """Knowledge-base source document."""

    __tablename__ = "kb_documents"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('pdf','md','txt','url')",
            name="ck_kb_documents_source_type",
        ),
        CheckConstraint(
            "status IN ('pending','processing','ready','failed')",
            name="ck_kb_documents_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    title: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str | None] = mapped_column(Text)
    source_uri: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str | None] = mapped_column(Text, server_default="pending")
    chunk_count: Mapped[int | None] = mapped_column(Integer, server_default=text("0"))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    chunks: Mapped[list[KbChunk]] = relationship(back_populates="document")


class KbChunk(Base):
    """Chunked knowledge-base content with embedding."""

    __tablename__ = "kb_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kb_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    chunk_index: Mapped[int | None] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(_EMBEDDING_DIM))

    document: Mapped[KbDocument] = relationship(back_populates="chunks")


class Ticket(Base):
    """Human handoff ticket."""

    __tablename__ = "tickets"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open','in_progress','resolved')",
            name="ck_tickets_status",
        ),
    )

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id"),
    )
    reason: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str | None] = mapped_column(Text, server_default="normal")
    status: Mapped[str | None] = mapped_column(Text, server_default="open")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class Appointment(Base):
    """Booked call-back appointment."""

    __tablename__ = "appointments"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id"),
    )
    slot_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    name: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text)
    topic: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class MockOrder(Base):
    """Mock store order used by external API stubs."""

    __tablename__ = "mock_orders"

    order_id: Mapped[str] = mapped_column(Text, primary_key=True)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    ordered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tracking_number: Mapped[str | None] = mapped_column(Text)
    items: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    shipping_address: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(Text, nullable=False, server_default="USD")


class MockShipment(Base):
    """Mock carrier shipment with tracking events."""

    __tablename__ = "mock_shipments"

    tracking_number: Mapped[str] = mapped_column(Text, primary_key=True)
    order_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("mock_orders.order_id", ondelete="CASCADE"),
        nullable=False,
    )
    carrier: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    events: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)


class MockSlot(Base):
    """Mock calendar call-back slot."""

    __tablename__ = "mock_slots"

    slot_id: Mapped[str] = mapped_column(Text, primary_key=True)
    slot_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    slot_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timezone: Mapped[str] = mapped_column(Text, nullable=False, server_default="UTC")
    is_booked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )


class MockCrmContact(Base):
    """Mock CRM contact / lead."""

    __tablename__ = "mock_crm_contacts"

    email: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list[str] | None] = mapped_column(JSONB)
    notes: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class MockReturn(Base):
    """Mock return / RMA record."""

    __tablename__ = "mock_returns"

    rma_id: Mapped[str] = mapped_column(Text, primary_key=True)
    order_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("mock_orders.order_id", ondelete="CASCADE"),
        nullable=False,
    )
    item_skus: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="open")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
