# ADR-004: Outbox vs Direct API Delivery

## Status
**Accepted** (PR#2)

## Context

When a job mixes database operations and external API calls, consistency becomes challenging:

```yaml
steps:
  - db.insert: Create order in database
  - api.call: Notify external webhook
```

**The Problem**: What if the DB insert succeeds but the API call fails?

- If we **rollback the DB**, the order is lost but we might retry the whole job
- If we **don't rollback**, the order is created but the webhook was never sent
- The external system has no way to "rollback" the API call

This is the classic **dual-write problem** in distributed systems.

## Decision

### Two Delivery Modes

Portl supports **two delivery modes** for external effects (`api.call`, `lambda.invoke`):

#### 1. Direct Mode (Default)
```yaml
- id: notify
  type: api.call
  config:
    delivery: direct  # Default
    method: POST
    url: https://api.example.com/webhooks
```

**Semantics**:
- HTTP call executes **immediately** during step execution
- If inside a db-group transaction, DB changes are **not yet committed**
- If API call fails, transaction rolls back (DB changes undone)
- If API call succeeds but later step fails, transaction rolls back (API effect is **not** rolled back)

**Use when**:
- API is **idempotent** (safe to retry)
- API effect is independent of DB state
- Low-latency response required

**Guarantees**:
- ❌ No guarantee API call only happens once
- ❌ No guarantee DB commit + API call are atomic
- ✅ If API fails, DB will rollback

---

#### 2. Outbox Mode (Transactional)
```yaml
- id: notify
  type: api.call
  config:
    delivery: outbox  # Transactional guarantee
    method: POST
    url: https://api.example.com/webhooks
    idempotency_key: "{{ run_id }}-{{ step_id }}"
```

**Semantics**:
- API call **intent** is written to `portl_outbox` table inside the transaction
- Outbox row is committed atomically with DB changes
- After commit, `OutboxDispatcher` delivers the API call
- Delivery uses idempotency key to prevent duplicates

**Use when**:
- API call should **only happen** if DB commit succeeds
- Exactly-once semantics required
- Acceptable to have slight delay (sync flush after commit)

**Guarantees**:
- ✅ API intent is committed atomically with DB changes
- ✅ Delivery happens at least once (via retry)
- ✅ Idempotency prevents duplicate effects
- ❌ Delivery is not instant (sync flush after commit, or async worker)

## Implementation

### Outbox Table Schema
```sql
CREATE TABLE portl_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id VARCHAR(255) NOT NULL,
    step_id VARCHAR(255) NOT NULL,
    delivery_type VARCHAR(50) NOT NULL,  -- 'api.call', 'lambda.invoke'
    payload JSONB NOT NULL,
    idempotency_key VARCHAR(255) UNIQUE,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    delivered_at TIMESTAMPTZ,
    retry_count INT DEFAULT 0,
    last_error TEXT
);

CREATE INDEX idx_outbox_pending 
ON portl_outbox(status, created_at) 
WHERE status = 'pending';
```

### Execution Flow

**Outbox Mode:**
1. `api.call` step executes → writes row to `portl_outbox` (status: `pending`)
2. Transaction commits (DB changes + outbox intent)
3. `OutboxDispatcher.flush_for_run(run_id)` executes
4. Dispatcher: `SELECT ... FOR UPDATE SKIP LOCKED` (concurrency-safe)
5. Make HTTP call with `Idempotency-Key` header
6. Update status to `delivered` or `failed`

**Direct Mode:**
1. `api.call` step executes → makes HTTP call immediately
2. If HTTP succeeds, step continues
3. If HTTP fails, step fails → transaction rolls back

### Idempotency

Both modes support idempotency keys:
```yaml
idempotency_key: "{{ run_id }}-{{ step_id }}-{{ idx }}"
```

This key is sent as an HTTP header:
```
Idempotency-Key: abc123-notify_webhook-0
```

The receiving API should deduplicate requests with the same key.

## Consequences

### When to Use Outbox

✅ **Use outbox when**:
- Payment/billing operations (must only charge if order created)
- Inventory reservation (must only reserve if order valid)
- Audit logging (must only log if transaction commits)
- Webhook notifications (should only send if business operation succeeded)

❌ **Don't use outbox when**:
- Pre-flight validation calls (okay to fail before DB)
- Read-only API calls (no side effects to worry about)
- Real-time responses required (outbox adds latency)

### When to Use Direct

✅ **Use direct when**:
- API is read-only (GET requests)
- API is naturally idempotent (PUT with deterministic IDs)
- You need synchronous error handling
- External call is independent of DB state

❌ **Don't use direct when**:
- API creates side effects (charge card, send email, reserve resource)
- You need exactly-once delivery guarantees
- API call should only happen if DB commits

### Performance Implications

**Outbox overhead**:
- Extra DB write (INSERT into outbox table)
- Extra DB reads (SELECT pending events)
- HTTP delivery latency (sync flush blocks commit)

**Typical latency**:
- Direct mode: ~50-200ms (HTTP roundtrip)
- Outbox mode: ~100-300ms (DB write + flush + HTTP)

For 99% of workflows, this overhead is acceptable.

### Operational Concerns

**Monitoring outbox health**:
```sql
-- Check for stuck events
SELECT COUNT(*) FROM portl_outbox 
WHERE status = 'pending' 
AND created_at < NOW() - INTERVAL '5 minutes';

-- Check for failed events
SELECT * FROM portl_outbox 
WHERE status = 'failed' 
ORDER BY created_at DESC 
LIMIT 10;
```

**Retry strategy**:
- For now: Sync flush retries failed events
- Future: Async worker with exponential backoff

## Comparison to Industry Patterns

| System | Pattern | Notes |
|--------|---------|-------|
| Stripe | Webhooks via outbox | Guarantee: paid invoice → webhook sent |
| Shopify | Event bus via outbox | Guarantee: order created → event published |
| AWS EventBridge | Direct PUT with retry | Relies on idempotency |
| Temporal | Activities (direct) | Uses workflow retry for consistency |

Portl's dual-mode approach provides **flexibility**: Use outbox for strong guarantees, direct for simplicity.

## Future Evolution

- **Async outbox worker**: Background polling for delivery (vs sync flush)
- **Batch delivery**: Deliver multiple events per HTTP request
- **Dead letter queue**: Move failed events after N retries
- **Webhook verification**: Sign payloads with HMAC

## References

- [Transactional Outbox Pattern](https://microservices.io/patterns/data/transactional-outbox.html)
- [Dual Write Problem](https://thorben-janssen.com/dual-writes/)
- [Stripe Idempotent Requests](https://stripe.com/docs/api/idempotent_requests)

---

**Author**: Backend Team  
**Date**: 2025-10-28  
**Supersedes**: None

