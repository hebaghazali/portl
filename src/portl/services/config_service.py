"""
Configuration service for handling config files and environment variables.

This service supports loading configuration from various sources:
- Configuration files (.portl.yaml, portl.config.yaml)
- Environment variables
- Command line arguments
"""

import os
import re
from pathlib import Path
from typing import Dict, Any, Optional, List
import yaml
from ..schema import JobConfig, SchemaValidator, generate_schema_template


class ConfigService:
    """Handles configuration loading from files and environment variables."""
    
    def __init__(self):
        self.config_filenames = [
            ".portl.yaml",
            ".portl.yml", 
            "portl.config.yaml",
            "portl.config.yml",
            "portl.yaml",
            "portl.yml"
        ]
    
    def load_config(self, config_path: Optional[Path] = None) -> Dict[str, Any]:
        """
        Load configuration from file or environment variables.
        
        Args:
            config_path: Specific config file path, or None to auto-discover
            
        Returns:
            Configuration dictionary
        """
        config = {}
        
        # Load from file
        if config_path:
            config.update(self._load_config_file(config_path))
        else:
            # Auto-discover config file
            discovered_config = self._discover_config_file()
            if discovered_config:
                config.update(discovered_config)
        
        # Override with environment variables
        env_config = self._load_from_environment()
        config.update(env_config)
        
        return config
    
    def _discover_config_file(self) -> Dict[str, Any]:
        """Discover and load configuration file from current directory."""
        current_dir = Path.cwd()
        
        for filename in self.config_filenames:
            config_path = current_dir / filename
            if config_path.exists():
                return self._load_config_file(config_path)
        
        return {}
    
    def _load_config_file(self, config_path: Path) -> Dict[str, Any]:
        """Load configuration from a specific file."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Resolve environment variables in the content
            resolved_content = self._resolve_env_variables(content)
            
            # Parse the resolved YAML
            config = yaml.safe_load(resolved_content) or {}
            return config
        except Exception as e:
            raise ValueError(f"Error loading config file {config_path}: {e}")
    
    def _load_from_environment(self) -> Dict[str, Any]:
        """Load configuration from environment variables."""
        config = {}
        
        # Database connection environment variables
        env_mappings = {
            # Source database
            'PORTL_SOURCE_HOST': ['source', 'host'],
            'PORTL_SOURCE_PORT': ['source', 'port'],
            'PORTL_SOURCE_DATABASE': ['source', 'database'],
            'PORTL_SOURCE_USERNAME': ['source', 'username'],
            'PORTL_SOURCE_PASSWORD': ['source', 'password'],
            'PORTL_SOURCE_SCHEMA': ['source', 'schema'],
            'PORTL_SOURCE_TABLE': ['source', 'table'],
            
            # Destination database
            'PORTL_DEST_HOST': ['destination', 'host'],
            'PORTL_DEST_PORT': ['destination', 'port'],
            'PORTL_DEST_DATABASE': ['destination', 'database'],
            'PORTL_DEST_USERNAME': ['destination', 'username'],
            'PORTL_DEST_PASSWORD': ['destination', 'password'],
            'PORTL_DEST_SCHEMA': ['destination', 'schema'],
            'PORTL_DEST_TABLE': ['destination', 'table'],
            
            # Google Sheets
            'PORTL_GOOGLE_CREDENTIALS': ['google_credentials_path'],
            'PORTL_GOOGLE_SPREADSHEET_ID': ['google_spreadsheet_id'],
            
            # Processing options
            'PORTL_BATCH_SIZE': ['batch_size'],
            'PORTL_CONFLICT_STRATEGY': ['conflict'],
            'PORTL_PARALLEL_JOBS': ['parallel_jobs'],
        }
        
        for env_var, config_path in env_mappings.items():
            value = os.getenv(env_var)
            if value is not None:
                # Convert numeric values
                if env_var.endswith('_PORT') or env_var.endswith('_SIZE') or env_var.endswith('_JOBS'):
                    try:
                        value = int(value)
                    except ValueError:
                        pass
                
                # Set nested configuration
                self._set_nested_config(config, config_path, value)
        
        return config
    
    def _set_nested_config(self, config: Dict[str, Any], path: List[str], value: Any):
        """Set a nested configuration value."""
        current = config
        
        # Navigate to the parent of the target key
        for key in path[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # Set the final value
        current[path[-1]] = value
    
    def generate_config_template(self, output_path: Path) -> bool:
        """
        Generate a configuration file template using the schema system.
        
        Args:
            output_path: Where to save the template
            
        Returns:
            True if successful
        """
        try:
            # Use the schema-based template generator
            template_content = generate_schema_template()
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(template_content)
            
            return True
        except Exception as e:
            raise ValueError(f"Error generating config template: {e}")
    
    def load_validated_config(self, config_path: Optional[Path] = None) -> JobConfig:
        """
        Load and validate configuration using the schema system.
        
        Args:
            config_path: Specific config file path, or None to auto-discover
            
        Returns:
            JobConfig: Validated configuration object
            
        Raises:
            ValueError: If configuration is invalid
            FileNotFoundError: If config file not found
        """
        # Load raw configuration
        raw_config = self.load_config(config_path)
        
        if not raw_config:
            raise ValueError("No configuration found")
        
        # Validate using schema system
        return SchemaValidator.validate_yaml_config(raw_config)
    
    def _generate_config_yaml(self, config: Dict[str, Any]) -> str:
        """Generate YAML content with comments."""
        lines = []
        
        lines.append("# Portl Configuration File")
        lines.append("# Use this file for non-interactive mode")
        lines.append("# Environment variables can be used with ${VAR_NAME:-default}")
        lines.append("")
        
        # Generate YAML (excluding comment keys)
        clean_config = {k: v for k, v in config.items() if not k.startswith('#')}
        yaml_content = yaml.dump(clean_config, default_flow_style=False, sort_keys=False)
        
        lines.extend(yaml_content.split('\n'))
        
        return '\n'.join(lines)
    
    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate configuration loaded from files/environment.
        
        Args:
            config: Configuration dictionary
            
        Returns:
            Validation result
        """
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        # Check for required sections
        if not config.get('source'):
            validation_result["errors"].append("Missing source configuration")
            validation_result["valid"] = False
        
        if not config.get('destination'):
            validation_result["errors"].append("Missing destination configuration")
            validation_result["valid"] = False
        
        # Validate source
        if config.get('source'):
            if not config['source'].get('type'):
                validation_result["errors"].append("Source type is required")
                validation_result["valid"] = False
        
        # Validate destination
        if config.get('destination'):
            if not config['destination'].get('type'):
                validation_result["errors"].append("Destination type is required")
                validation_result["valid"] = False
        
        # Check for environment variable placeholders that weren't resolved
        unresolved_vars = self._find_unresolved_variables(config)
        if unresolved_vars:
            validation_result["warnings"].extend([
                f"Unresolved environment variable: {var}" for var in unresolved_vars
            ])
        
        return validation_result
    
    def _find_unresolved_variables(self, obj: Any, path: str = "") -> List[str]:
        """Find unresolved environment variable placeholders."""
        unresolved = []
        
        if isinstance(obj, dict):
            for key, value in obj.items():
                new_path = f"{path}.{key}" if path else key
                unresolved.extend(self._find_unresolved_variables(value, new_path))
        
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                new_path = f"{path}[{i}]"
                unresolved.extend(self._find_unresolved_variables(item, new_path))
        
        elif isinstance(obj, str):
            if obj.startswith('${') and obj.endswith('}'):
                # This is an unresolved environment variable
                var_name = obj[2:-1].split(':-')[0]  # Extract variable name
                unresolved.append(f"{var_name} (at {path})")
        
        return unresolved
    
    def _resolve_env_variables(self, content: str) -> str:
        """
        Resolve environment variables in YAML content.
        
        Supports syntax: ${VAR_NAME} and ${VAR_NAME:-default_value}
        """
        def replace_env_var(match):
            var_expr = match.group(1)
            
            # Check if there's a default value
            if ':-' in var_expr:
                var_name, default_value = var_expr.split(':-', 1)
                return os.getenv(var_name, default_value)
            else:
                # No default value, return empty string if not found
                return os.getenv(var_expr, '')
        
        # Pattern to match ${VAR_NAME} or ${VAR_NAME:-default}
        pattern = r'\$\{([^}]+)\}'
        resolved_content = re.sub(pattern, replace_env_var, content)
        
        return resolved_content
