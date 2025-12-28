# Google Sheets Connector Summary

This document provides an overview of the Google Sheets connector implementation for Portl.

## Overview

The Google Sheets connector provides source and destination capabilities for reading from and writing to Google Spreadsheets using the Google Sheets API v4.

## Authentication

The connector supports two authentication methods:

### 1. Service Account (Recommended for automation)

```yaml
connections:
  sheets_main:
    type: google_sheets
    config:
      spreadsheet_id: "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
      sheet_name: "Sheet1"
      credentials_path: "./service-account.json"
```

**Setup:**
1. Create a service account in Google Cloud Console
2. Download the JSON key file
3. Share the spreadsheet with the service account email
4. Set `credentials_path` to the JSON key file path

### 2. Application Default Credentials (ADC)

```yaml
connections:
  sheets_main:
    type: google_sheets
    config:
      spreadsheet_id: "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
      sheet_name: "Sheet1"
      # No credentials_path - uses ADC
```

**Setup:**
1. Run `gcloud auth application-default login`
2. Or set `GOOGLE_APPLICATION_CREDENTIALS` environment variable

## Configuration Options

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| spreadsheet_id | string | Yes | The ID from the spreadsheet URL |
| sheet_name | string | No | Sheet tab name (default: "Sheet1") |
| range_name | string | No | A1 notation range (e.g., "A1:D100") |
| credentials_path | string | No | Path to service account JSON |

### Getting the Spreadsheet ID

The spreadsheet ID is the long string in the URL:
```
https://docs.google.com/spreadsheets/d/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/edit
                                       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                       This is the spreadsheet_id
```

## Features

### Source Connector (GoogleSheetsSourceConnector)

- **Read all data**: Fetches all rows from the sheet
- **Header parsing**: First row is treated as column headers
- **Short row handling**: Rows with fewer cells are padded with empty strings
- **Schema introspection**: Returns headers with 'string' type

### Destination Connector (GoogleSheetsDestinationConnector)

- **Append rows**: New rows are added after existing data
- **Header creation**: Can create header row from schema
- **Clear sheet**: Can clear data while preserving headers
- **User-entered values**: Values are parsed (dates, numbers) by Sheets

## Data Types

All Google Sheets data is treated as strings by Portl. Use the Field Mapping System to convert types:

```yaml
transformations:
  - column: price
    operation: parse_number
  - column: date
    operation: parse_date
    parameters:
      format: "%m/%d/%Y"
```

## Example Usage

### Reading from Google Sheets

```yaml
# Legacy job format
source:
  type: google_sheets
  spreadsheet_id: "${SPREADSHEET_ID}"
  sheet_name: "Customers"
  credentials_path: "./credentials.json"

destination:
  type: postgres
  # ... postgres config

transformations:
  - column: email
    operation: lowercase
  - column: signup_date
    operation: parse_date
    parameters:
      format: "%Y-%m-%d"
```

### Writing to Google Sheets

```yaml
# Steps DSL format
connections:
  pg_main:
    type: postgres
    config:
      # ... postgres config
      
  sheets_dest:
    type: google_sheets
    config:
      spreadsheet_id: "${SPREADSHEET_ID}"
      sheet_name: "Export"
      credentials_path: "./credentials.json"

steps:
  - id: fetch_data
    type: db.query_many
    connection: pg_main
    query: "SELECT * FROM users WHERE status = 'active'"
    save_as: users
    
  # Note: Writing to Sheets from steps isn't directly supported yet
  # Use legacy job format for Sheets destinations
```

## Rate Limits

Google Sheets API has rate limits:

| Limit Type | Limit |
|------------|-------|
| Read requests | 300 per minute per project |
| Write requests | 300 per minute per project |
| Cells per read | 10 million cells |

For large datasets, consider:
- Batch reads instead of frequent small reads
- Using BigQuery for large-scale data operations
- Implementing exponential backoff for retries

## Transaction Behavior

⚠️ **Important**: Google Sheets does NOT support transactions.

- All writes are immediately persisted
- There is no rollback capability
- `begin_transaction()`, `commit_transaction()`, `rollback_transaction()` are no-ops

For data integrity:
- Validate data before writing
- Consider writing to a staging sheet first
- Use batch operations to minimize partial failures

## Known Limitations

1. **No transactions**: Writes are immediate and cannot be rolled back
2. **No conflict resolution**: All writes append; upsert not supported
3. **All data is strings**: Schema is always string type
4. **Rate limits**: API has strict rate limits for free tier
5. **Pagination**: No efficient server-side pagination
6. **Cell limits**: 10 million cells per spreadsheet maximum

## Error Handling

Common Google Sheets API errors:

| HTTP Code | Meaning |
|-----------|---------|
| 400 | Invalid request (bad range, etc.) |
| 401 | Authentication failed |
| 403 | Permission denied (check sharing settings) |
| 404 | Spreadsheet not found |
| 429 | Rate limit exceeded |
| 503 | Service temporarily unavailable |

## Dependencies

Required packages:
```
google-api-python-client>=2.0.0
google-auth>=2.0.0
```

These are included in Portl's requirements.txt.

