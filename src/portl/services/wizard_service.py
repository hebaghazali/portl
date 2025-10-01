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
        
        # Conflict resolution
        conflict_strategies = ["overwrite", "skip", "fail", "merge"]
        self.ui.print_info("How should conflicts be handled when records already exist?")
        config['conflict'] = self._select_from_list("Conflict strategy", conflict_strategies)
        
        # Batch size
        batch_size = typer.prompt(
            "Batch size (rows per batch)",
            default=1000,
            type=int,
            show_default=True
        )
        config['batch_size'] = batch_size
        
        return config
    
    def _configure_advanced(self) -> Dict[str, Any]:
        """Configure advanced options."""
        config = {}
        
        # Schema mapping
        if Confirm.ask("Do you need custom column mapping?"):
            config['schema_mapping'] = self._configure_schema_mapping()
        
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
        """Configure database source."""
        config = {}
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
        """Configure database destination."""
        config = {}
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
    
    def _configure_hooks(self) -> Dict[str, str]:
        """Configure processing hooks."""
        hooks = {}
        
        hook_types = [
            ("before_job", "Before entire job starts"),
            ("after_job", "After entire job completes"),
            ("before_batch", "Before each batch"),
            ("after_batch", "After each batch")
        ]
        
        for hook_key, description in hook_types:
            if Confirm.ask(f"Add {description.lower()} hook?"):
                script_path = typer.prompt(f"Script path for {description.lower()}")
                hooks[hook_key] = script_path
        
        return hooks
    
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
        self.ui.print_info("• Custom column mapping")
        self.ui.print_info("• Data transformations")
        self.ui.print_info("• Processing hooks")
        
        return Confirm.ask("Configure advanced options?", default=False)
