"""
YAML job configuration schema definitions.

This module defines the complete schema for Portl migration job configurations
using dataclasses for type safety and validation.
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


def generate_schema_template() -> str:
    """Generate a comprehensive YAML template with all options."""
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
