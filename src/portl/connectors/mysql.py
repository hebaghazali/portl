"""
MySQL connector implementations for Portl.

This module provides MySQL source and destination connectors with
connection management, transaction support, and batch processing capabilities.
"""

import pymysql
import pymysql.cursors
from typing import Iterator, Dict, Any, List, Optional
import logging
from contextlib import contextmanager

from .base import BaseSourceConnector, BaseDestinationConnector
from ..schema import DatabaseConfig

logger = logging.getLogger(__name__)


class MySQLConnectorMixin:
    """Mixin class with common MySQL functionality."""
    
    def __init__(self, config: DatabaseConfig):
        """Initialize with database configuration."""
        super().__init__(config.__dict__)
        self.db_config = config
        self._connection = None
        
        # Validate that this is a mysql config
        if config.type != 'mysql':
            raise ValueError(f"Expected mysql config, got {config.type}")
    
    def _get_connection_params(self) -> Dict[str, Any]:
        """Get MySQL connection parameters from config."""
        return {
            'host': self.db_config.host,
            'port': self.db_config.port or 3306,
            'user': self.db_config.username,
            'password': self.db_config.password,
            'database': self.db_config.database,
            'charset': 'utf8mb4',
            'cursorclass': pymysql.cursors.DictCursor,
            'autocommit': False,
        }
    
    def _get_connection(self):
        """Get the current connection."""
        if self._connection:
            return self._connection
        else:
            raise RuntimeError("No connection available. Call connect() first.")
    
    def connect(self) -> None:
        """Establish connection to MySQL."""
        try:
            conn_params = self._get_connection_params()
            self._connection = pymysql.connect(**conn_params)
            
            self.logger.info(
                f"Connected to MySQL: {self.db_config.host}:{self.db_config.port or 3306}/"
                f"{self.db_config.database}"
            )
            
        except pymysql.Error as e:
            self.logger.error(f"Failed to connect to MySQL: {e}")
            raise ConnectionError(f"MySQL connection failed: {e}")
    
    def disconnect(self) -> None:
        """Close MySQL connection."""
        try:
            if self._connection:
                self._connection.close()
                self._connection = None
                self.logger.info("Disconnected from MySQL")
        except pymysql.Error as e:
            self.logger.error(f"Error disconnecting from MySQL: {e}")
    
    def test_connection(self) -> bool:
        """Test MySQL connection."""
        try:
            with self.connection_context():
                conn = self._get_connection()
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    result = cursor.fetchone()
                    return result is not None
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False
    
    def _execute_query(
        self, 
        query: str, 
        params: Optional[tuple] = None, 
        fetch: bool = True
    ) -> Optional[List[Dict[str, Any]]]:
        """Execute a query safely with error handling."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                if fetch:
                    return cursor.fetchall()
                return None
        except pymysql.Error as e:
            self.logger.error(f"Query execution failed: {e}")
            raise
    
    def _quote_identifier(self, identifier: str) -> str:
        """Quote a MySQL identifier (table/column name)."""
        # MySQL uses backticks for quoting
        return f"`{identifier}`"
    
    def _get_table_identifier(self) -> str:
        """Get properly quoted table identifier."""
        if self.db_config.schema:
            return f"{self._quote_identifier(self.db_config.schema)}.{self._quote_identifier(self.db_config.table)}"
        return self._quote_identifier(self.db_config.table)


class MySQLSourceConnector(MySQLConnectorMixin, BaseSourceConnector):
    """MySQL source connector for reading data."""
    
    def get_schema(self) -> Dict[str, str]:
        """Get table schema from MySQL information_schema."""
        if self.db_config.query:
            return self._get_query_schema()
        else:
            return self._get_table_schema()
    
    def _get_table_schema(self) -> Dict[str, str]:
        """Get schema for a specific table."""
        query = """
        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
        FROM information_schema.COLUMNS 
        WHERE TABLE_NAME = %s 
        AND TABLE_SCHEMA = %s
        ORDER BY ORDINAL_POSITION
        """
        
        try:
            rows = self._execute_query(
                query, 
                (self.db_config.table, self.db_config.database)
            )
            
            schema = {}
            for row in rows:
                col_name = row['COLUMN_NAME']
                data_type = row['DATA_TYPE']
                is_nullable = row['IS_NULLABLE'] == 'YES'
                
                schema[col_name] = self._map_mysql_type(data_type, is_nullable)
            
            return schema
            
        except pymysql.Error as e:
            self.logger.error(f"Failed to get table schema: {e}")
            raise
    
    def _get_query_schema(self) -> Dict[str, str]:
        """Get schema by analyzing query result."""
        query = f"SELECT * FROM ({self.db_config.query}) AS subquery LIMIT 0"
        
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(query)
                
                schema = {}
                if cursor.description:
                    for desc in cursor.description:
                        col_name = desc[0]
                        # MySQL cursor description doesn't include type easily
                        # We'll default to 'text' for query schemas
                        schema[col_name] = 'text'
                
                return schema
                
        except pymysql.Error as e:
            self.logger.error(f"Failed to analyze query schema: {e}")
            raise
    
    def _map_mysql_type(self, mysql_type: str, is_nullable: bool = False) -> str:
        """Map MySQL data types to generic types."""
        type_mapping = {
            'int': 'int',
            'integer': 'int',
            'bigint': 'bigint',
            'smallint': 'smallint',
            'tinyint': 'smallint',
            'mediumint': 'int',
            'decimal': 'decimal',
            'numeric': 'decimal',
            'float': 'float',
            'double': 'double',
            'varchar': 'varchar',
            'char': 'char',
            'text': 'text',
            'tinytext': 'text',
            'mediumtext': 'text',
            'longtext': 'text',
            'boolean': 'boolean',
            'bool': 'boolean',
            'date': 'date',
            'datetime': 'timestamp',
            'timestamp': 'timestamp',
            'time': 'time',
            'json': 'json',
            'blob': 'binary',
            'binary': 'binary',
            'varbinary': 'binary',
        }
        
        generic_type = type_mapping.get(mysql_type.lower(), 'text')
        return f"{generic_type}{'?' if is_nullable else ''}"
    
    def get_row_count(self) -> int:
        """Get total row count from source."""
        if self.db_config.query:
            query = f"SELECT COUNT(*) as count FROM ({self.db_config.query}) AS subquery"
        else:
            table_id = self._get_table_identifier()
            query = f"SELECT COUNT(*) as count FROM {table_id}"
        
        try:
            result = self._execute_query(query)
            return result[0]['count'] if result else 0
        except pymysql.Error as e:
            self.logger.error(f"Failed to get row count: {e}")
            raise
    
    def read_data(self, batch_size: int = 1000, offset: int = 0) -> Iterator[List[Dict[str, Any]]]:
        """Read data in batches from MySQL."""
        if self.db_config.query:
            base_query = f"SELECT * FROM ({self.db_config.query}) AS subquery"
        else:
            table_id = self._get_table_identifier()
            base_query = f"SELECT * FROM {table_id}"
        
        current_offset = offset
        
        while True:
            paginated_query = f"{base_query} LIMIT %s OFFSET %s"
            params = (batch_size, current_offset)
            
            try:
                rows = self._execute_query(paginated_query, params)
                
                if not rows:
                    break
                
                # Convert to regular dicts (already DictCursor)
                batch = [dict(row) for row in rows]
                yield batch
                
                if len(batch) < batch_size:
                    break
                
                current_offset += batch_size
                
            except pymysql.Error as e:
                self.logger.error(f"Failed to read data batch at offset {current_offset}: {e}")
                raise


class MySQLDestinationConnector(MySQLConnectorMixin, BaseDestinationConnector):
    """MySQL destination connector for writing data."""
    
    def get_schema(self) -> Dict[str, str]:
        """Get destination table schema."""
        return self._get_table_schema()
    
    def _get_table_schema(self) -> Dict[str, str]:
        """Get schema for the destination table."""
        query = """
        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
        FROM information_schema.COLUMNS 
        WHERE TABLE_NAME = %s 
        AND TABLE_SCHEMA = %s
        ORDER BY ORDINAL_POSITION
        """
        
        try:
            rows = self._execute_query(
                query, 
                (self.db_config.table, self.db_config.database)
            )
            
            schema = {}
            for row in rows:
                col_name = row['COLUMN_NAME']
                data_type = row['DATA_TYPE']
                is_nullable = row['IS_NULLABLE'] == 'YES'
                
                schema[col_name] = self._map_mysql_type(data_type, is_nullable)
            
            return schema
            
        except pymysql.Error as e:
            self.logger.warning(f"Could not get table schema (table may not exist): {e}")
            return {}
    
    def _map_mysql_type(self, mysql_type: str, is_nullable: bool = False) -> str:
        """Map MySQL data types to generic types."""
        type_mapping = {
            'int': 'int',
            'integer': 'int',
            'bigint': 'bigint',
            'smallint': 'smallint',
            'tinyint': 'smallint',
            'mediumint': 'int',
            'decimal': 'decimal',
            'numeric': 'decimal',
            'float': 'float',
            'double': 'double',
            'varchar': 'varchar',
            'char': 'char',
            'text': 'text',
            'tinytext': 'text',
            'mediumtext': 'text',
            'longtext': 'text',
            'boolean': 'boolean',
            'bool': 'boolean',
            'date': 'date',
            'datetime': 'timestamp',
            'timestamp': 'timestamp',
            'time': 'time',
            'json': 'json',
            'blob': 'binary',
            'binary': 'binary',
            'varbinary': 'binary',
        }
        
        generic_type = type_mapping.get(mysql_type.lower(), 'text')
        return f"{generic_type}{'?' if is_nullable else ''}"
    
    def create_table_if_not_exists(self, schema: Dict[str, str]) -> None:
        """Create destination table if it doesn't exist."""
        if not schema:
            raise ValueError("Cannot create table without schema definition")
        
        # Map generic types to MySQL types
        mysql_type_mapping = {
            'int': 'INT',
            'bigint': 'BIGINT',
            'smallint': 'SMALLINT',
            'decimal': 'DECIMAL(10,2)',
            'float': 'FLOAT',
            'double': 'DOUBLE',
            'varchar': 'VARCHAR(255)',
            'char': 'CHAR(1)',
            'text': 'TEXT',
            'boolean': 'BOOLEAN',
            'date': 'DATE',
            'timestamp': 'DATETIME',
            'timestamptz': 'DATETIME',
            'time': 'TIME',
            'json': 'JSON',
            'uuid': 'CHAR(36)',
            'binary': 'BLOB',
        }
        
        # Build column definitions
        column_defs = []
        for col_name, col_type in schema.items():
            is_nullable = col_type.endswith('?')
            base_type = col_type.rstrip('?')
            
            mysql_type = mysql_type_mapping.get(base_type, 'TEXT')
            nullable_clause = '' if is_nullable else ' NOT NULL'
            
            column_defs.append(
                f"{self._quote_identifier(col_name)} {mysql_type}{nullable_clause}"
            )
        
        table_id = self._get_table_identifier()
        create_query = f"""
            CREATE TABLE IF NOT EXISTS {table_id} ({', '.join(column_defs)})
            ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
        
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(create_query)
            conn.commit()
            self.logger.info(f"Created table {table_id}")
            
        except pymysql.Error as e:
            self.logger.error(f"Failed to create table: {e}")
            raise
    
    def write_batch(
        self, 
        rows: List[Dict[str, Any]], 
        conflict_strategy: str = 'overwrite',
        key_columns: Optional[List[str]] = None
    ) -> int:
        """Write a batch of rows to MySQL."""
        if not rows:
            return 0
        
        grouped_rows = self._group_rows_by_operation(rows)
        total_processed = 0
        
        try:
            conn = self._get_connection()
            
            if grouped_rows['insert']:
                total_processed += self._execute_inserts(
                    conn, grouped_rows['insert'], conflict_strategy
                )
            
            if grouped_rows['update']:
                if not key_columns:
                    raise ValueError("key_columns must be specified for update operations")
                total_processed += self._execute_updates(
                    conn, grouped_rows['update'], key_columns
                )
            
            if grouped_rows['delete']:
                if not key_columns:
                    raise ValueError("key_columns must be specified for delete operations")
                total_processed += self._execute_deletes(
                    conn, grouped_rows['delete'], key_columns
                )
            
            return total_processed
                
        except pymysql.Error as e:
            self.logger.error(f"Failed to write batch: {e}")
            raise
    
    def _build_insert_query(self, columns: List[str]) -> str:
        """Build a basic INSERT query."""
        table_id = self._get_table_identifier()
        col_list = ', '.join([self._quote_identifier(c) for c in columns])
        placeholders = ', '.join(['%s'] * len(columns))
        
        return f"INSERT INTO {table_id} ({col_list}) VALUES ({placeholders})"
    
    def _build_insert_ignore_query(self, columns: List[str]) -> str:
        """Build INSERT IGNORE query."""
        table_id = self._get_table_identifier()
        col_list = ', '.join([self._quote_identifier(c) for c in columns])
        placeholders = ', '.join(['%s'] * len(columns))
        
        return f"INSERT IGNORE INTO {table_id} ({col_list}) VALUES ({placeholders})"
    
    def _build_upsert_query(self, columns: List[str]) -> str:
        """Build INSERT ... ON DUPLICATE KEY UPDATE query."""
        table_id = self._get_table_identifier()
        col_list = ', '.join([self._quote_identifier(c) for c in columns])
        placeholders = ', '.join(['%s'] * len(columns))
        
        # ON DUPLICATE KEY UPDATE col=VALUES(col), ...
        update_list = ', '.join([
            f"{self._quote_identifier(c)}=VALUES({self._quote_identifier(c)})"
            for c in columns
        ])
        
        return f"""
            INSERT INTO {table_id} ({col_list}) 
            VALUES ({placeholders}) 
            ON DUPLICATE KEY UPDATE {update_list}
        """
    
    def _execute_inserts(
        self, 
        conn, 
        rows: List[Dict[str, Any]], 
        conflict_strategy: str
    ) -> int:
        """Execute insert operations."""
        if not rows:
            return 0
        
        columns = list(rows[0].keys())
        
        if conflict_strategy == 'overwrite':
            insert_query = self._build_upsert_query(columns)
        elif conflict_strategy == 'skip':
            insert_query = self._build_insert_ignore_query(columns)
        elif conflict_strategy == 'fail':
            insert_query = self._build_insert_query(columns)
        else:
            raise ValueError(f"Unsupported conflict strategy: {conflict_strategy}")
        
        with conn.cursor() as cursor:
            values_list = []
            for row in rows:
                values = tuple(row.get(col) for col in columns)
                values_list.append(values)
            
            cursor.executemany(insert_query, values_list)
            
        self.logger.info(f"Inserted {len(rows)} rows")
        return len(rows)
    
    def _execute_updates(
        self, 
        conn, 
        rows: List[Dict[str, Any]], 
        key_columns: List[str]
    ) -> int:
        """Execute update operations."""
        if not rows:
            return 0
        
        columns = list(rows[0].keys())
        update_columns = [col for col in columns if col not in key_columns]
        
        if not update_columns:
            self.logger.warning("No columns to update (all columns are key columns)")
            return 0
        
        update_query = self._build_update_query(update_columns, key_columns)
        
        with conn.cursor() as cursor:
            updated_count = 0
            for row in rows:
                update_values = [row.get(col) for col in update_columns]
                key_values = [row.get(col) for col in key_columns]
                values = tuple(update_values + key_values)
                
                cursor.execute(update_query, values)
                updated_count += cursor.rowcount
            
        self.logger.info(f"Updated {updated_count} rows")
        return updated_count
    
    def _execute_deletes(
        self, 
        conn, 
        rows: List[Dict[str, Any]], 
        key_columns: List[str]
    ) -> int:
        """Execute delete operations."""
        if not rows:
            return 0
        
        delete_query = self._build_delete_query(key_columns)
        
        with conn.cursor() as cursor:
            deleted_count = 0
            for row in rows:
                key_values = tuple(row.get(col) for col in key_columns)
                cursor.execute(delete_query, key_values)
                deleted_count += cursor.rowcount
            
        self.logger.info(f"Deleted {deleted_count} rows")
        return deleted_count
    
    def _build_update_query(
        self, 
        update_columns: List[str], 
        key_columns: List[str]
    ) -> str:
        """Build UPDATE query with WHERE clause."""
        table_id = self._get_table_identifier()
        
        set_clause = ', '.join([
            f"{self._quote_identifier(col)} = %s" for col in update_columns
        ])
        
        where_clause = ' AND '.join([
            f"{self._quote_identifier(col)} = %s" for col in key_columns
        ])
        
        return f"UPDATE {table_id} SET {set_clause} WHERE {where_clause}"
    
    def _build_delete_query(self, key_columns: List[str]) -> str:
        """Build DELETE query with WHERE clause."""
        table_id = self._get_table_identifier()
        
        where_clause = ' AND '.join([
            f"{self._quote_identifier(col)} = %s" for col in key_columns
        ])
        
        return f"DELETE FROM {table_id} WHERE {where_clause}"
    
    def begin_transaction(self) -> None:
        """Begin a database transaction."""
        conn = self._get_connection()
        conn.begin()
    
    def commit_transaction(self) -> None:
        """Commit the current transaction."""
        conn = self._get_connection()
        conn.commit()
    
    def rollback_transaction(self) -> None:
        """Rollback the current transaction."""
        conn = self._get_connection()
        conn.rollback()


