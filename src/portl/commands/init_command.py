from pathlib import Path
from typing import Optional, Dict, Any
import typer

from ..ui.console import ConsoleUI
from ..services.wizard_service import WizardService
from ..services.yaml_generator import YamlGenerator
from ..services.config_service import ConfigService


class InitCommandHandler:
    def __init__(self):
        self.ui = ConsoleUI()
        self.wizard = WizardService()
        self.yaml_generator = YamlGenerator()
        self.config_service = ConfigService()
    
    def handle(
        self,
        output: Optional[Path] = None,
        interactive: bool = True
    ):
        self.ui.print_welcome_banner()
        
        if interactive:
            self._handle_interactive_mode(output)
        else:
            self._handle_non_interactive_mode(output)
    
    def _handle_interactive_mode(self, output: Optional[Path] = None):
        """Run the interactive wizard to collect migration configuration."""
        self.ui.print_info("[bold cyan]Starting Interactive Migration Wizard[/bold cyan]")
        self.ui.print_info("I'll guide you through setting up your data migration job.\n")
        
        try:
            # Collect configuration through wizard
            config = self.wizard.run_wizard()
            
            # Show job plan preview and generate YAML with syntax highlighting
            self.ui.print_info("\n" + "="*60)
            yaml_content = self.yaml_generator.generate_and_preview_yaml(config, show_preview=True)
            
            # Validate the generated YAML and show results
            self.ui.print_info("\n" + "="*60)
            validation_passed = self.yaml_generator.validate_and_report_yaml(yaml_content)
            
            if not validation_passed:
                self.ui.print_error("Generated YAML has validation errors. Please check the configuration.")
                return
            
            # Ask for confirmation before saving
            self.ui.print_info("\n" + "="*60)
            save_confirmed = self.ui.confirm("Save this configuration to a YAML file?")
            
            if save_confirmed:
                # Determine output file
                if output is None:
                    output = self._get_output_file()
                
                # Save YAML file with mode handling
                saved = self.yaml_generator.save_yaml_with_mode_handling(yaml_content, output)
                
                if saved:
                    # Show summary and next steps
                    self._show_completion_summary(output, config)
                else:
                    self.ui.print_warning("Configuration not saved.")
            else:
                self.ui.print_info("Configuration not saved. You can run the wizard again anytime.")
            
        except KeyboardInterrupt:
            self.ui.print_warning("\n\nWizard cancelled by user.")
            raise typer.Exit(0)
        except Exception as e:
            self.ui.print_error(f"Wizard failed: {e}")
            raise typer.Exit(1)
    
    def _handle_non_interactive_mode(self, output: Optional[Path] = None):
        """Handle non-interactive mode with config file or environment variables."""
        self.ui.print_info("[bold cyan]Non-Interactive Mode[/bold cyan]")
        self.ui.print_info("Looking for configuration from files or environment variables...\n")
        
        try:
            # Try to load existing configuration
            config = self.config_service.load_config()
            
            if not config:
                # No config found, offer to create template
                self._handle_no_config_found(output)
                return
            
            # Validate loaded configuration
            validation = self.config_service.validate_config(config)
            
            if not validation["valid"]:
                self.ui.print_error("Configuration validation failed:")
                for error in validation["errors"]:
                    self.ui.print_error(f"  • {error}")
                raise typer.Exit(1)
            
            # Show warnings if any
            for warning in validation["warnings"]:
                self.ui.print_warning(f"  • {warning}")
            
            # Generate YAML from configuration
            yaml_content = self.yaml_generator.generate_yaml(config)
            
            # Determine output file
            if output is None:
                output = Path("portl_job.yaml")
            
            # Save YAML file with mode handling
            saved = self.yaml_generator.save_yaml_with_mode_handling(yaml_content, output, overwrite=True)
            
            # Show completion summary if saved successfully
            if saved:
                self._show_completion_summary(output, config)
            
        except Exception as e:
            self.ui.print_error(f"Non-interactive mode failed: {e}")
            self.ui.print_info("\nTry interactive mode instead: [cyan]portl init[/cyan]")
            raise typer.Exit(1)
    
    def _handle_no_config_found(self, output: Optional[Path] = None):
        """Handle case where no configuration is found in non-interactive mode."""
        self.ui.print_warning("No configuration found in current directory or environment variables.")
        self.ui.print_info("\nLooking for configuration files:")
        
        for filename in self.config_service.config_filenames:
            self.ui.print_info(f"  • {filename}")
        
        self.ui.print_info("\nOr set environment variables like:")
        self.ui.print_info("  • PORTL_SOURCE_HOST, PORTL_SOURCE_DATABASE, etc.")
        
        create_template = typer.confirm(
            "\nWould you like to create a configuration template?",
            default=True
        )
        
        if create_template:
            template_path = Path(".portl.yaml")
            
            if template_path.exists():
                overwrite = typer.confirm(
                    f"Configuration file '{template_path}' already exists. Overwrite?",
                    default=False
                )
                if not overwrite:
                    self.ui.print_warning("Template creation cancelled.")
                    return
            
            try:
                self.config_service.generate_config_template(template_path)
                self.ui.print_success(f"Configuration template created: [cyan]{template_path}[/cyan]")
                self.ui.print_info("\nNext steps:")
                self.ui.print_info(f"1. Edit the template: [cyan]{template_path}[/cyan]")
                self.ui.print_info(f"2. Set environment variables or update the file")
                self.ui.print_info(f"3. Run again: [cyan]portl init --non-interactive[/cyan]")
            except Exception as e:
                self.ui.print_error(f"Failed to create template: {e}")
        else:
            self.ui.print_info("Please create a configuration file or use interactive mode:")
            self.ui.print_info("[cyan]portl init[/cyan]")
    
    def _get_output_file(self) -> Path:
        """Get output file path from user."""
        default_name = "portl_job.yaml"
        
        filename = typer.prompt(
            f"Output filename", 
            default=default_name,
            show_default=True
        )
        
        output_path = Path(filename)
        
        # Check if file exists
        if output_path.exists():
            overwrite = typer.confirm(
                f"File '{output_path}' already exists. Overwrite?",
                default=False
            )
            if not overwrite:
                self.ui.print_warning("Please choose a different filename.")
                return self._get_output_file()
        
        return output_path
    
    
    def _show_completion_summary(self, output_path: Path, config: Dict[str, Any]):
        """Show completion summary and next steps."""
        self.ui.print_info("\n" + "="*60)
        self.ui.print_success("[bold green]Migration Configuration Complete![/bold green]")
        self.ui.print_info("="*60)
        
        # Show configuration summary
        source_type = config.get('source', {}).get('type', 'unknown')
        dest_type = config.get('destination', {}).get('type', 'unknown')
        
        self.ui.print_info(f"Source: [cyan]{source_type}[/cyan]")
        self.ui.print_info(f"Destination: [cyan]{dest_type}[/cyan]")
        self.ui.print_info(f"Config file: [cyan]{output_path}[/cyan]")
        
        # Show next steps
        self.ui.print_info("\n[bold]Next Steps:[/bold]")
        self.ui.print_info(f"1. Review the configuration: [cyan]cat {output_path}[/cyan]")
        self.ui.print_info(f"2. Test with dry-run: [cyan]portl run {output_path} --dry-run[/cyan]")
        self.ui.print_info(f"3. Run the migration: [cyan]portl run {output_path}[/cyan]")
