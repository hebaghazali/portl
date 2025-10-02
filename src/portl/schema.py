"""
YAML job configuration schema definitions.

This module defines the complete schema for Portl migration job configurations
using dataclasses for type safety and validation.

Supports both legacy single-source/destination jobs (JobConfig) and new 
multi-step workflow jobs (Job).
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List, Union, Literal
from pathlib import Path
import yaml


# Type aliases for better readability
SourceType = Literal['postgres', 'mysql', 'csv', 'google_sheets']
DestinationType = Literal['postgres', 'mysql', 'csv', 'google_sheets']
ConflictStrategy = Literal['overwrite', 'skip', 'fail', 'merge']
TransformOperation = Literal['lowercase', 'uppercase', 'trim', 'parse_date', 'parse_number']

# New Job Step DSL types
StepType = Literal['csv.read', 'db.upsert', 'db.insert', 'db.update', 'db.query_one', 'lambda.invoke', 'api.call', 'conditional']
TransactionScope = Literal['db', 'none']


@dataclass
class DatabaseConfig:
    """Configuration for database connections (Postgres/MySQL)."""
    type: Union[Literal['postgres'], Literal['mysql']]
    host: str
    database: str
    username: str
    password: str
    port: Optional[int] = None
    schema: Optional[str] = None
    table: Optional[str] = None
    query: Optional[str] = None
    
    def __post_init__(self):
        """Validate database configuration after initialization."""
        if self.port is None:
            self.port = 5432 if self.type == 'postgres' else 3306
        
        if self.schema is None:
            self.schema = 'public' if self.type == 'postgres' else None
        
        if not self.table and not self.query:
            raise ValueError("Database config must specify either 'table' or 'query'")


@dataclass
class CsvConfig:
    """Configuration for CSV file sources/destinations."""
    type: Literal['csv']
    path: str
    delimiter: str = ','
    encoding: str = 'utf-8'
    has_header: bool = True
    
    def __post_init__(self):
        """Validate CSV configuration."""
        path_obj = Path(self.path)
        if not path_obj.parent.exists():
            raise ValueError(f"Directory does not exist: {path_obj.parent}")


@dataclass
class GoogleSheetsConfig:
    """Configuration for Google Sheets sources/destinations."""
    type: Literal['google_sheets']
    spreadsheet_id: str
    sheet_name: str
    credentials_path: Optional[str] = None
    range_name: Optional[str] = None
    
    def __post_init__(self):
        """Validate Google Sheets configuration."""
        if self.credentials_path and not Path(self.credentials_path).exists():
            raise ValueError(f"Credentials file not found: {self.credentials_path}")


# Union type for all source/destination configurations
SourceConfig = Union[DatabaseConfig, CsvConfig, GoogleSheetsConfig]
DestinationConfig = Union[DatabaseConfig, CsvConfig, GoogleSheetsConfig]


@dataclass
class TransformationRule:
    """Configuration for data transformation rules."""
    column: str
    operation: TransformOperation
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate transformation rule."""
        if self.operation == 'parse_date' and 'format' not in self.parameters:
            self.parameters['format'] = '%Y-%m-%d'


@dataclass
class HooksConfig:
    """Configuration for processing hooks."""
    before_job: Optional[str] = None
    after_job: Optional[str] = None
    before_batch: Optional[str] = None
    after_batch: Optional[str] = None
    before_row: Optional[str] = None
    after_row: Optional[str] = None
    
    def __post_init__(self):
        """Validate hook configurations."""
        for hook_name, hook_value in self.__dict__.items():
            if hook_value and isinstance(hook_value, str):
                # Check if it's a file path
                if hook_value.startswith('./') or hook_value.startswith('/'):
                    hook_path = Path(hook_value)
                    if not hook_path.exists():
                        raise ValueError(f"Hook script not found: {hook_value}")


@dataclass
class JobConfig:
    """Complete job configuration schema."""
    source: SourceConfig
    destination: DestinationConfig
    conflict: ConflictStrategy = 'overwrite'
    batch_size: int = 1000
    parallel_jobs: int = 1
    schema_mapping: Optional[Dict[str, str]] = None
    transformations: Optional[List[TransformationRule]] = None
    hooks: Optional[HooksConfig] = None
    
    def __post_init__(self):
        """Validate complete job configuration."""
        if self.batch_size <= 0:
            raise ValueError("batch_size must be positive")
        
        if self.parallel_jobs <= 0:
            raise ValueError("parallel_jobs must be positive")
        
        # Validate that source and destination are different
        if (hasattr(self.source, 'type') and hasattr(self.destination, 'type') and
            self.source.type == self.destination.type):
            # Additional validation for same-type migrations
            if isinstance(self.source, DatabaseConfig) and isinstance(self.destination, DatabaseConfig):
                if (self.source.host == self.destination.host and 
                    self.source.database == self.destination.database and
                    self.source.table == self.destination.table):
                    raise ValueError("Source and destination cannot be identical")


# Job Steps DSL Schema Classes

@dataclass
class BatchConfig:
    """Configuration for step batching."""
    from_: str = field(metadata={'alias': 'from'})  # Jinja expression
    as_: str = field(metadata={'alias': 'as'})      # Alias for batch items
    
    def __post_init__(self):
        """Validate batch configuration."""
        if not self.from_:
            raise ValueError("Batch 'from' expression is required")
        if not self.as_:
            raise ValueError("Batch 'as' alias is required")


@dataclass
class RetryConfig:
    """Configuration for step retry behavior."""
    max_attempts: int = 3
    backoff_ms: int = 1000
    retry_on: Optional[List[str]] = None  # List of error types to retry on
    
    def __post_init__(self):
        """Validate retry configuration."""
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.backoff_ms < 0:
            raise ValueError("backoff_ms cannot be negative")


@dataclass
class ConnectionConfig:
    """Configuration for external connections."""
    name: str
    type: str  # 'postgres', 'mysql', 'lambda', 'http'
    config: Dict[str, Any]
    
    def __post_init__(self):
        """Validate connection configuration."""
        if not self.name:
            raise ValueError("Connection name is required")
        if not self.type:
            raise ValueError("Connection type is required")


@dataclass
class Step:
    """Base step configuration for Job."""
    id: str
    type: StepType
    connection: Optional[str] = None
    save_as: Optional[str] = None
    when: Optional[str] = None  # Jinja condition
    batch: Optional[BatchConfig] = None
    retry: Optional[RetryConfig] = None
    config: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate step configuration."""
        if not self.id:
            raise ValueError("Step id is required")
        if not self.type:
            raise ValueError("Step type is required")
        
        # Validate step type specific requirements
        if self.type in ['db.upsert', 'db.insert', 'db.update', 'db.query_one']:
            if not self.connection:
                raise ValueError(f"Step type '{self.type}' requires a connection")


@dataclass
class TransactionConfig:
    """Configuration for transaction management."""
    scope: TransactionScope = 'db'
    
    def __post_init__(self):
        """Validate transaction configuration."""
        if self.scope not in ['db', 'none']:
            raise ValueError(f"Invalid transaction scope: {self.scope}")


@dataclass
class Job:
    """Job configuration with Steps DSL."""
    steps: List[Step]
    connections: Optional[Dict[str, ConnectionConfig]] = None
    transaction: Optional[TransactionConfig] = None
    
    def __post_init__(self):
        """Validate Job configuration."""
        if not self.steps:
            raise ValueError("At least one step is required")
        
        # Validate step IDs are unique
        step_ids = [step.id for step in self.steps]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("Step IDs must be unique")
        
        # Validate connection references
        if self.connections:
            connection_names = set(self.connections.keys())
            for step in self.steps:
                if step.connection and step.connection not in connection_names:
                    raise ValueError(f"Step '{step.id}' references unknown connection '{step.connection}'")


class SchemaValidator:
    """Validates YAML configurations against the schema."""
    
    @staticmethod
    def parse_source_config(config_dict: Dict[str, Any]) -> SourceConfig:
        """Parse and validate source configuration."""
        config_type = config_dict.get('type')
        
        if config_type == 'csv':
            return CsvConfig(**config_dict)
        elif config_type in ['postgres', 'mysql']:
            return DatabaseConfig(**config_dict)
        elif config_type == 'google_sheets':
            return GoogleSheetsConfig(**config_dict)
        else:
            raise ValueError(f"Unsupported source type: {config_type}")
    
    @staticmethod
    def parse_destination_config(config_dict: Dict[str, Any]) -> DestinationConfig:
        """Parse and validate destination configuration."""
        config_type = config_dict.get('type')
        
        if config_type == 'csv':
            return CsvConfig(**config_dict)
        elif config_type in ['postgres', 'mysql']:
            return DatabaseConfig(**config_dict)
        elif config_type == 'google_sheets':
            return GoogleSheetsConfig(**config_dict)
        else:
            raise ValueError(f"Unsupported destination type: {config_type}")
    
    @staticmethod
    def parse_transformations(transformations_list: List[Dict[str, Any]]) -> List[TransformationRule]:
        """Parse and validate transformation rules."""
        return [TransformationRule(**rule) for rule in transformations_list]
    
    @staticmethod
    def parse_hooks(hooks_dict: Dict[str, Any]) -> HooksConfig:
        """Parse and validate hooks configuration."""
        return HooksConfig(**hooks_dict)
    
    @classmethod
    def validate_yaml_config(cls, config_dict: Dict[str, Any]) -> JobConfig:
        """
        Validate complete YAML configuration and return structured JobConfig.
        
        Args:
            config_dict: Raw configuration dictionary from YAML
            
        Returns:
            JobConfig: Validated and structured configuration
            
        Raises:
            ValueError: If configuration is invalid
        """
        try:
            # Parse required sections
            source = cls.parse_source_config(config_dict['source'])
            destination = cls.parse_destination_config(config_dict['destination'])
            
            # Parse optional sections
            conflict = config_dict.get('conflict', 'overwrite')
            batch_size = config_dict.get('batch_size', 1000)
            parallel_jobs = config_dict.get('parallel_jobs', 1)
            schema_mapping = config_dict.get('schema_mapping')
            
            transformations = None
            if config_dict.get('transformations'):
                transformations = cls.parse_transformations(config_dict['transformations'])
            
            hooks = None
            if config_dict.get('hooks'):
                hooks = cls.parse_hooks(config_dict['hooks'])
            
            # Create and validate complete configuration
            job_config = JobConfig(
                source=source,
                destination=destination,
                conflict=conflict,
                batch_size=batch_size,
                parallel_jobs=parallel_jobs,
                schema_mapping=schema_mapping,
                transformations=transformations,
                hooks=hooks
            )
            
            return job_config
            
        except KeyError as e:
            raise ValueError(f"Missing required configuration section: {e}")
        except TypeError as e:
            raise ValueError(f"Invalid configuration format: {e}")
    
    @staticmethod
    def validate_yaml_file(file_path: Path) -> JobConfig:
        """
        Load and validate a YAML configuration file.
        
        Args:
            file_path: Path to YAML configuration file
            
        Returns:
            JobConfig: Validated configuration
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If configuration is invalid
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config_dict = yaml.safe_load(f)
            
            if not config_dict:
                raise ValueError("Configuration file is empty")
            
            return SchemaValidator.validate_yaml_config(config_dict)
            
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML syntax: {e}")
    
    @classmethod
    def validate_Job_config(cls, config_dict: Dict[str, Any]) -> Job:
        """
        Validate Job YAML configuration and return structured Job.
        
        Args:
            config_dict: Raw configuration dictionary from YAML
            
        Returns:
            Job: Validated and structured configuration
            
        Raises:
            ValueError: If configuration is invalid
        """
        try:
            # Parse steps
            steps_data = config_dict.get('steps', [])
            if not steps_data:
                raise ValueError("Job requires at least one step")
            
            steps = []
            for step_data in steps_data:
                step = cls._parse_step(step_data)
                steps.append(step)
            
            # Parse connections
            connections = None
            if config_dict.get('connections'):
                connections = {}
                for conn_name, conn_data in config_dict['connections'].items():
                    connections[conn_name] = ConnectionConfig(
                        name=conn_name,
                        type=conn_data.get('type'),
                        config=conn_data.get('config', {})
                    )
            
            # Parse transaction config
            transaction = None
            if config_dict.get('transaction'):
                transaction = TransactionConfig(
                    scope=config_dict['transaction'].get('scope', 'db')
                )
            
            # Create and validate complete Job configuration
            job_v2 = Job(
                steps=steps,
                connections=connections,
                transaction=transaction
            )
            
            return job_v2
            
        except KeyError as e:
            raise ValueError(f"Missing required Job configuration section: {e}")
        except TypeError as e:
            raise ValueError(f"Invalid Job configuration format: {e}")
    
    @classmethod
    def _parse_step(cls, step_data: Dict[str, Any]) -> Step:
        """Parse a single step configuration."""
        # Parse batch config if present
        batch = None
        if step_data.get('batch'):
            batch_data = step_data['batch']
            batch = BatchConfig(
                from_=batch_data.get('from'),
                as_=batch_data.get('as')
            )
        
        # Parse retry config if present
        retry = None
        if step_data.get('retry'):
            retry_data = step_data['retry']
            retry = RetryConfig(
                max_attempts=retry_data.get('max_attempts', 3),
                backoff_ms=retry_data.get('backoff_ms', 1000),
                retry_on=retry_data.get('retry_on')
            )
        
        # Extract step-specific config (everything except base fields)
        base_fields = {'id', 'type', 'connection', 'save_as', 'when', 'batch', 'retry'}
        config = {k: v for k, v in step_data.items() if k not in base_fields}
        
        return Step(
            id=step_data.get('id'),
            type=step_data.get('type'),
            connection=step_data.get('connection'),
            save_as=step_data.get('save_as'),
            when=step_data.get('when'),
            batch=batch,
            retry=retry,
            config=config
        )
    
    @classmethod
    def detect_job_format(cls, config_dict: Dict[str, Any]) -> str:
        """
        Detect whether a YAML config is legacy JobConfig or new Job format.
        
        Args:
            config_dict: Raw configuration dictionary from YAML
            
        Returns:
            str: 'legacy' or 'Job'
        """
        # Job format has 'steps' as a key indicator
        if 'steps' in config_dict:
            return 'Job'
        
        # Legacy format has 'source' and 'destination'
        if 'source' in config_dict and 'destination' in config_dict:
            return 'legacy'
        
        # Default to legacy for backward compatibility
        return 'legacy'
    
    @classmethod
    def validate_any_config(cls, config_dict: Dict[str, Any]) -> Union[JobConfig, Job]:
        """
        Auto-detect and validate either legacy JobConfig or Job format.
        
        Args:
            config_dict: Raw configuration dictionary from YAML
            
        Returns:
            Union[JobConfig, Job]: Validated configuration
        """
        format_type = cls.detect_job_format(config_dict)
        
        if format_type == 'Job':
            return cls.validate_Job_config(config_dict)
        else:
            return cls.validate_yaml_config(config_dict)


def generate_schema_template() -> str:
    """Generate a comprehensive YAML template with all options (legacy format)."""
    template = """# Portl Migration Job Configuration
# Complete template with all available options

source:
  type: postgres  # Options: postgres, mysql, csv, google_sheets
  
  # Database configuration (postgres/mysql)
  host: localhost
  port: 5432  # 5432 for postgres, 3306 for mysql
  database: source_db
  username: user
  password: password  # Use environment variables in production
  schema: public  # Optional, defaults to 'public' for postgres
  table: source_table  # Either table OR query, not both
  # query: "SELECT * FROM users WHERE active = true"  # Custom query
  
  # CSV configuration
  # path: ./data/source.csv
  # delimiter: ","
  # encoding: utf-8
  # has_header: true
  
  # Google Sheets configuration
  # spreadsheet_id: "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
  # sheet_name: "Sheet1"
  # credentials_path: ./credentials.json
  # range_name: "A1:Z1000"  # Optional

destination:
  type: postgres  # Options: postgres, mysql, csv, google_sheets
  host: localhost
  port: 5432
  database: dest_db
  username: user
  password: password
  schema: public
  table: dest_table

# Conflict resolution strategy
conflict: overwrite  # Options: overwrite, skip, fail, merge

# Processing configuration
batch_size: 1000  # Number of rows per batch
parallel_jobs: 1  # Number of parallel processing jobs

# Optional: Column mapping (source -> destination)
schema_mapping:
  user_id: id
  full_name: name
  email_address: email

# Optional: Data transformations
transformations:
  - column: email
    operation: lowercase
  - column: created_at
    operation: parse_date
    parameters:
      format: "%Y-%m-%d %H:%M:%S"
  - column: price
    operation: parse_number

# Optional: Processing hooks
hooks:
  before_job: ./scripts/backup.sh
  after_job: ./scripts/notify.sh
  before_batch: ./scripts/log_batch.py
  after_batch: ./scripts/validate_batch.py
  # before_row: "lambda row: print(f'Processing {row}')"
  # after_row: "lambda row, result: print(f'Processed {row}')"
"""
    return template


def generate_Job_template() -> str:
    """Generate a comprehensive Job template with Steps DSL."""
    template = """# Portl Job Configuration - Steps DSL
# Multi-step workflow with transactions, context passing, and retries

# Connection definitions (shared across steps)
connections:
  pg_main:
    type: postgres
    config:
      host: ${env:PG_HOST:-localhost}
      port: 5432
      database: ${env:PG_DATABASE:-mydb}
      username: ${env:PG_USER:-user}
      password: ${env:PG_PASSWORD:-password}
      schema: public
  
  lambda_processor:
    type: lambda
    config:
      region: us-east-1
      function_name: data-processor
      timeout: 30
  
  api_notify:
    type: http
    config:
      base_url: https://api.example.com
      headers:
        Authorization: "Bearer ${env:API_TOKEN}"
        Content-Type: application/json

# Transaction management (DB scope only)
transaction:
  scope: db  # Options: db, none

# Processing steps (executed in order)
steps:
  # Step 1: Read CSV data
  - id: read_csv
    type: csv.read
    save_as: csv_data
    path: ./data/input.csv
    delimiter: ","
    has_header: true
  
  # Step 2: Process data with Lambda (with batching)
  - id: process_data
    type: lambda.invoke
    connection: lambda_processor
    save_as: processed_data
    batch:
      from: "{{ csv_data.rows }}"
      as: row
    payload:
      code: "{{ row.code }}"
      source: "{{ row.source }}"
      data: "{{ row | tojson }}"
    retry:
      max_attempts: 3
      backoff_ms: 1000
      retry_on: ["TimeoutError", "ConnectionError"]
  
  # Step 3: Upsert resources to database
  - id: upsert_resources
    type: db.upsert
    connection: pg_main
    save_as: resource_results
    table: resources
    key: ["code", "source"]
    batch:
      from: "{{ processed_data }}"
      as: item
    mapping:
      code: "{{ item.code }}"
      source: "{{ item.source }}"
      name: "{{ item.processed_name }}"
      metadata: "{{ item.metadata | tojson }}"
      updated_at: "{{ now() }}"
    retry:
      max_attempts: 2
      backoff_ms: 500
  
  # Step 4: Conditional version handling
  - id: handle_versions
    type: conditional
    when: "{{ resource_results | length > 0 }}"
    then:
      # Step 4a: Query existing versions
      - id: check_versions
        type: db.query_one
        connection: pg_main
        save_as: version_check
        batch:
          from: "{{ resource_results }}"
          as: resource
        query: |
          SELECT id, status, version_number 
          FROM resource_versions 
          WHERE resource_id = {{ resource.id }}
          ORDER BY version_number DESC 
          LIMIT 1
      
      # Step 4b: Insert or update version
      - id: upsert_version
        type: db.upsert
        connection: pg_main
        save_as: version_results
        table: resource_versions
        key: ["resource_id"]
        batch:
          from: "{{ resource_results }}"
          as: resource
        when: "{{ not version_check or version_check.status == 'published' }}"
        mapping:
          resource_id: "{{ resource.id }}"
          version_number: "{{ (version_check.version_number or 0) + 1 }}"
          content_hash: "{{ resource.metadata | md5 }}"
          status: "draft"
          created_at: "{{ now() }}"
    else:
      - id: log_no_resources
        type: api.call
        connection: api_notify
        method: POST
        path: /logs
        body:
          level: "info"
          message: "No resources to process"
          timestamp: "{{ now() }}"
  
  # Step 5: Notify external API
  - id: notify_completion
    type: api.call
    connection: api_notify
    method: POST
    path: /webhooks/completion
    batch:
      from: "{{ resource_results }}"
      as: resource
    body:
      resource_id: "{{ resource.id }}"
      version_number: "{{ version_results[idx].version_number }}"
      status: "processed"
      timestamp: "{{ now() }}"
    headers:
      X-Idempotency-Key: "{{ resource.id }}-{{ resource.updated_at | md5 }}"
    retry:
      max_attempts: 5
      backoff_ms: 2000
      retry_on: ["HTTPError", "ConnectionError"]
"""
    return template
