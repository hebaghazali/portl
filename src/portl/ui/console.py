from rich.console import Console
from rich.panel import Panel
from pathlib import Path

from ..services.job_runner import JobRunnerConfig


class ConsoleUI:
    def __init__(self):
        self.console = Console()
    
    def print_welcome_banner(self):
        self.console.print(Panel.fit(
            "[bold blue]Portl Migration Wizard[/bold blue]\n\n"
            "This will help you create YAML job configurations for your data migrations.",
            title="Welcome to Portl",
            border_style="blue"
        ))
    
    def print_init_features(self):
        self.console.print("\nThis will guide you through:")
        self.console.print("• Source type selection (Postgres/MySQL/CSV/Google Sheets)")
        self.console.print("• Connection details and authentication")
        self.console.print("• Schema mapping and transformations")
        self.console.print("• Conflict resolution strategies")
        self.console.print("• Hooks and performance configuration")
    
    def print_no_job_file_prompt(self):
        self.console.print(Panel.fit(
            "[bold yellow]No job file specified[/bold yellow]\n\n"
            "Would you like to create a template configuration file to get started?",
            title="Missing Configuration",
            border_style="yellow"
        ))
    
    def print_job_execution_banner(self, config: JobRunnerConfig):
        if config.dry_run:
            self.console.print(Panel.fit(
                f"[bold yellow]Dry Run Mode[/bold yellow]\n\n"
                f"Validating job configuration from: [cyan]{config.job_file}[/cyan]\n"
                f"No data will be modified during this run.",
                border_style="yellow"
            ))
        else:
            self.console.print(Panel.fit(
                f"[bold green]Running Migration Job[/bold green]\n\n"
                f"Executing job from: [cyan]{config.job_file}[/cyan]",
                border_style="green"
            ))
    
    def print_job_options(self, config: JobRunnerConfig):
        if config.batch_size:
            self.console.print(f"[dim]Using custom batch size: {config.batch_size}[/dim]")
        
        if config.verbose:
            self.console.print("[dim]Verbose mode enabled[/dim]")
    
    def print_template_created(self, template_path: Path):
        self.console.print(f"[green]✅ Template created: {template_path}[/green]")
        self.console.print("\n[dim]Please edit the template file with your specific configuration.[/dim]")
    
    def print_template_usage_instructions(self, template_path: Path):
        self.console.print(f"\nTo run your migration later, use:")
        self.console.print(f"[cyan]portl run {template_path}[/cyan]")
    
    def print_error(self, message: str):
        self.console.print(f"[red]Error: {message}[/red]")
    
    def print_warning(self, message: str):
        self.console.print(f"[yellow]Warning: {message}[/yellow]")
    
    def print_success(self, message: str):
        self.console.print(f"[green]{message}[/green]")
    
    def print_info(self, message: str):
        self.console.print(message)
    
    def print_version(self, version: str):
        self.console.print(f"portl version {version}")
    
    def print_coming_soon(self, feature: str):
        self.console.print(f"\n[yellow]{feature} coming soon![/yellow]")
    
    def print_not_implemented(self, feature: str):
        self.console.print(f"\n[yellow]{feature} not yet implemented[/yellow]")
