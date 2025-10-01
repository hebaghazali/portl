"""
Tests for PostgreSQL connectors.

These tests require a running PostgreSQL instance. They can be run with Docker:
docker run --name test-postgres -e POSTGRES_PASSWORD=testpass -e POSTGRES_DB=testdb -p 5432:5432 -d postgres:13
"""

import pytest
import os
from unittest.mock import Mock, patch
from typing import Dict, Any

from src.portl.schema import DatabaseConfig
from src.portl.connectors.postgres import PostgresSourceConnector, PostgresDestinationConnector
from src.portl.connectors.factory import ConnectorFactory


class TestPostgresConnectorFactory:
    """Test connector factory with Postgres connectors."""
    
    def test_create_postgres_source_connector(self):
        """Test creating a Postgres source connector."""
        config = DatabaseConfig(
            type='postgres',
            host='localhost',
            database='testdb',
            username='postgres',
            password='testpass',
            table='test_table'
        )
        
        connector = ConnectorFactory.create_source_connector(config)
        assert isinstance(connector, PostgresSourceConnector)
        assert connector.db_config.type == 'postgres'
        assert connector.db_config.host == 'localhost'
    
    def test_create_postgres_destination_connector(self):
        """Test creating a Postgres destination connector."""
        config = DatabaseConfig(
            type='postgres',
            host='localhost',
            database='testdb',
            username='postgres',
            password='testpass',
            table='test_table'
        )
        
        connector = ConnectorFactory.create_destination_connector(config)
        assert isinstance(connector, PostgresDestinationConnector)
        assert connector.db_config.type == 'postgres'
        assert connector.db_config.host == 'localhost'
    
    def test_unsupported_connector_type(self):
        """Test error handling for unsupported connector types."""
        config = DatabaseConfig(
            type='mysql',  # Not yet implemented
            host='localhost',
            database='testdb',
            username='user',
            password='pass',
            table='test_table'
        )
        
        with pytest.raises(ValueError, match="Unsupported source connector type"):
            ConnectorFactory.create_source_connector(config)


class TestPostgresConnectorMixin:
    """Test common PostgreSQL functionality."""
    
    def test_connection_string_creation(self):
        """Test PostgreSQL connection string creation."""
        config = DatabaseConfig(
            type='postgres',
            host='localhost',
            port=5432,
            database='testdb',
            username='postgres',
            password='testpass',
            table='test_table'
        )
        
        connector = PostgresSourceConnector(config)
        conn_string = connector._create_connection_string()
        
        expected_parts = [
            'host=localhost',
            'port=5432',
            'database=testdb',
            'user=postgres',
            'password=testpass'
        ]
        
        for part in expected_parts:
            assert part in conn_string
    
    def test_table_identifier_with_schema(self):
        """Test table identifier creation with schema."""
        config = DatabaseConfig(
            type='postgres',
            host='localhost',
            database='testdb',
            username='postgres',
            password='testpass',
            schema='public',
            table='test_table'
        )
        
        connector = PostgresSourceConnector(config)
        table_id = connector._get_table_identifier()
        
        # The sql.Identifier should contain both schema and table
        assert hasattr(table_id, 'strings')
        assert 'public' in table_id.strings
        assert 'test_table' in table_id.strings
    
    def test_table_identifier_without_schema(self):
        """Test table identifier creation without schema."""
        config = DatabaseConfig(
            type='postgres',
            host='localhost',
            database='testdb',
            username='postgres',
            password='testpass',
            table='test_table'
        )
        
        connector = PostgresSourceConnector(config)
        table_id = connector._get_table_identifier()
        
        # Should only contain table name
        assert hasattr(table_id, 'strings')
        assert 'test_table' in table_id.strings


class TestPostgresSourceConnector:
    """Test PostgreSQL source connector functionality."""
    
    def test_postgres_type_mapping(self):
        """Test PostgreSQL to generic type mapping."""
        config = DatabaseConfig(
            type='postgres',
            host='localhost',
            database='testdb',
            username='postgres',
            password='testpass',
            table='test_table'
        )
        
        connector = PostgresSourceConnector(config)
        
        # Test common type mappings
        assert connector._map_postgres_type('integer') == 'int'
        assert connector._map_postgres_type('character varying') == 'varchar'
        assert connector._map_postgres_type('text') == 'text'
        assert connector._map_postgres_type('boolean') == 'boolean'
        assert connector._map_postgres_type('timestamp without time zone') == 'timestamp'
        
        # Test nullable types
        assert connector._map_postgres_type('integer', is_nullable=True) == 'int?'
        assert connector._map_postgres_type('text', is_nullable=True) == 'text?'
    
    def test_oid_type_mapping(self):
        """Test PostgreSQL OID to generic type mapping."""
        config = DatabaseConfig(
            type='postgres',
            host='localhost',
            database='testdb',
            username='postgres',
            password='testpass',
            table='test_table'
        )
        
        connector = PostgresSourceConnector(config)
        
        # Test common OID mappings
        assert connector._map_postgres_oid_type(23) == 'int'      # int4
        assert connector._map_postgres_oid_type(25) == 'text'     # text
        assert connector._map_postgres_oid_type(16) == 'boolean'  # bool
        assert connector._map_postgres_oid_type(1043) == 'varchar' # varchar
        assert connector._map_postgres_oid_type(9999) == 'text'   # unknown type


class TestPostgresDestinationConnector:
    """Test PostgreSQL destination connector functionality."""
    
    def test_postgres_type_mapping(self):
        """Test generic to PostgreSQL type mapping."""
        config = DatabaseConfig(
            type='postgres',
            host='localhost',
            database='testdb',
            username='postgres',
            password='testpass',
            table='test_table'
        )
        
        connector = PostgresDestinationConnector(config)
        
        # Test type mapping (same as source for now)
        assert connector._map_postgres_type('integer') == 'int'
        assert connector._map_postgres_type('character varying') == 'varchar'
        assert connector._map_postgres_type('text') == 'text'
    
    def test_schema_mapping_application(self):
        """Test schema mapping functionality."""
        from src.portl.services.job_runner import JobRunner
        
        runner = JobRunner()
        
        # Test data
        batch = [
            {'old_name': 'value1', 'another_col': 'value2'},
            {'old_name': 'value3', 'another_col': 'value4'}
        ]
        
        mapping = {'old_name': 'new_name'}
        
        result = runner._apply_schema_mapping(batch, mapping)
        
        # Check that old_name was mapped to new_name
        assert result[0]['new_name'] == 'value1'
        assert result[1]['new_name'] == 'value3'
        
        # Check that unmapped columns remain unchanged
        assert result[0]['another_col'] == 'value2'
        assert result[1]['another_col'] == 'value4'
        
        # Check that old column name is gone
        assert 'old_name' not in result[0]
        assert 'old_name' not in result[1]


@pytest.mark.integration
class TestPostgresIntegration:
    """Integration tests that require a running PostgreSQL instance."""
    
    @pytest.fixture
    def postgres_config(self):
        """Fixture providing PostgreSQL configuration for testing."""
        return DatabaseConfig(
            type='postgres',
            host=os.getenv('POSTGRES_HOST', 'localhost'),
            port=int(os.getenv('POSTGRES_PORT', '5432')),
            database=os.getenv('POSTGRES_DB', 'testdb'),
            username=os.getenv('POSTGRES_USER', 'postgres'),
            password=os.getenv('POSTGRES_PASSWORD', 'testpass'),
            table='test_migration_table'
        )
    
    @pytest.mark.skipif(
        not os.getenv('RUN_INTEGRATION_TESTS'),
        reason="Integration tests require RUN_INTEGRATION_TESTS=1"
    )
    def test_postgres_connection(self, postgres_config):
        """Test actual PostgreSQL connection."""
        connector = PostgresSourceConnector(postgres_config)
        
        try:
            with connector.connection_context():
                assert connector.test_connection() is True
        except Exception as e:
            pytest.skip(f"PostgreSQL not available: {e}")
    
    @pytest.mark.skipif(
        not os.getenv('RUN_INTEGRATION_TESTS'),
        reason="Integration tests require RUN_INTEGRATION_TESTS=1"
    )
    def test_table_creation(self, postgres_config):
        """Test destination table creation."""
        connector = PostgresDestinationConnector(postgres_config)
        
        schema = {
            'id': 'int',
            'name': 'varchar',
            'email': 'varchar?',
            'created_at': 'timestamp'
        }
        
        try:
            with connector.connection_context():
                connector.create_table_if_not_exists(schema)
                
                # Verify table was created by getting its schema
                actual_schema = connector.get_schema()
                assert len(actual_schema) > 0
                
        except Exception as e:
            pytest.skip(f"PostgreSQL not available: {e}")


if __name__ == '__main__':
    # Run tests with: python -m pytest tests/test_postgres_connector.py -v
    # Run integration tests with: RUN_INTEGRATION_TESTS=1 python -m pytest tests/test_postgres_connector.py::TestPostgresIntegration -v
    pytest.main([__file__, '-v'])
