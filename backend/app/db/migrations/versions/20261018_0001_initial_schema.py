"""Initial schema with pgvector and mock tables.

Revision ID: 20261018_0001
Revises:
Create Date: 2026-10-18

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "20261018_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _embedding_dim() -> int:
    bind = op.get_bind()
    dim = bind.info.get("embedding_dim")
    if dim is None:
        return 1536
    return int(dim)


def upgrade() -> None:
    """Create extensions and all application tables."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    embedding_dim = _embedding_dim()

    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), server_default="active", nullable=False),
        sa.Column("customer_email", sa.Text(), nullable=True),
        sa.Column("channel", sa.Text(), server_default="web", nullable=True),
        sa.CheckConstraint(
            "status IN ('active','handed_off','closed')",
            name="ck_conversations_status",
        ),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("structured", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('user','assistant','tool','system')",
            name="ck_messages_role",
        ),
    )

    op.create_table(
        "trace_steps",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step_no", sa.Integer(), nullable=False),
        sa.Column("node", sa.Text(), nullable=False),
        sa.Column("tool_name", sa.Text(), nullable=True),
        sa.Column("input", postgresql.JSONB(), nullable=True),
        sa.Column("output", postgresql.JSONB(), nullable=True),
        sa.Column("error", postgresql.JSONB(), nullable=True),
        sa.Column("attempt", sa.Integer(), server_default=sa.text("1"), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "kb_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("source_type", sa.Text(), nullable=True),
        sa.Column("source_uri", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default="pending", nullable=True),
        sa.Column(
            "chunk_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=True,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_type IN ('pdf','md','txt','url')",
            name="ck_kb_documents_source_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending','processing','ready','failed')",
            name="ck_kb_documents_status",
        ),
    )

    op.create_table(
        "kb_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("kb_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("embedding", Vector(embedding_dim), nullable=True),
    )
    op.execute(
        "CREATE INDEX ix_kb_chunks_embedding_hnsw "
        "ON kb_chunks USING hnsw (embedding vector_cosine_ops)"
    )

    op.create_table(
        "tickets",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id"),
            nullable=True,
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("priority", sa.Text(), server_default="normal", nullable=True),
        sa.Column("status", sa.Text(), server_default="open", nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('open','in_progress','resolved')",
            name="ck_tickets_status",
        ),
    )

    op.create_table(
        "appointments",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id"),
            nullable=True,
        ),
        sa.Column("slot_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("topic", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "mock_orders",
        sa.Column("order_id", sa.Text(), primary_key=True),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("ordered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("tracking_number", sa.Text(), nullable=True),
        sa.Column("items", postgresql.JSONB(), nullable=False),
        sa.Column("shipping_address", postgresql.JSONB(), nullable=True),
        sa.Column("total_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.Text(), server_default="USD", nullable=False),
    )

    op.create_table(
        "mock_shipments",
        sa.Column("tracking_number", sa.Text(), primary_key=True),
        sa.Column(
            "order_id",
            sa.Text(),
            sa.ForeignKey("mock_orders.order_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("carrier", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("events", postgresql.JSONB(), nullable=False),
    )

    op.create_table(
        "mock_slots",
        sa.Column("slot_id", sa.Text(), primary_key=True),
        sa.Column("slot_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("slot_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("timezone", sa.Text(), server_default="UTC", nullable=False),
        sa.Column(
            "is_booked",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )

    op.create_table(
        "mock_crm_contacts",
        sa.Column("email", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("tags", postgresql.JSONB(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    op.create_table(
        "mock_returns",
        sa.Column("rma_id", sa.Text(), primary_key=True),
        sa.Column(
            "order_id",
            sa.Text(),
            sa.ForeignKey("mock_orders.order_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("item_skus", postgresql.JSONB(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default="open", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Drop all application tables and the vector extension."""
    op.drop_table("mock_returns")
    op.drop_table("mock_crm_contacts")
    op.drop_table("mock_slots")
    op.drop_table("mock_shipments")
    op.drop_table("mock_orders")
    op.drop_table("appointments")
    op.drop_table("tickets")
    op.execute("DROP INDEX IF EXISTS ix_kb_chunks_embedding_hnsw")
    op.drop_table("kb_chunks")
    op.drop_table("kb_documents")
    op.drop_table("trace_steps")
    op.drop_table("messages")
    op.drop_table("conversations")
    op.execute("DROP EXTENSION IF EXISTS vector")
