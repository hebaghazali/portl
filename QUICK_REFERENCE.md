# Portl Quick Reference - New Features (PR#1 + PR#2)

## Basic Job Structure

```yaml
connections:
  pg:
    type: postgres
    config:
      host: localhost
      port: 5432
      database: mydb
      username: user
      password: pass

transaction:
  scope: db  # Required for compensation

steps:
  - id: step_name
    type: step_type
    connection: pg
    config:
      # Step-specific config
```

---

## Step Types

### CSV Operations
```yaml
- id: read_data
  type: csv.read
  path: ./data/input.csv
  delimiter: ","
  has_header: true
  limit: 1000  # Optional
```

### Database Operations

**Insert:**
```yaml
- id: insert_order
  type: db.insert
  connection: pg
  config:
    table: orders
    mapping:
      order_id: "{{ item.id }}"
      amount: "{{ item.total }}"
```

**Update:**
```yaml
- id: update_status
  type: db.update
  connection: pg
  config:
    table: orders
    where:
      order_id: "ORD-123"
    mapping:
      status: "shipped"
```

**Upsert:**
```yaml
- id: upsert_user
  type: db.upsert
  connection: pg
  config:
    table: users
    key: ["email"]  # ON CONFLICT columns
    mapping:
      email: "user@example.com"
      name: "John Doe"
```

**Query:**
```yaml
- id: get_order
  type: db.query_one
  connection: pg
  config:
    query: "SELECT * FROM orders WHERE id = %(order_id)s"
    params:
      order_id: "123"
```

### API Calls

**Direct (Immediate):**
```yaml
- id: notify
  type: api.call
  config:
    delivery: direct  # Default
    method: POST
    url: https://api.example.com/webhooks
    headers:
      Authorization: "Bearer token"
    body:
      event: "order_created"
    idempotency_key: "{{ run_id }}-{{ step_id }}"
```

**Outbox (Transactional):**
```yaml
- id: notify
  type: api.call
  connection: pg  # Required for outbox
  config:
    delivery: outbox  # Atomic with DB
    method: POST
    url: https://api.example.com/webhooks
    body:
      event: "order_created"
```

---

## Compensation (Saga Pattern)

```yaml
transaction:
  scope: db  # REQUIRED

steps:
  - id: reserve_inventory
    type: db.update
    connection: pg
    on_error: compensate  # Enable compensation
    compensate_with: unreserve_inventory  # Step to run on failure
    config:
      table: inventory
      where: {sku: "WIDGET-001"}
      mapping: {reserved: 10}
  
  - id: create_order
    type: db.insert
    connection: pg
    # If this fails, unreserve_inventory runs
    config:
      table: orders
      mapping: {...}
  
  # Compensation step (only runs on failure)
  - id: unreserve_inventory
    type: db.update
    connection: pg
    config:
      table: inventory
      where: {sku: "WIDGET-001"}
      mapping: {reserved: 0}
```

**What happens on failure:**
1. `reserve_inventory` succeeds → pushes `unreserve_inventory` to stack
2. `create_order` fails → pops stack and runs `unreserve_inventory`
3. Transaction rolls back (all DB changes undone)

---

## Template Helpers

### Access Previous Step Results
```yaml
- id: step2
  config:
    value: "{{ steps.step1.rows[0].field }}"  # Access step1 output
    count: "{{ steps.step1.count }}"           # Row count
```

### Filters
```yaml
# Hash
value: "{{ data | md5 }}"

# JSON
json: "{{ data | tojson }}"
parsed: "{{ json_str | fromjson }}"

# Type conversion
num: "{{ '123' | int }}"
decimal: "{{ '45.67' | float }}"

# String manipulation
upper: "{{ name | upper }}"
lower: "{{ email | lower }}"
trimmed: "{{ ' text ' | trim }}"

# Null handling
safe: "{{ optional_field | default('fallback') }}"
first: "{{ value1 | coalesce(value2, value3, 'default') }}"

# JSON path
city: "{{ user | json_path('address.city') }}"
```

### Globals
```yaml
# Current timestamp
timestamp: "{{ now() }}"
formatted: "{{ now('%Y-%m-%d') }}"

# Iteration
loop: "{% for i in range(5) %}{{ i }}{% endfor %}"
```

---

## Conditional Execution

```yaml
- id: conditional_step
  type: db.insert
  when: "{{ steps.previous_step.count > 0 }}"  # Only if condition true
  config: {...}
```

---

## Error Policies

```yaml
- id: step_name
  on_error: fail  # Options: fail | continue | compensate
  compensate_with: cleanup_step  # Required if on_error=compensate
```

### fail (default)
- Step fails → job fails
- Transaction rolls back

### continue
- Step fails → log error → continue to next step
- Transaction continues

### compensate
- Step fails → run compensation → rollback → fail job
- Requires `transaction.scope='db'`

---

## Retry Configuration

```yaml
- id: api_call
  type: api.call
  retry:
    max_attempts: 3
    backoff_ms: 1000
    retry_on: ["HTTPError", "ConnectionError"]  # Optional
  config: {...}
```

---

## Batching (Loop Execution)

```yaml
- id: read_csv
  type: csv.read
  save_as: csv_data
  path: ./data.csv

- id: process_rows
  type: db.insert
  connection: pg
  batch:
    from: "{{ csv_data.rows }}"  # Collection to loop over
    as: row                       # Alias for each item
  config:
    table: processed
    mapping:
      id: "{{ row.id }}"
      value: "{{ row.value | int }}"
```

---

## Common Patterns

### Pattern 1: CSV → DB with Compensation
```yaml
transaction:
  scope: db

steps:
  - type: csv.read
    path: ./orders.csv
  
  - type: db.insert
    on_error: compensate
    compensate_with: mark_failed
    table: orders
  
  - type: mark_failed  # Compensation
    type: db.insert
    table: failed_imports
```

### Pattern 2: DB → API with Outbox
```yaml
steps:
  - type: db.upsert
    table: customers
  
  - type: api.call
    delivery: outbox  # Only sent if DB commits
    url: https://crm.com/webhooks/customer
```

### Pattern 3: Multi-Step with Query
```yaml
steps:
  - type: db.upsert
    save_as: order_result
  
  - type: db.query_one
    query: "SELECT * FROM orders WHERE id = %(order_id)s"
    params:
      order_id: "{{ steps.order_result.id }}"
  
  - type: api.call
    body:
      order_id: "{{ steps.query.record.id }}"
```

---

## Debugging

### Check Execution Context
```python
# After job execution
context = engine.execute()
print(context.get_metrics_summary())
# {'total_steps': 5, 'ok_steps': 4, 'error_steps': 1, ...}
```

### Check Step Results
```python
result = context.get_step_result('step_id')
print(result.status)   # OK, ERROR, SKIPPED
print(result.output)   # Step-specific output
print(result.metrics)  # duration_ms, row_count, etc.
```

### Check Outbox Status
```sql
SELECT * FROM portl_outbox 
WHERE run_id = 'your-run-id'
ORDER BY created_at DESC;
```

---

## Security Notes

### Safe Templates ✅
```yaml
value: "{{ user.email | lower }}"
hash: "{{ data | md5 }}"
timestamp: "{{ now() }}"
```

### Unsafe Templates ❌
```yaml
# These will fail with SecurityError
value: "{{ ''.__class__ }}"
code: "{{ __import__('os').system('ls') }}"
exec: "{{ eval('1+1') }}"
```

---

## Performance Tips

1. **Use outbox for critical operations** (consistency > latency)
2. **Use direct for read-only APIs** (lower latency)
3. **Batch CSV reads** with `limit` if file is huge
4. **Use query_one** for single-row lookups (vs fetching all rows)
5. **Set idempotency keys** for all external calls

---

## Troubleshooting

### "No executor registered for step type"
→ Check step `type` matches registered executors  
→ Run `portl list-executors` (if implemented)

### "Compensation requires transaction.scope='db'"
→ Add `transaction: {scope: db}` to job config

### "compensate_with references unknown step"
→ Ensure step ID exists in job

### "SecurityError: access to attribute is unsafe"
→ Template tried to access blocked attribute  
→ Use only allowlisted filters/globals

---

## CLI Commands

```bash
# Dry run (preview without execution)
portl run job.yaml --dry-run

# Live run
portl run job.yaml

# Verbose logging
portl run job.yaml --verbose

# With environment variables
PG_HOST=prod.db.com portl run job.yaml
```

---

**For full documentation, see:**
- `docs/ADR-002-compensation-scope.md`
- `docs/ADR-003-jinja-sandbox.md`
- `docs/ADR-004-outbox-vs-direct.md`
- `tests/fixtures/sample_job.yaml`

