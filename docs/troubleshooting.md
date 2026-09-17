# Troubleshooting Guide

## Trace a single order end-to-end

CloudWatch Logs Insights query (run against all three Lambda log groups):

```
fields @timestamp, @message
| filter order_id = "PUT-ORDER-ID-HERE"
| sort @timestamp asc
```

## "My order is stuck in RECEIVED"

1. Check the `orders-queue` SQS metrics — is `ApproximateNumberOfMessagesVisible`
   draining, or growing?
2. Check `process_order` Lambda error metrics in CloudWatch:
   ```
   fields @timestamp, @message
   | filter @message like /ERROR/
   | sort @timestamp desc
   | limit 50
   ```
3. Check the DLQ (`orders-dlq`) — if the message landed there, the order
   failed processing 3 times. See "Redriving messages from the DLQ" below.

## Redriving messages from the DLQ

Once the root cause is fixed:

```bash
aws sqs start-message-move-task \
  --source-arn "$(terraform output -raw dlq_arn)" \
  --destination-arn "$(terraform output -raw orders_queue_arn)"
```

Monitor progress:

```bash
aws sqs list-message-move-tasks --source-arn "$(terraform output -raw dlq_arn)"
```

## "Customer says they didn't get a notification"

Notifications are best-effort. Check:

```
fields @timestamp, @message
| filter order_id = "PUT-ORDER-ID-HERE"
| filter @logStream like /notify/
```

If the order status is `PROCESSED` in DynamoDB but no notification log entry
exists, check the SNS topic's delivery status / the `notify` Lambda's error
logs — the order itself was still processed successfully.

## API Gateway returning 5xx

1. Check API Gateway's CloudWatch metrics for `5XXError`.
2. Check the `create_order` Lambda's error logs for stack traces.
3. Confirm the Lambda's IAM role still has the permissions defined in
   `terraform/iam.tf` — a common cause of sudden 5xx spikes after a
   Terraform change is an accidentally narrowed IAM policy.

## Common validation errors (400 responses)

| Error message | Cause |
|---|---|
| `"customer_id is required"` | Missing `customer_id` field |
| `"items must be a non-empty list"` | `items` missing, empty, or wrong type |
| `"quantity must be a positive integer"` | An item's `qty` is zero, negative, or non-numeric |
