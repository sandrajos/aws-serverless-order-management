"""Shared helpers used across all Lambda functions in this project."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any


def get_logger(name: str) -> logging.Logger:
    """Return a JSON-structured logger.

    Using structured logging makes it possible to correlate log lines
    across Lambdas by order_id / request_id in CloudWatch Logs Insights.
    """
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(_JsonFormatter())
        logger.addHandler(handler)
    logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
    return logger


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Allow callers to pass extra structured fields, e.g.
        # logger.info("...", extra={"order_id": order_id})
        for key in ("order_id", "request_id", "customer_id"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class _DecimalEncoder(json.JSONEncoder):
    """DynamoDB returns numeric attributes as decimal.Decimal, which the
    stdlib json module can't serialize by default. Convert to int when the
    value is whole, otherwise float.
    """

    def default(self, o: Any) -> Any:
        if isinstance(o, Decimal):
            return int(o) if o % 1 == 0 else float(o)
        return super().default(o)


def api_response(status_code: int, body: dict[str, Any]) -> dict[str, Any]:
    """Build a well-formed API Gateway Lambda proxy response."""
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, cls=_DecimalEncoder),
    }


class ValidationError(Exception):
    """Raised when an incoming order payload fails validation."""


def validate_order_payload(payload: dict[str, Any]) -> None:
    """Validate an incoming order creation request.

    Raises ValidationError with a human-readable message on failure.
    Kept dependency-free and easily unit-testable.
    """
    if not isinstance(payload, dict):
        raise ValidationError("request body must be a JSON object")

    customer_id = payload.get("customer_id")
    if not customer_id or not isinstance(customer_id, str):
        raise ValidationError("customer_id is required")

    items = payload.get("items")
    if not isinstance(items, list) or len(items) == 0:
        raise ValidationError("items must be a non-empty list")

    for item in items:
        if not isinstance(item, dict) or "sku" not in item or "qty" not in item:
            raise ValidationError("each item must have 'sku' and 'qty'")
        qty = item["qty"]
        if not isinstance(qty, int) or isinstance(qty, bool) or qty <= 0:
            raise ValidationError("quantity must be a positive integer")
