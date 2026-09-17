import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "common"))


def _sns_event(order_id: str, customer_id: str):
    detail = {"order_id": order_id, "customer_id": customer_id}
    eventbridge_payload = {"detail": detail}
    return {
        "Records": [
            {"Sns": {"Message": json.dumps(eventbridge_payload)}}
        ]
    }


def test_notify_handles_valid_event(caplog):
    from notify import handler as notify_handler

    event = _sns_event("order-1", "cust-1")
    result = notify_handler.handler(event, context=None)

    assert result["statusCode"] == 200


def test_notify_does_not_raise_on_malformed_record():
    from notify import handler as notify_handler

    bad_event = {"Records": [{"Sns": {"Message": "not-json"}}]}
    # Should not raise -- errors are caught and logged per-record
    result = notify_handler.handler(bad_event, context=None)

    assert result["statusCode"] == 200
