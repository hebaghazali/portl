"""
Portl CLI - Entry point for the command-line interface.
"""

import typer
from typing import Optional
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

console = Console()
app = typer.Typer(
    name="portl",
    help="A developer-first CLI tool for moving data across databases, CSVs, and Google Sheets.\n\nInstead of writing one-off SQL or Python scripts for every migration, Portl gives you an interactive wizard and YAML job configs you can re-run, share, and version-control.",
    rich_markup_mode="rich"
)


def version_callback(value: bool):
    if value:
        console.print("portl version 0.0.1")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True,
        help="Show the application version and exit."
    )
):
    """
    Portl - A developer-first CLI tool for moving data across databases, CSVs, and Google Sheets.
    """
    pass


@app.command()
def init(
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", 
        help="Output file path for the generated YAML configuration"
    ),
    interactive: bool = typer.Option(
        True, "--interactive/--non-interactive", 
        help="Run in interactive wizard mode (default) or non-interactive mode"
    )
):
    """
    Start a new migration wizard to create YAML job configurations.
    
    This interactive wizard will guide you through setting up:
    - Source and destination configurations
    - Schema mapping and transformations
    - Conflict resolution strategies
    - Hooks and batch processing options
    """
    console.print(Panel.fit(
        "🚀 [bold blue]Portl Migration Wizard[/bold blue]\n\n"
        "This will help you create YAML job configurations for your data migrations.",
        title="Welcome to Portl",
        border_style="blue"
    ))
    
    if interactive:
        console.print("\n[yellow]Interactive wizard mode coming soon![/yellow]")
        console.print("This will guide you through:")
        console.print("• Source type selection (Postgres/MySQL/CSV/Google Sheets)")
        console.print("• Connection details and authentication")
        console.print("• Schema mapping and transformations")
        console.print("• Conflict resolution strategies")
        console.print("• Hooks and performance configuration")
    else:
        console.print("\n[yellow]Non-interactive mode not yet implemented[/yellow]")
    
    if output:
        console.print(f"\n[dim]Output will be saved to: {output}[/dim]")
    
    console.print("\nFor now, check out the documentation at: [link]https://github.com/hebaghazali/portl[/link]")


@app.command()
def run(
    job_file: Path = typer.Argument(..., help="Path to the YAML job configuration file"),
    dry_run: bool = typer.Option(
        False, "--dry-run", "-d",
        help="Preview the migration without executing - validate schema and show sample data"
    ),
    batch_size: Optional[int] = typer.Option(
        None, "--batch-size", "-b",
        help="Override the batch size for processing (default: use value from YAML)"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v",
        help="Enable verbose logging and detailed progress information"
    )
):
    """
    Run a migration job from a YAML configuration file.
    
    This command executes the data migration specified in the YAML file,
    with support for dry-run mode, custom batch sizes, and verbose logging.
    """
    # Validate job file exists
    if not job_file.exists():
        console.print(f"[red]Error: Job file '{job_file}' not found[/red]")
        raise typer.Exit(1)
    
    if not job_file.suffix.lower() in ['.yaml', '.yml']:
        console.print(f"[yellow]Warning: File '{job_file}' doesn't have a .yaml or .yml extension[/yellow]")
    
    if dry_run:
        console.print(Panel.fit(
            f"🔍 [bold yellow]Dry Run Mode[/bold yellow]\n\n"
            f"Validating job configuration from: [cyan]{job_file}[/cyan]\n"
            f"No data will be modified during this run.",
            border_style="yellow"
        ))
    else:
        console.print(Panel.fit(
            f"⚡ [bold green]Running Migration Job[/bold green]\n\n"
            f"Executing job from: [cyan]{job_file}[/cyan]",
            border_style="green"
        ))
    
    if batch_size:
        console.print(f"[dim]Using custom batch size: {batch_size}[/dim]")
    
    if verbose:
        console.print("[dim]Verbose mode enabled[/dim]")
    
    console.print("\n[yellow]Migration execution engine coming soon![/yellow]")


def cli():
    """Entry point for the CLI when called as a script."""
    app()


if __name__ == '__main__':
    cli()
