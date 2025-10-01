"""
Interactive wizard service for collecting migration configuration.

This service provides a guided question-and-answer interface to help users
configure their data migration jobs step by step.
"""

from typing import Dict, Any, List
import typer
from rich.prompt import Confirm
from rich.table import Table
from rich.console import Console

from ..ui.console import ConsoleUI


class WizardService:
    """Interactive wizard for collecting migration configuration."""
    
    def __init__(self):
        self.ui = ConsoleUI()
        self.console = Console()
    
    def run_wizard(self) -> Dict[str, Any]:
        """Run the complete interactive wizard and return configuration."""
        config = {}
        
        # Step 1: Source Configuration
        self.ui.print_info("📊 [bold]Step 1: Source Configuration[/bold]")
        config['source'] = self._configure_source()
        
        # Step 2: Destination Configuration  
        self.ui.print_info("\n🎯 [bold]Step 2: Destination Configuration[/bold]")
        config['destination'] = self._configure_destination()
        
        # Step 3: Processing Options
        self.ui.print_info("\n⚙️  [bold]Step 3: Processing Options[/bold]")
        config.update(self._configure_processing())
        
        # Step 4: Advanced Options (optional)
        if self._ask_advanced_options():
            self.ui.print_info("\n🔧 [bold]Step 4: Advanced Configuration[/bold]")
            config.update(self._configure_advanced())
        
        # Step 5: Validation & Dry Run Options
        self.ui.print_info("\n✅ [bold]Step 5: Validation & Testing Options[/bold]")
        config.update(self._configure_validation_options())
        
        return config
    
    def _configure_source(self) -> Dict[str, Any]:
        """Configure source connection."""
        source_types = ["csv", "postgres", "mysql", "google_sheets"]
        
        self.ui.print_info("What type of data source are you migrating FROM?")
        source_type = self._select_from_list("Source type", source_types)
        
        source_config = {"type": source_type}
        
        if source_type == "csv":
            source_config.update(self._configure_csv_source())
        elif source_type in ["postgres", "mysql"]:
            source_config.update(self._configure_database_source(source_type))
        elif source_type == "google_sheets":
            source_config.update(self._configure_sheets_source())
        
        return source_config
    
    def _configure_destination(self) -> Dict[str, Any]:
        """Configure destination connection."""
        dest_types = ["postgres", "mysql", "csv", "google_sheets"]
        
        self.ui.print_info("What type of data destination are you migrating TO?")
        dest_type = self._select_from_list("Destination type", dest_types)
        
        dest_config = {"type": dest_type}
        
        if dest_type == "csv":
            dest_config.update(self._configure_csv_destination())
        elif dest_type in ["postgres", "mysql"]:
            dest_config.update(self._configure_database_destination(dest_type))
        elif dest_type == "google_sheets":
            dest_config.update(self._configure_sheets_destination())
        
        return dest_config
    
    def _configure_processing(self) -> Dict[str, Any]:
        """Configure processing options."""
        config = {}
        
        # Primary key conflict resolution
        self.ui.print_info("Primary Key Conflict Resolution:")
        conflict_strategies = ["skip", "overwrite", "merge", "fail"]
        
        self.ui.print_info("• skip: Skip conflicting records, keep existing data")
        self.ui.print_info("• overwrite: Replace existing records with new data")
        self.ui.print_info("• merge: Merge new data with existing (update non-null fields)")
        self.ui.print_info("• fail: Stop processing on first conflict")
        
        config['conflict'] = self._select_from_list("Conflict strategy", conflict_strategies)
        
        # If merge strategy selected, ask for merge options
        if config['conflict'] == 'merge':
            config.update(self._configure_merge_options())
        
        # Batch size
        batch_size = typer.prompt(
            "Batch size (rows per batch)",
            default=1000,
            type=int,
            show_default=True
        )
        config['batch_size'] = batch_size
        
        # Parallel execution options
        if Confirm.ask("Enable parallel processing?", default=False):
            parallel_jobs = typer.prompt(
                "Number of parallel workers",
                default=2,
                type=int,
                show_default=True
            )
            config['parallel_jobs'] = parallel_jobs
        else:
            config['parallel_jobs'] = 1
        
        # Retry strategy
        self.ui.print_info("Retry Strategy on Failure:")
        retry_strategies = ["skip", "retry_n_times", "fail_fast"]
        
        self.ui.print_info("• skip: Skip failed records and continue")
        self.ui.print_info("• retry_n_times: Retry failed records N times before skipping")
        self.ui.print_info("• fail_fast: Stop processing on first failure")
        
        retry_strategy = self._select_from_list("Retry strategy", retry_strategies)
        config['retry_strategy'] = retry_strategy
        
        if retry_strategy == "retry_n_times":
            retry_count = typer.prompt(
                "Maximum retry attempts",
                default=3,
                type=int,
                show_default=True
            )
            config['max_retries'] = retry_count
            
            retry_delay = typer.prompt(
                "Delay between retries (seconds)",
                default=1.0,
                type=float,
                show_default=True
            )
            config['retry_delay'] = retry_delay
        
        return config
    
    def _configure_merge_options(self) -> Dict[str, Any]:
        """Configure merge strategy options."""
        config = {}
        
        self.ui.print_info("Merge Strategy Configuration:")
        
        # Merge behavior for null values
        merge_null_strategies = ["keep_existing", "overwrite_with_null", "skip_null"]
        self.ui.print_info("How to handle null values during merge?")
        self.ui.print_info("• keep_existing: Keep existing value if new value is null")
        self.ui.print_info("• overwrite_with_null: Replace existing value with null")
        self.ui.print_info("• skip_null: Skip null fields entirely")
        
        config['merge_null_strategy'] = self._select_from_list(
            "Null value strategy", 
            merge_null_strategies
        )
        
        # Merge timestamp tracking
        if Confirm.ask("Add timestamp tracking for merged records?", default=True):
            config['merge_add_timestamp'] = True
            timestamp_column = typer.prompt(
                "Timestamp column name", 
                default="updated_at"
            )
            config['merge_timestamp_column'] = timestamp_column
        
        return config
    
    def _configure_advanced(self) -> Dict[str, Any]:
        """Configure advanced options."""
        config = {}
        
        # Schema mapping configuration
        config.update(self._configure_schema_options())
        
        # Transformations
        if Confirm.ask("Do you need data transformations?"):
            config['transformations'] = self._configure_transformations()
        
        # Hooks
        if Confirm.ask("Do you need to run scripts before/after processing?"):
            config['hooks'] = self._configure_hooks()
        
        return config
    
    def _configure_csv_source(self) -> Dict[str, Any]:
        """Configure CSV source."""
        path = typer.prompt("CSV file path", default="./data/source.csv")
        return {"path": path}
    
    def _configure_database_source(self, db_type: str) -> Dict[str, Any]:
        """Configure database source with config file support."""
        config = {}
        
        # Check if user wants to load from config file
        if Confirm.ask("Load database connection from config file?", default=False):
            config_path = typer.prompt("Config file path", default=".portl.yaml")
            config['config_file'] = config_path
            
            # Still ask for table/query since it's specific to this migration
            use_query = Confirm.ask("Use custom SQL query instead of table name?")
            if use_query:
                config['query'] = typer.prompt("SQL query")
            else:
                config['table'] = typer.prompt("Table name")
                if db_type == "postgres":
                    config['schema'] = typer.prompt("Schema", default="public")
        else:
            # Manual configuration
            config['host'] = typer.prompt("Database host", default="localhost")
            config['port'] = typer.prompt(f"Port", default=5432 if db_type == "postgres" else 3306, type=int)
            config['database'] = typer.prompt("Database name")
            config['username'] = typer.prompt("Username")
            
            # Handle password securely
            password = typer.prompt("Password", hide_input=True)
            config['password'] = password
            
            # Table or query
            use_query = Confirm.ask("Use custom SQL query instead of table name?")
            if use_query:
                config['query'] = typer.prompt("SQL query")
            else:
                config['table'] = typer.prompt("Table name")
                if db_type == "postgres":
                    config['schema'] = typer.prompt("Schema", default="public")
        
        return config
    
    def _configure_sheets_source(self) -> Dict[str, Any]:
        """Configure Google Sheets source."""
        config = {}
        config['spreadsheet_id'] = typer.prompt("Google Sheets ID (from URL)")
        config['sheet_name'] = typer.prompt("Sheet name", default="Sheet1")
        config['credentials_path'] = typer.prompt(
            "Credentials file path", 
            default="./credentials.json"
        )
        return config
    
    def _configure_csv_destination(self) -> Dict[str, Any]:
        """Configure CSV destination."""
        path = typer.prompt("Output CSV file path", default="./data/output.csv")
        return {"path": path}
    
    def _configure_database_destination(self, db_type: str) -> Dict[str, Any]:
        """Configure database destination with config file support."""
        config = {}
        
        # Check if user wants to load from config file
        if Confirm.ask("Load database connection from config file?", default=False):
            config_path = typer.prompt("Config file path", default=".portl.yaml")
            config['config_file'] = config_path
            
            # Still ask for table since it's specific to this migration
            config['table'] = typer.prompt("Target table name")
            if db_type == "postgres":
                config['schema'] = typer.prompt("Schema", default="public")
        else:
            # Manual configuration
            config['host'] = typer.prompt("Database host", default="localhost")
            config['port'] = typer.prompt(f"Port", default=5432 if db_type == "postgres" else 3306, type=int)
            config['database'] = typer.prompt("Database name")
            config['username'] = typer.prompt("Username")
            
            # Handle password securely
            password = typer.prompt("Password", hide_input=True)
            config['password'] = password
            
            config['table'] = typer.prompt("Target table name")
            if db_type == "postgres":
                config['schema'] = typer.prompt("Schema", default="public")
        
        return config
    
    def _configure_sheets_destination(self) -> Dict[str, Any]:
        """Configure Google Sheets destination."""
        config = {}
        config['spreadsheet_id'] = typer.prompt("Google Sheets ID (from URL)")
        config['sheet_name'] = typer.prompt("Sheet name", default="Sheet1")
        config['credentials_path'] = typer.prompt(
            "Credentials file path", 
            default="./credentials.json"
        )
        return config
    
    def _configure_schema_options(self) -> Dict[str, Any]:
        """Configure comprehensive schema and mapping options."""
        config = {}
        
        # Auto-map vs manual mapping
        self.ui.print_info("Column Mapping Strategy:")
        mapping_strategies = [
            "auto_map_by_name", 
            "manual_mapping", 
            "no_mapping"
        ]
        
        self.ui.print_info("• auto_map_by_name: Automatically match columns with same names")
        self.ui.print_info("• manual_mapping: Define custom column mappings")
        self.ui.print_info("• no_mapping: Use columns as-is (source and destination must match)")
        
        mapping_strategy = self._select_from_list("Mapping strategy", mapping_strategies)
        config['mapping_strategy'] = mapping_strategy
        
        # If manual mapping selected, configure the mappings
        if mapping_strategy == "manual_mapping":
            config['schema_mapping'] = self._configure_schema_mapping()
        
        # Auto-create missing columns option
        if Confirm.ask("Auto-create missing columns in destination?", default=True):
            config['auto_create_columns'] = True
        else:
            config['auto_create_columns'] = False
        
        # Handle extra destination columns
        if config.get('auto_create_columns', False):
            extra_column_strategies = ["ignore", "error", "warn"]
            self.ui.print_info("How to handle extra columns in destination that don't exist in source?")
            config['extra_columns_strategy'] = self._select_from_list(
                "Extra columns strategy", 
                extra_column_strategies
            )
        
        return config
    
    def _configure_schema_mapping(self) -> Dict[str, str]:
        """Configure column mapping."""
        self.ui.print_info("Configure column mapping (source_column: destination_column)")
        self.ui.print_info("Enter mappings one by one. Press Enter with empty input to finish.")
        
        mapping = {}
        while True:
            source_col = typer.prompt("Source column name", default="", show_default=False)
            if not source_col.strip():
                break
            
            dest_col = typer.prompt(f"Maps to destination column", default=source_col)
            mapping[source_col] = dest_col
        
        return mapping
    
    def _configure_transformations(self) -> List[Dict[str, Any]]:
        """Configure data transformations."""
        self.ui.print_info("Configure data transformations")
        self.ui.print_info("Available operations: lowercase, uppercase, parse_date, to_number")
        
        transformations = []
        while True:
            column = typer.prompt("Column to transform", default="", show_default=False)
            if not column.strip():
                break
            
            operations = ["lowercase", "uppercase", "parse_date", "to_number", "custom"]
            operation = self._select_from_list("Transformation", operations)
            
            transform = {"column": column, "operation": operation}
            
            if operation == "parse_date":
                format_str = typer.prompt("Date format", default="%Y-%m-%d")
                transform["format"] = format_str
            elif operation == "custom":
                expression = typer.prompt("Custom expression (Python)")
                transform["expression"] = expression
            
            transformations.append(transform)
        
        return transformations
    
    def _configure_hooks(self) -> Dict[str, Any]:
        """Configure comprehensive processing hooks."""
        hooks = {}
        
        # Job-level hooks
        self.ui.print_info("Job-Level Hooks:")
        job_hook_types = [
            ("before_job", "Before entire job starts"),
            ("after_job", "After entire job completes")
        ]
        
        for hook_key, description in job_hook_types:
            if Confirm.ask(f"Add {description.lower()} hook?"):
                hook_config = self._configure_single_hook(description.lower())
                hooks[hook_key] = hook_config
        
        # Batch-level hooks
        self.ui.print_info("\nBatch-Level Hooks:")
        batch_hook_types = [
            ("before_batch", "Before each batch"),
            ("after_batch", "After each batch")
        ]
        
        for hook_key, description in batch_hook_types:
            if Confirm.ask(f"Add {description.lower()} hook?"):
                hook_config = self._configure_single_hook(description.lower())
                hooks[hook_key] = hook_config
        
        # Row-level hooks
        self.ui.print_info("\nRow-Level Hooks:")
        row_hook_types = [
            ("before_row", "Before each row processing"),
            ("after_row", "After each row processing")
        ]
        
        for hook_key, description in row_hook_types:
            if Confirm.ask(f"Add {description.lower()} hook?"):
                hook_config = self._configure_single_hook(description.lower())
                hooks[hook_key] = hook_config
        
        return hooks
    
    def _configure_single_hook(self, description: str) -> Dict[str, Any]:
        """Configure a single hook with type and parameters."""
        hook_types = ["script", "api_call", "lambda", "notification"]
        
        self.ui.print_info(f"Hook type for {description}:")
        self.ui.print_info("• script: Execute a shell script or Python file")
        self.ui.print_info("• api_call: Make HTTP request to an endpoint")
        self.ui.print_info("• lambda: Execute inline Python code")
        self.ui.print_info("• notification: Send notification (email, slack, etc.)")
        
        hook_type = self._select_from_list("Hook type", hook_types)
        hook_config = {"type": hook_type}
        
        if hook_type == "script":
            script_path = typer.prompt("Script path")
            hook_config["path"] = script_path
            
            # Script arguments
            if Confirm.ask("Pass arguments to script?"):
                args = typer.prompt("Script arguments (space-separated)", default="")
                hook_config["args"] = args.split() if args else []
        
        elif hook_type == "api_call":
            url = typer.prompt("API endpoint URL")
            hook_config["url"] = url
            
            method = self._select_from_list("HTTP method", ["GET", "POST", "PUT", "PATCH"])
            hook_config["method"] = method
            
            if method in ["POST", "PUT", "PATCH"]:
                if Confirm.ask("Include request body?"):
                    body = typer.prompt("Request body (JSON)", default="{}")
                    hook_config["body"] = body
            
            if Confirm.ask("Add custom headers?"):
                headers = {}
                while True:
                    header_name = typer.prompt("Header name", default="", show_default=False)
                    if not header_name.strip():
                        break
                    header_value = typer.prompt(f"Value for {header_name}")
                    headers[header_name] = header_value
                hook_config["headers"] = headers
        
        elif hook_type == "lambda":
            code = typer.prompt("Python code to execute")
            hook_config["code"] = code
        
        elif hook_type == "notification":
            notification_types = ["email", "slack", "webhook", "console"]
            notification_type = self._select_from_list("Notification type", notification_types)
            hook_config["notification_type"] = notification_type
            
            if notification_type == "email":
                recipients = typer.prompt("Email recipients (comma-separated)")
                hook_config["recipients"] = [r.strip() for r in recipients.split(",")]
                hook_config["subject"] = typer.prompt("Email subject", default=f"Hook: {description}")
            
            elif notification_type == "slack":
                webhook_url = typer.prompt("Slack webhook URL")
                hook_config["webhook_url"] = webhook_url
                channel = typer.prompt("Slack channel", default="#general")
                hook_config["channel"] = channel
            
            elif notification_type == "webhook":
                webhook_url = typer.prompt("Webhook URL")
                hook_config["webhook_url"] = webhook_url
        
        return hook_config
    
    def _configure_validation_options(self) -> Dict[str, Any]:
        """Configure validation and dry run options."""
        config = {}
        
        # Dry run preview
        if Confirm.ask("Enable dry run preview (test without writing data)?", default=True):
            config['dry_run_enabled'] = True
            
            preview_rows = typer.prompt(
                "Number of rows to preview in dry run",
                default=10,
                type=int,
                show_default=True
            )
            config['dry_run_preview_rows'] = preview_rows
        else:
            config['dry_run_enabled'] = False
        
        # Schema compatibility validation
        if Confirm.ask("Enable schema compatibility validation?", default=True):
            config['validate_schema'] = True
            
            # Schema validation options
            validation_levels = ["strict", "warn", "ignore"]
            self.ui.print_info("Schema validation level:")
            self.ui.print_info("• strict: Fail if schemas don't match exactly")
            self.ui.print_info("• warn: Show warnings but continue processing")
            self.ui.print_info("• ignore: Skip schema validation entirely")
            
            config['schema_validation_level'] = self._select_from_list(
                "Validation level", 
                validation_levels
            )
        else:
            config['validate_schema'] = False
        
        # Row count comparison
        if Confirm.ask("Enable row count comparison after migration?", default=True):
            config['validate_row_count'] = True
            
            # Row count tolerance
            tolerance = typer.prompt(
                "Row count difference tolerance (%)",
                default=0.0,
                type=float,
                show_default=True
            )
            config['row_count_tolerance'] = tolerance
        else:
            config['validate_row_count'] = False
        
        # Data sampling validation
        if Confirm.ask("Enable data sampling validation?", default=False):
            config['validate_data_sampling'] = True
            
            sample_size = typer.prompt(
                "Sample size for data validation",
                default=100,
                type=int,
                show_default=True
            )
            config['data_sample_size'] = sample_size
            
            # Data validation checks
            validation_checks = []
            if Confirm.ask("Check for null values in required fields?"):
                validation_checks.append("null_check")
            if Confirm.ask("Check data type consistency?"):
                validation_checks.append("type_check")
            if Confirm.ask("Check for duplicate primary keys?"):
                validation_checks.append("duplicate_check")
            if Confirm.ask("Check value ranges/constraints?"):
                validation_checks.append("constraint_check")
            
            config['validation_checks'] = validation_checks
        else:
            config['validate_data_sampling'] = False
        
        # Performance monitoring
        if Confirm.ask("Enable performance monitoring?", default=True):
            config['monitor_performance'] = True
            
            # Performance thresholds
            if Confirm.ask("Set performance alert thresholds?"):
                max_duration = typer.prompt(
                    "Maximum job duration (minutes) before alert",
                    default=60,
                    type=int,
                    show_default=True
                )
                config['max_job_duration'] = max_duration
                
                min_throughput = typer.prompt(
                    "Minimum throughput (rows/second) before alert",
                    default=10.0,
                    type=float,
                    show_default=True
                )
                config['min_throughput'] = min_throughput
        else:
            config['monitor_performance'] = False
        
        return config
    
    def _select_from_list(self, prompt: str, options: List[str]) -> str:
        """Present a numbered list for selection."""
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Number", style="cyan")
        table.add_column("Option", style="white")
        
        for i, option in enumerate(options, 1):
            table.add_row(str(i), option)
        
        self.console.print(table)
        
        while True:
            try:
                choice = typer.prompt(f"{prompt} (1-{len(options)})", type=int)
                if 1 <= choice <= len(options):
                    return options[choice - 1]
                else:
                    self.ui.print_warning(f"Please enter a number between 1 and {len(options)}")
            except ValueError:
                self.ui.print_warning("Please enter a valid number")
    
    def _ask_advanced_options(self) -> bool:
        """Ask if user wants to configure advanced options."""
        self.ui.print_info("\nAdvanced options include:")
        self.ui.print_info("• Schema mapping strategies (auto-map, manual, none)")
        self.ui.print_info("• Auto-create missing columns")
        self.ui.print_info("• Handle extra destination columns")
        self.ui.print_info("• Data transformations")
        self.ui.print_info("• Processing hooks (job, batch, and row-level)")
        self.ui.print_info("• Hook types: scripts, API calls, lambda, notifications")
        
        return Confirm.ask("Configure advanced options?", default=False)
