"""
Field mapping and transformation engine.

This module provides the MappingEngine for applying column mappings,
type coercions, and data transformations during ETL operations.
"""

import hashlib
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, List, Callable, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class TransformError(Exception):
    """Raised when a transform fails."""
    
    def __init__(self, message: str, column: str, value: Any, operation: str):
        self.column = column
        self.value = value
        self.operation = operation
        super().__init__(f"{message} (column={column}, operation={operation}, value={value!r})")


class TransformRegistry:
    """
    Registry of available transform functions.
    
    Transform functions must accept (value, params) and return transformed value.
    Register transforms using the @TransformRegistry.register decorator.
    """
    _transforms: Dict[str, Callable[[Any, Dict[str, Any]], Any]] = {}
    
    @classmethod
    def register(cls, name: str):
        """
        Decorator to register a transform function.
        
        Args:
            name: Transform name used in configuration
            
        Returns:
            Decorator function
            
        Example:
            @TransformRegistry.register("lowercase")
            def transform_lowercase(value, params):
                return str(value).lower() if value else value
        """
        def decorator(func: Callable[[Any, Dict[str, Any]], Any]):
            cls._transforms[name] = func
            logger.debug(f"Registered transform: {name}")
            return func
        return decorator
    
    @classmethod
    def get(cls, name: str) -> Callable[[Any, Dict[str, Any]], Any]:
        """
        Get transform function by name.
        
        Args:
            name: Transform name
            
        Returns:
            Transform function
            
        Raises:
            ValueError: If transform name is not registered
        """
        if name not in cls._transforms:
            available = ', '.join(sorted(cls._transforms.keys()))
            raise ValueError(f"Unknown transform: '{name}'. Available: {available}")
        return cls._transforms[name]
    
    @classmethod
    def list_transforms(cls) -> List[str]:
        """Get list of all registered transform names."""
        return sorted(cls._transforms.keys())
    
    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Check if a transform is registered."""
        return name in cls._transforms


# =============================================================================
# Built-in Transform Functions
# =============================================================================

@TransformRegistry.register("lowercase")
def transform_lowercase(value: Any, params: Dict[str, Any]) -> Optional[str]:
    """Convert value to lowercase string."""
    if value is None:
        return None
    return str(value).lower()


@TransformRegistry.register("uppercase")
def transform_uppercase(value: Any, params: Dict[str, Any]) -> Optional[str]:
    """Convert value to uppercase string."""
    if value is None:
        return None
    return str(value).upper()


@TransformRegistry.register("trim")
def transform_trim(value: Any, params: Dict[str, Any]) -> Optional[str]:
    """Strip leading and trailing whitespace."""
    if value is None:
        return None
    return str(value).strip()


@TransformRegistry.register("parse_date")
def transform_parse_date(value: Any, params: Dict[str, Any]) -> Optional[datetime]:
    """
    Parse string to datetime.
    
    Params:
        format: strptime format string (default: "%Y-%m-%d")
    """
    if value is None:
        return None
    
    fmt = params.get("format", "%Y-%m-%d")
    
    try:
        return datetime.strptime(str(value), fmt)
    except ValueError as e:
        raise ValueError(f"Cannot parse date '{value}' with format '{fmt}': {e}")


@TransformRegistry.register("parse_number")
def transform_parse_number(value: Any, params: Dict[str, Any]) -> Optional[Decimal]:
    """
    Parse string to Decimal number.
    
    Handles comma-separated numbers (e.g., "1,234.56" -> 1234.56).
    
    Params:
        decimal_places: Optional number of decimal places to round to
    """
    if value is None:
        return None
    
    try:
        # Remove commas and whitespace
        cleaned = str(value).replace(",", "").strip()
        result = Decimal(cleaned)
        
        decimal_places = params.get("decimal_places")
        if decimal_places is not None:
            result = round(result, decimal_places)
        
        return result
    except InvalidOperation as e:
        raise ValueError(f"Cannot parse number '{value}': {e}")


@TransformRegistry.register("concat")
def transform_concat(value: Any, params: Dict[str, Any]) -> str:
    """
    Concatenate prefix and/or suffix to value.
    
    Params:
        prefix: String to prepend (default: "")
        suffix: String to append (default: "")
    """
    prefix = params.get("prefix", "")
    suffix = params.get("suffix", "")
    
    value_str = str(value) if value is not None else ""
    return f"{prefix}{value_str}{suffix}"


@TransformRegistry.register("coalesce")
def transform_coalesce(value: Any, params: Dict[str, Any]) -> Any:
    """
    Replace None/empty values with a default.
    
    Params:
        default: Value to use when input is None or empty string
    """
    default = params.get("default")
    
    if value is None or value == "":
        return default
    return value


@TransformRegistry.register("hash_md5")
def transform_hash_md5(value: Any, params: Dict[str, Any]) -> Optional[str]:
    """Compute MD5 hash of value."""
    if value is None:
        return None
    return hashlib.md5(str(value).encode('utf-8')).hexdigest()


@TransformRegistry.register("hash_sha256")
def transform_hash_sha256(value: Any, params: Dict[str, Any]) -> Optional[str]:
    """Compute SHA-256 hash of value."""
    if value is None:
        return None
    return hashlib.sha256(str(value).encode('utf-8')).hexdigest()


@TransformRegistry.register("replace")
def transform_replace(value: Any, params: Dict[str, Any]) -> Optional[str]:
    """
    Replace occurrences of a pattern in value.
    
    Params:
        old: String to search for (required)
        new: String to replace with (default: "")
    """
    if value is None:
        return None
    
    old = params.get("old")
    if old is None:
        raise ValueError("replace transform requires 'old' parameter")
    
    new = params.get("new", "")
    return str(value).replace(old, new)


@TransformRegistry.register("substring")
def transform_substring(value: Any, params: Dict[str, Any]) -> Optional[str]:
    """
    Extract substring from value.
    
    Params:
        start: Starting index (default: 0)
        end: Ending index (default: end of string)
    """
    if value is None:
        return None
    
    start = params.get("start", 0)
    end = params.get("end")
    
    s = str(value)
    if end is None:
        return s[start:]
    return s[start:end]


@TransformRegistry.register("to_int")
def transform_to_int(value: Any, params: Dict[str, Any]) -> Optional[int]:
    """Convert value to integer."""
    if value is None:
        return None
    
    try:
        # Handle float strings like "123.45"
        return int(float(str(value).replace(",", "").strip()))
    except (ValueError, TypeError) as e:
        raise ValueError(f"Cannot convert '{value}' to int: {e}")


@TransformRegistry.register("to_float")
def transform_to_float(value: Any, params: Dict[str, Any]) -> Optional[float]:
    """Convert value to float."""
    if value is None:
        return None
    
    try:
        return float(str(value).replace(",", "").strip())
    except (ValueError, TypeError) as e:
        raise ValueError(f"Cannot convert '{value}' to float: {e}")


@TransformRegistry.register("to_bool")
def transform_to_bool(value: Any, params: Dict[str, Any]) -> Optional[bool]:
    """
    Convert value to boolean.
    
    Truthy: "true", "yes", "1", "on", 1, True
    Falsy: "false", "no", "0", "off", 0, False, None, ""
    """
    if value is None:
        return None
    
    if isinstance(value, bool):
        return value
    
    if isinstance(value, (int, float)):
        return bool(value)
    
    s = str(value).lower().strip()
    
    if s in ("true", "yes", "1", "on"):
        return True
    elif s in ("false", "no", "0", "off", ""):
        return False
    else:
        raise ValueError(f"Cannot convert '{value}' to bool")


@TransformRegistry.register("default_now")
def transform_default_now(value: Any, params: Dict[str, Any]) -> datetime:
    """Replace None with current datetime."""
    if value is None:
        return datetime.now()
    return value


# =============================================================================
# MappingEngine
# =============================================================================

@dataclass
class TransformResult:
    """Result of applying a transform."""
    column: str
    original_value: Any
    transformed_value: Any
    success: bool
    error: Optional[str] = None


class MappingEngine:
    """
    Applies field mappings and transforms to data rows.
    
    Supports:
    - Column renaming via schema_mapping
    - Data transformations via transformation rules
    - Error handling policies (fail, null, skip)
    
    Example:
        engine = MappingEngine(
            schema_mapping={'user_id': 'id', 'full_name': 'name'},
            transformations=[
                {'column': 'email', 'operation': 'lowercase'},
                {'column': 'price', 'operation': 'parse_number'},
            ]
        )
        transformed_row = engine.apply(row)
    """
    
    def __init__(
        self,
        schema_mapping: Optional[Dict[str, str]] = None,
        transformations: Optional[List[Dict[str, Any]]] = None,
    ):
        """
        Initialize mapping engine.
        
        Args:
            schema_mapping: Dict mapping source column names to destination names
            transformations: List of transformation rule dicts with:
                - column: Column to transform
                - operation: Transform name
                - parameters: Optional dict of transform parameters
                - on_error: Error handling ('fail', 'null', 'skip')
        """
        self.schema_mapping = schema_mapping or {}
        self.transformations = transformations or []
        
        # Validate transformations at init time
        for t in self.transformations:
            operation = t.get('operation')
            if operation and not TransformRegistry.is_registered(operation):
                raise ValueError(
                    f"Unknown transform operation: '{operation}'. "
                    f"Available: {', '.join(TransformRegistry.list_transforms())}"
                )
    
    def apply(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply all mappings and transforms to a single row.
        
        Processing order:
        1. Apply column renames (schema_mapping)
        2. Apply transforms in order
        
        Args:
            row: Input row dict
            
        Returns:
            Transformed row dict
            
        Raises:
            TransformError: If transform fails and on_error='fail'
        """
        # Step 1: Apply column renaming
        result = self._apply_schema_mapping(row)
        
        # Step 2: Apply transforms
        result = self._apply_transforms(result)
        
        return result
    
    def apply_batch(
        self, 
        rows: List[Dict[str, Any]], 
        collect_errors: bool = False
    ) -> tuple[List[Dict[str, Any]], List[TransformError]]:
        """
        Apply mappings and transforms to multiple rows.
        
        Args:
            rows: List of input rows
            collect_errors: If True, collect errors instead of raising
            
        Returns:
            Tuple of (transformed_rows, errors)
            
        Raises:
            TransformError: If collect_errors=False and a transform fails
        """
        results = []
        errors = []
        
        for idx, row in enumerate(rows):
            try:
                transformed = self.apply(row)
                results.append(transformed)
            except TransformError as e:
                if collect_errors:
                    errors.append(e)
                    # Still include original row or skip?
                    # For now, skip failed rows when collecting errors
                else:
                    raise TransformError(
                        f"Transform failed at row {idx}: {e}",
                        column=e.column,
                        value=e.value,
                        operation=e.operation
                    )
        
        return results, errors
    
    def _apply_schema_mapping(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply column renaming based on schema_mapping.
        
        Source columns not in mapping are kept with original names.
        """
        if not self.schema_mapping:
            return dict(row)
        
        result = {}
        
        for col, value in row.items():
            # Map to new name if specified, otherwise keep original
            new_col = self.schema_mapping.get(col, col)
            result[new_col] = value
        
        return result
    
    def _apply_transforms(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """Apply all transforms to the row in order."""
        result = dict(row)
        
        for transform_rule in self.transformations:
            column = transform_rule.get('column')
            operation = transform_rule.get('operation')
            params = transform_rule.get('parameters', {})
            on_error = transform_rule.get('on_error', 'fail')
            
            if not column or not operation:
                continue
            
            # Skip if column doesn't exist in row
            if column not in result:
                logger.debug(f"Transform column '{column}' not found in row, skipping")
                continue
            
            original_value = result[column]
            
            try:
                # Get and apply transform
                transform_func = TransformRegistry.get(operation)
                result[column] = transform_func(original_value, params)
                
            except Exception as e:
                error_msg = str(e)
                logger.warning(
                    f"Transform '{operation}' failed on column '{column}': {error_msg}"
                )
                
                if on_error == 'fail':
                    raise TransformError(
                        error_msg,
                        column=column,
                        value=original_value,
                        operation=operation
                    )
                elif on_error == 'null':
                    result[column] = None
                elif on_error == 'skip':
                    # Keep original value
                    pass
                else:
                    # Unknown on_error value, default to fail
                    raise TransformError(
                        error_msg,
                        column=column,
                        value=original_value,
                        operation=operation
                    )
        
        return result


def get_mapping_engine(
    schema_mapping: Optional[Dict[str, str]] = None,
    transformations: Optional[List[Dict[str, Any]]] = None,
) -> Optional[MappingEngine]:
    """
    Create a MappingEngine if mappings or transforms are configured.
    
    Returns None if no mappings or transforms are specified.
    """
    if not schema_mapping and not transformations:
        return None
    
    return MappingEngine(
        schema_mapping=schema_mapping,
        transformations=transformations,
    )


