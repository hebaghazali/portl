"""
Database query_one step executor.

Performs SELECT query and returns single row (or None if no results).
"""

import logging
from typing import Dict, Any, Optional

from ..executor import register_executor
from ..context import ExecutionContext, StepResult, StepStatus
from ...schema import BaseStep
from ...connectors.base import BaseDestinationConnector

logger = logging.getLogger(__name__)


@register_executor("db.query_one")
class DBQueryOneExecutor:
    """Executor for db.query_one step type."""
    
    def execute(self, step: BaseStep, context: ExecutionContext) -> StepResult:
        """
        Execute database query and return single row.
        
        Args:
            step: DB query_one step configuration
            context: Execution context (must include _connection in current_vars)
            
        Returns:
            StepResult with query result (record or None)
        """
        # Get connection from context
        connection = context.current_vars.get('_connection')
        if not connection:
            raise ValueError("DB query_one step requires a database connection in context")
        
        if not isinstance(connection, BaseDestinationConnector):
            raise TypeError(f"Connection must be a BaseDestinationConnector, got {type(connection)}")
        
        # Get configuration
        if hasattr(step, 'config') and isinstance(step.config, dict):
            # Dataclass Step
            config = step.config
            query = config.get('query')
            params = config.get('params', {})
        else:
            # Pydantic Step
            query = getattr(step, 'query', None)
            params = getattr(step, 'params', {})
        
        if not query:
            raise ValueError("DB query_one step requires 'query' field")
        
        logger.info(f"Executing query: {query[:100]}...")
        
        try:
            # Execute query
            record = self._execute_query_one(connection, query, params)
            
            return StepResult(
                step_id=step.id,
                status=StepStatus.OK,
                output={'record': record},
                metrics={
                    'operation': 'query_one',
                    'found': record is not None,
                },
                touched_transaction=False,  # Queries don't modify data
            )
        
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            raise
    
    def _execute_query_one(
        self, 
        connection: BaseDestinationConnector, 
        query: str, 
        params: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Execute the SELECT query and return first row.
        
        Args:
            connection: Database connector
            query: SQL SELECT statement (can contain %(name)s placeholders)
            params: Dict of query parameters
            
        Returns:
            Dict with first row, or None if no results
        """
        # Get database connection
        if not hasattr(connection, '_connection') or connection._connection is None:
            raise ConnectionError("Database connection not established")
        
        db_conn = connection._connection
        cursor = db_conn.cursor()
        
        try:
            # Execute query with named parameters
            cursor.execute(query, params)
            
            # Fetch first row
            result_row = cursor.fetchone()
            
            if result_row:
                # Get column names
                col_names = [desc[0] for desc in cursor.description]
                record = dict(zip(col_names, result_row))
                return record
            else:
                return None
        
        finally:
            cursor.close()

