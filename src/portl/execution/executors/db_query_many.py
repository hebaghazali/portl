"""
Database query_many step executor.

Performs SELECT query and returns all matching rows as a list.
Supports both inline SQL and sql_file references.
"""

import logging
from typing import Dict, Any, List, Optional

from ..executor import register_executor
from ..context import ExecutionContext, StepResult, StepStatus
from ..sql_loader import SQLFileLoader
from ...schema import BaseStep
from ...connectors.base import BaseDestinationConnector

logger = logging.getLogger(__name__)


@register_executor("db.query_many")
class DBQueryManyExecutor:
    """
    Executor for db.query_many step type.
    
    Returns all rows matching the query as a list of dicts.
    
    Configuration:
        query: Inline SQL query (mutually exclusive with sql_file)
        sql_file: Path to SQL file (mutually exclusive with query)
        params: Dict of query parameters for named placeholders
        limit: Optional limit on number of rows returned
    
    Example:
        - id: fetch_users
          type: db.query_many
          connection: pg_main
          sql_file: queries/active_users.sql
          params:
            status: "active"
            limit: 100
    """
    
    def execute(self, step: BaseStep, context: ExecutionContext) -> StepResult:
        """
        Execute database query and return all rows.
        
        Args:
            step: DB query_many step configuration
            context: Execution context (must include _connection in current_vars)
            
        Returns:
            StepResult with list of records as output
        """
        # Get connection from context
        connection = context.current_vars.get('_connection')
        if not connection:
            raise ValueError("DB query_many step requires a database connection in context")
        
        if not isinstance(connection, BaseDestinationConnector):
            raise TypeError(
                f"Connection must be a BaseDestinationConnector, got {type(connection)}"
            )
        
        # Get configuration
        config = step.config if hasattr(step, 'config') and isinstance(step.config, dict) else {}
        
        sql = config.get('query') or getattr(step, 'query', None)
        sql_file = config.get('sql_file') or getattr(step, 'sql_file', None)
        params = config.get('params') or getattr(step, 'params', None) or {}
        limit = config.get('limit') or getattr(step, 'limit', None)
        
        # Validate: sql XOR sql_file
        if sql and sql_file:
            raise ValueError(
                f"Step '{step.id}': Cannot specify both 'query' and 'sql_file'"
            )
        if not sql and not sql_file:
            raise ValueError(
                f"Step '{step.id}': Must specify either 'query' or 'sql_file'"
            )
        
        # Load SQL from file if specified
        if sql_file:
            job_dir = context.current_vars.get('_job_file_dir')
            loader = SQLFileLoader(job_dir)
            template_context = context.to_template_dict()
            sql = loader.render(sql_file, template_context)
            sql_source = f"file:{sql_file}"
        else:
            sql_source = "inline"
        
        # Apply limit if specified
        if limit:
            # Wrap query with limit
            sql = f"SELECT * FROM ({sql}) AS subquery LIMIT {int(limit)}"
        
        logger.info(
            f"Executing query_many (source: {sql_source})",
            extra={'step_id': step.id, 'sql_source': sql_source}
        )
        
        try:
            rows = self._execute_query(connection, sql, params)
            
            return StepResult(
                step_id=step.id,
                status=StepStatus.OK,
                output={'rows': rows, 'count': len(rows)},
                metrics={
                    'operation': 'query_many',
                    'row_count': len(rows),
                    'sql_source': sql_source,
                },
                touched_transaction=False,  # Queries don't modify data
            )
        
        except Exception as e:
            logger.error(f"Query failed: {e}")
            raise
    
    def _execute_query(
        self, 
        connection: BaseDestinationConnector, 
        sql: str, 
        params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Execute query and return all rows as dicts.
        
        Args:
            connection: Database connector
            sql: SQL SELECT statement
            params: Query parameters
            
        Returns:
            List of row dicts
        """
        # Get database connection
        if not hasattr(connection, '_connection') or connection._connection is None:
            raise ConnectionError("Database connection not established")
        
        db_conn = connection._connection
        cursor = db_conn.cursor()
        
        try:
            # Execute query with parameters
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            
            if rows:
                # Get column names from cursor description
                col_names = [desc[0] for desc in cursor.description]
                return [dict(zip(col_names, row)) for row in rows]
            
            return []
        
        finally:
            cursor.close()

