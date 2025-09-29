"""
Portl CLI - Entry point for the command-line interface.
"""

import click


@click.group()
@click.version_option(version="0.0.1", prog_name="portl")
def cli():
    """
    Portl - A developer-first CLI tool for moving data across databases, CSVs, and Google Sheets.
    
    Instead of writing one-off SQL or Python scripts for every migration, Portl gives you an
    interactive wizard and YAML job configs you can re-run, share, and version-control.
    """
    pass


@cli.command()
def init():
    """Start a new migration wizard."""
    click.echo("🚀 Portl migration wizard coming soon!")
    click.echo("This will help you create YAML job configurations for your data migrations.")
    click.echo("\nFor now, check out the documentation at: https://github.com/hebaghazali/portl")


@cli.command()
@click.argument('job_file')
@click.option('--dry-run', is_flag=True, help='Preview the migration without executing')
def run(job_file, dry_run):
    """Run a migration job from a YAML file."""
    if dry_run:
        click.echo(f"🔍 Dry run mode: Would execute job from {job_file}")
    else:
        click.echo(f"⚡ Running migration job: {job_file}")
    
    click.echo("Migration execution coming soon!")


if __name__ == '__main__':
    cli()
