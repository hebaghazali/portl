# MySQL Connector Summary

This document provides an overview of the MySQL connector implementation for Portl.

## Overview

The MySQL connector provides source and destination capabilities for reading from and writing to MySQL databases. It supports MySQL 5.7+ and MySQL 8.0+.

## Connection Configuration

### Basic Configuration

```yaml
connections:
  mysql_main:
    type: mysql
    config:
      host: localhost
      port: 3306
      database: mydb
      username: ${env:MYSQL_USER}
      password: ${env:MYSQL_PASSWORD}
```

### Configuration Options

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| host | string | required | MySQL server hostname |
| port | int | 3306 | MySQL server port |
| database | string | required | Database name |
| username | string | required | MySQL username |
| password | string | required | MySQL password |
| table | string | optional | Table name (for legacy jobs) |
| query | string | optional | Custom SELECT query |

## Features

### Source Connector (MySQLSourceConnector)

- **Schema introspection**: Reads table schema from `information_schema.COLUMNS`
- **Batch reading**: Supports paginated reads with `LIMIT`/`OFFSET`
- **Custom queries**: Can read from arbitrary SELECT statements
- **Type mapping**: Maps MySQL types to generic Portl types

### Destination Connector (MySQLDestinationConnector)

- **Batch inserts**: Uses `executemany` for efficient bulk inserts
- **Upsert support**: `INSERT ... ON DUPLICATE KEY UPDATE`
- **Conflict strategies**: `overwrite`, `skip`, `fail`
- **Transaction support**: Full ACID transaction support

## Upsert Behavior

MySQL upsert uses `INSERT ... ON DUPLICATE KEY UPDATE`:

```sql
INSERT INTO table (col1, col2, col3) 
VALUES (%s, %s, %s) 
ON DUPLICATE KEY UPDATE col1=VALUES(col1), col2=VALUES(col2), col3=VALUES(col3)
```

### Differences from PostgreSQL

| Feature | PostgreSQL | MySQL |
|---------|------------|-------|
| Upsert syntax | `ON CONFLICT ... DO UPDATE` | `ON DUPLICATE KEY UPDATE` |
| RETURNING clause | Supported | Not supported |
| Conflict keys | Explicit in query | Implicit (uses UNIQUE/PRIMARY KEY) |
| Last insert ID | Via RETURNING | Via `cursor.lastrowid` |

### Key Requirements

For upsert to work in MySQL:
- The table must have a PRIMARY KEY or UNIQUE index on the key columns
- The key columns must be included in the INSERT statement

## Type Mapping

### MySQL to Generic Types

| MySQL Type | Generic Type |
|------------|--------------|
| INT, INTEGER | int |
| BIGINT | bigint |
| SMALLINT, TINYINT | smallint |
| DECIMAL, NUMERIC | decimal |
| FLOAT | float |
| DOUBLE | double |
| VARCHAR | varchar |
| CHAR | char |
| TEXT, TINYTEXT, MEDIUMTEXT, LONGTEXT | text |
| BOOLEAN, BOOL | boolean |
| DATE | date |
| DATETIME, TIMESTAMP | timestamp |
| TIME | time |
| JSON | json |
| BLOB, BINARY, VARBINARY | binary |

### Generic to MySQL Types

| Generic Type | MySQL Type |
|--------------|------------|
| int | INT |
| bigint | BIGINT |
| smallint | SMALLINT |
| decimal | DECIMAL(10,2) |
| float | FLOAT |
| double | DOUBLE |
| varchar | VARCHAR(255) |
| char | CHAR(1) |
| text | TEXT |
| boolean | BOOLEAN |
| date | DATE |
| timestamp | DATETIME |
| time | TIME |
| json | JSON |
| uuid | CHAR(36) |
| binary | BLOB |

## Example Usage

### Legacy Job Format (CSV to MySQL)

```yaml
source:
  type: csv
  path: ./data/users.csv

destination:
  type: mysql
  host: localhost
  port: 3306
  database: mydb
  username: root
  password: ${MYSQL_PASSWORD}
  table: users

conflict: overwrite
batch_size: 1000
```

### Steps DSL Format

```yaml
connections:
  mysql_main:
    type: mysql
    config:
      host: ${env:MYSQL_HOST:-localhost}
      port: 3306
      database: ${env:MYSQL_DATABASE:-mydb}
      username: ${env:MYSQL_USER:-root}
      password: ${env:MYSQL_PASSWORD}

steps:
  - id: upsert_users
    type: db.upsert
    connection: mysql_main
    table: users
    key: ["email"]
    mapping:
      email: "{{ row.email }}"
      name: "{{ row.name }}"
      updated_at: "{{ now() }}"
```

## Transaction Semantics

- Transactions are auto-started when `transaction.scope: db` is set
- All steps within a transaction group share the same connection
- Rollback reverts all changes within the group
- MySQL uses InnoDB engine (required for transactions)

## Known Limitations

1. **No RETURNING clause**: MySQL doesn't support `RETURNING`, so inserted records must be queried separately if needed
2. **Implicit conflict keys**: `ON DUPLICATE KEY UPDATE` uses whatever UNIQUE/PRIMARY KEY exists; you can't specify which constraint to use
3. **No partial upsert**: All columns are updated on conflict; PostgreSQL allows selective column updates
4. **ROW_COUNT behavior**: `cursor.rowcount` returns 1 for insert, 2 for update (MySQL-specific)

## Error Handling

Common MySQL errors and their meanings:

| Error Code | Meaning |
|------------|---------|
| 1045 | Access denied (wrong credentials) |
| 1049 | Unknown database |
| 1062 | Duplicate entry (conflict on unique key) |
| 1146 | Table doesn't exist |
| 2003 | Can't connect to MySQL server |

## Performance Tips

1. **Use batch inserts**: `executemany` is much faster than individual inserts
2. **Disable autocommit**: Keep autocommit off for bulk operations
3. **Index key columns**: Ensure UNIQUE/PRIMARY KEY indexes for upsert performance
4. **Use connection pooling**: For high-throughput applications (not yet implemented in Portl)


