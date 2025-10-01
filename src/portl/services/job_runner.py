from pathlib import Path
from typing import Optional, Dict, Any, List
import yaml
import logging
from datetime import datetime

from .config_service import ConfigService
from ..schema import JobConfig, SchemaValidator
from ..connectors.factory import ConnectorFactory, test_connector_connection
from ..connectors.base import BaseSourceConnector, BaseDestinationConnector


class JobRunnerConfig:
    def __init__(
        self,
        job_file: Path,
        dry_run: bool = False,
        batch_size: Optional[int] = None,
        verbose: bool = False
    ):
        self.job_file = job_file
        self.dry_run = dry_run
        self.batch_size = batch_size
        self.verbose = verbose


class JobRunner:
    def __init__(self):
        self.config_service = ConfigService()
        self.logger = logging.getLogger(__name__)
        self._source_connector = None
        self._destination_connector = None
    
    def validate_job_file(self, job_file: Path) -> Dict[str, Any]:
        if not job_file.exists():
            raise FileNotFoundError(f"Job file not found: {job_file}")
        
        validation_result = {
            "valid": True,
            "warnings": [],
            "errors": []
        }
        
        # Check file extension
        if job_file.suffix.lower() not in ['.yaml', '.yml']:
            validation_result["warnings"].append(
                f"File '{job_file}' doesn't have a .yaml or .yml extension"
            )
        
        # Validate YAML syntax and structure using schema validator
        try:
            # Use the schema validator for comprehensive validation
            job_config = SchemaValidator.validate_yaml_file(job_file)
            
            # If we get here, validation passed
            validation_result["valid"] = True
            
            # Add informational warnings
            if not hasattr(job_config, 'conflict') or job_config.conflict == 'overwrite':
                validation_result["warnings"].append("Using 'overwrite' conflict strategy")
            
        except FileNotFoundError as e:
            validation_result["errors"].append(str(e))
            validation_result["valid"] = False
        except ValueError as e:
            validation_result["errors"].append(str(e))
            validation_result["valid"] = False
        except Exception as e:
            validation_result["errors"].append(f"Validation error: {e}")
            validation_result["valid"] = False
        
        return validation_result
    
    def execute_job(self, config: JobRunnerConfig) -> Dict[str, Any]:
        """
        Execute a migration job.
        
        Args:
            config: Job runner configuration
            
        Returns:
            Dictionary with execution results and statistics
        """
        start_time = datetime.now()
        execution_result = {
            'success': False,
            'start_time': start_time.isoformat(),
            'end_time': None,
            'duration_seconds': 0,
            'rows_processed': 0,
            'rows_written': 0,
            'batches_processed': 0,
            'errors': [],
            'warnings': []
        }
        
        try:
            # Validate job file first
            validation = self.validate_job_file(config.job_file)
            
            if not validation["valid"]:
                execution_result['errors'] = validation['errors']
                return execution_result
            
            # Add validation warnings to result
            execution_result['warnings'].extend(validation.get('warnings', []))
            
            # Load job configuration
            job_config = self.load_job_config(config.job_file)
            
            # Override batch size if specified in runner config
            if config.batch_size:
                job_config.batch_size = config.batch_size
            
            self.logger.info(f"Starting job execution: {config.job_file}")
            self.logger.info(f"Mode: {'Dry Run' if config.dry_run else 'Live Execution'}")
            
            # Execute the migration
            if config.dry_run:
                result = self._execute_dry_run(job_config)
            else:
                result = self._execute_migration(job_config)
            
            # Update execution result
            execution_result.update(result)
            execution_result['success'] = True
            
        except Exception as e:
            self.logger.error(f"Job execution failed: {e}")
            execution_result['errors'].append(str(e))
            execution_result['success'] = False
        
        finally:
            end_time = datetime.now()
            execution_result['end_time'] = end_time.isoformat()
            execution_result['duration_seconds'] = (end_time - start_time).total_seconds()
            
            # Clean up connections
            self._cleanup_connections()
        
        return execution_result
    
    def get_job_summary(self, config: JobRunnerConfig) -> Dict[str, Any]:
        return {
            "job_file": str(config.job_file),
            "dry_run": config.dry_run,
            "batch_size": config.batch_size,
            "verbose": config.verbose,
            "mode": "Dry Run" if config.dry_run else "Live Execution"
        }
    
    def load_job_config(self, job_file: Path) -> JobConfig:
        """
        Load and validate a job configuration from a YAML file.
        
        Args:
            job_file: Path to the YAML job configuration file
            
        Returns:
            JobConfig: Validated job configuration
            
        Raises:
            FileNotFoundError: If the job file doesn't exist
            ValueError: If the configuration is invalid
        """
        return SchemaValidator.validate_yaml_file(job_file)
    
    def _execute_dry_run(self, job_config: JobConfig) -> Dict[str, Any]:
        """
        Execute a dry run to validate the migration without writing data.
        
        Args:
            job_config: Validated job configuration
            
        Returns:
            Dictionary with dry run results
        """
        result = {
            'rows_processed': 0,
            'rows_written': 0,
            'batches_processed': 0,
            'schema_validation': [],
            'preview_data': []
        }
        
        try:
            # Create connectors
            source_connector = ConnectorFactory.create_source_connector(job_config.source)
            destination_connector = ConnectorFactory.create_destination_connector(job_config.destination)
            
            # Test connections
            self.logger.info("Testing source connection...")
            with source_connector.connection_context():
                if not source_connector.test_connection():
                    raise ConnectionError("Source connection test failed")
                
                # Get source schema and row count
                source_schema = source_connector.get_schema()
                total_rows = source_connector.get_row_count()
                
                self.logger.info(f"Source schema: {len(source_schema)} columns")
                self.logger.info(f"Total rows in source: {total_rows}")
                
                # Get preview data
                preview_data = source_connector.preview_data(limit=5)
                result['preview_data'] = preview_data
                result['rows_processed'] = total_rows
            
            self.logger.info("Testing destination connection...")
            with destination_connector.connection_context():
                if not destination_connector.test_connection():
                    raise ConnectionError("Destination connection test failed")
                
                # Validate schema compatibility
                schema_warnings = destination_connector.validate_schema_compatibility(source_schema)
                result['schema_validation'] = schema_warnings
                
                if schema_warnings:
                    self.logger.warning("Schema compatibility issues found:")
                    for warning in schema_warnings:
                        self.logger.warning(f"  - {warning}")
                else:
                    self.logger.info("Schema compatibility check passed")
            
            self.logger.info("Dry run completed successfully")
            
        except Exception as e:
            self.logger.error(f"Dry run failed: {e}")
            raise
        
        return result
    
    def _execute_migration(self, job_config: JobConfig) -> Dict[str, Any]:
        """
        Execute the actual data migration.
        
        Args:
            job_config: Validated job configuration
            
        Returns:
            Dictionary with migration results
        """
        result = {
            'rows_processed': 0,
            'rows_written': 0,
            'batches_processed': 0
        }
        
        try:
            # Create connectors
            source_connector = ConnectorFactory.create_source_connector(job_config.source)
            destination_connector = ConnectorFactory.create_destination_connector(job_config.destination)
            
            self._source_connector = source_connector
            self._destination_connector = destination_connector
            
            # Execute migration with both connectors
            with source_connector.connection_context():
                with destination_connector.connection_context():
                    # Validate connections
                    if not source_connector.test_connection():
                        raise ConnectionError("Source connection failed")
                    if not destination_connector.test_connection():
                        raise ConnectionError("Destination connection failed")
                    
                    # Get source schema for table creation
                    source_schema = source_connector.get_schema()
                    total_rows = source_connector.get_row_count()
                    
                    self.logger.info(f"Starting migration of {total_rows} rows")
                    
                    # Create destination table if needed
                    try:
                        destination_connector.create_table_if_not_exists(source_schema)
                    except Exception as e:
                        self.logger.warning(f"Could not create destination table: {e}")
                    
                    # Process data in batches
                    batch_count = 0
                    total_written = 0
                    
                    # Use transaction context for the entire migration
                    with destination_connector.transaction_context():
                        for batch in source_connector.read_data(batch_size=job_config.batch_size):
                            batch_count += 1
                            rows_in_batch = len(batch)
                            
                            self.logger.info(f"Processing batch {batch_count} ({rows_in_batch} rows)")
                            
                            # Apply schema mapping if configured
                            if job_config.schema_mapping:
                                batch = self._apply_schema_mapping(batch, job_config.schema_mapping)
                            
                            # Write batch to destination
                            written = destination_connector.write_batch(
                                batch, 
                                conflict_strategy=job_config.conflict
                            )
                            
                            total_written += written
                            result['rows_processed'] += rows_in_batch
                            result['rows_written'] += written
                            result['batches_processed'] = batch_count
                            
                            self.logger.info(f"Batch {batch_count} completed: {written}/{rows_in_batch} rows written")
                    
                    self.logger.info(f"Migration completed: {total_written}/{result['rows_processed']} rows written")
            
        except Exception as e:
            self.logger.error(f"Migration failed: {e}")
            raise
        
        return result
    
    def _apply_schema_mapping(self, batch: List[Dict[str, Any]], mapping: Dict[str, str]) -> List[Dict[str, Any]]:
        """
        Apply column name mapping to a batch of data.
        
        Args:
            batch: List of row dictionaries
            mapping: Dictionary mapping source column names to destination column names
            
        Returns:
            Batch with renamed columns
        """
        mapped_batch = []
        
        for row in batch:
            mapped_row = {}
            for source_col, value in row.items():
                # Use mapped name if available, otherwise keep original
                dest_col = mapping.get(source_col, source_col)
                mapped_row[dest_col] = value
            mapped_batch.append(mapped_row)
        
        return mapped_batch
    
    def _cleanup_connections(self) -> None:
        """Clean up connector connections."""
        try:
            if self._source_connector:
                self._source_connector.disconnect()
                self._source_connector = None
        except Exception as e:
            self.logger.error(f"Error cleaning up source connector: {e}")
        
        try:
            if self._destination_connector:
                self._destination_connector.disconnect()
                self._destination_connector = None
        except Exception as e:
            self.logger.error(f"Error cleaning up destination connector: {e}")
    
    def test_connections(self, job_config: JobConfig) -> Dict[str, Any]:
        """
        Test both source and destination connections.
        
        Args:
            job_config: Job configuration to test
            
        Returns:
            Dictionary with connection test results
        """
        results = {
            'source': {'success': False, 'error': None},
            'destination': {'success': False, 'error': None},
            'overall_success': False
        }
        
        try:
            # Test source connection
            source_result = test_connector_connection(job_config.source)
            results['source'] = source_result
            
            # Test destination connection
            dest_result = test_connector_connection(job_config.destination)
            results['destination'] = dest_result
            
            results['overall_success'] = source_result['success'] and dest_result['success']
            
        except Exception as e:
            self.logger.error(f"Connection testing failed: {e}")
            results['error'] = str(e)
        
        return results
