"""
Tests for MySQL connector implementation.

These tests require a MySQL database to be running.
Run with: docker-compose -f docker-compose.test.yml up -d mysql
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from portl.schema import DatabaseConfig


# Skip tests if pymysql is not installed
pymysql = pytest.importorskip("pymysql")


class TestMySQLConnectorUnit:
    """Unit tests for MySQL connector (no database required)."""
    
    @pytest.fixture
    def mysql_config(self):
        """Create a MySQL database config."""
        return DatabaseConfig(
            type='mysql',
            host='localhost',
            port=3306,
            database='portl_test',
            username='root',
            password='test',
            table='test_table',
        )
    
    def test_connector_validates_config_type(self, mysql_config):
        """Verify connector rejects non-mysql config."""
        from portl.connectors.mysql import MySQLSourceConnector
        
        # Valid mysql config should work
        connector = MySQLSourceConnector(mysql_config)
        assert connector.db_config.type == 'mysql'
        
        # Invalid config type should fail
        mysql_config.type = 'postgres'
        with pytest.raises(ValueError) as exc_info:
            MySQLSourceConnector(mysql_config)
        assert 'Expected mysql config' in str(exc_info.value)
    
    def test_get_connection_params(self, mysql_config):
        """Verify connection parameters are built correctly."""
        from portl.connectors.mysql import MySQLSourceConnector
        
        connector = MySQLSourceConnector(mysql_config)
        params = connector._get_connection_params()
        
        assert params['host'] == 'localhost'
        assert params['port'] == 3306
        assert params['user'] == 'root'
        assert params['password'] == 'test'
        assert params['database'] == 'portl_test'
        assert params['charset'] == 'utf8mb4'
    
    def test_quote_identifier(self, mysql_config):
        """Verify MySQL identifiers are quoted correctly."""
        from portl.connectors.mysql import MySQLSourceConnector
        
        connector = MySQLSourceConnector(mysql_config)
        
        assert connector._quote_identifier('table') == '`table`'
        assert connector._quote_identifier('column_name') == '`column_name`'
    
    def test_table_identifier(self, mysql_config):
        """Verify table identifier is built correctly."""
        from portl.connectors.mysql import MySQLSourceConnector
        
        connector = MySQLSourceConnector(mysql_config)
        
        # Without schema
        assert connector._get_table_identifier() == '`test_table`'
        
        # With schema
        mysql_config.schema = 'myschema'
        connector2 = MySQLSourceConnector(mysql_config)
        assert connector2._get_table_identifier() == '`myschema`.`test_table`'
    
    def test_type_mapping(self, mysql_config):
        """Verify MySQL types are mapped correctly."""
        from portl.connectors.mysql import MySQLSourceConnector
        
        connector = MySQLSourceConnector(mysql_config)
        
        # Test various MySQL types
        assert connector._map_mysql_type('int', False) == 'int'
        assert connector._map_mysql_type('varchar', False) == 'varchar'
        assert connector._map_mysql_type('datetime', False) == 'timestamp'
        assert connector._map_mysql_type('json', False) == 'json'
        
        # Test nullable types
        assert connector._map_mysql_type('int', True) == 'int?'
        assert connector._map_mysql_type('text', True) == 'text?'


class TestMySQLDestinationConnectorUnit:
    """Unit tests for MySQL destination connector."""
    
    @pytest.fixture
    def mysql_config(self):
        return DatabaseConfig(
            type='mysql',
            host='localhost',
            port=3306,
            database='portl_test',
            username='root',
            password='test',
            table='test_table',
        )
    
    def test_build_insert_query(self, mysql_config):
        """Verify INSERT query is built correctly."""
        from portl.connectors.mysql import MySQLDestinationConnector
        
        connector = MySQLDestinationConnector(mysql_config)
        query = connector._build_insert_query(['id', 'name', 'email'])
        
        assert 'INSERT INTO' in query
        assert '`id`' in query
        assert '`name`' in query
        assert '`email`' in query
        assert 'VALUES (%s, %s, %s)' in query
    
    def test_build_insert_ignore_query(self, mysql_config):
        """Verify INSERT IGNORE query is built correctly."""
        from portl.connectors.mysql import MySQLDestinationConnector
        
        connector = MySQLDestinationConnector(mysql_config)
        query = connector._build_insert_ignore_query(['id', 'name'])
        
        assert 'INSERT IGNORE INTO' in query
    
    def test_build_upsert_query(self, mysql_config):
        """Verify INSERT ON DUPLICATE KEY UPDATE query is built correctly."""
        from portl.connectors.mysql import MySQLDestinationConnector
        
        connector = MySQLDestinationConnector(mysql_config)
        query = connector._build_upsert_query(['id', 'name', 'email'])
        
        assert 'INSERT INTO' in query
        assert 'ON DUPLICATE KEY UPDATE' in query
        assert '`id`=VALUES(`id`)' in query
        assert '`name`=VALUES(`name`)' in query
    
    def test_build_update_query(self, mysql_config):
        """Verify UPDATE query is built correctly."""
        from portl.connectors.mysql import MySQLDestinationConnector
        
        connector = MySQLDestinationConnector(mysql_config)
        query = connector._build_update_query(['name', 'email'], ['id'])
        
        assert 'UPDATE' in query
        assert 'SET' in query
        assert '`name` = %s' in query
        assert 'WHERE' in query
        assert '`id` = %s' in query
    
    def test_build_delete_query(self, mysql_config):
        """Verify DELETE query is built correctly."""
        from portl.connectors.mysql import MySQLDestinationConnector
        
        connector = MySQLDestinationConnector(mysql_config)
        query = connector._build_delete_query(['id'])
        
        assert 'DELETE FROM' in query
        assert 'WHERE' in query
        assert '`id` = %s' in query


class TestMySQLConnectorIntegration:
    """
    Integration tests for MySQL connector.
    
    These tests require a running MySQL instance.
    Skip if MySQL is not available.
    """
    
    @pytest.fixture
    def mysql_config(self):
        return DatabaseConfig(
            type='mysql',
            host='localhost',
            port=3306,
            database='portl_test',
            username='root',
            password='test',
            table='test_users',
        )
    
    @pytest.fixture
    def mysql_connection(self, mysql_config):
        """
        Create MySQL connection for testing.
        
        Skip test if MySQL is not available.
        """
        try:
            from portl.connectors.mysql import MySQLDestinationConnector
            
            connector = MySQLDestinationConnector(mysql_config)
            connector.connect()
            
            # Create test table
            conn = connector._get_connection()
            with conn.cursor() as cursor:
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS test_users (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        email VARCHAR(255) UNIQUE NOT NULL,
                        name VARCHAR(255),
                        age INT
                    ) ENGINE=InnoDB
                """)
            conn.commit()
            
            yield connector
            
            # Cleanup
            with conn.cursor() as cursor:
                cursor.execute("DROP TABLE IF EXISTS test_users")
            conn.commit()
            connector.disconnect()
            
        except Exception as e:
            pytest.skip(f"MySQL not available: {e}")
    
    @pytest.mark.integration
    def test_connection(self, mysql_connection):
        """Test MySQL connection works."""
        assert mysql_connection._connection is not None
    
    @pytest.mark.integration
    def test_insert_row(self, mysql_connection):
        """Test single row insert."""
        rows = [{'email': 'test@example.com', 'name': 'Test User', 'age': 30}]
        
        count = mysql_connection._execute_inserts(
            mysql_connection._get_connection(),
            rows,
            'fail'
        )
        mysql_connection._get_connection().commit()
        
        assert count == 1
    
    @pytest.mark.integration
    def test_insert_batch(self, mysql_connection):
        """Test batch insert."""
        rows = [
            {'email': 'user1@example.com', 'name': 'User 1', 'age': 25},
            {'email': 'user2@example.com', 'name': 'User 2', 'age': 30},
            {'email': 'user3@example.com', 'name': 'User 3', 'age': 35},
        ]
        
        count = mysql_connection._execute_inserts(
            mysql_connection._get_connection(),
            rows,
            'fail'
        )
        mysql_connection._get_connection().commit()
        
        assert count == 3
    
    @pytest.mark.integration
    def test_upsert_insert_new(self, mysql_connection):
        """Upsert inserts new row when no conflict."""
        rows = [{'email': 'new@example.com', 'name': 'New User', 'age': 40}]
        
        count = mysql_connection._execute_inserts(
            mysql_connection._get_connection(),
            rows,
            'overwrite'  # Uses ON DUPLICATE KEY UPDATE
        )
        mysql_connection._get_connection().commit()
        
        assert count == 1
    
    @pytest.mark.integration
    def test_upsert_update_existing(self, mysql_connection):
        """Upsert updates existing row on conflict."""
        conn = mysql_connection._get_connection()
        
        # First insert
        rows = [{'email': 'update@example.com', 'name': 'Original', 'age': 20}]
        mysql_connection._execute_inserts(conn, rows, 'fail')
        conn.commit()
        
        # Then upsert with same email
        rows = [{'email': 'update@example.com', 'name': 'Updated', 'age': 21}]
        mysql_connection._execute_inserts(conn, rows, 'overwrite')
        conn.commit()
        
        # Verify update
        with conn.cursor() as cursor:
            cursor.execute("SELECT name, age FROM test_users WHERE email = %s", 
                          ('update@example.com',))
            result = cursor.fetchone()
        
        assert result['name'] == 'Updated'
        assert result['age'] == 21
    
    @pytest.mark.integration
    def test_transaction_commit(self, mysql_connection):
        """Transaction commits properly."""
        conn = mysql_connection._get_connection()
        
        mysql_connection.begin_transaction()
        
        rows = [{'email': 'commit@example.com', 'name': 'Commit Test', 'age': 50}]
        mysql_connection._execute_inserts(conn, rows, 'fail')
        
        mysql_connection.commit_transaction()
        
        # Verify row exists
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as cnt FROM test_users WHERE email = %s",
                          ('commit@example.com',))
            result = cursor.fetchone()
        
        assert result['cnt'] == 1
    
    @pytest.mark.integration
    def test_transaction_rollback(self, mysql_connection):
        """Transaction rollback works."""
        conn = mysql_connection._get_connection()
        
        mysql_connection.begin_transaction()
        
        rows = [{'email': 'rollback@example.com', 'name': 'Rollback Test', 'age': 50}]
        mysql_connection._execute_inserts(conn, rows, 'fail')
        
        mysql_connection.rollback_transaction()
        
        # Verify row does not exist
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) as cnt FROM test_users WHERE email = %s",
                          ('rollback@example.com',))
            result = cursor.fetchone()
        
        assert result['cnt'] == 0


# Run tests if executed directly
if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'not integration'])

