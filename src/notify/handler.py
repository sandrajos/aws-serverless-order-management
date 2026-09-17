"""Lambda: notify.

Triggered by the order-notifications SNS topic.

For this portfolio project, notification delivery is represented by a
structured CloudWatch log entry. A real implementation could replace the
adapter with Amazon SES, Slack, or another notification provider.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "common"))

from common.utils import get_logger

logger = get_logger(__name__)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Process SNS notification records."""

    processed = 0

    for record in event.get("Records", []):
        try:
            _handle_sns_record(record)
            processed += 1
        except Exception:  # noqa: BLE001 - isolate individual SNS records
            logger.exception("Failed to process notification record")

    return {
        "statusCode": 200,
        "processed": processed,
    }


def _handle_sns_record(record: dict[str, Any]) -> None:
    sns_message = record["Sns"]["Message"]
    eventbridge_event = json.loads(sns_message)

    detail = eventbridge_event.get("detail") or {}

    order_id = detail.get("order_id")
    customer_id = detail.get("customer_id")

    if not order_id:
        raise ValueError("OrderProcessed event is missing order_id")

    _send_notification(order_id, customer_id)


def _send_notification(
    order_id: str,
    customer_id: str | None,
) -> None:
    """Represent notification delivery through structured logging."""

    logger.info(
        "Notification sent to customer",
        extra={
            "order_id": order_id,
            "customer_id": customer_id,
            "notification_type": "ORDER_PROCESSED",
        },
    )