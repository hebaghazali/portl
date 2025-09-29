# Configuration Guide

## YAML Job Configuration

Portl uses YAML files to define migration jobs. Here's a breakdown of the configuration options:

### Source Configuration

```yaml
source:
  type: postgres  # Options: postgres, mysql, csv, google_sheet
  # For databases
  host: localhost
  port: 5432
  user: postgres
  password: password
  database: mydb
  schema: public
  table: users
  # For CSV
  path: ./data/users.csv
  # For Google Sheet
  sheet_id: 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms
  tab_name: Sheet1
```

### Destination Configuration

```yaml
destination:
  type: postgres  # Options: postgres, mysql, csv, google_sheet
  # Configuration options same as source
```

### Field Mapping

```yaml
mapping:
  user_id: id  # Maps source.user_id to destination.id
  first_name: first_name
  last_name: last_name
  # Use null to skip fields
  created_at: null
```

### Conflict Resolution

```yaml
conflict: overwrite  # Options: skip, overwrite, merge, fail
```

### Batch Processing

```yaml
batch_size: 100  # Number of rows per batch
```

### Hooks

```yaml
hooks:
  before_batch: ./scripts/notify_start.sh
  after_batch: ./scripts/notify_done.sh
  before_row: "lambda row: print(f'Processing {row}')"
  after_row: "lambda row, result: print(f'Processed {row}')"
```
