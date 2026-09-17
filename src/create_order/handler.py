"""Lambda: create_order

Triggered by API Gateway on POST /orders and GET /orders/{order_id}.
Validates the request, writes the order to DynamoDB, and enqueues it for
asynchronous processing via SQS.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from typing import Any

import boto3

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "common"))

from common.db import create_order as db_create_order  # noqa: E402
from common.db import DuplicateOrderError, get_order  # noqa: E402
from common.utils import (  # noqa: E402
    ValidationError,
    api_response,
    get_logger,
    now_iso,
    validate_order_payload,
)

logger = get_logger(__name__)
sqs = boto3.client("sqs")

QUEUE_URL = os.environ.get("ORDERS_QUEUE_URL")


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    request_id = getattr(context, "aws_request_id", "local")
    http_method = event.get("httpMethod", "POST")
    path_params = event.get("pathParameters") or {}

    try:
        if http_method == "GET" and path_params.get("order_id"):
            return _handle_get(path_params["order_id"])
        return _handle_create(event, request_id)
    except ValidationError as exc:
        logger.warning("Validation failed", extra={"request_id": request_id})
        return api_response(400, {"error": str(exc)})
    except Exception:  # noqa: BLE001 - top-level Lambda handler boundary
        logger.exception("Unhandled error in create_order", extra={"request_id": request_id})
        return api_response(500, {"error": "internal server error"})


def _handle_get(order_id: str) -> dict[str, Any]:
    order = get_order(order_id)
    if order is None:
        return api_response(404, {"error": "order not found"})
    return api_response(200, order)


def _handle_create(event: dict[str, Any], request_id: str) -> dict[str, Any]:
    body = json.loads(event.get("body") or "{}")
    validate_order_payload(body)

    order_id = body.get("order_id") or str(uuid.uuid4())
    order = {
        "order_id": order_id,
        "customer_id": body["customer_id"],
        "items": body["items"],
        "status": "RECEIVED",
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }

    try:
        db_create_order(order)
    except DuplicateOrderError:
        # Idempotent create: if the client retried with the same order_id,
        # return the existing order instead of erroring.
        logger.info(
            "Duplicate order_id on create, returning existing order",
            extra={"order_id": order_id, "request_id": request_id},
        )
        existing = get_order(order_id)
        return api_response(200, existing or order)

    _enqueue_for_processing(order_id)

    logger.info("Order created", extra={"order_id": order_id, "request_id": request_id})
    return api_response(
        201,
        {"order_id": order_id, "status": order["status"], "created_at": order["created_at"]},
    )


def _enqueue_for_processing(order_id: str) -> None:
    if not QUEUE_URL:
        logger.warning("ORDERS_QUEUE_URL not set; skipping enqueue (local/test mode)")
        return
    sqs.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=json.dumps({"order_id": order_id}),
    )
