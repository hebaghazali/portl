"""
PostgreSQL connector implementations for Portl.

This module provides PostgreSQL source and destination connectors with
connection pooling, transaction support, and batch processing capabilities.
"""

import psycopg2
import psycopg2.extras
import psycopg2.pool
from psycopg2 import sql
from typing import Iterator, Dict, Any, List, Optional, Union
import logging
from contextlib import contextmanager

from .base import BaseSourceConnector, BaseDestinationConnector
from ..schema import DatabaseConfig

logger = logging.getLogger(__name__)


class PostgresConnectorMixin:
    """Mixin class with common PostgreSQL functionality."""
    
    def __init__(self, config: DatabaseConfig):
        """Initialize with database configuration."""
        super().__init__(config.__dict__)
        self.db_config = config
        self._connection_pool = None
        self._connection = None
        
        # Validate that this is a postgres config
        if config.type != 'postgres':
            raise ValueError(f"Expected postgres config, got {config.type}")
    
    def _create_connection_string(self) -> str:
        """Create PostgreSQL connection string from config."""
        conn_params = {
            'host': self.db_config.host,
            'port': self.db_config.port,
            'database': self.db_config.database,
            'user': self.db_config.username,
            'password': self.db_config.password
        }
        
        # Build connection string
        conn_string = ' '.join([f"{k}={v}" for k, v in conn_params.items() if v is not None])
        return conn_string
    
    def _get_connection(self):
        """Get a connection from the pool or create a new one."""
        if self._connection_pool:
            return self._connection_pool.getconn()
        elif self._connection:
            return self._connection
        else:
            raise RuntimeError("No connection available. Call connect() first.")
    
    def _return_connection(self, conn):
        """Return a connection to the pool."""
        if self._connection_pool:
            self._connection_pool.putconn(conn)
    
    def connect(self) -> None:
        """Establish connection to PostgreSQL."""
        try:
            conn_string = self._create_connection_string()
            
            # For production use, we'd want connection pooling
            # For now, use a simple connection
            self._connection = psycopg2.connect(conn_string)
            self._connection.autocommit = False
            
            self.logger.info(f"Connected to PostgreSQL: {self.db_config.host}:{self.db_config.port}/{self.db_config.database}")
            
        except psycopg2.Error as e:
            self.logger.error(f"Failed to connect to PostgreSQL: {e}")
            raise ConnectionError(f"PostgreSQL connection failed: {e}")
    
    def disconnect(self) -> None:
        """Close PostgreSQL connection."""
        try:
            if self._connection:
                self._connection.close()
                self._connection = None
                self.logger.info("Disconnected from PostgreSQL")
        except psycopg2.Error as e:
            self.logger.error(f"Error disconnecting from PostgreSQL: {e}")
    
    def test_connection(self) -> bool:
        """Test PostgreSQL connection."""
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
    
    def _execute_query(self, query: str, params: Optional[tuple] = None, fetch: bool = True) -> Optional[List[tuple]]:
        """Execute a query safely with error handling."""
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.execute(query, params)
                if fetch:
                    return cursor.fetchall()
                return None
        except psycopg2.Error as e:
            self.logger.error(f"Query execution failed: {e}")
            raise
    
    def _get_table_identifier(self) -> sql.Identifier:
        """Get properly quoted table identifier."""
        if self.db_config.schema:
            return sql.Identifier(self.db_config.schema, self.db_config.table)
        return sql.Identifier(self.db_config.table)


class PostgresSourceConnector(PostgresConnectorMixin, BaseSourceConnector):
    """PostgreSQL source connector for reading data."""
    
    def get_schema(self) -> Dict[str, str]:
        """Get table schema from PostgreSQL information_schema."""
        if self.db_config.query:
            # For custom queries, we need to analyze the result set
            return self._get_query_schema()
        else:
            return self._get_table_schema()
    
    def _get_table_schema(self) -> Dict[str, str]:
        """Get schema for a specific table."""
        query = """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns 
        WHERE table_name = %s 
        AND table_schema = %s
        ORDER BY ordinal_position
        """
        
        try:
            rows = self._execute_query(
                query, 
                (self.db_config.table, self.db_config.schema or 'public')
            )
            
            schema = {}
            for row in rows:
                col_name = row['column_name']
                data_type = row['data_type']
                is_nullable = row['is_nullable'] == 'YES'
                
                # Map PostgreSQL types to generic types
                schema[col_name] = self._map_postgres_type(data_type, is_nullable)
            
            return schema
            
        except psycopg2.Error as e:
            self.logger.error(f"Failed to get table schema: {e}")
            raise
    
    def _get_query_schema(self) -> Dict[str, str]:
        """Get schema by analyzing query result."""
        # Execute query with LIMIT 0 to get column info without data
        query = f"SELECT * FROM ({self.db_config.query}) AS subquery LIMIT 0"
        
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(query)
                
                schema = {}
                for desc in cursor.description:
                    col_name = desc.name
                    # Map PostgreSQL type OIDs to generic types
                    schema[col_name] = self._map_postgres_oid_type(desc.type_code)
                
                return schema
                
        except psycopg2.Error as e:
            self.logger.error(f"Failed to analyze query schema: {e}")
            raise
    
    def _map_postgres_type(self, pg_type: str, is_nullable: bool = False) -> str:
        """Map PostgreSQL data types to generic types."""
        type_mapping = {
            'integer': 'int',
            'bigint': 'bigint',
            'smallint': 'smallint',
            'numeric': 'decimal',
            'decimal': 'decimal',
            'real': 'float',
            'double precision': 'double',
            'character varying': 'varchar',
            'varchar': 'varchar',
            'character': 'char',
            'char': 'char',
            'text': 'text',
            'boolean': 'boolean',
            'date': 'date',
            'timestamp without time zone': 'timestamp',
            'timestamp with time zone': 'timestamptz',
            'time': 'time',
            'json': 'json',
            'jsonb': 'jsonb',
            'uuid': 'uuid'
        }
        
        generic_type = type_mapping.get(pg_type.lower(), 'text')
        return f"{generic_type}{'?' if is_nullable else ''}"
    
    def _map_postgres_oid_type(self, type_code: int) -> str:
        """Map PostgreSQL OID type codes to generic types."""
        # Common PostgreSQL type OIDs
        oid_mapping = {
            16: 'boolean',      # bool
            20: 'bigint',       # int8
            21: 'smallint',     # int2
            23: 'int',          # int4
            25: 'text',         # text
            700: 'float',       # float4
            701: 'double',      # float8
            1043: 'varchar',    # varchar
            1082: 'date',       # date
            1114: 'timestamp',  # timestamp
            1184: 'timestamptz', # timestamptz
            1700: 'decimal',    # numeric
            2950: 'uuid',       # uuid
            114: 'json',        # json
            3802: 'jsonb'       # jsonb
        }
        
        return oid_mapping.get(type_code, 'text')
    
    def get_row_count(self) -> int:
        """Get total row count from source."""
        if self.db_config.query:
            query = f"SELECT COUNT(*) as count FROM ({self.db_config.query}) AS subquery"
        else:
            table_id = self._get_table_identifier()
            query = sql.SQL("SELECT COUNT(*) as count FROM {}").format(table_id)
        
        try:
            result = self._execute_query(str(query))
            return result[0]['count'] if result else 0
        except psycopg2.Error as e:
            self.logger.error(f"Failed to get row count: {e}")
            raise
    
    def read_data(self, batch_size: int = 1000, offset: int = 0) -> Iterator[List[Dict[str, Any]]]:
        """Read data in batches from PostgreSQL."""
        if self.db_config.query:
            base_query = self.db_config.query
        else:
            table_id = self._get_table_identifier()
            base_query = sql.SQL("SELECT * FROM {}").format(table_id)
        
        current_offset = offset
        
        while True:
            # Add LIMIT and OFFSET to the query
            if isinstance(base_query, sql.SQL):
                paginated_query = base_query + sql.SQL(" LIMIT %s OFFSET %s")
                query_str = paginated_query.as_string(self._get_connection())
                params = (batch_size, current_offset)
            else:
                paginated_query = f"SELECT * FROM ({base_query}) AS subquery LIMIT %s OFFSET %s"
                query_str = paginated_query
                params = (batch_size, current_offset)
            
            try:
                rows = self._execute_query(query_str, params)
                
                if not rows:
                    break
                
                # Convert RealDictRow to regular dict
                batch = [dict(row) for row in rows]
                yield batch
                
                # If we got fewer rows than batch_size, we're done
                if len(batch) < batch_size:
                    break
                
                current_offset += batch_size
                
            except psycopg2.Error as e:
                self.logger.error(f"Failed to read data batch at offset {current_offset}: {e}")
                raise


class PostgresDestinationConnector(PostgresConnectorMixin, BaseDestinationConnector):
    """PostgreSQL destination connector for writing data."""
    
    def get_schema(self) -> Dict[str, str]:
        """Get destination table schema."""
        return self._get_table_schema()
    
    def _get_table_schema(self) -> Dict[str, str]:
        """Get schema for the destination table."""
        query = """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns 
        WHERE table_name = %s 
        AND table_schema = %s
        ORDER BY ordinal_position
        """
        
        try:
            rows = self._execute_query(
                query, 
                (self.db_config.table, self.db_config.schema or 'public')
            )
            
            schema = {}
            for row in rows:
                col_name = row['column_name']
                data_type = row['data_type']
                is_nullable = row['is_nullable'] == 'YES'
                
                schema[col_name] = self._map_postgres_type(data_type, is_nullable)
            
            return schema
            
        except psycopg2.Error as e:
            # Table might not exist yet
            self.logger.warning(f"Could not get table schema (table may not exist): {e}")
            return {}
    
    def _map_postgres_type(self, pg_type: str, is_nullable: bool = False) -> str:
        """Map PostgreSQL data types to generic types."""
        type_mapping = {
            'integer': 'int',
            'bigint': 'bigint',
            'smallint': 'smallint',
            'numeric': 'decimal',
            'decimal': 'decimal',
            'real': 'float',
            'double precision': 'double',
            'character varying': 'varchar',
            'varchar': 'varchar',
            'character': 'char',
            'char': 'char',
            'text': 'text',
            'boolean': 'boolean',
            'date': 'date',
            'timestamp without time zone': 'timestamp',
            'timestamp with time zone': 'timestamptz',
            'time': 'time',
            'json': 'json',
            'jsonb': 'jsonb',
            'uuid': 'uuid'
        }
        
        generic_type = type_mapping.get(pg_type.lower(), 'text')
        return f"{generic_type}{'?' if is_nullable else ''}"
    
    def create_table_if_not_exists(self, schema: Dict[str, str]) -> None:
        """Create destination table if it doesn't exist."""
        if not schema:
            raise ValueError("Cannot create table without schema definition")
        
        # Map generic types back to PostgreSQL types
        pg_type_mapping = {
            'int': 'INTEGER',
            'bigint': 'BIGINT',
            'smallint': 'SMALLINT',
            'decimal': 'DECIMAL',
            'float': 'REAL',
            'double': 'DOUBLE PRECISION',
            'varchar': 'VARCHAR(255)',
            'char': 'CHAR(1)',
            'text': 'TEXT',
            'boolean': 'BOOLEAN',
            'date': 'DATE',
            'timestamp': 'TIMESTAMP',
            'timestamptz': 'TIMESTAMPTZ',
            'time': 'TIME',
            'json': 'JSON',
            'jsonb': 'JSONB',
            'uuid': 'UUID'
        }
        
        # Build column definitions
        column_defs = []
        for col_name, col_type in schema.items():
            # Handle nullable types (ending with ?)
            is_nullable = col_type.endswith('?')
            base_type = col_type.rstrip('?')
            
            pg_type = pg_type_mapping.get(base_type, 'TEXT')
            nullable_clause = '' if is_nullable else ' NOT NULL'
            
            column_defs.append(f"{col_name} {pg_type}{nullable_clause}")
        
        # Create table query
        table_id = self._get_table_identifier()
        create_query = sql.SQL("""
            CREATE TABLE IF NOT EXISTS {} ({})
        """).format(
            table_id,
            sql.SQL(', '.join(column_defs))
        )
        
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                cursor.execute(create_query)
            conn.commit()
            self.logger.info(f"Created table {self.db_config.schema}.{self.db_config.table}")
            
        except psycopg2.Error as e:
            self.logger.error(f"Failed to create table: {e}")
            raise
    
    def write_batch(self, rows: List[Dict[str, Any]], conflict_strategy: str = 'overwrite') -> int:
        """Write a batch of rows to PostgreSQL."""
        if not rows:
            return 0
        
        table_id = self._get_table_identifier()
        columns = list(rows[0].keys())
        
        # Build the INSERT query
        if conflict_strategy == 'overwrite':
            # Use ON CONFLICT DO UPDATE (requires a primary key or unique constraint)
            insert_query = self._build_upsert_query(table_id, columns)
        elif conflict_strategy == 'skip':
            # Use ON CONFLICT DO NOTHING
            insert_query = self._build_insert_ignore_query(table_id, columns)
        elif conflict_strategy == 'fail':
            # Regular INSERT that will fail on conflicts
            insert_query = self._build_insert_query(table_id, columns)
        else:
            raise ValueError(f"Unsupported conflict strategy: {conflict_strategy}")
        
        try:
            conn = self._get_connection()
            with conn.cursor() as cursor:
                # Prepare data for batch insert
                values_list = []
                for row in rows:
                    values = tuple(row.get(col) for col in columns)
                    values_list.append(values)
                
                # Execute batch insert
                psycopg2.extras.execute_batch(cursor, insert_query, values_list)
                
                return len(rows)
                
        except psycopg2.Error as e:
            self.logger.error(f"Failed to write batch: {e}")
            raise
    
    def _build_insert_query(self, table_id: sql.Identifier, columns: List[str]) -> str:
        """Build a basic INSERT query."""
        column_list = sql.SQL(', ').join(map(sql.Identifier, columns))
        placeholders = sql.SQL(', ').join(sql.Placeholder() * len(columns))
        
        query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            table_id, column_list, placeholders
        )
        
        return query.as_string(self._get_connection())
    
    def _build_insert_ignore_query(self, table_id: sql.Identifier, columns: List[str]) -> str:
        """Build INSERT ... ON CONFLICT DO NOTHING query."""
        column_list = sql.SQL(', ').join(map(sql.Identifier, columns))
        placeholders = sql.SQL(', ').join(sql.Placeholder() * len(columns))
        
        query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) ON CONFLICT DO NOTHING").format(
            table_id, column_list, placeholders
        )
        
        return query.as_string(self._get_connection())
    
    def _build_upsert_query(self, table_id: sql.Identifier, columns: List[str]) -> str:
        """Build INSERT ... ON CONFLICT DO UPDATE query."""
        column_list = sql.SQL(', ').join(map(sql.Identifier, columns))
        placeholders = sql.SQL(', ').join(sql.Placeholder() * len(columns))
        
        # For upsert, we need to update all columns except the conflict column
        # This is a simplified version - in practice, you'd want to identify the primary key
        update_list = sql.SQL(', ').join(
            sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(col), sql.Identifier(col))
            for col in columns
        )
        
        query = sql.SQL("""
            INSERT INTO {} ({}) VALUES ({}) 
            ON CONFLICT DO UPDATE SET {}
        """).format(
            table_id, column_list, placeholders, update_list
        )
        
        return query.as_string(self._get_connection())
    
    def begin_transaction(self) -> None:
        """Begin a database transaction."""
        conn = self._get_connection()
        conn.autocommit = False
    
    def commit_transaction(self) -> None:
        """Commit the current transaction."""
        conn = self._get_connection()
        conn.commit()
    
    def rollback_transaction(self) -> None:
        """Rollback the current transaction."""
        conn = self._get_connection()
        conn.rollback()
