"""
CSV connector implementations for Portl.

This module provides CSV source and destination connectors with
chunked reading, type inference, and batch processing capabilities.
"""

import pandas as pd
import csv
from pathlib import Path
from typing import Iterator, Dict, Any, List, Optional, Union
import logging
import chardet

from .base import BaseSourceConnector, BaseDestinationConnector
from ..schema import CsvConfig

logger = logging.getLogger(__name__)


class CsvConnectorMixin:
    """Mixin class with common CSV functionality."""
    
    def __init__(self, config: CsvConfig):
        """Initialize with CSV configuration."""
        super().__init__(config.__dict__)
        self.csv_config = config
        
        # Validate that this is a csv config
        if config.type != 'csv':
            raise ValueError(f"Expected csv config, got {config.type}")
    
    def _detect_encoding(self, file_path: Path) -> str:
        """Detect file encoding using chardet."""
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read(10000)  # Read first 10KB for detection
                result = chardet.detect(raw_data)
                encoding = result.get('encoding', 'utf-8')
                confidence = result.get('confidence', 0)
                
                # If confidence is low, fall back to utf-8
                if confidence < 0.7:
                    encoding = 'utf-8'
                
                self.logger.info(f"Detected encoding: {encoding} (confidence: {confidence:.2f})")
                return encoding
                
        except Exception as e:
            self.logger.warning(f"Could not detect encoding: {e}, using utf-8")
            return 'utf-8'
    
    def _get_file_info(self) -> Dict[str, Any]:
        """Get basic file information."""
        file_path = Path(self.csv_config.path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"CSV file not found: {file_path}")
        
        return {
            'path': file_path,
            'size': file_path.stat().st_size,
            'encoding': self._detect_encoding(file_path)
        }
    
    def connect(self) -> None:
        """CSV files don't require connection, just validate file exists."""
        file_path = Path(self.csv_config.path)
        
        if not file_path.exists():
            # For source connectors, file must exist
            if isinstance(self, BaseSourceConnector):
                raise FileNotFoundError(f"CSV file not found: {file_path}")
            # For destination connectors, we'll create the file later
            else:
                self.logger.info(f"CSV file will be created: {file_path}")
                return
        
        self.logger.info(f"CSV file validated: {file_path}")
    
    def disconnect(self) -> None:
        """CSV files don't require disconnection."""
        self.logger.info("CSV file access completed")
    
    def test_connection(self) -> bool:
        """Test if CSV file can be accessed."""
        try:
            file_path = Path(self.csv_config.path)
            
            # For source connectors, file must exist
            if isinstance(self, BaseSourceConnector):
                return file_path.exists() and file_path.is_file()
            # For destination connectors, we just need to be able to create the parent directory
            else:
                # Check if we can create the parent directory
                parent_dir = file_path.parent
                parent_dir.mkdir(parents=True, exist_ok=True)
                return True
                
        except Exception as e:
            self.logger.error(f"CSV file test failed: {e}")
            return False


class CsvSourceConnector(CsvConnectorMixin, BaseSourceConnector):
    """CSV source connector for reading data."""
    
    def get_schema(self) -> Dict[str, str]:
        """Get CSV schema by analyzing the first few rows."""
        try:
            file_info = self._get_file_info()
            file_path = file_info['path']
            encoding = file_info['encoding']
            
            # Read a small sample to infer types
            sample_df = pd.read_csv(
                file_path,
                nrows=1000,  # Read first 1000 rows for type inference
                delimiter=self.csv_config.delimiter,
                encoding=encoding,
                header=0 if self.csv_config.has_header else None
            )
            
            schema = {}
            for column in sample_df.columns:
                # Map pandas dtypes to generic types
                dtype = sample_df[column].dtype
                generic_type = self._map_pandas_type(dtype)
                schema[column] = generic_type
            
            self.logger.info(f"CSV schema inferred: {len(schema)} columns")
            return schema
            
        except Exception as e:
            self.logger.error(f"Failed to get CSV schema: {e}")
            raise
    
    def _map_pandas_type(self, pandas_dtype) -> str:
        """Map pandas data types to generic types."""
        type_mapping = {
            'int64': 'int',
            'int32': 'int',
            'int16': 'smallint',
            'int8': 'smallint',
            'float64': 'double',
            'float32': 'float',
            'bool': 'boolean',
            'object': 'text',
            'string': 'text',
            'datetime64[ns]': 'timestamp',
            'datetime64[ns, UTC]': 'timestamptz',
            'category': 'text'
        }
        
        # Handle nullable types
        is_nullable = pandas_dtype.name.startswith('Int') or pandas_dtype.name.startswith('Float')
        base_type = type_mapping.get(str(pandas_dtype), 'text')
        
        return f"{base_type}{'?' if is_nullable else ''}"
    
    def get_row_count(self) -> int:
        """Get total row count from CSV file."""
        try:
            file_info = self._get_file_info()
            file_path = file_info['path']
            encoding = file_info['encoding']
            
            # Count lines efficiently
            with open(file_path, 'r', encoding=encoding, newline='') as f:
                reader = csv.reader(f, delimiter=self.csv_config.delimiter)
                row_count = sum(1 for _ in reader)
            
            # Subtract header if present
            if self.csv_config.has_header:
                row_count -= 1
            
            self.logger.info(f"CSV row count: {row_count}")
            return max(0, row_count)
            
        except Exception as e:
            self.logger.error(f"Failed to get CSV row count: {e}")
            raise
    
    def read_data(self, batch_size: int = 1000, offset: int = 0) -> Iterator[List[Dict[str, Any]]]:
        """Read data in batches from CSV file."""
        try:
            file_info = self._get_file_info()
            file_path = file_info['path']
            encoding = file_info['encoding']
            
            # Calculate skip rows for offset
            skip_rows = offset
            if self.csv_config.has_header:
                skip_rows += 1  # Skip header row
            
            current_offset = offset
            
            while True:
                # Read batch using pandas for efficient chunking
                chunk_df = pd.read_csv(
                    file_path,
                    skiprows=range(1, skip_rows + 1) if skip_rows > 0 else None,
                    nrows=batch_size,
                    delimiter=self.csv_config.delimiter,
                    encoding=encoding,
                    header=0 if self.csv_config.has_header else None
                )
                
                if chunk_df.empty:
                    break
                
                # Convert DataFrame to list of dictionaries
                batch = chunk_df.to_dict('records')
                
                # Convert pandas types to Python native types
                processed_batch = []
                for row in batch:
                    processed_row = {}
                    for key, value in row.items():
                        # Handle pandas NaN values
                        if pd.isna(value):
                            processed_row[key] = None
                        elif isinstance(value, (pd.Timestamp, pd.DatetimeIndex)):
                            processed_row[key] = value.to_pydatetime()
                        else:
                            processed_row[key] = value
                    processed_batch.append(processed_row)
                
                yield processed_batch
                
                # If we got fewer rows than batch_size, we're done
                if len(processed_batch) < batch_size:
                    break
                
                # Update offset for next iteration
                current_offset += len(processed_batch)
                skip_rows = current_offset
                if self.csv_config.has_header:
                    skip_rows += 1
            
        except Exception as e:
            self.logger.error(f"Failed to read CSV data: {e}")
            raise


class CsvDestinationConnector(CsvConnectorMixin, BaseDestinationConnector):
    """CSV destination connector for writing data."""
    
    def __init__(self, config: CsvConfig):
        """Initialize CSV destination connector."""
        super().__init__(config)
        self._file_handle = None
        self._csv_writer = None
        self._headers_written = False
    
    def get_schema(self) -> Dict[str, str]:
        """Get schema from existing CSV file if it exists."""
        try:
            file_path = Path(self.csv_config.path)
            
            if not file_path.exists():
                return {}
            
            # Read existing file to get schema
            file_info = self._get_file_info()
            encoding = file_info['encoding']
            
            sample_df = pd.read_csv(
                file_path,
                nrows=1,
                delimiter=self.csv_config.delimiter,
                encoding=encoding,
                header=0 if self.csv_config.has_header else None
            )
            
            schema = {}
            for column in sample_df.columns:
                dtype = sample_df[column].dtype
                generic_type = self._map_pandas_type(dtype)
                schema[column] = generic_type
            
            return schema
            
        except Exception as e:
            self.logger.warning(f"Could not read existing CSV schema: {e}")
            return {}
    
    def _map_pandas_type(self, pandas_dtype) -> str:
        """Map pandas data types to generic types."""
        type_mapping = {
            'int64': 'int',
            'int32': 'int',
            'int16': 'smallint',
            'int8': 'smallint',
            'float64': 'double',
            'float32': 'float',
            'bool': 'boolean',
            'object': 'text',
            'string': 'text',
            'datetime64[ns]': 'timestamp',
            'datetime64[ns, UTC]': 'timestamptz',
            'category': 'text'
        }
        
        # Handle nullable types
        is_nullable = pandas_dtype.name.startswith('Int') or pandas_dtype.name.startswith('Float')
        base_type = type_mapping.get(str(pandas_dtype), 'text')
        
        return f"{base_type}{'?' if is_nullable else ''}"
    
    def create_table_if_not_exists(self, schema: Dict[str, str]) -> None:
        """Create CSV file with headers if it doesn't exist."""
        try:
            file_path = Path(self.csv_config.path)
            
            # Create directory if it doesn't exist
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # If file doesn't exist, create it with headers
            if not file_path.exists():
                # Use the configured encoding or default to utf-8
                encoding = self.csv_config.encoding
                
                with open(file_path, 'w', encoding=encoding, newline='') as f:
                    if self.csv_config.has_header and schema:
                        writer = csv.writer(f, delimiter=self.csv_config.delimiter)
                        writer.writerow(schema.keys())
                
                self.logger.info(f"Created CSV file: {file_path}")
            
        except Exception as e:
            self.logger.error(f"Failed to create CSV file: {e}")
            raise
    
    def write_batch(self, rows: List[Dict[str, Any]], conflict_strategy: str = 'overwrite', 
                   key_columns: Optional[List[str]] = None) -> int:
        """Write a batch of rows to CSV file with support for insert/update/delete operations."""
        if not rows:
            return 0
        
        # Group rows by operation type
        grouped_rows = self._group_rows_by_operation(rows)
        total_processed = 0
        
        try:
            # Process inserts (simple append)
            if grouped_rows['insert']:
                total_processed += self._execute_csv_inserts(grouped_rows['insert'])
            
            # Process updates and deletes (requires reading/rewriting the file)
            if grouped_rows['update'] or grouped_rows['delete']:
                if not key_columns:
                    raise ValueError("key_columns must be specified for update/delete operations")
                
                total_processed += self._execute_csv_updates_deletes(
                    grouped_rows['update'], grouped_rows['delete'], key_columns
                )
            
            return total_processed
            
        except Exception as e:
            self.logger.error(f"Failed to write CSV batch: {e}")
            raise
    
    def _execute_csv_inserts(self, rows: List[Dict[str, Any]]) -> int:
        """Execute insert operations by appending to CSV file."""
        if not rows:
            return 0
        
        file_path = Path(self.csv_config.path)
        encoding = self.csv_config.encoding
        
        # Determine write mode
        write_mode = 'a' if file_path.exists() else 'w'
        
        with open(file_path, write_mode, encoding=encoding, newline='') as f:
            writer = csv.writer(f, delimiter=self.csv_config.delimiter)
            
            # Write header if this is the first write and headers are enabled
            if write_mode == 'w' and self.csv_config.has_header:
                writer.writerow(rows[0].keys())
            
            # Write data rows
            for row in rows:
                # Convert row to list in the same order as headers
                if self.csv_config.has_header and write_mode == 'w':
                    # Use the order from the first row
                    row_values = [row.get(key) for key in rows[0].keys()]
                else:
                    # Use the order from the row itself
                    row_values = list(row.values())
                
                writer.writerow(row_values)
        
        self.logger.info(f"Inserted {len(rows)} rows to CSV")
        return len(rows)
    
    def _execute_csv_updates_deletes(self, update_rows: List[Dict[str, Any]], 
                                   delete_rows: List[Dict[str, Any]], 
                                   key_columns: List[str]) -> int:
        """Execute update and delete operations by rewriting the CSV file."""
        file_path = Path(self.csv_config.path)
        
        if not file_path.exists():
            self.logger.warning("CSV file doesn't exist for update/delete operations")
            return 0
        
        encoding = self.csv_config.encoding
        
        # Read existing data
        existing_data = []
        headers = None
        
        with open(file_path, 'r', encoding=encoding, newline='') as f:
            reader = csv.reader(f, delimiter=self.csv_config.delimiter)
            
            if self.csv_config.has_header:
                headers = next(reader, None)
                if not headers:
                    self.logger.warning("No headers found in CSV file")
                    return 0
            
            for row_values in reader:
                if headers:
                    row_dict = dict(zip(headers, row_values))
                else:
                    # If no headers, use column indices
                    row_dict = {f"col_{i}": val for i, val in enumerate(row_values)}
                existing_data.append(row_dict)
        
        # Create lookup dictionaries for updates and deletes
        update_lookup = self._create_key_lookup(update_rows, key_columns)
        delete_lookup = self._create_key_lookup(delete_rows, key_columns)
        
        # Process existing data
        updated_data = []
        update_count = 0
        delete_count = 0
        
        for existing_row in existing_data:
            row_key = self._get_row_key(existing_row, key_columns)
            
            if row_key in delete_lookup:
                # Skip this row (delete it)
                delete_count += 1
                continue
            elif row_key in update_lookup:
                # Update this row
                updated_row = existing_row.copy()
                update_data = update_lookup[row_key]
                
                # Update only non-key columns
                for col, value in update_data.items():
                    if col not in key_columns:
                        updated_row[col] = value
                
                updated_data.append(updated_row)
                update_count += 1
            else:
                # Keep existing row unchanged
                updated_data.append(existing_row)
        
        # Write updated data back to file
        with open(file_path, 'w', encoding=encoding, newline='') as f:
            writer = csv.writer(f, delimiter=self.csv_config.delimiter)
            
            if self.csv_config.has_header and headers:
                writer.writerow(headers)
            
            for row in updated_data:
                if headers:
                    row_values = [row.get(col, '') for col in headers]
                else:
                    row_values = list(row.values())
                writer.writerow(row_values)
        
        self.logger.info(f"Updated {update_count} rows, deleted {delete_count} rows in CSV")
        return update_count + delete_count
    
    def _create_key_lookup(self, rows: List[Dict[str, Any]], key_columns: List[str]) -> Dict[tuple, Dict[str, Any]]:
        """Create a lookup dictionary using key columns."""
        lookup = {}
        for row in rows:
            key = self._get_row_key(row, key_columns)
            lookup[key] = row
        return lookup
    
    def _get_row_key(self, row: Dict[str, Any], key_columns: List[str]) -> tuple:
        """Get the key tuple for a row based on key columns."""
        return tuple(str(row.get(col, '')) for col in key_columns)
    
    def begin_transaction(self) -> None:
        """CSV files don't support transactions, but we can track state."""
        self.logger.info("CSV write transaction started")
    
    def commit_transaction(self) -> None:
        """CSV files don't support transactions, but we can flush buffers."""
        self.logger.info("CSV write transaction committed")
    
    def rollback_transaction(self) -> None:
        """CSV files don't support rollback, but we can log the attempt."""
        self.logger.warning("CSV files don't support rollback - data may be partially written")
    
    def validate_schema_compatibility(self, source_schema: Dict[str, str]) -> List[str]:
        """
        Validate that source schema is compatible with destination CSV.
        
        Args:
            source_schema: Schema from the source connector
            
        Returns:
            List of validation warnings/errors
        """
        warnings = []
        
        try:
            dest_schema = self.get_schema()
            
            if not dest_schema:
                # New file, no compatibility issues
                return warnings
            
            # Check for missing columns in destination
            missing_columns = set(source_schema.keys()) - set(dest_schema.keys())
            if missing_columns:
                warnings.append(f"Missing columns in destination CSV: {', '.join(missing_columns)}")
            
            # Check for type mismatches (basic check)
            for col_name in source_schema:
                if col_name in dest_schema:
                    source_type = source_schema[col_name].lower()
                    dest_type = dest_schema[col_name].lower()
                    if source_type != dest_type:
                        warnings.append(f"Type mismatch for column '{col_name}': source={source_type}, dest={dest_type}")
        
        except Exception as e:
            warnings.append(f"Error validating CSV schema compatibility: {e}")
        
        return warnings
