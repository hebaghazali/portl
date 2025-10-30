# ADR-005: SQL-from-File in DSL (Safe, Parameterized SELECTs)

## Status
Accepted — targeted for PR#3

## Context
Long, parameterized SELECT queries embedded directly in YAML reduce readability, inhibit reuse, and make editor tooling (SQL linting/formatting) awkward. We often need non-trivial projections/CTEs/window functions during extract steps (e.g., shaping rows before moving them to another sink). Storing SQL in `.sql` files gives:
- **Readability & maintainability**: SQL is edited with proper syntax highlighting/linters.
- **Reuse**: The same query can be referenced by multiple jobs.
- **Separation of concerns**: DSL focuses on orchestration; SQL lives beside it as a first-class asset.

Security and correctness constraints still apply: path traversal must be blocked, templates must remain sandboxed, and parameters must be bound (never concatenated).

## Decision
Introduce an optional `sql_file` field for query steps:
- Supported in v1 on `db.query_one` and `db.query_many` (new step type).
- `sql_file` and inline `sql` are **mutually exclusive** (XOR).
- File resolution is **relative** to the job file directory (and optionally a configured `queries/` root). Absolute paths are **rejected**.
- Path traversal is **blocked** after normalization; any `..` segments are disallowed.
- Max file size 256 KB (configurable). UTF-8 only.
- Templating is allowed inside the `.sql` via the **existing sandboxed Jinja** (StrictUndefined + allowlisted filters/globals).
- Parameters are passed via the existing **driver parameter binding** (named parameters), not string concatenation.
- The engine logs `sql_source: "file:<relative_path>"` (or `"inline"`) for observability.

### Result schema validation for CSV writes
- When results from `db.query_many` are written to CSV, the `csv.write` step's `columns: [...]` acts as the expected schema.
- All declared columns must exist in each row of the result. If any are missing, the job fails. In `--dry-run`, a preflight on sampled data must fail fast with the same error surface.
- Optional `strict_extra_columns` (default: false) can be used to fail if the result contains unexpected columns not listed in `columns`.

Example:
```yaml
steps:
  - id: fetch_customers
    type: db.query_many
    sql_file: queries/customers_by_segment.sql
    params:
      segment: "enterprise"
      limit: 500

  - id: fetch_one
    type: db.query_one
    sql_file: queries/customer_by_id.sql
    params:
      customer_id: "{{ globals.customer_id }}"
```

## Consequences

### Positive Outcomes
- **Improved maintainability** – Complex SQL logic lives in versioned `.sql` files with syntax highlighting and linting support.  
- **Cleaner DSLs** – YAML jobs remain concise; SQL is kept where SQL belongs.  
- **Reusable queries** – The same `.sql` file can feed multiple steps or jobs, reducing duplication.  
- **Safer parameterization** – By keeping query text static and parameters bound separately, the risk of SQL injection is minimized.  
- **Consistent auditing** – Storing queries as files makes code reviews, diffs, and change tracking easier.

### Negative / Trade-offs
- **Extra I/O and caching complexity** – Each job must read external files; caching logic must be added to prevent performance regressions.  
- **More failure modes** – Missing files, wrong encodings, or path violations can break plan loading.  
- **Configuration sprawl** – The engine must know where to look for queries (default `queries/`, possibly configurable later).  
- **Version skew risk** – DSL YAML and SQL files may drift if not versioned together.  
- **Limited portability** – File-based references tie jobs to a filesystem context; remote execution environments need packaging support.

### System-Level Impact
- **Validation Layer** – Plan loader must verify file existence, size, encoding, and path policy at load time to fail fast.  
- **Execution Layer** – Executors must read, template, and cache file contents; cache invalidation becomes part of correctness.  
- **Security Posture** – Path traversal and sandbox enforcement become part of the threat model; logs must surface rejected paths clearly.  
- **Observability** – Step logs now include `sql_source` metadata so operators can tell whether a query came from inline text or file.  
- **Extensibility** – The caching seam and path policy can later support connector-specific allowlists or remote SQL sources.

### CSV schema guarantees
- By validating expected CSV columns against the query result, the pipeline fails early when SQL edits accidentally drop/rename fields.  
- Dry-run preflight provides a safe feedback loop before touching sinks.  
- Optional strictness for extra columns lets teams choose between permissive selection vs. exact schema enforcement.

### Long-Term Considerations
- This feature introduces a **new artifact type (SQL files)** in the project lifecycle; teams must version and test them.  
- Future enhancements like **query linting, remote fetch, or digest verification** can build on this design.  
- If misused (e.g., dynamic SQL templating beyond parameters), it could reintroduce injection risks; strict sandboxing must remain enforced.
