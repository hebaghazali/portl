from pathlib import Path
from typing import Optional, Dict, Any, List
import yaml
from .config_service import ConfigService


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
        
        # Validate YAML syntax and structure
        try:
            # Use ConfigService to load and resolve environment variables
            config = self.config_service._load_config_file(job_file)
            
            if config is None:
                validation_result["errors"].append("YAML file is empty")
                validation_result["valid"] = False
                return validation_result
            
            # Validate required sections
            validation_result.update(self._validate_yaml_structure(config))
            
        except yaml.YAMLError as e:
            validation_result["errors"].append(f"YAML syntax error: {e}")
            validation_result["valid"] = False
        except Exception as e:
            validation_result["errors"].append(f"Error reading file: {e}")
            validation_result["valid"] = False
        
        return validation_result
    
    def execute_job(self, config: JobRunnerConfig) -> bool:
        # Validate job file first
        validation = self.validate_job_file(config.job_file)
        
        if not validation["valid"]:
            raise ValueError(f"Job validation failed: {validation['errors']}")
        
        # TODO: Implement actual job execution logic
        # This is where the migration engine will be implemented
        
        return True
    
    def get_job_summary(self, config: JobRunnerConfig) -> Dict[str, Any]:
        return {
            "job_file": str(config.job_file),
            "dry_run": config.dry_run,
            "batch_size": config.batch_size,
            "verbose": config.verbose,
            "mode": "Dry Run" if config.dry_run else "Live Execution"
        }
    
    def _validate_yaml_structure(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the YAML configuration structure."""
        validation_result = {
            "valid": True,
            "warnings": [],
            "errors": []
        }
        
        # Check required top-level sections
        required_sections = ['source', 'destination']
        for section in required_sections:
            if section not in config:
                validation_result["errors"].append(f"Missing required section: {section}")
                validation_result["valid"] = False
        
        # Validate source configuration
        if 'source' in config:
            source_errors = self._validate_source_config(config['source'])
            validation_result["errors"].extend(source_errors)
            if source_errors:
                validation_result["valid"] = False
        
        # Validate destination configuration
        if 'destination' in config:
            dest_errors = self._validate_destination_config(config['destination'])
            validation_result["errors"].extend(dest_errors)
            if dest_errors:
                validation_result["valid"] = False
        
        # Validate optional sections
        if 'conflict' in config:
            valid_conflicts = ['overwrite', 'skip', 'fail', 'merge']
            if config['conflict'] not in valid_conflicts:
                validation_result["errors"].append(
                    f"Invalid conflict strategy: {config['conflict']}. "
                    f"Must be one of: {', '.join(valid_conflicts)}"
                )
                validation_result["valid"] = False
        
        if 'batch_size' in config:
            if not isinstance(config['batch_size'], int) or config['batch_size'] <= 0:
                validation_result["errors"].append("batch_size must be a positive integer")
                validation_result["valid"] = False
        
        # Warnings for missing recommended fields
        if 'conflict' not in config:
            validation_result["warnings"].append("No conflict resolution strategy specified")
        
        if 'batch_size' not in config:
            validation_result["warnings"].append("No batch size specified, will use default")
        
        return validation_result
    
    def _validate_source_config(self, source: Dict[str, Any]) -> List[str]:
        """Validate source configuration."""
        errors = []
        
        if 'type' not in source:
            errors.append("Source type is required")
            return errors
        
        source_type = source['type']
        valid_types = ['csv', 'postgres', 'mysql', 'google_sheets']
        
        if source_type not in valid_types:
            errors.append(f"Invalid source type: {source_type}. Must be one of: {', '.join(valid_types)}")
            return errors
        
        if source_type == 'csv':
            if 'path' not in source:
                errors.append("CSV source requires 'path' field")
        
        elif source_type in ['postgres', 'mysql']:
            required_fields = ['host', 'database', 'username']
            for field in required_fields:
                if field not in source:
                    errors.append(f"Database source requires '{field}' field")
            
            if 'table' not in source and 'query' not in source:
                errors.append("Database source requires either 'table' or 'query' field")
        
        elif source_type == 'google_sheets':
            required_fields = ['spreadsheet_id', 'sheet_name']
            for field in required_fields:
                if field not in source:
                    errors.append(f"Google Sheets source requires '{field}' field")
        
        return errors
    
    def _validate_destination_config(self, destination: Dict[str, Any]) -> List[str]:
        """Validate destination configuration."""
        errors = []
        
        if 'type' not in destination:
            errors.append("Destination type is required")
            return errors
        
        dest_type = destination['type']
        valid_types = ['csv', 'postgres', 'mysql', 'google_sheets']
        
        if dest_type not in valid_types:
            errors.append(f"Invalid destination type: {dest_type}. Must be one of: {', '.join(valid_types)}")
            return errors
        
        if dest_type == 'csv':
            if 'path' not in destination:
                errors.append("CSV destination requires 'path' field")
        
        elif dest_type in ['postgres', 'mysql']:
            required_fields = ['host', 'database', 'username', 'table']
            for field in required_fields:
                if field not in destination:
                    errors.append(f"Database destination requires '{field}' field")
        
        elif dest_type == 'google_sheets':
            required_fields = ['spreadsheet_id', 'sheet_name']
            for field in required_fields:
                if field not in destination:
                    errors.append(f"Google Sheets destination requires '{field}' field")
        
        return errors
