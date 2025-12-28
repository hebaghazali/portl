"""
Database upsert step executor.

Performs INSERT ... ON CONFLICT ... DO UPDATE for Postgres
or INSERT ... ON DUPLICATE KEY UPDATE for MySQL.
Optionally applies field transformations before upsert.
"""

import logging
from typing import Dict, Any, List

from ..executor import register_executor
from ..context import ExecutionContext, StepResult, StepStatus
from ..mapping import get_mapping_engine
from ...schema import BaseStep, DBUpsertStep
from ...connectors.base import BaseDestinationConnector

logger = logging.getLogger(__name__)


@register_executor("db.upsert")
class DBUpsertExecutor:
    """Executor for db.upsert step type."""
    
    def execute(self, step: BaseStep, context: ExecutionContext) -> StepResult:
        """
        Execute database upsert operation.
        
        Args:
            step: DB upsert step configuration
            context: Execution context (must include _connection in current_vars)
            
        Returns:
            StepResult with upserted record info
        """
        # Get connection from context
        connection = context.current_vars.get('_connection')
        if not connection:
            raise ValueError("DB upsert step requires a database connection in context")
        
        if not isinstance(connection, BaseDestinationConnector):
            raise TypeError(f"Connection must be a BaseDestinationConnector, got {type(connection)}")
        
        # Get configuration - check both direct attributes (Pydantic) and config dict (dataclass)
        if hasattr(step, 'config') and isinstance(step.config, dict):
            # Dataclass Step - config is in dict
            config = step.config
            table = config.get('table')
            key_columns = config.get('key')
            mapping = config.get('mapping')
            transformations = config.get('transformations')
        else:
            # Pydantic Step - config as attributes
            table = getattr(step, 'table', None)
            key_columns = getattr(step, 'key', None)
            mapping = getattr(step, 'mapping', None)
            transformations = getattr(step, 'transformations', None)
        
        if not table:
            raise ValueError("DB upsert step requires 'table' field")
        if not key_columns:
            raise ValueError("DB upsert step requires 'key' field (list of key columns)")
        if not mapping:
            raise ValueError("DB upsert step requires 'mapping' field")
        
        logger.info(f"Upserting to table '{table}' with keys {key_columns}")
        
        # Apply transformations to mapping values if configured
        mapping_engine = get_mapping_engine(transformations=transformations)
        if mapping_engine:
            mapping = mapping_engine.apply(mapping)
        
        try:
            # Build upsert SQL
            columns = list(mapping.keys())
            values = list(mapping.values())
            
            # Detect database type
            db_type = getattr(connection.config, 'type', 'postgres')
            
        # Get conflict strategy (defaults to 'overwrite')
        conflict_strategy = config.get('conflict') if hasattr(step, 'config') and isinstance(step.config, dict) else None
        conflict_strategy = conflict_strategy or getattr(step, 'conflict', None) or 'overwrite'
        
        if db_type == 'postgres':
            sql = self._build_postgres_upsert(table, columns, key_columns, conflict_strategy)
        elif db_type == 'mysql':
            sql = self._build_mysql_upsert(table, columns, key_columns, conflict_strategy)
        else:
            raise ValueError(f"Unsupported database type: {db_type}")
            
            # Execute upsert
            result = self._execute_upsert(connection, sql, mapping)
            
            return StepResult(
                step_id=step.id,
                status=StepStatus.OK,
                output=result,
                metrics={
                    'table': table,
                    'operation': 'upsert',
                },
                touched_transaction=True,
            )
        
        except Exception as e:
            logger.error(f"Error upserting to table '{table}': {e}")
            raise
    
    def _build_postgres_upsert(
        self, 
        table: str, 
        columns: List[str], 
        key_columns: List[str],
        conflict_strategy: str = 'overwrite'
    ) -> str:
        """
        Build PostgreSQL INSERT ... ON CONFLICT ... DO UPDATE statement.
        
        Args:
            table: Table name
            columns: All columns to insert/update
            key_columns: Key columns for conflict detection
            conflict_strategy: How to handle conflicts:
                - 'overwrite': Replace all non-key columns (default)
                - 'merge_non_null': Only update if new value is not null
                - 'merge_newer': Only update if new updated_at > existing
                - 'skip': Do nothing on conflict
            
        Returns:
            SQL statement with placeholders
        """
        # INSERT INTO table (col1, col2, ...) VALUES (%s, %s, ...)
        cols_str = ', '.join(columns)
        placeholders = ', '.join(['%s'] * len(columns))
        
        # ON CONFLICT (key1, key2) DO UPDATE SET ...
        conflict_keys = ', '.join(key_columns)
        
        # Build UPDATE SET clause based on strategy
        update_cols = [col for col in columns if col not in key_columns]
        update_set = self._build_postgres_update_clause(table, update_cols, conflict_strategy)
        
        if conflict_strategy == 'skip':
            sql = f"""
                INSERT INTO {table} ({cols_str})
                VALUES ({placeholders})
                ON CONFLICT ({conflict_keys})
                DO NOTHING
                RETURNING *, FALSE AS was_inserted
            """
        else:
            sql = f"""
                INSERT INTO {table} ({cols_str})
                VALUES ({placeholders})
                ON CONFLICT ({conflict_keys})
                DO UPDATE SET {update_set}
                RETURNING *, (xmax = 0) AS was_inserted
            """
        
        return sql.strip()
    
    def _build_postgres_update_clause(
        self, 
        table: str, 
        columns: List[str], 
        strategy: str
    ) -> str:
        """
        Build UPDATE SET clause based on merge strategy.
        
        Args:
            table: Table name (for referencing existing values)
            columns: Columns to update
            strategy: Merge strategy
            
        Returns:
            SET clause string
        """
        if strategy == 'overwrite':
            # Simply overwrite all columns
            return ', '.join([f"{col} = EXCLUDED.{col}" for col in columns])
        
        elif strategy == 'merge_non_null':
            # Only update if new value is not null, otherwise keep existing
            return ', '.join([
                f"{col} = COALESCE(EXCLUDED.{col}, {table}.{col})"
                for col in columns
            ])
        
        elif strategy == 'merge_newer':
            # Only update if new updated_at > existing updated_at
            # Requires 'updated_at' column in the table
            if 'updated_at' not in columns:
                logger.warning(
                    "merge_newer strategy requires 'updated_at' column; "
                    "falling back to overwrite"
                )
                return ', '.join([f"{col} = EXCLUDED.{col}" for col in columns])
            
            return ', '.join([
                f"{col} = CASE WHEN EXCLUDED.updated_at > {table}.updated_at "
                f"THEN EXCLUDED.{col} ELSE {table}.{col} END"
                for col in columns
            ])
        
        else:
            # Unknown strategy, default to overwrite
            logger.warning(f"Unknown conflict strategy '{strategy}', using 'overwrite'")
            return ', '.join([f"{col} = EXCLUDED.{col}" for col in columns])
    
    def _build_mysql_upsert(
        self, 
        table: str, 
        columns: List[str], 
        key_columns: List[str],
        conflict_strategy: str = 'overwrite'
    ) -> str:
        """
        Build MySQL INSERT ... ON DUPLICATE KEY UPDATE statement.
        
        Args:
            table: Table name
            columns: All columns to insert/update
            key_columns: Key columns (must have UNIQUE constraint)
            conflict_strategy: How to handle conflicts:
                - 'overwrite': Replace all non-key columns (default)
                - 'merge_non_null': Only update if new value is not null
                - 'merge_newer': Only update if new updated_at > existing
                - 'skip': Use INSERT IGNORE
            
        Returns:
            SQL statement with placeholders
        """
        cols_str = ', '.join(columns)
        placeholders = ', '.join(['%s'] * len(columns))
        
        if conflict_strategy == 'skip':
            sql = f"""
                INSERT IGNORE INTO {table} ({cols_str})
                VALUES ({placeholders})
            """
            return sql.strip()
        
        # Build UPDATE clause based on strategy
        update_cols = [col for col in columns if col not in key_columns]
        update_set = self._build_mysql_update_clause(table, update_cols, conflict_strategy)
        
        sql = f"""
            INSERT INTO {table} ({cols_str})
            VALUES ({placeholders})
            ON DUPLICATE KEY UPDATE {update_set}
        """
        
        return sql.strip()
    
    def _build_mysql_update_clause(
        self, 
        table: str, 
        columns: List[str], 
        strategy: str
    ) -> str:
        """
        Build ON DUPLICATE KEY UPDATE clause based on merge strategy.
        
        Args:
            table: Table name
            columns: Columns to update
            strategy: Merge strategy
            
        Returns:
            UPDATE clause string
        """
        if strategy == 'overwrite':
            # Simply overwrite all columns
            return ', '.join([f"{col} = VALUES({col})" for col in columns])
        
        elif strategy == 'merge_non_null':
            # Only update if new value is not null, otherwise keep existing
            return ', '.join([
                f"{col} = COALESCE(VALUES({col}), {col})"
                for col in columns
            ])
        
        elif strategy == 'merge_newer':
            # Only update if new updated_at > existing updated_at
            # Requires 'updated_at' column in the table
            if 'updated_at' not in columns:
                logger.warning(
                    "merge_newer strategy requires 'updated_at' column; "
                    "falling back to overwrite"
                )
                return ', '.join([f"{col} = VALUES({col})" for col in columns])
            
            return ', '.join([
                f"{col} = IF(VALUES(updated_at) > updated_at, VALUES({col}), {col})"
                for col in columns
            ])
        
        else:
            # Unknown strategy, default to overwrite
            logger.warning(f"Unknown conflict strategy '{strategy}', using 'overwrite'")
            return ', '.join([f"{col} = VALUES({col})" for col in columns])
    
    def _execute_upsert(
        self, 
        connection: BaseDestinationConnector, 
        sql: str, 
        mapping: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute the upsert SQL with the provided values.
        
        Args:
            connection: Database connector
            sql: SQL statement
            mapping: Column -> value mapping
            
        Returns:
            Dict with result info (id, was_inserted, etc.)
        """
        # Get database connection
        if not hasattr(connection, '_connection') or connection._connection is None:
            raise ConnectionError("Database connection not established")
        
        db_conn = connection._connection
        cursor = db_conn.cursor()
        
        try:
            # Extract values in column order
            values = list(mapping.values())
            
            # Execute
            cursor.execute(sql, values)
            
            # Fetch result (for RETURNING clause)
            if 'RETURNING' in sql:
                result_row = cursor.fetchone()
                if result_row:
                    # Get column names
                    col_names = [desc[0] for desc in cursor.description]
                    result = dict(zip(col_names, result_row))
                else:
                    result = {'affected_rows': cursor.rowcount}
            else:
                # MySQL doesn't support RETURNING
                result = {
                    'affected_rows': cursor.rowcount,
                    'last_insert_id': cursor.lastrowid if hasattr(cursor, 'lastrowid') else None,
                }
            
            return result
        
        finally:
            cursor.close()

