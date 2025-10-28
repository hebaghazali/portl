"""
Jinja2 templating engine for step configuration.

Provides a sandboxed Jinja2 environment with custom helpers for
template resolution in step configurations.
"""

import json
import hashlib
from datetime import datetime
from typing import Any, Dict, Optional
from jinja2 import StrictUndefined, UndefinedError
from jinja2.sandbox import SandboxedEnvironment, SecurityError
import logging

logger = logging.getLogger(__name__)


class TemplateEngine:
    """
    Sandboxed Jinja2 template engine for step configurations.
    
    Features:
    - Sandboxed execution (prevents code injection)
    - Strict undefined (errors on missing variables)
    - Allowlisted filters and globals only
    - Blocks attribute introspection (__class__, __subclasses__, etc.)
    
    Security:
    Uses SandboxedEnvironment to prevent template escape attacks.
    All attribute access is validated via is_safe_attribute().
    """
    
    def __init__(self):
        """Initialize the sandboxed template engine."""
        self.env = SandboxedEnvironment(
            undefined=StrictUndefined,
            autoescape=False,  # Don't autoescape - we're not rendering HTML
        )
        
        # Override attribute access control
        self.env.is_safe_attribute = self._is_safe_attribute
        
        # Register only safe helpers (allowlist approach)
        self._register_safe_helpers()
    
    def _is_safe_attribute(self, obj: Any, attr: str, value: Any) -> bool:
        """
        Determine if an attribute access is safe.
        
        Security policy:
        - Block all private attributes (starting with _)
        - Block class introspection attributes
        - Block dangerous builtins
        
        Args:
            obj: Object being accessed
            attr: Attribute name being accessed
            value: Attribute value (if already retrieved)
            
        Returns:
            True if access is allowed, False otherwise
        """
        # Block all private attributes
        if attr.startswith('_'):
            logger.warning(f"Blocked access to private attribute: {attr}")
            return False
        
        # Block known dangerous attributes
        BLOCKED_ATTRS = {
            '__class__', '__bases__', '__subclasses__', '__mro__',
            '__init__', '__globals__', '__builtins__', '__code__',
            '__closure__', '__func__', '__self__',
            'eval', 'exec', 'compile', 'open', 'file',
            'input', '__import__', 'reload',
        }
        
        if attr in BLOCKED_ATTRS:
            logger.warning(f"Blocked access to dangerous attribute: {attr}")
            return False
        
        return True
    
    def _register_safe_helpers(self):
        """
        Register only allowlisted filters and globals.
        
        Uses an explicit allowlist approach - only these functions
        are available in templates.
        """
        # Allowlist of safe filters
        SAFE_FILTERS = {
            'md5': self._md5_hash,
            'tojson': self._to_json,
            'fromjson': self._from_json,
            'int': self._to_int,
            'float': self._to_float,
            'str': str,
            'bool': bool,
            'upper': lambda s: str(s).upper(),
            'lower': lambda s: str(s).lower(),
            'trim': lambda s: str(s).strip(),
            'coalesce': self._coalesce,
            'default': self._default,
            'json_path': self._json_path,
        }
        
        # Allowlist of safe globals
        SAFE_GLOBALS = {
            'now': self._now,
            'range': range,  # Safe built-in
        }
        
        # Clear existing filters/globals and register only safe ones
        self.env.filters.clear()
        self.env.globals.clear()
        
        for name, func in SAFE_FILTERS.items():
            self.env.filters[name] = func
        
        for name, func in SAFE_GLOBALS.items():
            self.env.globals[name] = func
        
        # Safe tests
        self.env.tests['empty'] = lambda x: not x
    
    @staticmethod
    def _md5_hash(value: Any) -> str:
        """
        Compute MD5 hash of a value.
        
        Args:
            value: Value to hash (converted to string)
            
        Returns:
            Hexadecimal MD5 hash
        """
        if isinstance(value, (dict, list)):
            value = json.dumps(value, sort_keys=True)
        else:
            value = str(value)
        
        return hashlib.md5(value.encode('utf-8')).hexdigest()
    
    @staticmethod
    def _to_json(value: Any, indent: Optional[int] = None) -> str:
        """
        Convert value to JSON string.
        
        Args:
            value: Value to serialize
            indent: Optional indentation
            
        Returns:
            JSON string
        """
        return json.dumps(value, indent=indent, default=str)
    
    @staticmethod
    def _from_json(value: str) -> Any:
        """
        Parse JSON string.
        
        Args:
            value: JSON string
            
        Returns:
            Parsed value
        """
        return json.loads(value)
    
    @staticmethod
    def _to_int(value: Any, default: int = 0) -> int:
        """
        Convert value to integer.
        
        Args:
            value: Value to convert
            default: Default if conversion fails
            
        Returns:
            Integer value
        """
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        """
        Convert value to float.
        
        Args:
            value: Value to convert
            default: Default if conversion fails
            
        Returns:
            Float value
        """
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    @staticmethod
    def _coalesce(*values: Any) -> Any:
        """
        Return first non-None value.
        
        Args:
            *values: Values to check
            
        Returns:
            First non-None value or None if all are None
        """
        for value in values:
            if value is not None:
                return value
        return None
    
    @staticmethod
    def _default(value: Any, default_value: Any) -> Any:
        """
        Return default if value is None or empty.
        
        Args:
            value: Value to check
            default_value: Default to return
            
        Returns:
            Value or default
        """
        if value is None or (isinstance(value, (str, list, dict)) and not value):
            return default_value
        return value
    
    @staticmethod
    def _now(format: Optional[str] = None) -> str:
        """
        Get current timestamp.
        
        Args:
            format: Optional strftime format string
            
        Returns:
            Formatted timestamp (ISO format by default)
        """
        dt = datetime.utcnow()
        if format:
            return dt.strftime(format)
        return dt.isoformat()
    
    @staticmethod
    def _json_path(data: Any, path: str, default: Any = None) -> Any:
        """
        Extract value from nested data using dot notation.
        
        Args:
            data: Data to query
            path: Dot-separated path (e.g., "user.address.city")
            default: Default value if path not found
            
        Returns:
            Value at path or default
        """
        parts = path.split('.')
        current = data
        
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            elif isinstance(current, list) and part.isdigit():
                idx = int(part)
                current = current[idx] if 0 <= idx < len(current) else None
            else:
                return default
            
            if current is None:
                return default
        
        return current
    
    def render_string(self, template_str: str, context: Dict[str, Any]) -> str:
        """
        Render a template string with context.
        
        Args:
            template_str: Template string with Jinja2 syntax
            context: Template context
            
        Returns:
            Rendered string
            
        Raises:
            UndefinedException: If template references missing variable
        """
        try:
            template = self.env.from_string(template_str)
            return template.render(context)
        except UndefinedError as e:
            logger.error(f"Template variable not found: {e}")
            raise
    
    def render_value(self, value: Any, context: Dict[str, Any]) -> Any:
        """
        Render a value that may contain template strings.
        
        Recursively processes dicts and lists, rendering any strings
        that contain Jinja2 template syntax.
        
        Args:
            value: Value to render (can be str, dict, list, or primitive)
            context: Template context
            
        Returns:
            Rendered value
        """
        if isinstance(value, str):
            # Only render if it looks like a template
            if '{{' in value or '{%' in value:
                return self.render_string(value, context)
            return value
        
        elif isinstance(value, dict):
            return {
                k: self.render_value(v, context)
                for k, v in value.items()
            }
        
        elif isinstance(value, list):
            return [self.render_value(item, context) for item in value]
        
        else:
            # Primitive value, return as-is
            return value
    
    def render_config(self, config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Render a complete configuration dict with templates.
        
        Args:
            config: Configuration with template strings
            context: Template context
            
        Returns:
            Rendered configuration
        """
        return self.render_value(config, context)
    
    def evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """
        Evaluate a Jinja2 conditional expression.
        
        Args:
            condition: Jinja2 expression (e.g., "{{ user.active }}")
            context: Template context
            
        Returns:
            Boolean result (truthiness of expression)
        """
        # Wrap in if statement to evaluate as boolean
        template_str = f"{{% if {condition} %}}true{{% else %}}false{{% endif %}}"
        result = self.render_string(template_str, context)
        return result == 'true'


# Global template engine instance
_template_engine: Optional[TemplateEngine] = None


def get_template_engine() -> TemplateEngine:
    """
    Get the global template engine instance.
    
    Returns:
        TemplateEngine instance
    """
    global _template_engine
    if _template_engine is None:
        _template_engine = TemplateEngine()
    return _template_engine


def render_step_config(step_config: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to render step configuration.
    
    Args:
        step_config: Step configuration dict
        context: Template context
        
    Returns:
        Rendered configuration
    """
    engine = get_template_engine()
    return engine.render_config(step_config, context)

