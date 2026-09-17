"""Thin DynamoDB access layer for the Orders table.

Kept separate from the Lambda handlers so it can be unit tested in
isolation (with moto) and reused by every Lambda that touches the table.
"""
from __future__ import annotations

import os
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError

TABLE_NAME = os.environ.get("ORDERS_TABLE_NAME", "orders")


def _table():
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(TABLE_NAME)


class DuplicateOrderError(Exception):
    """Raised when attempting to create an order_id that already exists."""


def create_order(order: dict[str, Any]) -> None:
    """Write a new order with a conditional check to guarantee idempotency.

    If order_id already exists, this raises DuplicateOrderError instead of
    silently overwriting — this is what makes create_order safe to retry.
    """
    try:
        _table().put_item(
            Item=order,
            ConditionExpression="attribute_not_exists(order_id)",
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            raise DuplicateOrderError(order.get("order_id")) from exc
        raise


def get_order(order_id: str) -> Optional[dict[str, Any]]:
    response = _table().get_item(Key={"order_id": order_id})
    return response.get("Item")


def update_order_status(order_id: str, status: str, expected_current: Optional[str] = None) -> bool:
    """Update an order's status.

    If expected_current is provided, the update only applies when the
    order's current status matches — this is the idempotency guard used by
    process_order so a redelivered SQS message can't reprocess (or
    double-transition) an order that's already been handled.

    Returns True if the update was applied, False if the condition failed
    (i.e. the order was already in a different state — safe to ignore).
    """
    kwargs: dict[str, Any] = {
        "Key": {"order_id": order_id},
        "UpdateExpression": "SET #s = :new_status, updated_at = :updated_at",
        "ExpressionAttributeNames": {"#s": "status"},
        "ExpressionAttributeValues": {
            ":new_status": status,
            ":updated_at": _now_iso(),
        },
    }
    if expected_current is not None:
        kwargs["ConditionExpression"] = "#s = :expected"
        kwargs["ExpressionAttributeValues"][":expected"] = expected_current

    try:
        _table().update_item(**kwargs)
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
