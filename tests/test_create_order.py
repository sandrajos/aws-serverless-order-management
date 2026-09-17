import json
import os
import sys

import boto3
import pytest
from moto import mock_aws

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "common"))


@pytest.fixture
def aws_setup(monkeypatch):
    with mock_aws():
        monkeypatch.setenv("ORDERS_TABLE_NAME", "orders-test")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")

        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        dynamodb.create_table(
            TableName="orders-test",
            KeySchema=[{"AttributeName": "order_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "order_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        sqs = boto3.client("sqs", region_name="us-east-1")
        queue = sqs.create_queue(QueueName="orders-queue-test")
        monkeypatch.setenv("ORDERS_QUEUE_URL", queue["QueueUrl"])

        yield {"queue_url": queue["QueueUrl"]}


def _api_event(body: dict, method: str = "POST", path_params=None):
    return {
        "httpMethod": method,
        "body": json.dumps(body) if body is not None else None,
        "pathParameters": path_params,
    }


class DummyContext:
    aws_request_id = "test-request-id"


def test_create_order_success(aws_setup):
    from create_order import handler as create_order_handler

    event = _api_event({"customer_id": "cust-1", "items": [{"sku": "A1", "qty": 2}]})
    response = create_order_handler.handler(event, DummyContext())

    assert response["statusCode"] == 201
    body = json.loads(response["body"])
    assert body["status"] == "RECEIVED"
    assert "order_id" in body


def test_create_order_missing_customer_id(aws_setup):
    from create_order import handler as create_order_handler

    event = _api_event({"items": [{"sku": "A1", "qty": 2}]})
    response = create_order_handler.handler(event, DummyContext())

    assert response["statusCode"] == 400
    assert "customer_id" in json.loads(response["body"])["error"]


def test_create_order_empty_items(aws_setup):
    from create_order import handler as create_order_handler

    event = _api_event({"customer_id": "cust-1", "items": []})
    response = create_order_handler.handler(event, DummyContext())

    assert response["statusCode"] == 400


def test_create_order_invalid_quantity(aws_setup):
    from create_order import handler as create_order_handler

    event = _api_event({"customer_id": "cust-1", "items": [{"sku": "A1", "qty": 0}]})
    response = create_order_handler.handler(event, DummyContext())

    assert response["statusCode"] == 400


def test_create_order_is_idempotent_on_duplicate_id(aws_setup):
    from create_order import handler as create_order_handler

    order_id = "fixed-order-id"
    event = _api_event(
        {"order_id": order_id, "customer_id": "cust-1", "items": [{"sku": "A1", "qty": 1}]}
    )

    first = create_order_handler.handler(event, DummyContext())
    second = create_order_handler.handler(event, DummyContext())

    assert first["statusCode"] == 201
    assert second["statusCode"] == 200  # returns existing order, doesn't duplicate

    body1 = json.loads(first["body"])
    body2 = json.loads(second["body"])
    assert body1["order_id"] == body2["order_id"]


def test_get_order_not_found(aws_setup):
    from create_order import handler as create_order_handler

    event = _api_event(None, method="GET", path_params={"order_id": "does-not-exist"})
    response = create_order_handler.handler(event, DummyContext())

    assert response["statusCode"] == 404


def test_create_order_enqueues_sqs_message(aws_setup):
    from create_order import handler as create_order_handler

    event = _api_event({"customer_id": "cust-1", "items": [{"sku": "A1", "qty": 1}]})
    create_order_handler.handler(event, DummyContext())

    sqs = boto3.client("sqs", region_name="us-east-1")
    messages = sqs.receive_message(QueueUrl=aws_setup["queue_url"], MaxNumberOfMessages=1)
    assert "Messages" in messages
def test_unsupported_http_method_returns_405(aws_setup):
    from create_order import handler as create_order_handler

    event = _api_event(
        {"customer_id": "cust-1", "items": [{"sku": "A1", "qty": 1}]},
        method="DELETE",
    )

    response = create_order_handler.handler(event, DummyContext())

    assert response["statusCode"] == 405
