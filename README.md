# Production-Grade AWS Serverless Order Management & Event-Driven Processing Platform

A portfolio-grade, event-driven order processing system built entirely on AWS
serverless primitives and provisioned with Terraform. It demonstrates the
core skills expected of a Cloud/DevOps engineer: infrastructure as code,
event-driven architecture, asynchronous processing with retries and
dead-letter handling, observability, automated testing, and CI/CD.

> **Note:** This is a hands-on portfolio project built to demonstrate cloud
> and DevOps engineering skills. It has not been used in a production
> environment with real customer traffic.

## Architecture

```
Client
  │  POST /orders
  ▼
API Gateway (REST API)
  │
  ▼
Lambda: create_order  ──► DynamoDB (Orders table)
  │
  ▼
SQS: orders-queue  ──(on failure, after 3 attempts)──► SQS: orders-dlq
  │
  ▼
Lambda: process_order  ──► DynamoDB (status update)
  │
  ▼
EventBridge: "OrderProcessed" event
  │
  ▼
SNS Topic: order-notifications ──► Lambda: notify (email/log)

CloudWatch: structured logs, metrics, alarms on DLQ depth & Lambda errors
```

See [docs/architecture.md](docs/architecture.md) for the full write-up,
including design decisions, failure scenarios, security considerations, and
cost estimates.

## Why this project exists

This project consolidates what would otherwise be six small, disconnected
AWS demos (order management, queue processing, notifications, feedback
handling, and infrastructure setup) into a single coherent, realistic
platform — the kind of system a Cloud/DevOps engineer would actually be
asked to design, operate, and troubleshoot.

## Tech stack

| Layer | Technology |
|---|---|
| Compute | AWS Lambda (Python 3.12) |
| API | Amazon API Gateway (REST) |
| Data | Amazon DynamoDB |
| Messaging | Amazon SQS (+ DLQ), Amazon SNS, Amazon EventBridge |
| IaC | Terraform |
| CI/CD | GitHub Actions |
| Observability | Amazon CloudWatch (Logs, Metrics, Alarms) |
| Testing | pytest, moto (AWS mocking) |

## Repository layout

```
.
├── terraform/              # All infrastructure as code
├── src/
│   ├── create_order/       # Lambda: accepts new orders via API Gateway
│   ├── process_order/      # Lambda: consumes SQS, processes orders
│   ├── notify/              # Lambda: sends notifications on SNS events
│   └── common/              # Shared helpers (DynamoDB client, logging, validation)
├── tests/                   # Unit tests (pytest + moto)
├── .github/workflows/       # CI/CD pipeline
├── docs/                    # Architecture, runbook, troubleshooting guide
└── requirements.txt
```

## Getting started

### Prerequisites

- AWS account + credentials configured locally (`aws configure`)
- Terraform >= 1.6
- Python 3.12
- An AWS SNS-verified email (for the notification subscription), or adapt
  the `notify` Lambda to log/print for local demo purposes

### 1. Install dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run tests locally

```bash
pytest -v
```

### 3. Provision infrastructure

```bash
cd terraform
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

Terraform will output the API Gateway invoke URL.

### 4. Try it out

```bash
curl -X POST "$(terraform output -raw api_invoke_url)/orders" \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "cust-123", "items": [{"sku": "ABC-1", "qty": 2}]}'
```

### 5. Tear down

```bash
terraform destroy
```

## CI/CD

Every push runs automated tests and validates Terraform. Every merge to
`main` runs `terraform plan` (and, if you configure the environment secrets,
`terraform apply`) via GitHub Actions. See
[.github/workflows/ci-cd.yml](.github/workflows/ci-cd.yml).

## Sample API requests

See [docs/api-examples.md](docs/api-examples.md) for full request/response
examples, including error cases (validation failure, throttling, DLQ replay).

## Troubleshooting & operations

See [docs/troubleshooting.md](docs/troubleshooting.md) and
[docs/runbook.md](docs/runbook.md) for common failure scenarios and how to
diagnose them using CloudWatch Logs Insights queries provided in this repo.
