"""Pydantic argument models and OpenAI tools JSON Schema export.

@author jiaolin
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field


class SearchKnowledgeBaseArgs(BaseModel):
    """Arguments for search_knowledge_base."""

    query: str = Field(min_length=2, max_length=300)
    top_k: int = Field(default=4, ge=1, le=8)


class GetOrderArgs(BaseModel):
    """Arguments for get_order."""

    order_id: str = Field(pattern=r"^[A-Z]\d{4}$")
    email: EmailStr


class TrackShipmentArgs(BaseModel):
    """Arguments for track_shipment."""

    tracking_number: str = Field(min_length=6, max_length=40)


class CreateReturnRequestArgs(BaseModel):
    """Arguments for create_return_request."""

    order_id: str = Field(pattern=r"^[A-Z]\d{4}$")
    item_skus: list[str] = Field(min_length=1)
    reason: Literal[
        "damaged",
        "wrong_item",
        "not_as_described",
        "changed_mind",
        "other",
    ]
    note: str | None = Field(default=None, max_length=500)


class CheckAvailabilityArgs(BaseModel):
    """Arguments for check_availability."""

    date_from: str = Field(description="ISO date YYYY-MM-DD")
    date_to: str = Field(description="ISO date YYYY-MM-DD")
    timezone: str = Field(default="UTC")


class BookAppointmentArgs(BaseModel):
    """Arguments for book_appointment."""

    slot_id: str
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    topic: str | None = Field(default=None, max_length=200)


class UpsertCrmContactArgs(BaseModel):
    """Arguments for upsert_crm_contact."""

    email: EmailStr
    name: str | None = None
    phone: str | None = None
    tags: list[str] | None = None
    notes: str | None = Field(default=None, max_length=1000)


class HandoffToHumanArgs(BaseModel):
    """Arguments for handoff_to_human."""

    reason: Literal[
        "customer_request",
        "negative_sentiment",
        "out_of_policy",
        "low_confidence",
        "tool_failure",
        "other",
    ]
    summary: str = Field(max_length=1000)
    priority: Literal["low", "normal", "high"] = "normal"


def _function_schema(
    name: str,
    description: str,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
    }


def get_openai_tools_schema() -> list[dict[str, Any]]:
    """Export OpenAI tools JSON Schema matching SPEC section 7.

    Returns:
        list[dict[str, Any]]: Tools array in OpenAI function-calling format.
    """
    return [
        _function_schema(
            "search_knowledge_base",
            "Search store policies, FAQs and product docs. "
            "Use BEFORE answering any policy/product question.",
            {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "minLength": 2,
                        "maxLength": 300,
                    },
                    "top_k": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 8,
                        "default": 4,
                    },
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        ),
        _function_schema(
            "get_order",
            "Look up an order. Requires BOTH order_id and the email used on "
            "the order; never reveal data if they don't match.",
            {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "pattern": "^[A-Z]\\d{4}$"},
                    "email": {"type": "string", "format": "email"},
                },
                "required": ["order_id", "email"],
                "additionalProperties": False,
            },
        ),
        _function_schema(
            "track_shipment",
            "Get carrier tracking events for a verified order's tracking number.",
            {
                "type": "object",
                "properties": {
                    "tracking_number": {
                        "type": "string",
                        "minLength": 6,
                        "maxLength": 40,
                    }
                },
                "required": ["tracking_number"],
                "additionalProperties": False,
            },
        ),
        _function_schema(
            "create_return_request",
            "Create a return (RMA) for items in a verified order that is "
            "within the return window.",
            {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "pattern": "^[A-Z]\\d{4}$"},
                    "item_skus": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                    },
                    "reason": {
                        "type": "string",
                        "enum": [
                            "damaged",
                            "wrong_item",
                            "not_as_described",
                            "changed_mind",
                            "other",
                        ],
                    },
                    "note": {"type": "string", "maxLength": 500},
                },
                "required": ["order_id", "item_skus", "reason"],
                "additionalProperties": False,
            },
        ),
        _function_schema(
            "check_availability",
            "List open call-back slots in the store's calendar.",
            {
                "type": "object",
                "properties": {
                    "date_from": {"type": "string", "format": "date"},
                    "date_to": {"type": "string", "format": "date"},
                    "timezone": {
                        "type": "string",
                        "default": "UTC",
                        "description": "IANA timezone of the customer",
                    },
                },
                "required": ["date_from", "date_to"],
                "additionalProperties": False,
            },
        ),
        _function_schema(
            "book_appointment",
            "Book a call-back slot returned by check_availability. "
            "Only call after the customer confirms the slot.",
            {
                "type": "object",
                "properties": {
                    "slot_id": {"type": "string"},
                    "name": {"type": "string", "minLength": 1, "maxLength": 100},
                    "email": {"type": "string", "format": "email"},
                    "topic": {"type": "string", "maxLength": 200},
                },
                "required": ["slot_id", "name", "email"],
                "additionalProperties": False,
            },
        ),
        _function_schema(
            "upsert_crm_contact",
            "Create or update a lead/contact in the CRM when the customer "
            "shares contact details.",
            {
                "type": "object",
                "properties": {
                    "email": {"type": "string", "format": "email"},
                    "name": {"type": "string"},
                    "phone": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "notes": {"type": "string", "maxLength": 1000},
                },
                "required": ["email"],
                "additionalProperties": False,
            },
        ),
        _function_schema(
            "handoff_to_human",
            "Escalate to a human agent: customer asks for a human, is upset, "
            "request is out of policy, or you are not confident.",
            {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "enum": [
                            "customer_request",
                            "negative_sentiment",
                            "out_of_policy",
                            "low_confidence",
                            "tool_failure",
                            "other",
                        ],
                    },
                    "summary": {
                        "type": "string",
                        "maxLength": 1000,
                        "description": "Concise summary for the human agent",
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "normal", "high"],
                        "default": "normal",
                    },
                },
                "required": ["reason", "summary"],
                "additionalProperties": False,
            },
        ),
    ]
