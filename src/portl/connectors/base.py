"""
Base connector interfaces for Portl data sources and destinations.

This module defines the abstract base classes that all connectors must implement
to ensure consistent behavior across different data sources.
"""

from abc import ABC, abstractmethod
from typing import Iterator, Dict, Any, List, Optional
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


class BaseConnector(ABC):
    """Base class for all connectors with common functionality."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize connector with configuration.
        
        Args:
            config: Configuration dictionary specific to the connector type
        """
        self.config = config
        self._connection = None
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
    
    @abstractmethod
    def connect(self) -> None:
        """Establish connection to the data source."""
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """Close connection to the data source."""
        pass
    
    @abstractmethod
    def test_connection(self) -> bool:
        """Test if connection can be established successfully."""
        pass
    
    @contextmanager
    def connection_context(self):
        """Context manager for handling connections safely."""
        try:
            self.connect()
            yield self
        finally:
            self.disconnect()


class BaseSourceConnector(BaseConnector):
    """Base class for data source connectors that read data."""
    
    @abstractmethod
    def get_schema(self) -> Dict[str, str]:
        """
        Get the schema of the source data.
        
        Returns:
            Dict mapping column names to their data types
        """
        pass
    
    @abstractmethod
    def get_row_count(self) -> int:
        """
        Get the total number of rows available from the source.
        
        Returns:
            Total row count
        """
        pass
    
    @abstractmethod
    def read_data(self, batch_size: int = 1000, offset: int = 0) -> Iterator[List[Dict[str, Any]]]:
        """
        Read data from the source in batches.
        
        Args:
            batch_size: Number of rows to read per batch
            offset: Starting row offset
            
        Yields:
            Batches of rows as lists of dictionaries
        """
        pass
    
    def preview_data(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get a preview of the data for validation purposes.
        
        Args:
            limit: Maximum number of rows to preview
            
        Returns:
            List of sample rows
        """
        try:
            batch_iterator = self.read_data(batch_size=limit, offset=0)
            first_batch = next(batch_iterator, [])
            return first_batch[:limit]
        except Exception as e:
            self.logger.error(f"Error previewing data: {e}")
            return []


class BaseDestinationConnector(BaseConnector):
    """Base class for data destination connectors that write data."""
    
    @abstractmethod
    def get_schema(self) -> Dict[str, str]:
        """
        Get the schema of the destination.
        
        Returns:
            Dict mapping column names to their data types
        """
        pass
    
    @abstractmethod
    def create_table_if_not_exists(self, schema: Dict[str, str]) -> None:
        """
        Create the destination table if it doesn't exist.
        
        Args:
            schema: Dictionary mapping column names to data types
        """
        pass
    
    @abstractmethod
    def write_batch(self, rows: List[Dict[str, Any]], conflict_strategy: str = 'overwrite') -> int:
        """
        Write a batch of rows to the destination.
        
        Args:
            rows: List of row dictionaries to write
            conflict_strategy: How to handle conflicts ('overwrite', 'skip', 'fail', 'merge')
            
        Returns:
            Number of rows successfully written
        """
        pass
    
    @abstractmethod
    def begin_transaction(self) -> None:
        """Begin a database transaction."""
        pass
    
    @abstractmethod
    def commit_transaction(self) -> None:
        """Commit the current transaction."""
        pass
    
    @abstractmethod
    def rollback_transaction(self) -> None:
        """Rollback the current transaction."""
        pass
    
    @contextmanager
    def transaction_context(self):
        """Context manager for handling transactions safely."""
        try:
            self.begin_transaction()
            yield self
            self.commit_transaction()
        except Exception as e:
            self.logger.error(f"Transaction failed, rolling back: {e}")
            self.rollback_transaction()
            raise
    
    def validate_schema_compatibility(self, source_schema: Dict[str, str]) -> List[str]:
        """
        Validate that source schema is compatible with destination.
        
        Args:
            source_schema: Schema from the source connector
            
        Returns:
            List of validation warnings/errors
        """
        warnings = []
        try:
            dest_schema = self.get_schema()
            
            # Check for missing columns in destination
            missing_columns = set(source_schema.keys()) - set(dest_schema.keys())
            if missing_columns:
                warnings.append(f"Missing columns in destination: {', '.join(missing_columns)}")
            
            # Check for type mismatches (basic check)
            for col_name in source_schema:
                if col_name in dest_schema:
                    source_type = source_schema[col_name].lower()
                    dest_type = dest_schema[col_name].lower()
                    if source_type != dest_type:
                        warnings.append(f"Type mismatch for column '{col_name}': source={source_type}, dest={dest_type}")
        
        except Exception as e:
            warnings.append(f"Error validating schema compatibility: {e}")
        
        return warnings
