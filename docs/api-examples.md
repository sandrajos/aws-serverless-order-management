# Sample API Requests

## Create an order — success

**Request**

```bash
curl -X POST "$API_URL/orders" \
  -H "Content-Type: application/json" \
  -d '{
        "customer_id": "cust-123",
        "items": [
          {"sku": "ABC-1", "qty": 2},
          {"sku": "XYZ-9", "qty": 1}
        ]
      }'
```

**Response — `201 Created`**

```json
{
  "order_id": "3f2b9a2e-6b0a-4e0a-9c1a-4d2e6c5a9b10",
  "status": "RECEIVED",
  "created_at": "2026-09-17T10:15:32Z"
}
```

## Create an order — validation error

**Request**

```bash
curl -X POST "$API_URL/orders" \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "cust-123", "items": []}'
```

**Response — `400 Bad Request`**

```json
{
  "error": "items must be a non-empty list"
}
```

## Get order status

**Request**

```bash
curl "$API_URL/orders/3f2b9a2e-6b0a-4e0a-9c1a-4d2e6c5a9b10"
```

**Response — `200 OK`**

```json
{
  "order_id": "3f2b9a2e-6b0a-4e0a-9c1a-4d2e6c5a9b10",
  "customer_id": "cust-123",
  "status": "PROCESSED",
  "items": [
    {"sku": "ABC-1", "qty": 2},
    {"sku": "XYZ-9", "qty": 1}
  ],
  "created_at": "2026-09-17T10:15:32Z",
  "updated_at": "2026-09-17T10:15:34Z"
}
```

## Order not found

**Response — `404 Not Found`**

```json
{
  "error": "order not found"
}
```
