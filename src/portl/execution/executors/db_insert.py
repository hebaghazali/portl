"""
Database insert step executor.

Performs INSERT operations with parameter binding.
Optionally applies field transformations before insert.
"""

import logging
from typing import Dict, Any

from ..executor import register_executor
from ..context import ExecutionContext, StepResult, StepStatus
from ..mapping import get_mapping_engine
from ...schema import BaseStep
from ...connectors.base import BaseDestinationConnector

logger = logging.getLogger(__name__)


@register_executor("db.insert")
class DBInsertExecutor:
    """Executor for db.insert step type."""
    
    def execute(self, step: BaseStep, context: ExecutionContext) -> StepResult:
        """
        Execute database insert operation.
        
        Args:
            step: DB insert step configuration
            context: Execution context (must include _connection in current_vars)
            
        Returns:
            StepResult with insert info
        """
        # Get connection from context
        connection = context.current_vars.get('_connection')
        if not connection:
            raise ValueError("DB insert step requires a database connection in context")
        
        if not isinstance(connection, BaseDestinationConnector):
            raise TypeError(f"Connection must be a BaseDestinationConnector, got {type(connection)}")
        
        # Get configuration
        if hasattr(step, 'config') and isinstance(step.config, dict):
            # Dataclass Step
            config = step.config
            table = config.get('table')
            mapping = config.get('mapping')
            transformations = config.get('transformations')
        else:
            # Pydantic Step
            table = getattr(step, 'table', None)
            mapping = getattr(step, 'mapping', None)
            transformations = getattr(step, 'transformations', None)
        
        if not table:
            raise ValueError("DB insert step requires 'table' field")
        if not mapping:
            raise ValueError("DB insert step requires 'mapping' field")
        
        logger.info(f"Inserting into table '{table}'")
        
        # Apply transformations to mapping values if configured
        mapping_engine = get_mapping_engine(transformations=transformations)
        if mapping_engine:
            mapping = mapping_engine.apply(mapping)
        
        try:
            # Build insert SQL
            columns = list(mapping.keys())
            values = list(mapping.values())
            
            cols_str = ', '.join(columns)
            placeholders = ', '.join(['%s'] * len(columns))
            
            sql = f"""
                INSERT INTO {table} ({cols_str})
                VALUES ({placeholders})
                RETURNING *
            """
            
            # Execute insert
            result = self._execute_insert(connection, sql, values)
            
            return StepResult(
                step_id=step.id,
                status=StepStatus.OK,
                output=result,
                metrics={
                    'table': table,
                    'operation': 'insert',
                    'row_count': 1,
                },
                touched_transaction=True,
            )
        
        except Exception as e:
            logger.error(f"Error inserting into table '{table}': {e}")
            raise
    
    def _execute_insert(
        self, 
        connection: BaseDestinationConnector, 
        sql: str, 
        values: list
    ) -> Dict[str, Any]:
        """
        Execute the insert SQL with the provided values.
        
        Args:
            connection: Database connector
            sql: SQL statement
            values: Values to insert
            
        Returns:
            Dict with inserted record
        """
        # Get database connection
        if not hasattr(connection, '_connection') or connection._connection is None:
            raise ConnectionError("Database connection not established")
        
        db_conn = connection._connection
        cursor = db_conn.cursor()
        
        try:
            # Execute
            cursor.execute(sql, values)
            
            # Fetch inserted record (RETURNING clause)
            result_row = cursor.fetchone()
            
            if result_row:
                # Get column names
                col_names = [desc[0] for desc in cursor.description]
                record = dict(zip(col_names, result_row))
            else:
                record = {'row_count': cursor.rowcount}
            
            return {'record': record, 'row_count': cursor.rowcount}
        
        finally:
            cursor.close()

