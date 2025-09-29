from pathlib import Path
from typing import Optional, Dict, Any


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
        
        # TODO: Add YAML structure validation here
        
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
