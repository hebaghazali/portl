# PostgreSQL Connector Documentation

The PostgreSQL connector provides robust support for reading from and writing to PostgreSQL databases with advanced features like connection management, batch processing, and transaction support.

## Features

- **Connection Management**: Automatic connection handling with proper cleanup
- **Batch Processing**: Configurable batch sizes for optimal performance
- **Transaction Support**: Full ACID compliance with automatic rollback on errors
- **Schema Introspection**: Automatic schema detection and validation
- **Conflict Resolution**: Multiple strategies for handling duplicate data
- **Type Mapping**: Intelligent mapping between PostgreSQL and generic data types
- **Query Support**: Use custom SQL queries as data sources
- **Error Handling**: Comprehensive error handling with detailed logging

## Configuration

### Basic Configuration

```yaml
source:
  type: postgres
  host: localhost
  port: 5432
  database: mydb
  username: user
  password: password
  schema: public        # Optional, defaults to 'public'
  table: source_table   # Either table OR query, not both

destination:
  type: postgres
  host: localhost
  port: 5432
  database: mydb
  username: user
  password: password
  schema: public
  table: dest_table
```

### Using Custom Queries

Instead of specifying a table, you can use a custom SQL query:

```yaml
source:
  type: postgres
  host: localhost
  database: mydb
  username: user
  password: password
  query: |
    SELECT id, email, name, created_at 
    FROM users 
    WHERE active = true 
    AND created_at > '2023-01-01'
```

### Environment Variables

For security, use environment variables for sensitive information:

```yaml
source:
  type: postgres
  host: ${POSTGRES_HOST}
  database: ${POSTGRES_DB}
  username: ${POSTGRES_USER}
  password: ${POSTGRES_PASSWORD}
  table: users
```

Set the environment variables:
```bash
export POSTGRES_HOST=localhost
export POSTGRES_DB=mydb
export POSTGRES_USER=myuser
export POSTGRES_PASSWORD=mypassword
```

## Conflict Resolution Strategies

The PostgreSQL connector supports multiple conflict resolution strategies:

### 1. Overwrite (Default)
```yaml
conflict: overwrite
```
Uses `INSERT ... ON CONFLICT DO UPDATE` to update existing records.

### 2. Skip
```yaml
conflict: skip
```
Uses `INSERT ... ON CONFLICT DO NOTHING` to ignore conflicts.

### 3. Fail
```yaml
conflict: fail
```
Uses regular `INSERT` that will fail on conflicts, stopping the migration.

### 4. Merge (Future)
```yaml
conflict: merge
```
*Not yet implemented* - Will intelligently merge conflicting data.

## Schema Mapping

Map column names between source and destination:

```yaml
schema_mapping:
  user_id: id
  full_name: name
  email_address: email
  registration_date: created_at
```

## Performance Tuning

### Batch Size
Adjust batch size based on your data and system resources:

```yaml
batch_size: 1000  # Default: 1000 rows per batch
```

- **Small batches (100-500)**: Better for systems with limited memory
- **Medium batches (1000-5000)**: Good balance for most use cases
- **Large batches (5000+)**: Better for high-performance systems with large datasets

### Connection Pooling
The connector uses connection pooling internally for optimal performance.

## Data Type Mapping

The connector automatically maps PostgreSQL types to generic types:

| PostgreSQL Type | Generic Type | Notes |
|----------------|--------------|-------|
| `integer`, `int4` | `int` | 32-bit integer |
| `bigint`, `int8` | `bigint` | 64-bit integer |
| `smallint`, `int2` | `smallint` | 16-bit integer |
| `numeric`, `decimal` | `decimal` | Arbitrary precision |
| `real`, `float4` | `float` | 32-bit float |
| `double precision`, `float8` | `double` | 64-bit float |
| `varchar`, `character varying` | `varchar` | Variable length string |
| `char`, `character` | `char` | Fixed length string |
| `text` | `text` | Unlimited length string |
| `boolean` | `boolean` | True/false |
| `date` | `date` | Date only |
| `timestamp` | `timestamp` | Date and time |
| `timestamptz` | `timestamptz` | Date and time with timezone |
| `json` | `json` | JSON data |
| `jsonb` | `jsonb` | Binary JSON data |
| `uuid` | `uuid` | UUID type |

## Error Handling

The connector provides comprehensive error handling:

### Connection Errors
- Automatic retry logic for transient connection issues
- Clear error messages for configuration problems
- Connection validation before starting migrations

### Data Errors
- Transaction rollback on batch failures
- Detailed error logging with row-level information
- Graceful handling of type conversion errors

### Schema Errors
- Pre-migration schema validation
- Automatic table creation when possible
- Clear warnings for schema mismatches

## Examples

### Simple Table-to-Table Migration
```yaml
source:
  type: postgres
  host: source-db.example.com
  database: prod_db
  username: readonly_user
  password: ${SOURCE_PASSWORD}
  table: users

destination:
  type: postgres
  host: dest-db.example.com
  database: analytics_db
  username: writer_user
  password: ${DEST_PASSWORD}
  table: user_profiles

conflict: overwrite
batch_size: 1000
```

### Migration with Custom Query and Schema Mapping
```yaml
source:
  type: postgres
  host: localhost
  database: ecommerce
  username: analyst
  password: ${DB_PASSWORD}
  query: |
    SELECT 
      o.id as order_id,
      o.customer_id,
      o.total_amount,
      o.created_at as order_date,
      c.email as customer_email
    FROM orders o
    JOIN customers c ON o.customer_id = c.id
    WHERE o.created_at >= '2023-01-01'

destination:
  type: postgres
  host: localhost
  database: reporting
  username: reporter
  password: ${DB_PASSWORD}
  table: order_summary

schema_mapping:
  order_id: id
  customer_email: email
  order_date: created_at

conflict: skip
batch_size: 500
```

## Testing Your Configuration

Use dry-run mode to test your configuration without writing data:

```bash
portl run my_migration.yaml --dry-run
```

This will:
- Test both source and destination connections
- Validate schema compatibility
- Show a preview of the data to be migrated
- Display the total number of rows that would be processed

## Troubleshooting

### Common Issues

1. **Connection Refused**
   - Check that PostgreSQL is running
   - Verify host and port settings
   - Ensure firewall allows connections

2. **Authentication Failed**
   - Verify username and password
   - Check PostgreSQL `pg_hba.conf` configuration
   - Ensure user has necessary permissions

3. **Permission Denied**
   - Source user needs `SELECT` permission on source tables
   - Destination user needs `INSERT`, `UPDATE`, `CREATE` permissions
   - For schema creation, user needs `CREATE` permission on the database

4. **Schema Mismatch**
   - Use dry-run mode to identify schema issues
   - Use schema mapping to resolve column name differences
   - Ensure data types are compatible

### Performance Issues

1. **Slow Migrations**
   - Increase batch size for large datasets
   - Ensure proper indexing on destination tables
   - Consider using `UNLOGGED` tables for temporary data

2. **Memory Issues**
   - Decrease batch size
   - Monitor PostgreSQL memory usage
   - Consider connection pooling settings

### Debugging

Enable verbose logging to get detailed information:

```bash
portl run my_migration.yaml --verbose
```

This will show:
- Detailed connection information
- SQL queries being executed
- Batch processing progress
- Error details with stack traces

## Security Best Practices

1. **Use Environment Variables**: Never hardcode passwords in YAML files
2. **Least Privilege**: Use database users with minimal required permissions
3. **SSL Connections**: Use SSL for production connections (add `sslmode=require` to connection string)
4. **Network Security**: Use VPNs or private networks for database connections
5. **Audit Logging**: Enable PostgreSQL audit logging for compliance

## Advanced Configuration

### Connection String Parameters

You can add additional PostgreSQL connection parameters by modifying the connector code or using environment variables in the connection details.

### Custom Type Handling

For custom PostgreSQL types, the connector will fall back to `text` type. You may need to implement custom type mapping for specialized use cases.

### Parallel Processing

Currently, the connector processes data sequentially. Future versions will support parallel processing for improved performance on large datasets.

## Limitations

1. **No Parallel Processing**: Currently single-threaded
2. **Limited Custom Types**: Complex PostgreSQL types may not be fully supported
3. **No Streaming**: All data is loaded into memory in batches
4. **No Incremental Sync**: Full table migrations only

## Future Enhancements

- Connection pooling with configurable pool sizes
- Parallel batch processing
- Streaming support for very large datasets
- Incremental synchronization
- Advanced conflict resolution strategies
- Custom type mapping configuration
- SSL/TLS connection support
- Compression support for large text fields
