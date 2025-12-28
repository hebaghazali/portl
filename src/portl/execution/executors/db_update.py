"""
Database update step executor.

Performs UPDATE operations with WHERE clause and parameter binding.
Optionally applies field transformations before update.
"""

import logging
from typing import Dict, Any

from ..executor import register_executor
from ..context import ExecutionContext, StepResult, StepStatus
from ..mapping import get_mapping_engine
from ...schema import BaseStep
from ...connectors.base import BaseDestinationConnector

logger = logging.getLogger(__name__)


@register_executor("db.update")
class DBUpdateExecutor:
    """Executor for db.update step type."""
    
    def execute(self, step: BaseStep, context: ExecutionContext) -> StepResult:
        """
        Execute database update operation.
        
        Args:
            step: DB update step configuration
            context: Execution context (must include _connection in current_vars)
            
        Returns:
            StepResult with update info
        """
        # Get connection from context
        connection = context.current_vars.get('_connection')
        if not connection:
            raise ValueError("DB update step requires a database connection in context")
        
        if not isinstance(connection, BaseDestinationConnector):
            raise TypeError(f"Connection must be a BaseDestinationConnector, got {type(connection)}")
        
        # Get configuration
        if hasattr(step, 'config') and isinstance(step.config, dict):
            # Dataclass Step
            config = step.config
            table = config.get('table')
            where = config.get('where', {})
            mapping = config.get('mapping')
            transformations = config.get('transformations')
        else:
            # Pydantic Step
            table = getattr(step, 'table', None)
            where = getattr(step, 'where', {})
            mapping = getattr(step, 'mapping', None)
            transformations = getattr(step, 'transformations', None)
        
        if not table:
            raise ValueError("DB update step requires 'table' field")
        if not mapping:
            raise ValueError("DB update step requires 'mapping' field")
        if not where:
            raise ValueError("DB update step requires 'where' clause (safety check)")
        
        logger.info(f"Updating table '{table}' with WHERE clause")
        
        # Apply transformations to mapping values if configured
        mapping_engine = get_mapping_engine(transformations=transformations)
        if mapping_engine:
            mapping = mapping_engine.apply(mapping)
        
        try:
            # Build update SQL
            set_columns = list(mapping.keys())
            set_values = list(mapping.values())
            
            where_columns = list(where.keys())
            where_values = list(where.values())
            
            # SET clause
            set_clause = ', '.join([f"{col} = %s" for col in set_columns])
            
            # WHERE clause
            where_clause = ' AND '.join([f"{col} = %s" for col in where_columns])
            
            sql = f"""
                UPDATE {table}
                SET {set_clause}
                WHERE {where_clause}
                RETURNING *
            """
            
            # Combine values: SET values first, then WHERE values
            all_values = set_values + where_values
            
            # Execute update
            result = self._execute_update(connection, sql, all_values)
            
            return StepResult(
                step_id=step.id,
                status=StepStatus.OK,
                output=result,
                metrics={
                    'table': table,
                    'operation': 'update',
                    'row_count': result.get('row_count', 0),
                },
                touched_transaction=True,
            )
        
        except Exception as e:
            logger.error(f"Error updating table '{table}': {e}")
            raise
    
    def _execute_update(
        self, 
        connection: BaseDestinationConnector, 
        sql: str, 
        values: list
    ) -> Dict[str, Any]:
        """
        Execute the update SQL with the provided values.
        
        Args:
            connection: Database connector
            sql: SQL statement
            values: Values for SET and WHERE clauses
            
        Returns:
            Dict with updated record info
        """
        # Get database connection
        if not hasattr(connection, '_connection') or connection._connection is None:
            raise ConnectionError("Database connection not established")
        
        db_conn = connection._connection
        cursor = db_conn.cursor()
        
        try:
            # Execute
            cursor.execute(sql, values)
            
            # Fetch updated records (RETURNING clause)
            result_rows = cursor.fetchall()
            
            if result_rows:
                # Get column names
                col_names = [desc[0] for desc in cursor.description]
                records = [dict(zip(col_names, row)) for row in result_rows]
            else:
                records = []
            
            return {
                'records': records,
                'row_count': cursor.rowcount,
            }
        
        finally:
            cursor.close()

