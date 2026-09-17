# Architecture & Design Decisions

## 1. Overview

This platform accepts customer orders via a REST API, persists them,
processes them asynchronously, and notifies customers when processing
completes. It is built entirely from managed, serverless AWS services so
there is no server or container fleet to patch or scale manually.

## 2. Request flow

1. A client sends `POST /orders` to API Gateway.
2. API Gateway invokes the **create_order** Lambda, which validates the
   payload, writes an `Order` item to DynamoDB with status `RECEIVED`, and
   pushes a message onto the **orders-queue** SQS queue.
3. The **process_order** Lambda consumes messages from `orders-queue` in
   batches, applies business logic (e.g. inventory/pricing checks), and
   updates the order's status in DynamoDB to `PROCESSED` or `FAILED`.
4. On success, `process_order` publishes an `OrderProcessed` event to
   **EventBridge**.
5. An EventBridge rule routes `OrderProcessed` events to an **SNS** topic.
6. The **notify** Lambda subscribes to SNS and sends the customer a
   notification (email via SNS, or an integration point for SES/Slack/etc).

## 3. Reliability: retries and the Dead Letter Queue

- SQS is configured with a **redrive policy**: a message that fails
  processing is retried up to `maxReceiveCount = 3` times (with the
  queue's visibility timeout acting as a backoff window) before being
  moved to `orders-dlq`.
- `process_order` is idempotent (see below), so retries are safe.
- A CloudWatch alarm fires when `ApproximateNumberOfMessagesVisible` on the
  DLQ is greater than 0, so a human is paged before a backlog grows silently.
- Failed messages in the DLQ can be redriven back to the main queue once the
  root cause is fixed (SQS supports DLQ redrive natively).

## 4. Idempotency

Order creation uses a client-supplied or server-generated `order_id` as the
DynamoDB partition key with a **conditional write**
(`attribute_not_exists(order_id)`), so retried `create_order` invocations
(e.g. from an API Gateway retry or a duplicate client request) cannot create
duplicate orders. `process_order` checks the current status before
transitioning it, so redelivered SQS messages do not double-process an
already-`PROCESSED` order.

## 5. Security considerations

- **IAM**: each Lambda has its own least-privilege execution role
  (see `terraform/iam.tf`) scoped to only the specific DynamoDB table, SQS
  queue, SNS topic, and EventBridge bus it needs — no wildcard resource
  ARNs.
- **Input validation**: `create_order` validates and sanitizes the request
  body before writing anything, rejecting malformed or oversized payloads.
- **Transport security**: API Gateway enforces HTTPS by default; no plain
  HTTP endpoint is exposed.
- **Secrets**: no long-lived credentials are stored in code; Lambdas use
  their execution role for AWS API calls. If a third-party notification
  provider were added, its credentials would go in AWS Secrets Manager, not
  environment variables in plaintext.
- **Data at rest**: DynamoDB encryption at rest is enabled by default (AWS
  owned key); SQS/SNS use server-side encryption.
- **Least privilege for CI/CD**: the GitHub Actions role used to run
  `terraform plan`/`apply` is scoped to only the resources this stack
  manages and uses OIDC federation rather than long-lived AWS access keys.

## 6. Observability

- All Lambdas emit **structured JSON logs** (see `src/common/utils.py`)
  including `order_id` and `request_id` for correlation.
- CloudWatch Alarms are defined for:
  - Lambda error rate (`process_order`, `create_order`)
  - DLQ message count > 0
  - API Gateway 5xx rate
- CloudWatch Logs Insights sample queries are included in
  `docs/troubleshooting.md` for tracing a single order end-to-end.

## 7. Cost considerations

This architecture is essentially "pay per order" — with no idle compute:

| Service | Cost driver | Notes |
|---|---|---|
| Lambda | Invocations + duration | Free tier covers most portfolio-scale usage |
| API Gateway | Requests | REST API, ~$3.50/million requests |
| DynamoDB | On-demand read/write capacity | No provisioned capacity to pay for at rest |
| SQS | Requests | First 1M requests/month free |
| SNS/EventBridge | Requests/notifications | Negligible at low volume |
| CloudWatch | Logs storage + alarms | Set log retention (see Terraform) to avoid unbounded storage cost |

At low/demo volume this entire stack runs within AWS's free tier. The main
cost lever at scale is DynamoDB throughput mode (on-demand vs provisioned)
and CloudWatch log retention.

## 8. Failure scenarios

| Scenario | Behavior | Mitigation |
|---|---|---|
| DynamoDB write fails during order creation | `create_order` returns 500 to the client; no SQS message is sent (so no orphaned downstream processing) | Client can safely retry; conditional write prevents duplicates |
| `process_order` throws an exception | SQS retries the message up to 3 times, then moves it to the DLQ | CloudWatch alarm on DLQ depth; runbook describes redrive procedure |
| Downstream SNS publish fails | `process_order` still marks the order `PROCESSED`; notification is best-effort and logged as a warning | Notification failures do not block order fulfillment |
| Duplicate SQS delivery (at-least-once semantics) | `process_order` is idempotent; a duplicate delivery is a no-op | Status check before transition |
| Traffic spike | Lambda concurrency and DynamoDB on-demand scale automatically | Reserved concurrency limit set on `process_order` to protect downstream systems from a thundering herd |

## 9. What I would add for a real production deployment

- Multi-account / multi-environment setup (dev, staging, prod) via Terraform
  workspaces or separate state per environment
- Canary/blue-green deployment for Lambdas
- WAF in front of API Gateway
- Distributed tracing with AWS X-Ray
- A proper schema registry / contract testing between producers and
  consumers of EventBridge events
