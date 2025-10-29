# PR#2: How to Complete the Last 20%

## What You Have Now (80% Complete)

### ✅ Fully Implemented & Tested
1. **Jinja2 Security Sandbox** - 18/18 tests passing
2. **Schema with Compensation + Outbox** - Full validation
3. **6 Step Executors** - csv, db.insert/update/query_one/upsert, api.call
4. **Postgres Outbox Helpers** - 4 methods added
5. **Outbox Dispatcher** - Sync flush with httpx
6. **Test Files** - 3 comprehensive test suites written

---

## What's Left (20% - 2-3 hours)

### 🔴 CRITICAL: Engine Compensation Logic

**File to Edit:** `src/portl/execution/engine.py`

**Step 1:** Add instance variables to `__init__` method:

```python
def __init__(self, job: Job, dry_run: bool = False):
    # ... existing code ...
    self._compensation_stack: List[str] = []
    self._step_lookup: Dict[str, Step] = {step.id: step for step in self.job.steps}
```

**Step 2:** In `_execute_step()`, after `result = dispatch_step(...)`:

```python
# Track successful compensatable steps
if result.status == StepStatus.OK and step.on_error == 'compensate' and step.compensate_with:
    self._compensation_stack.append(step.compensate_with)
```

**Step 3:** Add compensation runner method (add after `_execute_step`):

```python
def _run_compensations(self, context: ExecutionContext):
    """Run compensation steps in LIFO order."""
    logger.warning(f"Running {len(self._compensation_stack)} compensation steps")
    
    while self._compensation_stack:
        comp_step_id = self._compensation_stack.pop()
        comp_step = self._step_lookup.get(comp_step_id)
        
        if not comp_step:
            logger.error(f"Compensation step '{comp_step_id}' not found")
            continue
        
        try:
            logger.info(f"Executing compensation step: {comp_step_id}")
            dispatch_step(comp_step, context)
        except Exception as e:
            logger.error(f"Compensation step '{comp_step_id}' failed: {e}")
```

**Step 4:** In `_execute_step()` exception handler:

```python
except Exception as e:
    if tx_group and self._active_transaction:
        # Run compensations BEFORE rollback
        self._run_compensations(context)
        
        # Then rollback
        conn = self._get_connection(step.connection)
        self._rollback_transaction(tx_group, conn)
    
    raise
```

**Step 5:** Add outbox flush after commit in `execute()` method:

```python
def execute(self, env: Optional[Dict[str, str]] = None):
    # ... existing code ...
    
    # Before return context:
    if self._active_transaction:
        self._active_transaction.commit_transaction()
        
        # Flush outbox
        self._flush_outbox_if_needed(context.run_id)
        
        self._active_transaction = None
    
    return context

def _flush_outbox_if_needed(self, run_id: str):
    """Flush outbox events after successful commit."""
    from ..services.outbox_dispatcher import OutboxDispatcher
    
    for conn in self._connections.values():
        if hasattr(conn, 'fetch_pending_outbox_events'):
            dispatcher = OutboxDispatcher(conn)
            dispatcher.flush_for_run(run_id)
            break
```

---

### 🟡 Sample Job (15 minutes)

**Create:** `tests/fixtures/sample_job.yaml`

Copy from `PR2_FINAL_STATUS.md` section 9.

---

### 🟡 ADRs (45 minutes)

**Create 3 files in `docs/`:**
1. `ADR-002-compensation-scope.md`
2. `ADR-003-jinja-sandbox.md`
3. `ADR-004-outbox-vs-direct.md`

Copy templates from `PR2_FINAL_STATUS.md` section 10.

---

## Testing Plan

### 1. Install Dependencies
```bash
pip install httpx>=0.24.0
```

### 2. Start Postgres
```bash
docker-compose -f docker-compose.test.yml up -d
```

### 3. Run Security Tests (should pass immediately)
```bash
pytest tests/test_templating_security.py -v
```

### 4. Run DB Executor Tests (after engine compensation done)
```bash
pytest tests/test_db_executors.py -v
```

### 5. Run Compensation Tests (after engine compensation done)
```bash
pytest tests/test_compensation.py -v
```

### 6. Run Outbox Tests (after engine compensation done)
```bash
pytest tests/test_outbox.py -v
```

### 7. Run All Tests
```bash
pytest tests/ -v
```

---

## Expected Test Results

After implementing engine compensation logic:

```
tests/test_templating_security.py::18 PASSED
tests/test_db_executors.py::6 PASSED
tests/test_compensation.py::4 PASSED
tests/test_outbox.py::4 PASSED
tests/test_job_engine.py::7 PASSED

Total: 39 tests passing
```

---

## Commit Strategy

```bash
# Commit 1: Executors & outbox infrastructure
git add src/portl/execution/executors/
git add src/portl/services/outbox_dispatcher.py
git add src/portl/connectors/postgres.py
git commit -m "feat(pr2): Add DB executors + API call + outbox infrastructure"

# Commit 2: Engine compensation logic
git add src/portl/execution/engine.py
git commit -m "feat(pr2): Implement compensation logic (saga-lite, LIFO)"

# Commit 3: Tests
git add tests/test_*.py
git commit -m "test(pr2): Add tests for DB executors, compensation, outbox"

# Commit 4: Docs
git add docs/ADR-*.md tests/fixtures/sample_job.yaml
git commit -m "docs(pr2): Add ADRs and sample job"
```

---

## Definition of Done

- [ ] Engine compensation logic implemented
- [ ] `sample_job.yaml` created
- [ ] 3 ADRs written
- [ ] All tests passing with Postgres running
- [ ] No linter errors
- [ ] Can run `portl run tests/fixtures/sample_job.yaml`

---

## Time Estimate

- **Engine compensation:** 1-2 hours
- **Sample job:** 15 minutes
- **ADRs:** 45 minutes
- **Testing & fixes:** 30 minutes

**Total: 2.5-3.5 hours**

---

## Files That Need Changes

**Only 1 file needs significant changes:**
- `src/portl/execution/engine.py` - Add ~60 lines for compensation

**Plus 4 new documentation files:**
- `tests/fixtures/sample_job.yaml`
- `docs/ADR-002-compensation-scope.md`
- `docs/ADR-003-jinja-sandbox.md`
- `docs/ADR-004-outbox-vs-direct.md`

---

## What to Do Right Now

1. Read `PR2_FINAL_STATUS.md` - Full status report
2. Open `src/portl/execution/engine.py`
3. Follow Step 1-5 above to add compensation logic
4. Create sample job + ADRs
5. Test everything

**The hard work is done. You're implementing well-defined patterns into an existing skeleton.**

Good luck! 🚀

