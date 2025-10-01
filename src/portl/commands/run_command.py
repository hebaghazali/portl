import typer
from pathlib import Path
from typing import Optional

from ..services.template_service import TemplateService
from ..services.job_runner import JobRunner, JobRunnerConfig
from ..ui.console import ConsoleUI


class RunCommandHandler:
    def __init__(self):
        self.template_service = TemplateService()
        self.job_runner = JobRunner()
        self.ui = ConsoleUI()
    
    def handle(
        self,
        job_file: Optional[Path] = None,
        dry_run: bool = False,
        batch_size: Optional[int] = None,
        verbose: bool = False
    ):
        if job_file is None:
            job_file = self._handle_missing_job_file()
            if job_file is None:
                return
            dry_run = True  # Force dry-run for templates
        
        config = JobRunnerConfig(
            job_file=job_file,
            dry_run=dry_run,
            batch_size=batch_size,
            verbose=verbose
        )
        
        try:
            validation = self.job_runner.validate_job_file(job_file)
            
            for warning in validation.get("warnings", []):
                self.ui.print_warning(warning)
            
        except FileNotFoundError as e:
            self.ui.print_error(str(e))
            raise typer.Exit(1)
        
        self.ui.print_job_execution_banner(config)
        self.ui.print_job_options(config)
        
        try:
            result = self.job_runner.execute_job(config)
            
            if result['success']:
                self._print_execution_results(result, dry_run)
            else:
                self.ui.print_error("Job execution failed:")
                for error in result.get('errors', []):
                    self.ui.print_error(f"  - {error}")
                raise typer.Exit(1)
                
        except Exception as e:
            self.ui.print_error(f"Job execution failed: {e}")
            raise typer.Exit(1)
    
    def _handle_missing_job_file(self) -> Optional[Path]:
        self.ui.print_no_job_file_prompt()
        
        create_template = typer.confirm(
            "Create a template configuration file?", 
            default=True
        )
        
        if not create_template:
            self.ui.print_warning("Operation cancelled. Please provide a job file path.")
            self.ui.print_info("\\nUsage: [cyan]portl run <job_file.yaml>[/cyan]")
            raise typer.Exit(0)
        
        template_path = Path(self.template_service.get_default_template_name())
        
        if template_path.exists():
            overwrite = typer.confirm(
                f"Template file '{template_path}' already exists. Overwrite?",
                default=False
            )
            if not overwrite:
                self.ui.print_warning("Template creation cancelled.")
                raise typer.Exit(0)
        
        try:
            self.template_service.create_template_file(
                template_path, 
                overwrite=True
            )
            self.ui.print_template_created(template_path)
        except Exception as e:
            self.ui.print_error(f"Failed to create template: {e}")
            self.ui.print_warning("Please ensure the package is properly installed.")
            raise typer.Exit(1)
        
        use_now = typer.confirm(
            "Would you like to run with this template now (dry-run mode)?",
            default=True
        )
        
        if use_now:
            self.ui.print_warning(f"Running in dry-run mode with template: {template_path}")
            return template_path
        else:
            self.ui.print_template_usage_instructions(template_path)
            raise typer.Exit(0)
    
    def _print_execution_results(self, result: dict, dry_run: bool):
        """Print job execution results."""
        if dry_run:
            self.ui.print_success("✅ Dry run completed successfully!")
            
            # Print schema validation results
            if result.get('schema_validation'):
                self.ui.print_warning("Schema compatibility warnings:")
                for warning in result['schema_validation']:
                    self.ui.print_warning(f"  - {warning}")
            else:
                self.ui.print_success("✅ Schema compatibility check passed")
            
            # Print preview data if available
            if result.get('preview_data'):
                self.ui.print_info("Preview of source data:")
                for i, row in enumerate(result['preview_data'][:3], 1):
                    self.ui.print_info(f"  Row {i}: {dict(list(row.items())[:3])}...")
            
            self.ui.print_info(f"Total rows that would be processed: {result.get('rows_processed', 0)}")
            
        else:
            self.ui.print_success("✅ Migration completed successfully!")
            self.ui.print_info(f"Rows processed: {result.get('rows_processed', 0)}")
            self.ui.print_info(f"Rows written: {result.get('rows_written', 0)}")
            self.ui.print_info(f"Batches processed: {result.get('batches_processed', 0)}")
            self.ui.print_info(f"Duration: {result.get('duration_seconds', 0):.2f} seconds")
        
        # Print warnings if any
        if result.get('warnings'):
            self.ui.print_warning("Warnings:")
            for warning in result['warnings']:
                self.ui.print_warning(f"  - {warning}")
