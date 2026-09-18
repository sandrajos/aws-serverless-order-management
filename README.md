# AWS Serverless Order Management & Event-Driven Processing Platform

A portfolio-grade, event-driven order processing platform built with AWS serverless services and Terraform. The project demonstrates practical Cloud/DevOps engineering skills including infrastructure as code, asynchronous processing, idempotency, retries and dead-letter handling, observability, automated testing, and CI validation.

> **Portfolio project:** This is a hands-on project created to demonstrate cloud and DevOps engineering skills. It has **not** been used in a production environment with real customer traffic.

## Architecture

```text
Client
  │
  │ POST /orders
  ▼
API Gateway (REST API)
  │
  ▼
Lambda: create_order
  │
  ├──────────────► DynamoDB
  │                 Orders table
  │
  ▼
SQS: orders-queue
  │
  │ Retry up to 3 times
  │
  ├──────────────► SQS: orders-dlq
  │
  ▼
Lambda: process_order
  │
  ├──────────────► DynamoDB
  │                 Status update
  │
  ▼
EventBridge
OrderProcessed event
  │
  ▼
SNS: order-notifications
  │
  ▼
Lambda: notify
  │
  └── Structured CloudWatch log

CloudWatch
  ├── Lambda logs
  ├── Metrics
  ├── Alarms
  └── Dashboard
```

See [docs/architecture.md](docs/architecture.md) for the detailed architecture, design decisions, failure scenarios, security considerations, and operational notes.

---

## Why this project exists

This project combines several AWS concepts into one coherent system instead of presenting them as isolated demos.

The goal is to demonstrate how a Cloud/DevOps engineer can design and reason about a distributed application involving:

* AWS serverless compute
* REST APIs
* asynchronous messaging
* durable data storage
* event-driven workflows
* retries and dead-letter queues
* idempotent processing
* infrastructure as code
* IAM permissions
* logging and monitoring
* automated testing
* CI validation
* failure handling and troubleshooting

The architecture is intentionally small enough to understand and operate while still providing realistic system-design and troubleshooting scenarios.

---

## Key engineering decisions

### Asynchronous processing

The API does not synchronously perform the complete order-processing workflow.

After an order is persisted, the order ID is sent to Amazon SQS. The processing Lambda consumes the message asynchronously.

This separates API responsiveness from downstream processing and provides buffering when processing is temporarily unavailable.

### Idempotent order creation

Orders use a conditional DynamoDB write.

If the same `order_id` is submitted again, the application does not create a duplicate order. Instead, it returns the existing order.

This demonstrates an important distributed-systems principle: retryable operations should be designed to tolerate duplicate requests.

### Idempotent order processing

The processing Lambda uses a conditional status transition so that an already processed order is not processed again unnecessarily.

This is important because distributed messaging systems can deliver messages more than once.

### Retry and dead-letter handling

SQS automatically retries messages that are not successfully processed.

After the configured number of unsuccessful attempts, the message is moved to the dead-letter queue.

This provides a controlled failure path instead of repeatedly processing a permanently failing message.

### Event-driven notifications

After successful order processing, the application publishes an `OrderProcessed` event to EventBridge.

An EventBridge rule forwards matching events to the SNS notification topic.

The notification Lambda consumes the SNS event and records a structured notification log.

The notification implementation intentionally uses logging rather than a real external email delivery service so the portfolio deployment remains cost-conscious.

---

## AWS services

| Layer                | AWS service / technology    |
| -------------------- | --------------------------- |
| API                  | Amazon API Gateway REST API |
| Compute              | AWS Lambda                  |
| Runtime              | Python 3.12                 |
| Database             | Amazon DynamoDB             |
| Queue                | Amazon SQS                  |
| Dead-letter queue    | Amazon SQS DLQ              |
| Event bus            | Amazon EventBridge          |
| Notifications        | Amazon SNS                  |
| Notification handler | AWS Lambda                  |
| Monitoring           | Amazon CloudWatch           |
| Infrastructure       | Terraform                   |
| CI                   | GitHub Actions              |
| Testing              | pytest + moto               |
| Version control      | Git / GitHub                |

---

## Repository structure

```text
.
├── terraform/
│   ├── api_gateway.tf
│   ├── cloudwatch.tf
│   ├── dynamodb.tf
│   ├── eventbridge.tf
│   ├── iam.tf
│   ├── lambda.tf
│   ├── sns.tf
│   ├── sqs.tf
│   ├── variables.tf
│   ├── outputs.tf
│   └── provider.tf
│
├── src/
│   ├── create_order/
│   │   └── handler.py
│   ├── process_order/
│   │   └── handler.py
│   ├── notify/
│   │   └── handler.py
│   └── common/
│       ├── db.py
│       └── utils.py
│
├── tests/
│   ├── test_create_order.py
│   ├── test_process_order.py
│   └── test_notify.py
│
├── scripts/
│   └── package_lambdas.py
│
├── docs/
│   ├── architecture.md
│   ├── api-examples.md
│   ├── runbook.md
│   └── troubleshooting.md
│
├── .github/
│   └── workflows/
│       └── ci-cd.yml
│
├── requirements.txt
├── .gitignore
└── README.md
```

---

## API

### Create an order

```http
POST /orders
Content-Type: application/json
```

Example request:

```json
{
  "customer_id": "cust-123",
  "items": [
    {
      "sku": "ABC-1",
      "qty": 2
    }
  ]
}
```

Example response:

```json
{
  "order_id": "generated-order-id",
  "status": "RECEIVED",
  "created_at": "2026-09-17T12:00:00+00:00"
}
```

### Get an order

```http
GET /orders/{order_id}
```

Example response:

```json
{
  "order_id": "generated-order-id",
  "customer_id": "cust-123",
  "items": [
    {
      "sku": "ABC-1",
      "qty": 2
    }
  ],
  "status": "PROCESSED",
  "created_at": "2026-09-17T12:00:00+00:00",
  "updated_at": "2026-09-17T12:00:05+00:00"
}
```

Additional request and error examples are available in [docs/api-examples.md](docs/api-examples.md).

---

## Order lifecycle

The order moves through a simple state transition:

```text
RECEIVED
   │
   ▼
SQS
   │
   ▼
process_order Lambda
   │
   ▼
PROCESSED
   │
   ▼
OrderProcessed event
   │
   ▼
Notification
```

The application uses conditional DynamoDB updates to reduce duplicate processing during retries or repeated message delivery.

---

## Reliability and failure handling

The project intentionally includes several failure-handling mechanisms.

### API validation

Invalid requests are rejected before persistence.

Examples include:

* missing `customer_id`
* invalid order items
* invalid quantities
* malformed JSON
* unsupported HTTP methods

### Duplicate order protection

A conditional DynamoDB write prevents the same `order_id` from being created multiple times.

### SQS retries

Messages that fail processing remain available for retry according to the queue configuration.

### Dead-letter queue

Repeatedly failing messages are moved to the DLQ after the configured retry threshold.

The DLQ provides a separate place to inspect and troubleshoot failed messages.

### Partial batch failure handling

The processing Lambda is configured to report failed SQS records individually.

This prevents successfully processed messages in the same batch from unnecessarily being retried.

### Lambda error handling

The Lambda handlers log unexpected failures and return controlled responses at the application boundary.

---

## Security considerations

The project follows several AWS security principles.

### IAM least privilege

Lambda functions receive separate IAM roles with permissions appropriate to their responsibilities.

Examples include:

* create-order Lambda → DynamoDB write/read + SQS send
* process-order Lambda → SQS consume + DynamoDB update + EventBridge publish
* notify Lambda → notification event consumption/logging

### DynamoDB encryption

The DynamoDB table is configured with server-side encryption.

### DynamoDB point-in-time recovery

Point-in-time recovery is configured through Terraform for the database resource.

### No credentials in source control

AWS credentials are not stored in the repository.

The GitHub Actions workflow does not require AWS credentials because it performs validation only.

For local AWS deployment, credentials should be provided through the AWS CLI credential mechanism or another secure AWS-supported authentication method.

---

## Observability

Amazon CloudWatch is used for operational visibility.

The project includes:

* Lambda log groups
* structured application logging
* Lambda error monitoring
* SQS/DLQ monitoring
* CloudWatch alarms
* CloudWatch dashboard configuration

Example operational questions the architecture supports:

* Are orders reaching the processing Lambda?
* Are messages accumulating in the queue?
* Are messages entering the DLQ?
* Are Lambda errors increasing?
* Is order processing failing after retries?
* Which order ID was involved in a failed operation?

---

## Infrastructure as Code

All AWS infrastructure is defined using Terraform.

The Terraform configuration covers the major application resources, including:

* API Gateway
* Lambda functions
* DynamoDB
* SQS queues
* SQS DLQ
* EventBridge
* SNS
* IAM roles and policies
* CloudWatch resources

Terraform provides a repeatable way to define and review infrastructure changes.

The repository also contains the Terraform provider lock file so provider resolution is reproducible.

---

## Lambda packaging

The repository includes a cross-platform packaging script:

```text
scripts/package_lambdas.py
```

Run:

```bash
python scripts/package_lambdas.py
```

The script generates:

```text
terraform/.build/create_order.zip
terraform/.build/process_order.zip
terraform/.build/notify.zip
```

The generated deployment packages are intentionally excluded from Git through `.gitignore`.

---

## Testing

The application includes unit tests using:

* pytest
* moto
* mocked AWS services

Run the tests locally:

```bash
pytest -v
```

The current test suite covers application behavior including:

* order validation
* order creation
* duplicate order handling
* order retrieval
* unsupported HTTP methods
* SQS processing
* processing idempotency
* notification handling
* error scenarios

The current local test suite passes with:

```text
14 passed
```

---

## CI/CD

GitHub Actions provides automated validation.

For pushes to `main` and pull requests, the workflow performs:

```text
Checkout
   │
   ▼
Python setup
   │
   ▼
Install dependencies
   │
   ▼
Run pytest
   │
   ▼
Package Lambda functions
   │
   ▼
Terraform fmt check
   │
   ▼
Terraform init
   │
   ▼
Terraform validate
```

The CI workflow **does not automatically deploy AWS infrastructure**.

It does not require AWS credentials, Terraform Cloud credentials, or an AWS deployment environment.

This keeps the repository suitable for a €0-first development workflow while still providing meaningful automated validation.

---

## Local development

### Prerequisites

Recommended local tooling:

* Python 3.12
* Terraform >= 1.6
* Git
* AWS CLI for optional AWS deployment

### Create a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### Install dependencies

```bash
python -m pip install -r requirements.txt
```

### Run tests

```bash
pytest -v
```

### Package Lambda functions

```bash
python scripts/package_lambdas.py
```

### Validate Terraform

```bash
cd terraform
terraform init -backend=false
terraform fmt -check -recursive
terraform validate
```

These commands do not require deploying the infrastructure.

---

## Optional AWS deployment

The project can be deployed to an AWS account for hands-on learning.

Before deploying, configure AWS credentials securely using the AWS CLI or another supported authentication method.

From the Terraform directory:

```bash
terraform init
terraform plan
terraform apply
```

After deployment, Terraform provides the configured API output.

> **Cost note:** AWS services can incur charges depending on configuration, usage, region, and account status. Resources such as CloudWatch features, DynamoDB recovery features, API Gateway, and other AWS services should be reviewed before deployment. This repository is designed with a €0-first development approach, but an actual AWS deployment should never be assumed to be completely free.

To remove deployed resources:

```bash
terraform destroy
```

Always review the Terraform plan before applying infrastructure.

---

## Cost-conscious development

The project was intentionally designed so that most development work can be completed without maintaining a continuously running AWS environment.

The preferred workflow is:

```text
Develop locally
      │
      ▼
Run pytest + moto
      │
      ▼
Package Lambda functions
      │
      ▼
terraform fmt / validate
      │
      ▼
GitHub Actions validation
      │
      ▼
Optional short-lived AWS deployment
```

This avoids unnecessary always-on resources during development.

The notification implementation also uses structured CloudWatch logging instead of integrating a paid or externally dependent email delivery service.

---

## Troubleshooting and operations

Operational documentation is available in:

* [docs/runbook.md](docs/runbook.md)
* [docs/troubleshooting.md](docs/troubleshooting.md)

These documents cover areas such as:

* Lambda failures
* SQS retry behavior
* DLQ investigation
* DynamoDB status inspection
* EventBridge troubleshooting
* CloudWatch log investigation
* common Terraform problems

---

## Engineering challenges demonstrated

This project intentionally addresses several problems that commonly appear in Cloud/DevOps engineering discussions.

### Challenge 1 — Preventing duplicate orders

**Problem:** A client may retry an API request.

**Approach:** Use a client-provided or generated `order_id` with a conditional DynamoDB write.

**Result:** Duplicate requests do not create duplicate records.

### Challenge 2 — Handling asynchronous failures

**Problem:** The downstream processing Lambda may temporarily fail.

**Approach:** Put the work behind SQS with retry behavior and a DLQ.

**Result:** Temporary failures can be retried while persistent failures become visible through the DLQ.

### Challenge 3 — Avoiding duplicate processing

**Problem:** Queue consumers can receive a message more than once.

**Approach:** Use conditional DynamoDB status transitions.

**Result:** Already processed orders are protected against unnecessary repeated processing.

### Challenge 4 — Decoupling notifications

**Problem:** Notification delivery should not be tightly coupled to the order-processing Lambda.

**Approach:** Publish an `OrderProcessed` event and route it through EventBridge and SNS.

**Result:** Notification handling is separated from the core order-processing path.

### Challenge 5 — Infrastructure consistency

**Problem:** Manually created cloud resources are difficult to reproduce.

**Approach:** Define infrastructure through Terraform.

**Result:** Infrastructure changes can be reviewed, validated, and reproduced.

---

## Future improvements

Possible next steps include:

* API Gateway request schemas
* API authentication/authorization
* API throttling
* AWS WAF integration
* AWS X-Ray tracing
* AWS Secrets Manager integration
* real email delivery through Amazon SES
* transactional outbox pattern for stronger event delivery guarantees
* automated infrastructure tests
* Terraform plan review in CI
* remote Terraform state with locking
* GitHub Actions deployment using AWS OIDC
* blue/green or canary deployment strategies
* enhanced dashboards and SLO-oriented monitoring

These are intentionally treated as future improvements rather than claiming they are already implemented.

---

## Interview discussion points

This project can be used to discuss:

### Architecture

* Why use Lambda instead of a continuously running server?
* Why introduce SQS between the API and processing layer?
* Why use EventBridge?
* Why use both EventBridge and SNS?
* What are the trade-offs of asynchronous processing?

### Reliability

* What happens when the processing Lambda fails?
* How does the DLQ work?
* How do you prevent duplicate processing?
* What happens if EventBridge publishing fails?
* How would you implement stronger event-delivery guarantees?

### Security

* How are Lambda IAM permissions separated?
* How would you authenticate the API?
* Where would secrets be stored?
* How would you protect the API from abuse?

### Operations

* How would you investigate a growing DLQ?
* Which CloudWatch metrics would you monitor?
* How would you troubleshoot a Lambda timeout?
* How would you trace a specific order through the system?

### Terraform

* How would you manage remote state?
* How would you handle state locking?
* How would you structure reusable Terraform modules?
* How would you introduce environment-specific configuration?

### CI/CD

* Why does the current CI workflow validate rather than deploy?
* How would you securely deploy through GitHub Actions?
* Why would OIDC be preferable to long-lived AWS access keys?
* How would you introduce Terraform plan approval?

---

## Project status

| Area                      | Status              |
| ------------------------- | ------------------- |
| Serverless architecture   | Complete            |
| API Gateway               | Complete            |
| Lambda functions          | Complete            |
| DynamoDB persistence      | Complete            |
| SQS processing            | Complete            |
| Dead-letter queue         | Complete            |
| EventBridge integration   | Complete            |
| SNS notification flow     | Complete            |
| CloudWatch monitoring     | Complete            |
| IAM configuration         | Complete            |
| Terraform IaC             | Complete            |
| Lambda packaging          | Complete            |
| Unit tests                | Complete            |
| GitHub Actions validation | Complete            |
| Production deployment     | **Not performed**   |
| Real customer traffic     | **None**            |
| Real email delivery       | **Not implemented** |

---

## Portfolio summary

**AWS Serverless Order Management & Event-Driven Processing Platform**

Designed and implemented a Terraform-managed AWS serverless order-processing platform using API Gateway, Lambda, DynamoDB, SQS/DLQ, EventBridge, SNS, and CloudWatch. Implemented asynchronous processing, idempotency, retry and failure-handling patterns, least-privilege IAM, automated Python testing with pytest/moto, cross-platform Lambda packaging, and GitHub Actions CI validation.

The project is a hands-on portfolio implementation and has not been used with real production customer traffic.
