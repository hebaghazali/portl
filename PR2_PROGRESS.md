# PR#2 Implementation Progress

## ✅ Completed (Steps 1-3)

### 1. Jinja Sandbox + Security Tests ✅
**Files created/modified:**
- `src/portl/execution/templating.py` - Switched to `SandboxedEnvironment`
- `tests/test_templating_security.py` - 18 security tests

**Results:**
- ✅ All 18 tests passing
- ✅ Blocks private attribute access (`__class__`, `__subclasses__`, etc.)
- ✅ Blocks builtins, file system, imports, eval/exec
- ✅ Safe operations (filters, globals) still work correctly
- ✅ Strict undefined still enforced

### 2. Schema & DSL Changes ✅
**Files modified:**
- `src/portl/schema.py` - Added compensation + delivery mode

**Changes:**
- ✅ `BaseStep` now has `on_error` and `compensate_with` fields
- ✅ `APICallStep` now has `delivery` mode (`'direct'` or `'outbox'`)
- ✅ Validation: `compensate_with` must reference existing step
- ✅ Validation: Compensation only allowed with `transaction.scope='db'`
- ✅ Validation: `on_error='compensate'` requires `compensate_with`

### 3. DB Executors ✅
**Files created:**
- `src/portl/execution/executors/db_insert.py`
- `src/portl/execution/executors/db_update.py`
- `src/portl/execution/executors/db_query_one.py`
- Updated `src/portl/execution/executors/__init__.py`

**Features:**
- ✅ `db.insert` - INSERT with RETURNING clause
- ✅ `db.update` - UPDATE with WHERE clause (safety check)
- ✅ `db.query_one` - SELECT returning single row or None
- ✅ All executors support both dataclass and Pydantic steps
- ✅ All executors properly mark `touched_transaction`
- ✅ Registered with executor registry

### 4. Test Infrastructure ✅
**Files created:**
- `docker-compose.test.yml` - Postgres test container
- `tests/fixtures/init.sql` - Schema + test data
- Updated `tests/conftest.py` - `postgres_connection` and `clean_db` fixtures

**Tables created:**
- `portl_outbox` - Transactional outbox pattern
- `orders` - Test orders table
- `inventory` - Test inventory table
- `audit_log` - Compensation tracking

---

## 🚧 In Progress (Steps 4-7)

### 4. Engine: Transactions + Compensation 🔄
**Status:** NOT YET IMPLEMENTED

**Requirements:**
- [ ] Add compensation stack (LIFO) to `JobEngine`
- [ ] Track which steps succeeded in current db-group
- [ ] On error: run compensations → rollback → honor step policy
- [ ] Structured logging (run_id, step_id, duration_ms, tx_group_id)
- [ ] Support `on_error: ['fail', 'continue', 'rollback', 'compensate']`

**Pseudocode:**
```python
class JobEngine:
    def __init__(self):
        self._compensation_stack = []  # Step IDs to compensate
    
    def _execute_step(self, step, context):
        result = dispatch_step(step, context)
        
        # If step succeeded and has compensation
        if result.status == OK and step.compensate_with:
            self._compensation_stack.append(step.compensate_with)
        
        return result
    
    def _run_compensations(self, context):
        while self._compensation_stack:
            comp_step_id = self._compensation_stack.pop()
            # Find and execute compensation step
            comp_step = self._find_step_by_id(comp_step_id)
            dispatch_step(comp_step, context)
```

### 5. Outbox Pattern 🔄
**Status:** NOT YET IMPLEMENTED

**Components needed:**
1. **Outbox helpers in `connectors/postgres.py`**:
   - `insert_outbox_event(run_id, step_id, payload, idempotency_key)`
   - `fetch_pending_events(run_id, batch_size)`
   - `mark_delivered(event_id)`

2. **API Call executor** (`execution/executors/api_call.py`):
   - `delivery='outbox'` → write to outbox table
   - `delivery='direct'` → immediate HTTP call
   - Set `Idempotency-Key` header

3. **Outbox dispatcher** (`services/outbox_dispatcher.py`):
   - `flush_for_run(run_id)` - sync flush
   - SELECT ... FOR UPDATE SKIP LOCKED
   - httpx for HTTP delivery
   - Mark delivered/failed

4. **Engine integration**:
   - After successful commit → call `flush_for_run(run_id)`

### 6. Tests 🔄
**Status:** NOT YET IMPLEMENTED

**Required tests:**
- [ ] `test_db_insert_update_query_one.py`
- [ ] `test_engine_rollback_and_compensation.py`
- [ ] `test_outbox_enqueue_and_sync_flush.py`
- [ ] E2E scenario in `test_job_engine.py`

### 7. ADRs 🔄
**Status:** NOT YET IMPLEMENTED

**Required docs:**
- [ ] `docs/ADR-002-compensation-scope.md`
- [ ] `docs/ADR-003-jinja-sandbox.md`
- [ ] `docs/ADR-004-outbox-vs-direct.md`

---

## 📊 Overall Progress

**Completed:** 3/8 major components (37.5%)
**Tests passing:** 18/18 security tests ✅
**Docker setup:** ✅ Ready
**Schema:** ✅ Complete

---

## 🎯 Next Actions

### Immediate (Next Session)
1. Implement compensation logic in `engine.py`
2. Create API call executor with outbox support
3. Implement outbox dispatcher with sync flush
4. Write unit tests for DB executors
5. Write integration tests for compensation

### Follow-up
6. E2E test with full flow
7. Write 3 ADRs
8. Test with real Postgres (docker-compose up)
9. Create sample job YAML

---

## 🔥 Critical Notes

1. **Compensation scope:** ONLY within db-group, LIFO order
2. **Outbox idempotency:** Use `run_id + step_id + batch_idx`
3. **Transaction isolation:** Default READ COMMITTED
4. **No retry on 4xx:** Only retry 5xx/network errors
5. **Compensation failures:** Log but continue compensating

---

## 📁 Files Modified/Created

### Modified (6 files)
- `src/portl/schema.py` (+50 lines: compensation + delivery)
- `src/portl/execution/templating.py` (+80 lines: sandbox)
- `src/portl/execution/executors/__init__.py` (+3 imports)
- `tests/conftest.py` (+60 lines: fixtures)
- `docker-compose.test.yml` (NEW)
- `tests/fixtures/init.sql` (NEW)

### Created (4 files)
- `src/portl/execution/executors/db_insert.py` (135 lines)
- `src/portl/execution/executors/db_update.py` (145 lines)
- `src/portl/execution/executors/db_query_one.py` (120 lines)
- `tests/test_templating_security.py` (276 lines)

### Pending Creation (~800 more lines needed)
- `src/portl/execution/executors/api_call.py`
- `src/portl/services/outbox_dispatcher.py`
- Engine compensation logic in `engine.py`
- 4+ test files
- 3 ADR documents

---

## ✅ Definition of Done Checklist

- [x] Jinja sandbox with security tests
- [x] Schema supports compensation + outbox
- [x] DB executors (insert, update, query_one)
- [ ] Engine compensation logic
- [ ] Outbox enqueue + dispatcher
- [ ] API call executor (direct + outbox)
- [ ] Unit tests for DB executors
- [ ] Integration tests for compensation
- [ ] E2E test with Postgres
- [ ] 3 ADRs written

**Progress: 3/10 complete (30%)**

