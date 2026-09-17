"""Lambda: process_order

Triggered by SQS (orders-queue). Applies business logic to an order,
transitions its status in DynamoDB, and emits an OrderProcessed event to
EventBridge on success.

Designed to be idempotent: SQS provides at-least-once delivery, so this
handler must tolerate being invoked more than once for the same message.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

import boto3

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "common"))

from common.db import get_order, update_order_status  # noqa: E402
from common.utils import get_logger  # noqa: E402

logger = get_logger(__name__)
events_client = boto3.client("events")

EVENT_BUS_NAME = os.environ.get("EVENT_BUS_NAME", "default")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """SQS-triggered handler. Processes each record; partial batch failures
    are reported back to SQS so only the failed messages are retried
    (rather than the whole batch), via reportBatchItemFailures.
    """
    batch_item_failures: list[dict[str, str]] = []

    for record in event.get("Records", []):
        message_id = record["messageId"]
        try:
            _process_record(record)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to process record", extra={"request_id": message_id})
            batch_item_failures.append({"itemIdentifier": message_id})

    return {"batchItemFailures": batch_item_failures}


def _process_record(record: dict[str, Any]) -> None:
    body = json.loads(record["body"])
    order_id = body["order_id"]

    order = get_order(order_id)
    if order is None:
        # Should not normally happen (would indicate a data consistency
        # bug), but we don't want to retry forever on missing data.
        logger.error("Order not found, dropping message", extra={"order_id": order_id})
        return

    if order.get("status") != "RECEIVED":
        # Already processed (or in some other terminal state) — this is a
        # redelivered/duplicate message. No-op, so retries are safe.
        logger.info(
            "Order already in non-RECEIVED state, skipping",
            extra={"order_id": order_id},
        )
        return

    _apply_business_logic(order)

    updated = update_order_status(order_id, "PROCESSED", expected_current="RECEIVED")
    if not updated:
        logger.info(
            "Order status changed concurrently, skipping duplicate transition",
            extra={"order_id": order_id},
        )
        return

    _publish_order_processed_event(order_id, order.get("customer_id"))
    logger.info("Order processed", extra={"order_id": order_id})


def _apply_business_logic(order: dict[str, Any]) -> None:
    """Placeholder for real business logic: inventory checks, pricing,
    fraud checks, etc. Kept intentionally simple for this portfolio
    project, but isolated here so it's easy to extend and unit test.
    """
    if not order.get("items"):
        raise ValueError(f"Order {order.get('order_id')} has no items to process")


def _publish_order_processed_event(order_id: str, customer_id: str | None) -> None:
    try:
        events_client.put_events(
            Entries=[
                {
                    "Source": "orders.platform",
                    "DetailType": "OrderProcessed",
                    "Detail": json.dumps({"order_id": order_id, "customer_id": customer_id}),
                    "EventBusName": EVENT_BUS_NAME,
                }
            ]
        )
    except Exception:  # noqa: BLE001
        # Notification is best-effort: the order is already durably marked
        # PROCESSED, so a failure to emit the event should not fail the
        # whole message (and cause an unnecessary retry of order logic).
        logger.exception(
            "Failed to publish OrderProcessed event", extra={"order_id": order_id}
        )
