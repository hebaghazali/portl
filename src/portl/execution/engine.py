"""
Job execution engine with transaction management.

Orchestrates multi-step job execution with context passing, transaction
management, conditionals, and batching.
"""

from typing import Dict, Any, List, Optional
import logging
from dataclasses import dataclass

from .context import ExecutionContext, StepResult, StepStatus
from .executor import dispatch_step
from .templating import get_template_engine
from ..schema import Job, BaseStep, ConditionalStep
from ..connectors.base import BaseDestinationConnector
from ..connectors.factory import ConnectorFactory

logger = logging.getLogger(__name__)


@dataclass
class TransactionGroup:
    """
    Transaction group definition.
    
    Groups DB steps into a single transaction boundary.
    """
    id: str
    step_ids: List[str]


class JobEngine:
    """
    Orchestration engine for multi-step jobs.
    
    Features:
    - Sequential step execution with context passing
    - Transaction management (db-group and step scopes)
    - Conditional execution (if/when expressions)
    - Batching (loop over collections)
    - Error handling with rollback
    """
    
    def __init__(self, job: Job, dry_run: bool = False):
        """
        Initialize job engine.
        
        Args:
            job: Job configuration with steps
            dry_run: If True, preview execution without side effects
        """
        self.job = job
        self.dry_run = dry_run
        self.template_engine = get_template_engine()
        
        # Connection management
        self._connections: Dict[str, Any] = {}
        self._active_transaction: Optional[Any] = None
        self._transaction_groups: List[TransactionGroup] = []
        
        # Build transaction groups
        self._build_transaction_groups()
    
    def _build_transaction_groups(self):
        """
        Build transaction groups from job configuration.
        
        For now, if transaction.scope == 'db', all DB steps go into one group.
        In the future, support explicit group definitions.
        """
        if not self.job.transaction or self.job.transaction.scope == 'none':
            return
        
        # Collect all DB steps
        db_step_ids = []
        for step in self.job.steps:
            if step.type.startswith('db.'):
                db_step_ids.append(step.id)
        
        if db_step_ids:
            self._transaction_groups.append(
                TransactionGroup(id='default_db_group', step_ids=db_step_ids)
            )
    
    def _get_connection(self, connection_name: str) -> Any:
        """
        Get or create a connection by name.
        
        Args:
            connection_name: Connection identifier
            
        Returns:
            Connection object (connector instance)
        """
        if connection_name in self._connections:
            return self._connections[connection_name]
        
        # Create new connection
        if not self.job.connections or connection_name not in self.job.connections:
            raise ValueError(f"Connection '{connection_name}' not defined in job")
        
        conn_config = self.job.connections[connection_name]
        
        # Map connection type to connector
        if conn_config.type in ['postgres', 'mysql']:
            # Create database connector
            connector = ConnectorFactory.create_destination_connector(conn_config.config)
            connector.connect()
            self._connections[connection_name] = connector
        else:
            # For lambda/http, we'll implement these later
            raise NotImplementedError(f"Connection type '{conn_config.type}' not yet implemented")
        
        return self._connections[connection_name]
    
    def _get_transaction_group_for_step(self, step_id: str) -> Optional[TransactionGroup]:
        """
        Get the transaction group that contains this step.
        
        Args:
            step_id: Step identifier
            
        Returns:
            TransactionGroup if step is in a group, None otherwise
        """
        for group in self._transaction_groups:
            if step_id in group.step_ids:
                return group
        return None
    
    def _is_first_step_in_group(self, step_id: str, group: TransactionGroup) -> bool:
        """Check if step is the first in its transaction group."""
        return group.step_ids[0] == step_id
    
    def _is_last_step_in_group(self, step_id: str, group: TransactionGroup) -> bool:
        """Check if step is the last in its transaction group."""
        return group.step_ids[-1] == step_id
    
    def _begin_transaction(self, group: TransactionGroup, connection: BaseDestinationConnector):
        """
        Begin a database transaction.
        
        Args:
            group: Transaction group
            connection: Database connector
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Would begin transaction for group '{group.id}'")
            return
        
        logger.info(f"Beginning transaction for group '{group.id}'")
        connection.begin_transaction()
        self._active_transaction = connection
    
    def _commit_transaction(self, group: TransactionGroup, connection: BaseDestinationConnector):
        """
        Commit a database transaction.
        
        Args:
            group: Transaction group
            connection: Database connector
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Would commit transaction for group '{group.id}'")
            return
        
        logger.info(f"Committing transaction for group '{group.id}'")
        connection.commit_transaction()
        self._active_transaction = None
    
    def _rollback_transaction(self, group: TransactionGroup, connection: BaseDestinationConnector):
        """
        Rollback a database transaction.
        
        Args:
            group: Transaction group
            connection: Database connector
        """
        if self.dry_run:
            logger.info(f"[DRY RUN] Would rollback transaction for group '{group.id}'")
            return
        
        logger.warning(f"Rolling back transaction for group '{group.id}'")
        connection.rollback_transaction()
        self._active_transaction = None
    
    def _should_execute_step(self, step: BaseStep, context: ExecutionContext) -> bool:
        """
        Check if step should be executed based on conditional (if/when).
        
        Args:
            step: Step configuration
            context: Current execution context
            
        Returns:
            True if step should execute, False if should be skipped
        """
        if not hasattr(step, 'when') or step.when is None:
            return True
        
        try:
            template_context = context.to_template_dict()
            result = self.template_engine.evaluate_condition(step.when, template_context)
            
            if not result:
                logger.info(f"Step '{step.id}' skipped due to condition: {step.when}")
            
            return result
        
        except Exception as e:
            logger.error(f"Error evaluating condition for step '{step.id}': {e}")
            raise
    
    def _render_step_config(self, step: BaseStep, context: ExecutionContext) -> BaseStep:
        """
        Render template expressions in step configuration.
        
        Args:
            step: Step with template expressions
            context: Current execution context
            
        Returns:
            Step with rendered values
        """
        # For dataclass steps, render the config dict in place
        # Don't try to reconstruct the step - just render its config values
        if hasattr(step, 'config') and isinstance(step.config, dict):
            template_context = context.to_template_dict()
            step.config = self.template_engine.render_config(step.config, template_context)
        
        # For Pydantic steps, we would use .dict() and reconstruct
        # But for now, just return the original step with updated config
        return step
    
    def execute(self, env: Optional[Dict[str, str]] = None) -> ExecutionContext:
        """
        Execute the job and return final execution context.
        
        Args:
            env: Environment variables for template interpolation
            
        Returns:
            Final ExecutionContext with all step results
            
        Raises:
            Exception: On job execution failure
        """
        # Initialize execution context
        context = ExecutionContext.new(env=env or {})
        
        logger.info(f"Starting job execution (run_id: {context.run_id}, dry_run: {self.dry_run})")
        
        try:
            # Execute steps sequentially
            for step in self.job.steps:
                context = self._execute_step(step, context)
            
            # Commit any pending transaction
            if self._active_transaction:
                logger.warning("Committing dangling transaction at job end")
                self._active_transaction.commit_transaction()
                self._active_transaction = None
            
            logger.info(f"Job completed successfully (run_id: {context.run_id})")
            logger.info(f"Metrics: {context.get_metrics_summary()}")
            
            return context
        
        except Exception as e:
            # Rollback any active transaction
            if self._active_transaction:
                logger.error("Rolling back transaction due to job failure")
                self._active_transaction.rollback_transaction()
                self._active_transaction = None
            
            logger.error(f"Job failed: {e}")
            raise
        
        finally:
            # Clean up connections
            self._cleanup_connections()
    
    def _execute_step(self, step: BaseStep, context: ExecutionContext) -> ExecutionContext:
        """
        Execute a single step with transaction management.
        
        Args:
            step: Step to execute
            context: Current execution context
            
        Returns:
            Updated execution context with step result
        """
        # Check if step should be executed
        if not self._should_execute_step(step, context):
            # Skip step
            result = StepResult(
                step_id=step.id,
                status=StepStatus.SKIPPED,
                output=None,
                metrics={},
            )
            return context.with_step_result(step.id, result)
        
        # Get transaction group for this step
        tx_group = self._get_transaction_group_for_step(step.id)
        
        # Begin transaction if first step in group
        if tx_group and self._is_first_step_in_group(step.id, tx_group):
            # Get connection for transaction
            if step.connection:
                conn = self._get_connection(step.connection)
                self._begin_transaction(tx_group, conn)
        
        try:
            # Check for batch/loop execution
            if hasattr(step, 'batch') and step.batch:
                # Execute step in batch mode
                result = self._execute_step_batched(step, context)
            else:
                # Render step config with templates
                rendered_step = self._render_step_config(step, context)
                
                # Inject connection if needed
                if step.connection:
                    conn = self._get_connection(step.connection)
                    # Store connection in context for executor access
                    context = context.with_vars(_connection=conn)
                
                # Dispatch to executor
                result = dispatch_step(rendered_step, context)
            
            # Update context with result
            context = context.with_step_result(step.id, result)
            
            # Commit transaction if last step in group and successful
            if tx_group and self._is_last_step_in_group(step.id, tx_group):
                if result.status == StepStatus.OK:
                    conn = self._get_connection(step.connection)
                    self._commit_transaction(tx_group, conn)
                else:
                    conn = self._get_connection(step.connection)
                    self._rollback_transaction(tx_group, conn)
            
            return context
        
        except Exception as e:
            # Rollback transaction on error
            if tx_group and self._active_transaction:
                conn = self._get_connection(step.connection)
                self._rollback_transaction(tx_group, conn)
            raise
    
    def _execute_step_batched(self, step: BaseStep, context: ExecutionContext) -> StepResult:
        """
        Execute a step in batch mode (loop over collection).
        
        Args:
            step: Step with batch configuration
            context: Current execution context
            
        Returns:
            Aggregated StepResult with all batch results
        """
        batch_config = step.batch
        
        # Resolve batch collection from context
        template_context = context.to_template_dict()
        collection_expr = batch_config.from_
        
        # Render the collection expression
        collection = self.template_engine.render_string(
            f"{{{{ {collection_expr} }}}}", 
            template_context
        )
        
        if not isinstance(collection, list):
            raise ValueError(f"Batch 'from' expression must evaluate to a list, got {type(collection)}")
        
        logger.info(f"Executing step '{step.id}' in batch mode over {len(collection)} items")
        
        # Execute step for each item
        batch_results = []
        alias = batch_config.as_
        
        for idx, item in enumerate(collection):
            # Create context with loop variables
            loop_context = context.with_vars(**{
                alias: item,
                'idx': idx,
                'index': idx,
            })
            
            # Render step config with loop context
            rendered_step = self._render_step_config(step, loop_context)
            
            # Inject connection if needed
            if step.connection:
                conn = self._get_connection(step.connection)
                loop_context = loop_context.with_vars(_connection=conn)
            
            # Execute
            item_result = dispatch_step(rendered_step, loop_context)
            
            if item_result.status == StepStatus.OK:
                batch_results.append(item_result.output)
            else:
                # Batch item failed
                logger.error(f"Batch item {idx} failed in step '{step.id}'")
                return item_result  # Return error result
        
        # Aggregate results
        return StepResult(
            step_id=step.id,
            status=StepStatus.OK,
            output=batch_results,
            metrics={
                'batch_size': len(collection),
                'successful_items': len(batch_results),
            },
        )
    
    def _cleanup_connections(self):
        """Clean up all connections."""
        for conn_name, conn in self._connections.items():
            try:
                if hasattr(conn, 'disconnect'):
                    conn.disconnect()
                logger.debug(f"Closed connection '{conn_name}'")
            except Exception as e:
                logger.error(f"Error closing connection '{conn_name}': {e}")
        
        self._connections.clear()

