# Portl

**Portl** is a developer-first CLI tool for moving data across databases, CSVs, and Google Sheets.
Instead of writing one-off SQL or Python scripts for every migration, Portl gives you an **interactive wizard** and **YAML job configs** you can re-run, share, and version-control.

*Portl turns migrations into a repeatable, reliable system — not a grind.*

---

## Features

* Sources: Postgres, MySQL, CSV, Google Sheets.
* Interactive wizard — no need to remember 12 flags.
* YAML job specs — portable, reusable, version-controlled.
* Hooks — run scripts or APIs before/after rows or batches.
* Dry run + schema validation.
* Batch execution with retries.

---

## Installation

```bash
pip install portl
```

---

## Quickstart

### 1. Start a New Migration

```bash
portl init
```

This launches the wizard and asks questions like:

* What's your source? (Postgres/MySQL/CSV/Google Sheet)
* What's your destination?
* How do you want to map fields?
* Conflict strategy? (skip/overwrite/merge/fail)
* Any hooks before/after rows or batches?

At the end, Portl generates a **YAML job file** for you.

---

### 2. Example YAML Job

```yaml
source:
  type: csv
  path: ./data/users.csv
destination:
  type: postgres
  host: localhost
  database: mydb
  table: users
conflict: overwrite
batch_size: 100
hooks:
  before_batch: ./scripts/notify_start.sh
  after_batch: ./scripts/notify_done.sh
```

---

### 3. Run the Migration

```bash
portl run jobs/users_to_pg.yaml
```

---

### 4. Dry Run Preview

```bash
portl run jobs/users_to_pg.yaml --dry-run
```

→ Shows sample rows, schema mapping, and a row count check without writing data.

---

## Documentation

See full docs & examples at: [coming soon]

---

## Contributing

We welcome issues, forks, and pull requests. MIT licensed.

---

With Portl, you'll **never write the same migration script twice.**
