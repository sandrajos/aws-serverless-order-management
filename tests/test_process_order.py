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
        monkeypatch.setenv("EVENT_BUS_NAME", "default")
        monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")

        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="orders-test",
            KeySchema=[{"AttributeName": "order_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "order_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )

        events_client = boto3.client("events", region_name="us-east-1")
        events_client.create_event_bus(Name="default") if False else None  # 'default' bus always exists

        yield {"table": table}


def _sqs_event(order_id: str, message_id: str = "msg-1"):
    return {
        "Records": [
            {
                "messageId": message_id,
                "body": json.dumps({"order_id": order_id}),
            }
        ]
    }


def test_process_order_success(aws_setup):
    from process_order import handler as process_order_handler

    table = aws_setup["table"]
    table.put_item(
        Item={
            "order_id": "order-1",
            "customer_id": "cust-1",
            "items": [{"sku": "A1", "qty": 1}],
            "status": "RECEIVED",
        }
    )

    result = process_order_handler.handler(_sqs_event("order-1"), context=None)

    assert result["batchItemFailures"] == []
    updated = table.get_item(Key={"order_id": "order-1"})["Item"]
    assert updated["status"] == "PROCESSED"


def test_process_order_skips_already_processed(aws_setup):
    """Simulates a redelivered SQS message for an order already processed."""
    from process_order import handler as process_order_handler

    table = aws_setup["table"]
    table.put_item(
        Item={
            "order_id": "order-2",
            "customer_id": "cust-1",
            "items": [{"sku": "A1", "qty": 1}],
            "status": "PROCESSED",
        }
    )

    result = process_order_handler.handler(_sqs_event("order-2"), context=None)

    assert result["batchItemFailures"] == []
    # Status should remain PROCESSED, not error or change
    item = table.get_item(Key={"order_id": "order-2"})["Item"]
    assert item["status"] == "PROCESSED"


def test_process_order_missing_order_does_not_fail_batch(aws_setup):
    from process_order import handler as process_order_handler

    result = process_order_handler.handler(_sqs_event("does-not-exist"), context=None)

    assert result["batchItemFailures"] == []


def test_process_order_reports_failure_for_bad_data(aws_setup):
    from process_order import handler as process_order_handler

    table = aws_setup["table"]
    table.put_item(
        Item={
            "order_id": "order-3",
            "customer_id": "cust-1",
            "items": [],  # invalid: triggers business logic error
            "status": "RECEIVED",
        }
    )

    result = process_order_handler.handler(_sqs_event("order-3", message_id="msg-3"), context=None)

    assert result["batchItemFailures"] == [{"itemIdentifier": "msg-3"}]
