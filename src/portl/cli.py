"""
Portl CLI - Entry point for the command-line interface.
"""

import typer
from typing import Optional
from pathlib import Path

from .ui.console import ConsoleUI
from .commands.init_command import InitCommandHandler
from .commands.run_command import RunCommandHandler
from . import __version__

console_ui = ConsoleUI()
app = typer.Typer(
    name="portl",
    help="A developer-first CLI tool for moving data across databases, CSVs, and Google Sheets.\n\n"
         "Instead of writing one-off SQL or Python scripts for every migration, Portl gives you an "
         "interactive wizard and YAML job configs you can re-run, share, and version-control.",
    rich_markup_mode="rich"
)


def version_callback(value: bool):
    if value:
        console_ui.print_version(__version__)
        raise typer.Exit()


@app.callback()
def main(
    _: Optional[bool] = typer.Option(
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
    handler = InitCommandHandler()
    handler.handle(output=output, interactive=interactive)


@app.command()
def run(
    job_file: Optional[Path] = typer.Argument(
        None, help="Path to the YAML job configuration file"
    ),
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
    handler = RunCommandHandler()
    handler.handle(
        job_file=job_file,
        dry_run=dry_run,
        batch_size=batch_size,
        verbose=verbose
    )


def cli():
    """Entry point for the CLI when called as a script."""
    app()


if __name__ == '__main__':
    cli()