# Operational Runbook

## Alarm: `orders-dlq-not-empty`

**Meaning:** One or more orders failed processing 3 times and landed in the
dead-letter queue.

**Steps:**
1. Inspect a sample of DLQ messages (without deleting them):
   ```bash
   aws sqs receive-message --queue-url "$(terraform output -raw dlq_url)" \
     --max-number-of-messages 5 --visibility-timeout 0
   ```
2. Correlate the `order_id` in each message with CloudWatch Logs for
   `process_order` to find the exception.
3. Fix the root cause (bad data, downstream dependency outage, bug).
4. Redrive messages back to `orders-queue` (see `troubleshooting.md`).
5. Confirm the DLQ alarm clears and orders reach `PROCESSED`.

## Alarm: `process-order-lambda-errors-high`

**Meaning:** Error rate on the `process_order` Lambda exceeded threshold
over a 5-minute window.

**Steps:**
1. Check recent deployments — was this Lambda's code or config just changed?
2. Check CloudWatch Logs for a recurring exception type.
3. If caused by a bad deploy, roll back:
   ```bash
   cd terraform
   git revert <bad-commit>
   terraform apply
   ```

## Alarm: `api-gateway-5xx-high`

**Meaning:** Clients are receiving server errors from the API.

**Steps:**
1. Check `create_order` Lambda logs for exceptions.
2. Check DynamoDB throttling metrics — a sudden traffic spike combined with
   on-demand mode should auto-scale, but check for `ThrottlingException` in
   logs just in case.
3. If DynamoDB is throttling, this is usually transient; monitor for
   recovery. If persistent, consider switching the table to provisioned
   capacity with auto-scaling.

## Routine maintenance

- **Monthly:** review CloudWatch log retention settings and DLQ contents for
  any stuck/ignored messages.
- **Quarterly:** review IAM policies for drift from least privilege
  (unused permissions accumulate over time).
- **On every dependency update:** run `pytest` locally and let CI re-run
  `terraform plan` to check for unexpected diffs before merging.
