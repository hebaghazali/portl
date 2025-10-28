# ADR-002: Compensation Scope (Saga-Lite)

## Status
**Accepted** (PR#2)

## Context

Multi-step workflows often involve mixed transactional (database) and non-transactional (external API/Lambda) operations. When a later step fails, we need a mechanism to undo earlier effects while respecting the constraints of different systems.

### The Problem

Consider this flow:
```yaml
steps:
  - db.update: Reserve inventory
  - api.call: Charge customer's credit card  
  - db.insert: Create order
```

If the `api.call` fails, we can rollback the database transaction, but we **cannot** rollback the external API call. Similarly, if `db.insert` fails, we might have already charged the customer.

### Options Considered

1. **Distributed Transactions (2PC)**: Coordinate commits across DB and external services
   - ❌ Complex, requires external service support, high latency
   
2. **Best-effort Rollback**: Try to call "undo" APIs
   - ❌ No guarantees, error-prone, doesn't work for many APIs

3. **Saga Pattern with Compensation**: Each forward action has a compensating action
   - ✅ Well-understood pattern, works with any external system
   - ✅ Clear semantics: compensations are business logic, not magic

4. **Outbox Pattern**: Write external intents inside DB transaction, deliver after commit
   - ✅ Provides ACID-like guarantees for external effects
   - ✅ Complementary to compensation

## Decision

### Compensation Scope: DB-Group Only

Portl implements **saga-lite** compensation with the following constraints:

1. **Compensation ONLY within `transaction.scope='db'` groups**
   - Compensatable steps must be part of a database transaction group
   - This ensures compensations run inside the transaction boundary
   
2. **LIFO Execution Order (Stack-Based)**
   - Compensations run in reverse order of successful forward steps
   - Mirrors try/finally semantics in code
   
3. **Compensations Run BEFORE Rollback**
   - Compensating actions execute inside the transaction
   - Then the entire transaction (including compensations) is rolled back
   - This ensures compensation logic is tested but effects are undone

4. **Continue on Compensation Failure**
   - If a compensation step fails, log the error but continue compensating
   - Don't fail the entire rollback process due to one bad compensator

### YAML API

```yaml
transaction:
  scope: db  # Required for compensation

steps:
  - id: reserve_inventory
    type: db.update
    on_error: compensate  # Mark as compensatable
    compensate_with: unreserve_inventory  # Step to run on rollback
    config:
      table: inventory
      where: {sku: "WIDGET-001"}
      mapping: {reserved: 10}
  
  - id: charge_payment
    type: api.call
    # No compensation - use idempotency instead
  
  - id: unreserve_inventory  # Compensation step
    type: db.update
    config:
      table: inventory
      where: {sku: "WIDGET-001"}
      mapping: {reserved: 0}
```

### Execution Semantics

When step `charge_payment` fails:
1. Engine pops compensation stack: `['unreserve_inventory']`
2. Executes `unreserve_inventory` (sets reserved back to 0)
3. Rolls back the entire db-group transaction
4. Result: Database is consistent (inventory not reserved, no order created)

## Consequences

### Positive
- ✅ **Clear mental model**: Compensations are explicit business logic
- ✅ **ACID guarantees for DB**: All DB changes rolled back atomically
- ✅ **Testable**: Compensations execute inside transaction, verifiable
- ✅ **Safe by default**: External effects use outbox or idempotency

### Negative
- ❌ **No distributed transactions**: Cannot coordinate rollback across DB + external APIs
- ❌ **Manual compensation definition**: Developer must define compensating actions
- ❌ **DB-group limitation**: Compensation not available outside transactions

### Trade-offs

- **External API effects** after DB operations should use **outbox pattern** (see ADR-004)
- **Direct API calls** must be designed for **idempotency** (safe to retry)
- **Compensation is not rollback**: It's business logic that logically undoes an action

## Non-Goals

- **Full saga orchestration**: We don't track distributed transaction state across services
- **Automatic compensation**: We don't infer compensations (e.g., INSERT → DELETE)
- **Cross-DB rollback**: Compensation is single-database only

## Future Evolution

- **Named transaction groups**: Allow multiple independent db-groups in one job
- **Async compensation**: Run compensations in background workers
- **Compensation timeout**: Fail job if compensation takes too long

## References

- [Saga Pattern Paper (1987)](https://www.cs.cornell.edu/andru/cs711/2002fa/reading/sagas.pdf)
- [Compensating Transactions (2009)](https://docs.microsoft.com/en-us/azure/architecture/patterns/compensating-transaction)
- [Temporal Compensation](https://docs.temporal.io/workflows#compensation)

---

**Author**: Backend Team  
**Date**: 2025-10-28  
**Supersedes**: None

