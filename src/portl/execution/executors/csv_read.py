"""
CSV read step executor.

Reads data from CSV files and returns rows as list of dicts.
"""

import csv
from pathlib import Path
from typing import List, Dict, Any
import logging

from ..executor import register_executor
from ..context import ExecutionContext, StepResult, StepStatus
from ...schema import BaseStep, CSVReadStep

logger = logging.getLogger(__name__)


@register_executor("csv.read")
class CSVReadExecutor:
    """Executor for csv.read step type."""
    
    def execute(self, step: BaseStep, context: ExecutionContext) -> StepResult:
        """
        Execute CSV read operation.
        
        Args:
            step: CSV read step configuration
            context: Execution context
            
        Returns:
            StepResult with rows as output
        """
        # Get configuration - check both direct attributes (Pydantic) and config dict (dataclass)
        if hasattr(step, 'config') and isinstance(step.config, dict):
            # Dataclass Step - config is in dict
            config = step.config
            path = config.get('path')
            delimiter = config.get('delimiter', ',')
            has_header = config.get('has_header', True)
            encoding = config.get('encoding', 'utf-8')
            limit = config.get('limit', None)
        else:
            # Pydantic Step - config as attributes
            path = getattr(step, 'path', None)
            delimiter = getattr(step, 'delimiter', ',')
            has_header = getattr(step, 'has_header', True)
            encoding = getattr(step, 'encoding', 'utf-8')
            limit = getattr(step, 'limit', None)
        
        if not path:
            raise ValueError("CSV read step requires 'path' field")
        
        # Resolve path
        file_path = Path(path)
        if not file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {path}")
        
        logger.info(f"Reading CSV file: {path}")
        
        # Read CSV data
        rows: List[Dict[str, Any]] = []
        
        try:
            with open(file_path, 'r', encoding=encoding) as f:
                if has_header:
                    reader = csv.DictReader(f, delimiter=delimiter)
                else:
                    # Generate column names: col_0, col_1, ...
                    reader = csv.reader(f, delimiter=delimiter)
                    first_row = next(reader, None)
                    if first_row:
                        fieldnames = [f'col_{i}' for i in range(len(first_row))]
                        # Rewind and create DictReader
                        f.seek(0)
                        reader = csv.DictReader(
                            f, 
                            delimiter=delimiter, 
                            fieldnames=fieldnames
                        )
                
                for idx, row in enumerate(reader):
                    if limit and idx >= limit:
                        break
                    rows.append(dict(row))
            
            row_count = len(rows)
            logger.info(f"Read {row_count} rows from CSV")
            
            return StepResult(
                step_id=step.id,
                status=StepStatus.OK,
                output=rows,
                metrics={
                    'row_count': row_count,
                    'file_path': str(file_path),
                },
            )
        
        except Exception as e:
            logger.error(f"Error reading CSV file '{path}': {e}")
            raise

