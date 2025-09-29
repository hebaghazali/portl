# Portl Development Todo List

## Foundation Phase

- [ ] **Project Setup**
  - Set up Python package structure with proper `__init__.py` files
  - Create `pyproject.toml` with dependencies (click/typer, pyyaml, psycopg2, pymysql, pandas, google-api-python-client)
  - Set up testing framework (pytest) and development dependencies
  - Create basic project structure (src/, tests/, docs/, examples/)
  - Add .gitignore and basic README

- [ ] **CLI Framework**
  - Implement CLI framework using Click or Typer
  - Create command structure: `portl init`, `portl run`, `--dry-run` flag
  - Add help text and command descriptions
  - Set up argument parsing and validation
  - **Dual-mode CLI Design:**
    - Interactive wizard mode for human users (guided questions)
    - YAML generator/consumer mode for automation
    - Support both interactive and non-interactive execution
    - Add configuration file support for connection details

- [ ] **YAML Configuration System**
  - Design YAML job configuration schema
  - Implement YAML parser with validation
  - Create configuration classes for source, destination, hooks, etc.
  - Add schema validation for required fields
  - **YAML Generation & Preview:**
    - Generate YAML from wizard responses
    - Show job plan preview before execution
    - Support YAML file overwrite vs append modes
    - Display formatted YAML output with syntax highlighting
    - Add YAML validation and error reporting

## Core Features Phase

- [ ] **Interactive Migration Orchestrator CLI**
  - Build comprehensive `portl init` interactive wizard with guided question flow
  - **Source & Destination Questions:**
    - Source type selection (Postgres/MySQL/CSV/Google Sheet/Other)
    - Database connection details (host/user/db/schema) with config file support
    - File path for CSV sources
    - Google Sheet ID and tab name for sheet sources
    - Destination type and connection details
    - Destination table name specification
  - **Schema & Mapping Questions:**
    - Auto-map columns by name vs manual mapping configuration
    - Column-by-column mapping interface
    - Auto-create missing columns option (y/n)
    - Handle extra destination columns (ignore/error)
  - **Conflict & Transformations Questions:**
    - Primary key conflict strategy (skip/overwrite/merge/fail)
    - Column transformation configuration (date string → datetime, price string → Decimal)
  - **Hooks Configuration Questions:**
    - Row-level hooks (before/after each row): script/lambda/API call/none
    - Batch-level hooks (before/after batch): maintenance notifications, cache clearing
  - **Batching & Performance Questions:**
    - Configurable batch size (e.g., 100 rows at a time)
    - Retry strategy on failure (skip/retry N times/fail fast)
    - Parallel execution options (y/n, number of workers)
  - **Validation & Dry Run Questions:**
    - Dry run preview (first N rows without writing)
    - Schema compatibility validation before running
    - Row count comparison between source and destination
  - **YAML Confirmation & Execution:**
    - Save configuration to YAML file option
    - Overwrite vs append for existing YAML files
    - Run migration immediately vs generate YAML only
    - Show job plan preview before execution
    - Interactive confirmation: "⚡ Here's the job plan. Run now? (y/n)"

- [ ] **Source Connectors**
  - Implement Postgres connector (psycopg2)
  - Implement MySQL connector (pymysql)
  - Implement CSV connector (pandas)
  - Implement Google Sheets connector (google-api-python-client)
  - Add connection management and error handling
  - Implement data reading with pagination support

- [ ] **Destination Connectors**
  - Implement Postgres writer with batch inserts
  - Implement MySQL writer with batch inserts
  - Implement CSV writer with chunking
  - Implement Google Sheets writer with batch updates
  - Add connection management and error handling
  - Implement data writing with transaction support

- [ ] **Field Mapping System**
  - Build field mapping engine to transform data between schemas
  - Support column renaming and type conversion
  - Add data validation and transformation rules
  - Implement mapping configuration in YAML

## Advanced Features Phase

- [ ] **Conflict Resolution**
  - Implement skip strategy (ignore conflicts)
  - Implement overwrite strategy (replace existing)
  - Implement merge strategy (combine data)
  - Implement fail strategy (stop on conflict)
  - Add conflict detection logic

- [ ] **Batch Processing**
  - Implement configurable batch sizes
  - Add progress tracking and reporting
  - Implement memory-efficient streaming for large datasets
  - Add batch-level error handling and recovery

- [ ] **Hooks System**
  - Implement before/after row hooks
  - Implement before/after batch hooks
  - Support script execution hooks
  - Support API call hooks
  - Add hook error handling and logging

- [ ] **Dry Run Mode**
  - Implement `--dry-run` flag functionality
  - Add schema validation and preview
  - Show sample rows and mapping results
  - Display row count estimates without writing data
  - Add validation warnings and errors

## Production Readiness Phase

- [ ] **Error Handling & Logging**
  - Add comprehensive error handling across all components
  - Implement structured logging with different levels
  - Add retry mechanisms for transient failures
  - Create error reporting and recovery strategies

- [ ] **Testing Suite**
  - Write unit tests for all connectors
  - Add integration tests for end-to-end workflows
  - Test error scenarios and edge cases
  - Add performance tests for large datasets
  - Test all conflict resolution strategies

- [ ] **Documentation**
  - Write user documentation with examples
  - Create API documentation for developers
  - Add migration examples for different scenarios
  - Write troubleshooting guide
  - Create video tutorials for common use cases

- [ ] **Packaging & Distribution**
  - Set up Python packaging with setuptools
  - Configure PyPI distribution
  - Add installation instructions
  - Create Docker image for containerized usage
  - Set up CI/CD pipeline for automated testing

- [ ] **Docker Deployment**
  - Create multi-stage Dockerfile for optimized image size
  - Add Docker Compose configuration for easy setup
  - Create Docker image with all dependencies pre-installed
  - Add volume mounting for data files and job configs
  - Test Docker image with different data sources
  - Publish to Docker Hub with automated builds
  - Add Docker usage documentation and examples

- [ ] **Native Binary Distribution**
  - Set up PyInstaller for creating standalone executables
  - Create platform-specific builds (Windows, macOS, Linux)
  - Implement auto-update mechanism for binaries
  - Add code signing for Windows/macOS security
  - Create installer packages (.msi, .dmg, .deb, .rpm)
  - Set up GitHub Actions for automated binary builds
  - Test binaries on clean systems without Python installed
  - Add binary distribution documentation

- [ ] **Performance Optimization**
  - Optimize for large datasets with streaming
  - Implement parallel processing where possible
  - Add memory management for large files
  - Optimize database connection pooling
  - Add performance monitoring and metrics

## Future Enhancements

- [ ] **Additional Connectors**
  - Add MongoDB connector
  - Add SQLite connector
  - Add BigQuery connector
  - Add S3 connector for file storage

- [ ] **Advanced Features**
  - Add data transformation functions (aggregation, filtering)
  - Implement incremental sync capabilities
  - Add data quality checks and validation
  - Create web dashboard for monitoring jobs

- [ ] **Meta-Driven Migration System**
  - Design declarative YAML/JSON specs for migration definitions
  - Create migration engine that reads specs and generates SQL/operations
  - Implement reusable migration patterns (suffix handling, conflict resolution, foreign key adjustments)
  - Build schema-aware utilities that wrap database introspection
  - Add functions like `migrate_table()`, `add_enum_values()`, `copy_with_suffix_handling()`

- [ ] **Migration Automation Layer**
  - Create CLI tool (`portl-migrate`) for scaffolding migration files
  - Implement boilerplate conflict handler injection
  - Enforce consistent naming conventions across migrations
  - Add migration pattern detection and suggestion system
  - Build migration validation and preview tools

- [ ] **Reusable Test Infrastructure**
  - Create generic pytest fixtures for migration testing
  - Implement "old table vs new table row counts match" tests
  - Add "enum coverage is preserved" validation tests
  - Build reusable test patterns for common migration scenarios
  - Create migration-specific test utilities and helpers

---

## Getting Started

1. Start with **Project Setup** to get your development environment ready
2. Move through the phases sequentially, but feel free to jump ahead if you need specific features
3. Test each component thoroughly before moving to the next
4. Keep the YAML configuration simple and extensible
5. Focus on error handling early - it will save you time later

## Notes

- This project will give you hands-on experience with database connectivity, data pipelines, and CLI development
- Perfect for learning backend engineering concepts like connection pooling, batch processing, and error handling
- The modular design will help you understand system architecture and component interaction
- Consider this a stepping stone toward building more complex financial data pipelines and trading systems
