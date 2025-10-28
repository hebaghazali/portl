# PR#2 Remaining Implementation Guide

## Current Status: 30% Complete

**✅ DONE:**
1. Jinja2 sandbox with 18 passing security tests
2. Schema with compensation (`on_error`, `compensate_with`) and outbox (`delivery` mode)
3. Three DB executors (`db.insert`, `db.update`, `db.query_one`)
4. Docker Compose + test fixtures + pytest fixtures

**🚧 TODO:** Engine compensation + Outbox + API executor + Tests + ADRs

---

## Implementation Roadmap (70% remaining)

### Step 4: Engine Compensation Logic (2-3 hours)

**File:** `src/portl/execution/engine.py`

**Key changes:**

1. Add compensation stack to `JobEngine.__init__`:
```python
self._compensation_stack: List[str] = []
self._compensation_steps: Dict[str, Step] = {}  # step_id -> Step
```

2. In `_build_transaction_groups()`, build step lookup dict:
```python
for step in self.job.steps:
    if step.compensate_with:
        self._compensation_steps[step.compensate_with] = self._find_step_by_id(step.compensate_with)
```

3. In `_execute_step()`, track successful compensatable steps:
```python
if result.status == StepStatus.OK and step.compensate_with:
    self._compensation_stack.append(step.compensate_with)
```

4. Add `_run_compensations()` method:
```python
def _run_compensations(self, context: ExecutionContext):
    """Run compensation steps in LIFO order."""
    logger.warning(f"Running {len(self._compensation_stack)} compensation steps")
    
    while self._compensation_stack:
        comp_step_id = self._compensation_stack.pop()
        comp_step = self._compensation_steps[comp_step_id]
        
        try:
            logger.info(f"Executing compensation step: {comp_step_id}")
            dispatch_step(comp_step, context)
        except Exception as e:
            logger.error(f"Compensation step '{comp_step_id}' failed: {e}")
            # Continue compensating even if one fails
```

5. In exception handling (inside `_execute_step`):
```python
except Exception as e:
    if tx_group and self._active_transaction:
        # Run compensations BEFORE rollback
        self._run_compensations(context)
        
        conn = self._get_connection(step.connection)
        self._rollback_transaction(tx_group, conn)
    
    # Honor step error policy
    if step.on_error == 'continue':
        return context.with_step_result(step.id, error_result)
    else:
        raise
```

---

### Step 5: Outbox Pattern (3-4 hours)

#### 5a) Postgres Outbox Helpers

**File:** `src/portl/connectors/postgres.py`

Add methods to PostgresConnector:

```python
def insert_outbox_event(
    self,
    run_id: str,
    step_id: str,
    delivery_type: str,
    payload: Dict[str, Any],
    idempotency_key: str
) -> str:
    """Insert event into outbox table. Returns event UUID."""
    cursor = self._connection.cursor()
    
    cursor.execute("""
        INSERT INTO portl_outbox (run_id, step_id, delivery_type, payload, idempotency_key)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id
    """, (run_id, step_id, delivery_type, json.dumps(payload), idempotency_key))
    
    event_id = cursor.fetchone()[0]
    cursor.close()
    return str(event_id)

def fetch_pending_outbox_events(self, run_id: str, batch_size: int = 50):
    """Fetch pending events for a specific run."""
    cursor = self._connection.cursor()
    
    cursor.execute("""
        SELECT id, delivery_type, payload, idempotency_key
        FROM portl_outbox
        WHERE run_id = %s AND status = 'pending'
        ORDER BY created_at
        LIMIT %s
        FOR UPDATE SKIP LOCKED
    """, (run_id, batch_size))
    
    events = cursor.fetchall()
    cursor.close()
    return events

def mark_outbox_delivered(self, event_id: str):
    """Mark outbox event as delivered."""
    cursor = self._connection.cursor()
    cursor.execute("""
        UPDATE portl_outbox
        SET status = 'delivered', delivered_at = NOW()
        WHERE id = %s
    """, (event_id,))
    cursor.close()

def mark_outbox_failed(self, event_id: str, error: str):
    """Mark outbox event as failed."""
    cursor = self._connection.cursor()
    cursor.execute("""
        UPDATE portl_outbox
        SET status = 'failed', retry_count = retry_count + 1, last_error = %s
        WHERE id = %s
    """, (error, event_id))
    cursor.close()
```

#### 5b) API Call Executor with Outbox

**File:** `src/portl/execution/executors/api_call.py` (CREATE NEW)

```python
import httpx
import logging
from typing import Dict, Any

from ..executor import register_executor
from ..context import ExecutionContext, StepResult, StepStatus
from ...schema import BaseStep

logger = logging.getLogger(__name__)


@register_executor("api.call")
class APICallExecutor:
    def execute(self, step: BaseStep, context: ExecutionContext) -> StepResult:
        delivery = step.config.get('delivery', 'direct')
        
        if delivery == 'outbox':
            return self._enqueue_to_outbox(step, context)
        else:
            return self._call_directly(step, context)
    
    def _enqueue_to_outbox(self, step, context):
        """Write API call intent to outbox (inside transaction)."""
        connection = context.current_vars.get('_connection')
        
        payload = {
            'method': step.config.get('method'),
            'url': step.config.get('url') or step.config.get('path'),
            'headers': step.config.get('headers', {}),
            'body': step.config.get('body'),
        }
        
        idempotency_key = step.config.get('idempotency_key', 
                                         f"{context.run_id}-{step.id}")
        
        event_id = connection.insert_outbox_event(
            run_id=context.run_id,
            step_id=step.id,
            delivery_type='api.call',
            payload=payload,
            idempotency_key=idempotency_key
        )
        
        return StepResult(
            step_id=step.id,
            status=StepStatus.OK,
            output={'outbox_id': event_id, 'status': 'enqueued'},
            metrics={'delivery': 'outbox'},
            touched_transaction=True
        )
    
    def _call_directly(self, step, context):
        """Make HTTP call immediately."""
        method = step.config.get('method')
        url = step.config.get('url') or step.config.get('path')
        headers = step.config.get('headers', {})
        body = step.config.get('body')
        idempotency_key = step.config.get('idempotency_key')
        
        if idempotency_key:
            headers['Idempotency-Key'] = idempotency_key
        
        response = httpx.request(
            method=method,
            url=url,
            headers=headers,
            json=body,
            timeout=30.0
        )
        response.raise_for_status()
        
        return StepResult(
            step_id=step.id,
            status=StepStatus.OK,
            output={'status_code': response.status_code, 'body': response.json()},
            metrics={'delivery': 'direct', 'status_code': response.status_code},
        )
```

#### 5c) Outbox Dispatcher

**File:** `src/portl/services/outbox_dispatcher.py` (CREATE NEW)

```python
import httpx
import logging

logger = logging.getLogger(__name__)


class OutboxDispatcher:
    """Synchronous outbox dispatcher for immediate delivery after commit."""
    
    def __init__(self, connection):
        self.connection = connection
    
    def flush_for_run(self, run_id: str, batch_size: int = 50):
        """
        Flush all pending outbox events for a specific run.
        
        Args:
            run_id: Run identifier
            batch_size: Max events to process
        """
        events = self.connection.fetch_pending_outbox_events(run_id, batch_size)
        
        for event_id, delivery_type, payload_json, idempotency_key in events:
            try:
                if delivery_type == 'api.call':
                    self._deliver_api_call(payload_json, idempotency_key)
                
                self.connection.mark_outbox_delivered(event_id)
                self.connection._connection.commit()
                
            except Exception as e:
                logger.error(f"Failed to deliver outbox event {event_id}: {e}")
                self.connection.mark_outbox_failed(event_id, str(e))
                self.connection._connection.commit()
    
    def _deliver_api_call(self, payload, idempotency_key):
        """Actually make the HTTP call."""
        headers = payload.get('headers', {})
        headers['Idempotency-Key'] = idempotency_key
        
        response = httpx.request(
            method=payload['method'],
            url=payload['url'],
            headers=headers,
            json=payload.get('body'),
            timeout=30.0
        )
        response.raise_for_status()
```

#### 5d) Hook into Engine

In `engine.py`, after successful commit:

```python
def execute(self, env=None):
    # ... existing code ...
    
    # Commit any pending transaction
    if self._active_transaction:
        self._active_transaction.commit_transaction()
        
        # Flush outbox events after commit
        if self._has_outbox_steps():
            self._flush_outbox(context.run_id)
    
    return context

def _flush_outbox(self, run_id):
    """Flush outbox events for this run."""
    from ..services.outbox_dispatcher import OutboxDispatcher
    
    # Get first DB connection (assumes single DB for now)
    for conn in self._connections.values():
        dispatcher = OutboxDispatcher(conn)
        dispatcher.flush_for_run(run_id)
        break
```

---

### Step 6: Tests (3-4 hours)

Create these test files:

1. **`tests/test_db_executors.py`** - Unit tests for insert/update/query_one
2. **`tests/test_compensation.py`** - Compensation LIFO execution
3. **`tests/test_outbox.py`** - Outbox enqueue + flush
4. Update **`tests/test_job_engine.py`** - E2E with Postgres

---

### Step 7: ADRs (1 hour)

Create three ADR documents:

1. **`docs/ADR-002-compensation-scope.md`**
2. **`docs/ADR-003-jinja-sandbox.md`**
3. **`docs/ADR-004-outbox-vs-direct.md`**

---

## Estimated Time to Complete

- **Engine compensation:** 2-3 hours
- **Outbox pattern:** 3-4 hours
- **Tests:** 3-4 hours
- **ADRs:** 1 hour
- **Total:** ~10-12 hours

---

## Dependencies to Install

```bash
pip install httpx>=0.24.0
```

Add to `requirements.txt`:
```
httpx>=0.24.0
```

---

## Test Execution Plan

1. Start Postgres: `docker-compose -f docker-compose.test.yml up -d`
2. Run security tests: `pytest tests/test_templating_security.py -v`
3. Run DB executor tests: `pytest tests/test_db_executors.py -v`
4. Run compensation tests: `pytest tests/test_compensation.py -v`
5. Run outbox tests: `pytest tests/test_outbox.py -v`
6. Run E2E: `pytest tests/test_job_engine.py -v`

---

## Success Criteria

- ✅ All tests pass
- ✅ Can run `portl run sample_job.yaml` against Postgres
- ✅ Compensation runs in LIFO order on failure
- ✅ Outbox events are created inside transaction and delivered after commit
- ✅ Security tests prove sandbox blocks escapes
- ✅ 3 ADRs document decisions

