"""
Step executor protocol and registry.

Implements the Strategy pattern with a registry for dispatching steps to
their corresponding executors, plus middleware composition for cross-cutting
concerns (retry, logging, metrics, templating).
"""

from typing import Protocol, Dict, Type, Callable, Any, Optional
from abc import abstractmethod
import logging
import time
from functools import wraps

from .context import ExecutionContext, StepResult, StepStatus
from ..schema import BaseStep

logger = logging.getLogger(__name__)


class StepExecutor(Protocol):
    """
    Protocol for step executors.
    
    Each executor implements business logic for a specific step type
    (csv.read, db.upsert, api.call, etc.) and returns a StepResult.
    
    Executors should be pure — middleware handles cross-cutting concerns.
    """
    
    @abstractmethod
    def execute(self, step: BaseStep, context: ExecutionContext) -> StepResult:
        """
        Execute a step and return its result.
        
        Args:
            step: Step configuration (typed subclass of BaseStep)
            context: Current execution context
            
        Returns:
            StepResult with status, output, and metrics
            
        Raises:
            Exception: On execution failure (middleware handles retry/error)
        """
        ...


# Global registry mapping step type names to executor classes
_EXECUTOR_REGISTRY: Dict[str, Type[StepExecutor]] = {}


def register_executor(step_type: str):
    """
    Decorator to register a step executor for a given step type.
    
    Usage:
        @register_executor("csv.read")
        class CSVReadExecutor:
            def execute(self, step, context):
                # ...
    
    Args:
        step_type: Step type identifier (e.g., "csv.read", "db.upsert")
        
    Returns:
        Decorator function
    """
    def decorator(executor_class: Type[StepExecutor]) -> Type[StepExecutor]:
        if step_type in _EXECUTOR_REGISTRY:
            logger.warning(f"Overwriting executor for step type '{step_type}'")
        
        _EXECUTOR_REGISTRY[step_type] = executor_class
        logger.debug(f"Registered executor for '{step_type}': {executor_class.__name__}")
        
        return executor_class
    
    return decorator


def get_executor(step_type: str) -> Optional[Type[StepExecutor]]:
    """
    Get the executor class for a given step type.
    
    Args:
        step_type: Step type identifier
        
    Returns:
        Executor class if registered, None otherwise
    """
    return _EXECUTOR_REGISTRY.get(step_type)


def list_registered_executors() -> Dict[str, Type[StepExecutor]]:
    """
    Get all registered executors.
    
    Returns:
        Dict mapping step types to executor classes
    """
    return dict(_EXECUTOR_REGISTRY)


# Middleware decorators for cross-cutting concerns

def with_metrics(executor_func: Callable) -> Callable:
    """
    Middleware to track execution metrics.
    
    Adds duration_ms, retries_count to step result metrics.
    """
    @wraps(executor_func)
    def wrapper(step: BaseStep, context: ExecutionContext) -> StepResult:
        start_time = time.time()
        
        try:
            result = executor_func(step, context)
            
            # Add timing metrics
            duration_ms = (time.time() - start_time) * 1000
            metrics = {**result.metrics, 'duration_ms': round(duration_ms, 2)}
            
            # Create new result with updated metrics
            return StepResult(
                step_id=result.step_id,
                status=result.status,
                output=result.output,
                metrics=metrics,
                error=result.error,
                touched_transaction=result.touched_transaction,
            )
        
        except Exception as e:
            # Still capture timing even on failure
            duration_ms = (time.time() - start_time) * 1000
            
            return StepResult(
                step_id=step.id,
                status=StepStatus.ERROR,
                output=None,
                metrics={'duration_ms': round(duration_ms, 2)},
                error=e,
                touched_transaction=False,
            )
    
    return wrapper


def with_logging(executor_func: Callable) -> Callable:
    """
    Middleware to log step execution.
    
    Logs start, completion, and errors with structured context.
    """
    @wraps(executor_func)
    def wrapper(step: BaseStep, context: ExecutionContext) -> StepResult:
        logger.info(
            f"Executing step '{step.id}' (type: {step.type})",
            extra={
                'run_id': context.run_id,
                'step_id': step.id,
                'step_type': step.type,
            }
        )
        
        try:
            result = executor_func(step, context)
            
            if result.status == StepStatus.OK:
                logger.info(
                    f"Step '{step.id}' completed successfully",
                    extra={
                        'run_id': context.run_id,
                        'step_id': step.id,
                        'metrics': result.metrics,
                    }
                )
            elif result.status == StepStatus.SKIPPED:
                logger.info(
                    f"Step '{step.id}' skipped",
                    extra={
                        'run_id': context.run_id,
                        'step_id': step.id,
                    }
                )
            else:
                logger.error(
                    f"Step '{step.id}' failed: {result.error}",
                    extra={
                        'run_id': context.run_id,
                        'step_id': step.id,
                        'error': str(result.error),
                    }
                )
            
            return result
        
        except Exception as e:
            logger.error(
                f"Step '{step.id}' raised exception: {e}",
                exc_info=True,
                extra={
                    'run_id': context.run_id,
                    'step_id': step.id,
                }
            )
            raise
    
    return wrapper


def with_retry(executor_func: Callable) -> Callable:
    """
    Middleware to implement retry logic with exponential backoff.
    
    Reads retry config from step.retry and implements retry with backoff.
    """
    @wraps(executor_func)
    def wrapper(step: BaseStep, context: ExecutionContext) -> StepResult:
        # Check if retry is configured
        retry_config = getattr(step, 'retry', None)
        
        if not retry_config:
            # No retry configured, execute once
            return executor_func(step, context)
        
        # Parse retry configuration
        max_attempts = getattr(retry_config, 'max_attempts', 3)
        backoff_ms = getattr(retry_config, 'backoff_ms', 1000)
        retry_on = getattr(retry_config, 'retry_on', None)
        
        last_error = None
        
        for attempt in range(1, max_attempts + 1):
            try:
                result = executor_func(step, context)
                
                # Update metrics with retry count
                metrics = {**result.metrics, 'attempts': attempt}
                
                return StepResult(
                    step_id=result.step_id,
                    status=result.status,
                    output=result.output,
                    metrics=metrics,
                    error=result.error,
                    touched_transaction=result.touched_transaction,
                )
            
            except Exception as e:
                last_error = e
                
                # Check if we should retry this error
                should_retry = True
                if retry_on:
                    error_type = type(e).__name__
                    should_retry = error_type in retry_on
                
                if not should_retry or attempt >= max_attempts:
                    # Don't retry or out of attempts
                    logger.warning(
                        f"Step '{step.id}' failed after {attempt} attempt(s): {e}",
                        extra={'run_id': context.run_id, 'step_id': step.id}
                    )
                    raise
                
                # Wait before retry with exponential backoff
                wait_ms = backoff_ms * (2 ** (attempt - 1))
                logger.info(
                    f"Step '{step.id}' attempt {attempt} failed, retrying in {wait_ms}ms...",
                    extra={'run_id': context.run_id, 'step_id': step.id}
                )
                time.sleep(wait_ms / 1000)
        
        # Should never reach here, but just in case
        raise last_error or Exception("Unknown retry failure")
    
    return wrapper


def compose_middlewares(*middlewares: Callable) -> Callable:
    """
    Compose multiple middleware decorators.
    
    Args:
        *middlewares: Middleware functions to compose (applied right to left)
        
    Returns:
        Composed middleware function
    """
    def decorator(func: Callable) -> Callable:
        result = func
        for middleware in reversed(middlewares):
            result = middleware(result)
        return result
    return decorator


def dispatch_step(step: BaseStep, context: ExecutionContext) -> StepResult:
    """
    Dispatch a step to its registered executor with middleware.
    
    Args:
        step: Step to execute
        context: Current execution context
        
    Returns:
        StepResult from executor
        
    Raises:
        ValueError: If no executor registered for step type
    """
    executor_class = get_executor(step.type)
    
    if not executor_class:
        raise ValueError(
            f"No executor registered for step type '{step.type}'. "
            f"Available types: {list(_EXECUTOR_REGISTRY.keys())}"
        )
    
    # Instantiate executor
    executor = executor_class()
    
    # Compose middleware stack: retry -> logging -> metrics -> execute
    execute_with_middleware = compose_middlewares(
        with_retry,
        with_logging,
        with_metrics,
    )(executor.execute)
    
    # Execute with middleware
    return execute_with_middleware(step, context)

