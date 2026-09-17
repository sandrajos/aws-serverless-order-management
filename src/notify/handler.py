"""Lambda: notify

Triggered by the order-notifications SNS topic (populated via an
EventBridge rule matching OrderProcessed events). Sends a customer
notification. For this portfolio project the "send" is a structured log
line; in a real deployment this would call SES, a transactional email
provider, or a Slack/webhook integration.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "common"))

from common.utils import get_logger  # noqa: E402

logger = get_logger(__name__)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    for record in event.get("Records", []):
        try:
            _handle_sns_record(record)
        except Exception:  # noqa: BLE001
            logger.exception("Failed to send notification")
    return {"statusCode": 200}


def _handle_sns_record(record: dict[str, Any]) -> None:
    sns_message = record["Sns"]["Message"]
    # EventBridge -> SNS delivers the original event as the SNS message body.
    detail = json.loads(sns_message).get("detail", {})
    order_id = detail.get("order_id")
    customer_id = detail.get("customer_id")

    _send_notification(order_id, customer_id)


def _send_notification(order_id: str | None, customer_id: str | None) -> None:
    # Placeholder for a real notification integration (SES/Slack/webhook).
    logger.info(
        "Notification sent to customer",
        extra={"order_id": order_id, "customer_id": customer_id},
    )
