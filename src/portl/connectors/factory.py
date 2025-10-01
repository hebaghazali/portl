"""
Connector factory for creating source and destination connectors.

This module provides a factory pattern for instantiating the appropriate
connector classes based on configuration type.
"""

from typing import Union, Dict, Any
import logging

from .base import BaseSourceConnector, BaseDestinationConnector
from .postgres import PostgresSourceConnector, PostgresDestinationConnector
from .csv import CsvSourceConnector, CsvDestinationConnector
from ..schema import DatabaseConfig, CsvConfig, GoogleSheetsConfig, SourceConfig, DestinationConfig

logger = logging.getLogger(__name__)


class ConnectorFactory:
    """Factory for creating connector instances from configuration."""
    
    # Registry of available source connectors
    SOURCE_CONNECTORS = {
        'postgres': PostgresSourceConnector,
        'csv': CsvSourceConnector,
        # Future connectors will be added here
        # 'mysql': MySqlSourceConnector,
        # 'google_sheets': GoogleSheetsSourceConnector,
    }
    
    # Registry of available destination connectors
    DESTINATION_CONNECTORS = {
        'postgres': PostgresDestinationConnector,
        'csv': CsvDestinationConnector,
        # Future connectors will be added here
        # 'mysql': MySqlDestinationConnector,
        # 'google_sheets': GoogleSheetsDestinationConnector,
    }
    
    @classmethod
    def create_source_connector(cls, config: SourceConfig) -> BaseSourceConnector:
        """
        Create a source connector from configuration.
        
        Args:
            config: Source configuration object
            
        Returns:
            Configured source connector instance
            
        Raises:
            ValueError: If connector type is not supported
            TypeError: If configuration type is invalid
        """
        connector_type = cls._get_connector_type(config)
        
        if connector_type not in cls.SOURCE_CONNECTORS:
            available_types = ', '.join(cls.SOURCE_CONNECTORS.keys())
            raise ValueError(
                f"Unsupported source connector type: {connector_type}. "
                f"Available types: {available_types}"
            )
        
        connector_class = cls.SOURCE_CONNECTORS[connector_type]
        
        try:
            connector = connector_class(config)
            logger.info(f"Created {connector_type} source connector")
            return connector
            
        except Exception as e:
            logger.error(f"Failed to create {connector_type} source connector: {e}")
            raise
    
    @classmethod
    def create_destination_connector(cls, config: DestinationConfig) -> BaseDestinationConnector:
        """
        Create a destination connector from configuration.
        
        Args:
            config: Destination configuration object
            
        Returns:
            Configured destination connector instance
            
        Raises:
            ValueError: If connector type is not supported
            TypeError: If configuration type is invalid
        """
        connector_type = cls._get_connector_type(config)
        
        if connector_type not in cls.DESTINATION_CONNECTORS:
            available_types = ', '.join(cls.DESTINATION_CONNECTORS.keys())
            raise ValueError(
                f"Unsupported destination connector type: {connector_type}. "
                f"Available types: {available_types}"
            )
        
        connector_class = cls.DESTINATION_CONNECTORS[connector_type]
        
        try:
            connector = connector_class(config)
            logger.info(f"Created {connector_type} destination connector")
            return connector
            
        except Exception as e:
            logger.error(f"Failed to create {connector_type} destination connector: {e}")
            raise
    
    @classmethod
    def _get_connector_type(cls, config: Union[SourceConfig, DestinationConfig]) -> str:
        """
        Extract connector type from configuration.
        
        Args:
            config: Configuration object
            
        Returns:
            Connector type string
            
        Raises:
            TypeError: If configuration type is not recognized
        """
        if isinstance(config, DatabaseConfig):
            return config.type
        elif isinstance(config, CsvConfig):
            return config.type
        elif isinstance(config, GoogleSheetsConfig):
            return config.type
        else:
            raise TypeError(f"Unknown configuration type: {type(config)}")
    
    @classmethod
    def get_available_source_types(cls) -> list[str]:
        """Get list of available source connector types."""
        return list(cls.SOURCE_CONNECTORS.keys())
    
    @classmethod
    def get_available_destination_types(cls) -> list[str]:
        """Get list of available destination connector types."""
        return list(cls.DESTINATION_CONNECTORS.keys())
    
    @classmethod
    def is_source_type_supported(cls, connector_type: str) -> bool:
        """Check if a source connector type is supported."""
        return connector_type in cls.SOURCE_CONNECTORS
    
    @classmethod
    def is_destination_type_supported(cls, connector_type: str) -> bool:
        """Check if a destination connector type is supported."""
        return connector_type in cls.DESTINATION_CONNECTORS
    
    @classmethod
    def register_source_connector(cls, connector_type: str, connector_class: type) -> None:
        """
        Register a new source connector type.
        
        Args:
            connector_type: String identifier for the connector
            connector_class: Connector class that implements BaseSourceConnector
            
        Raises:
            TypeError: If connector_class doesn't implement BaseSourceConnector
        """
        if not issubclass(connector_class, BaseSourceConnector):
            raise TypeError(
                f"Connector class must implement BaseSourceConnector, "
                f"got {connector_class.__name__}"
            )
        
        cls.SOURCE_CONNECTORS[connector_type] = connector_class
        logger.info(f"Registered source connector: {connector_type}")
    
    @classmethod
    def register_destination_connector(cls, connector_type: str, connector_class: type) -> None:
        """
        Register a new destination connector type.
        
        Args:
            connector_type: String identifier for the connector
            connector_class: Connector class that implements BaseDestinationConnector
            
        Raises:
            TypeError: If connector_class doesn't implement BaseDestinationConnector
        """
        if not issubclass(connector_class, BaseDestinationConnector):
            raise TypeError(
                f"Connector class must implement BaseDestinationConnector, "
                f"got {connector_class.__name__}"
            )
        
        cls.DESTINATION_CONNECTORS[connector_type] = connector_class
        logger.info(f"Registered destination connector: {connector_type}")


def test_connector_connection(config: Union[SourceConfig, DestinationConfig]) -> Dict[str, Any]:
    """
    Test connection for a given configuration.
    
    Args:
        config: Source or destination configuration
        
    Returns:
        Dictionary with test results including success status and any error messages
    """
    result = {
        'success': False,
        'connector_type': None,
        'error': None,
        'details': {}
    }
    
    try:
        connector_type = ConnectorFactory._get_connector_type(config)
        result['connector_type'] = connector_type
        
        # Try to create and test the connector
        if isinstance(config, (DatabaseConfig, CsvConfig, GoogleSheetsConfig)):
            # Determine if this should be a source or destination connector
            # For testing purposes, we'll try source first, then destination
            connector = None
            
            if ConnectorFactory.is_source_type_supported(connector_type):
                try:
                    connector = ConnectorFactory.create_source_connector(config)
                except Exception:
                    pass
            
            if not connector and ConnectorFactory.is_destination_type_supported(connector_type):
                try:
                    connector = ConnectorFactory.create_destination_connector(config)
                except Exception:
                    pass
            
            if not connector:
                raise ValueError(f"Could not create connector for type: {connector_type}")
            
            # Test the connection
            with connector.connection_context():
                success = connector.test_connection()
                result['success'] = success
                
                if success:
                    result['details']['message'] = 'Connection test successful'
                else:
                    result['details']['message'] = 'Connection test failed'
        
    except Exception as e:
        result['error'] = str(e)
        result['details']['exception_type'] = type(e).__name__
        logger.error(f"Connection test failed: {e}")
    
    return result
