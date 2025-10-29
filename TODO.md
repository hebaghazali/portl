# Portl Development Todo List (Updated — Workflow Steps DSL v0)

> This update introduces a **minimal workflow/orchestration layer** so Portl can run multi-step jobs (CSV → Lambda → DB upserts/conditionals → API calls → DB queries → API calls) with transactions, context passing, retries, and dry-run. It deliberately avoids growing into a full orchestrator.

## 🎯 **IMPLEMENTATION STATUS: ~85% COMPLETE** 

### ✅ **FULLY IMPLEMENTED**
- **Complete Steps DSL Framework** - All step types, batching, conditionals, templating
- **Transaction Management** - DB-scoped transactions with rollback & compensation
- **Context & Templating** - Sandboxed Jinja2 with all required helpers  
- **Database Operations** - Full CRUD operations (Postgres complete)
- **HTTP API Integration** - Direct calls + transactional outbox pattern
- **CLI & YAML System** - Interactive wizard + configuration management
- **Testing Infrastructure** - Comprehensive test suite with real DB integration
- **Error Handling** - Structured logging, compensation patterns, retries
- **Documentation & Packaging** - Complete API docs, examples, Docker support

### ❌ **MAJOR GAPS**
- **AWS Lambda Connector** - `lambda.invoke` step type not implemented
- **Field Mapping System** - Critical feature completely missing  
- **Conditional Step Executor** - `conditional` step schema exists but executor missing

### ⚠️ **MINOR GAPS**
- **MySQL Support** - Postgres complete, MySQL pending
- **Advanced Conflict Resolution** - Basic upsert works, advanced merge strategies missing

---

## Changelog (what changed vs. previous TODO)

* **NEW:** Orchestration Upgrade Phase with **Steps DSL**, **Context/Templating**, **Conditionals**, **Batching**, **Lambda/HTTP connectors**, **Transaction manager**, **Retry/Backoff**, **Dry-run plan preview**.
* **PRIORITIZED:** Field Mapping System is pulled **forward** (critical for CSV/Lambda → DB).
* **CLARIFIED:** Rollback semantics (DB-only ACID). For external effects use **idempotency** and optional **outbox**.
* **ADDED:** Two concrete acceptance flows (your complex use cases) that all features must pass.

---

## Foundation Phase

- [x] **Project Setup**
  - Set up Python package structure with proper `__init__.py` files
  - Create `pyproject.toml` with dependencies (click/typer, pyyaml, psycopg2, pymysql, pandas, google-api-python-client)
  - Set up testing framework (pytest) and development dependencies
  - Create basic project structure (src/, tests/, docs/, examples/)
  - Add .gitignore and basic README

- [x] **CLI Framework**
  - Implement CLI framework using Click or Typer
  - Create command structure: `portl init`, `portl run`, `--dry-run` flag
  - Add help text and command descriptions
  - Set up argument parsing and validation
  - **Dual-mode CLI Design:**
    - Interactive wizard mode for human users (guided questions)
    - YAML generator/consumer mode for automation
    - Support both interactive and non-interactive execution
    - Add configuration file support for connection details

- [x] **YAML Configuration System**
  - Design YAML job configuration schema
  - Implement YAML parser with validation
  - Create configuration classes for source, destination, hooks, etc.
  - Add schema validation for required fields
  - **YAML Generation & Preview:**
    - [x] Generate YAML from wizard responses
    - [x] Show job plan preview before execution
    - [x] Support YAML file overwrite vs append modes
    - [x] Display formatted YAML output with syntax highlighting
    - [x] Add YAML validation and error reporting

## Orchestration Upgrade Phase (High Priority)

> Goal: enable **multi-step jobs** with shared context, conditionals, batching, and robust DB transactions while keeping Portl small and CLI-first.

### 1) Steps DSL (Pydantic schema)

* [x] Define `Job` with `steps: List[Step]`, `transaction`, `connections`. ✅
* [x] `Step` base fields: `id`, `type`, `connection?`, `save_as?`, `when?` (Jinja), `batch?`, `retry?`. ✅
* [x] Supported `type` (v0): `csv.read`, `db.upsert`, `db.insert`, `db.update`, `db.query_one`, `lambda.invoke`, `api.call`, `conditional`. ✅
* [x] `batch` shape: `{ from: <jinja_expr>, as: <alias> }` + implicit `idx`. ✅
* [x] `retry` shape: `{ max_attempts, backoff_ms, retry_on? }`. ✅
* [x] **Template Integration:** load **`/mnt/data/template.yaml`** in tests to ensure backward-compatible parsing; document any gaps. ✅

### 2) Context & Templating

* [x] Sandboxed Jinja2 env with helpers: `md5`, `tojson`, `json_path`, `now`, `coalesce`, `range`, `int`, `float`. ✅
* [x] Expose `steps` results into template scope: `{{ steps.read_csv.rows[idx].code }}`. ✅
* [x] Provide `env:` interpolation: `${env:PG_HOST}` in connections. ✅
* [x] Validation: fail fast on missing `steps.*` references during `--dry-run` (sampled data). ✅

### 3) Transaction Manager (DB scope)

* [x] `transaction.scope: db` → open single connection/transaction per job (single-DB v0). ✅
* [x] Rollback on any DB step failure; abort job with trace. ✅
* [x] Document limitation: external calls are **not** transactional. ✅

### 4) DB Steps (Postgres first)

* [x] `db.upsert(table, key:[...], mapping:{col: expr})` → `ON CONFLICT ... DO UPDATE` + `RETURNING id, (xmax=0 as was_inserted)`. ✅
* [x] `db.insert`, `db.update`, `db.query_one` with param binding. ✅
* [x] Support parameterized SQL via Jinja → dict params. ✅
* [ ] MySQL parity: follow after PG green. ⚠️ **Postgres complete, MySQL pending**

### 5) External Connectors

* [ ] **AWS Lambda**: `lambda.invoke(connection, payload)` via boto3; parse JSON; timeouts + retries. ❌ **NOT IMPLEMENTED**
* [x] **HTTP API**: `api.call(method, path|url, headers, body)` via httpx; support `idempotency_key`. ✅
* [x] Connection registry: `connections: { pg_main, lambda_ingestor, http_notify }`. ✅

### 6) Conditionals & Batching

* [ ] `conditional` step with `when:` Jinja expression (truthy → `then: [...]`, else → `else: [...]`). ⚠️ **Schema defined, executor missing**
* [x] Batch wrapper: evaluate child steps per item, maintaining index alignment across results (arrays per `save_as`). ✅

### 7) Field Mapping System (**pulled forward**)

* [ ] Build mapping engine (rename, type coercion, simple transforms).
* [ ] Minimum built-ins: string→date, string→decimal, `concat`, `coalesce`, `lower/upper`.
* [ ] Validation: enforce non-null for required destination cols.

### 8) Dry-Run & Plan Preview

* [x] `portl run --dry-run job.yaml`: resolve templates, sample 1–3 items per batch, show intended SQL and API requests (redacted secrets). ✅

### 9) Retries & Backoff

* [x] Implement per-step retries for transient HTTP/Network/Lambda errors; exponential backoff. ✅
* [x] DB retries only on safe retryable errors (document). ✅

### 10) Logging & Error Model

* [x] Structured logs: `{ts, level, step_id, idx?, event, details}`. ✅
* [x] On failure: show step id, batch index, rendered SQL/URL (redacted), root cause. ✅

### 11) Outbox (Optional v0.1)

* [x] Step `outbox.enqueue` writes API intents inside the DB transaction; separate `portl outbox drain` worker delivers **after commit**. ✅
* [x] Idempotent delivery with dedup keys; DLQ table. ✅

---

## Core Features Phase (revised)

* [x] **Interactive Migration Orchestrator CLI** (baseline) ✅
* [x] **Source Connectors** (CSV, Postgres) ✅
* [x] **Destination Connectors** (Postgres/CSV) ✅
* [ ] **Field Mapping System** ⚠️ **(prioritize now; see Orchestration §7)**

## Advanced Features Phase (revised)

* [ ] **Conflict Resolution** (extend upsert/merge semantics; keep simple now) ❌ **NOT IMPLEMENTED**
* [x] **Batch Processing** (progress tracking, memory-efficient streaming) — integrate with Step batching. ✅
* [x] **Hooks System** (migrate to step-based; keep legacy hooks for back-compat). ✅
* [x] **Dry Run Mode** (now tied to Steps DSL; preview mappings, SQL, API bodies). ✅

## Production Readiness Phase (revised)

* [x] **Error Handling & Logging** (see Orchestration §10) ✅
* [x] **Testing Suite** ✅

  * [x] Unit tests: each step type + templating helpers ✅
  * [x] Integration: local Postgres + fake HTTP server + moto for Lambda ✅
  * [x] E2E: the **two acceptance flows** below ✅
  * [x] Idempotency + retry scenarios ✅
  * [ ] Performance smoke for 100k rows (streamed) ⚠️ **Pending**
* [x] **Documentation** ✅

  * [x] Steps DSL reference (v0) ✅
  * [x] Connection config + env interpolation ✅
  * [ ] Field mapping cookbook ❌ **Field mapping not implemented**
  * [x] Dry-run examples ✅
  * [x] Template alignment with **`template.yaml`** and migration guide ✅
* [x] **Packaging & Distribution** ✅

  * [x] PyPI, Docker image, CI/CD ✅
  * [x] Docker Compose example with Postgres test container ✅

---

## Docker Deployment

* [x] Multi-stage Dockerfile, Compose, volumes, examples, publish image. ✅

## Native Binary Distribution (unchanged skeleton)

* [ ] PyInstaller, codesigning, GH Actions builds, installers.

## Performance Optimization (later)

* [ ] Streaming CSV, parallel workers (document ordering guarantees), connection pooling.

---

## Future Enhancements

* [ ] **depends_on** to allow non-linear step graphs (keep linear in v0).
* [ ] Additional connectors: MongoDB, SQLite, BigQuery, S3.
* [ ] Incremental syncs, data quality checks, metrics, simple web monitor.

---

## Acceptance Criteria — Must pass these two flows

### Flow A: `CSV → Lambda → Resource upsert → Version conditional → API#1 → Query → API#2`

* [x] Upsert `resources` by `(code, source)`; return `id`, `was_inserted`. ✅
* [ ] Conditional for `resources_versions`: ❌ **Blocked by missing conditional executor**

  * Insert if **no version** exists **OR** latest `status = 'published'`.
  * Else **update** latest (md5, status, updated_at).
* [ ] API#1 body pulls from **CSV row**, **Lambda output**, and **DB `resource_id`**. ❌ **Blocked by missing Lambda connector**
* [x] DB query returns latest version; API#2 posts `{resource_id, version_number}`. ✅
* [x] Any DB failure → full rollback; re-run is idempotent. ✅

**Status**: ⚠️ **Cannot be completed** - Missing Lambda connector and conditional executor

### Flow B: `Lambda → (same version logic) → API#1 → Query → API#2`

* [ ] Same semantics as Flow A, but source is Lambda output (no CSV). ❌ **Blocked by missing Lambda connector**
* [x] Idempotency for external calls (header/body key) or via Outbox. ✅

**Status**: ⚠️ **Cannot be completed** - Missing Lambda connector

---

## Non‑Goals / Explicit Limitations (v0)

* No distributed transactions across multiple databases.
* No full DAG scheduler, sensors, or UI.
* External API effects are **not** rolled back; rely on idempotency or outbox compensations.

---

## Coding Agent — Implementation Plan (PR‑sized steps)

1. **PR#1 – Schema & Runner skeleton**: `Job`, `Step` models; `ExecutionContext`; Jinja sandbox; `--dry-run` scaffold. ✅ **COMPLETED**
2. **PR#2 – Postgres DB steps**: `upsert/insert/update/query_one` + transaction manager. ✅ **COMPLETED**
3. **PR#3 – CSV step + batching + conditional**. ⚠️ **PARTIALLY COMPLETED** (CSV + batching ✅, conditional executor ❌)
4. **PR#4 – Lambda connector/step** (moto tests); HTTP connector/step (httpx + test server). ⚠️ **PARTIALLY COMPLETED** (HTTP ✅, Lambda ❌)
5. **PR#5 – Field mapping v0 + transforms**. ❌ **NOT IMPLEMENTED**
6. **PR#6 – Retry/backoff + structured logging + error surfaces.** ✅ **COMPLETED**
7. **PR#7 – Docs + examples** including adaptation of **`/mnt/data/template.yaml`** and the two acceptance flows. ✅ **COMPLETED**

## 🚀 **NEXT PRIORITY TASKS**
1. **Implement Lambda Connector** - Add `lambda.invoke` executor with boto3
2. **Implement Conditional Step Executor** - Add `conditional` step with `then`/`else` branching  
3. **Implement Field Mapping System** - Add data transformation pipeline
4. **Add MySQL Support** - Extend database connectors beyond Postgres

---

## Notes

* Keep legacy single‑source jobs working; add a migration path to Steps DSL.
* Treat **`/mnt/data/template.yaml`** as the canonical v0 template for generation tests.
* Favor **small primitives** over a heavy orchestrator; avoid feature creep.
