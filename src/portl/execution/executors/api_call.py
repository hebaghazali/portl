"""
API call step executor.

Supports both direct HTTP calls and transactional outbox pattern.
"""

import httpx
import logging
from typing import Dict, Any

from ..executor import register_executor
from ..context import ExecutionContext, StepResult, StepStatus
from ...schema import BaseStep
from ...connectors.base import BaseDestinationConnector

logger = logging.getLogger(__name__)


@register_executor("api.call")
class APICallExecutor:
    """Executor for api.call step type."""
    
    def execute(self, step: BaseStep, context: ExecutionContext) -> StepResult:
        """
        Execute API call - either direct or via outbox.
        
        Args:
            step: API call step configuration
            context: Execution context
            
        Returns:
            StepResult with response data or outbox event ID
        """
        # Get configuration
        if hasattr(step, 'config') and isinstance(step.config, dict):
            # Dataclass Step
            config = step.config
            delivery = config.get('delivery', 'direct')
        else:
            # Pydantic Step
            delivery = getattr(step, 'delivery', 'direct')
            config = step.config if hasattr(step, 'config') else {}
        
        if delivery == 'outbox':
            return self._enqueue_to_outbox(step, context, config)
        else:
            return self._call_directly(step, context, config)
    
    def _enqueue_to_outbox(
        self, 
        step: BaseStep, 
        context: ExecutionContext,
        config: Dict[str, Any]
    ) -> StepResult:
        """
        Write API call intent to outbox (inside transaction).
        
        Args:
            step: Step configuration
            context: Execution context
            config: Step config dict
            
        Returns:
            StepResult with outbox event ID
        """
        connection = context.current_vars.get('_connection')
        if not connection:
            raise ValueError("API call with delivery='outbox' requires a database connection in context")
        
        if not isinstance(connection, BaseDestinationConnector):
            raise TypeError(f"Connection must be a BaseDestinationConnector, got {type(connection)}")
        
        # Build payload
        method = config.get('method')
        url = config.get('url') or config.get('path')
        headers = config.get('headers', {})
        body = config.get('body')
        
        if not method or not url:
            raise ValueError("API call requires 'method' and 'url' fields")
        
        payload = {
            'method': method,
            'url': url,
            'headers': headers,
            'body': body,
        }
        
        # Idempotency key
        idempotency_key = config.get('idempotency_key', f"{context.run_id}-{step.id}")
        
        logger.info(f"Enqueueing API call to outbox: {method} {url}")
        
        # Insert into outbox
        event_id = connection.insert_outbox_event(
            run_id=context.run_id,
            step_id=step.id,
            delivery_type='api.call',
            payload=payload,
            idempotency_key=idempotency_key
        )
        
        return StepResult(
            step_id=step.id,
            status=StepStatus.OK,
            output={'outbox_id': event_id, 'status': 'enqueued'},
            metrics={'delivery': 'outbox'},
            touched_transaction=True,
        )
    
    def _call_directly(
        self, 
        step: BaseStep, 
        context: ExecutionContext,
        config: Dict[str, Any]
    ) -> StepResult:
        """
        Make immediate HTTP call.
        
        Args:
            step: Step configuration
            context: Execution context
            config: Step config dict
            
        Returns:
            StepResult with HTTP response
        """
        method = config.get('method')
        url = config.get('url') or config.get('path')
        headers = config.get('headers', {}).copy()
        body = config.get('body')
        idempotency_key = config.get('idempotency_key')
        
        if not method or not url:
            raise ValueError("API call requires 'method' and 'url' fields")
        
        # Add idempotency key if provided
        if idempotency_key:
            headers['Idempotency-Key'] = idempotency_key
        
        logger.info(f"Making direct API call: {method} {url}")
        
        try:
            response = httpx.request(
                method=method,
                url=url,
                headers=headers,
                json=body if body else None,
                timeout=30.0
            )
            
            response.raise_for_status()
            
            # Try to parse JSON response
            try:
                response_body = response.json()
            except:
                response_body = response.text
            
            return StepResult(
                step_id=step.id,
                status=StepStatus.OK,
                output={
                    'status_code': response.status_code,
                    'body': response_body,
                },
                metrics={
                    'delivery': 'direct',
                    'status_code': response.status_code,
                },
            )
        
        except httpx.HTTPError as e:
            logger.error(f"API call failed: {e}")
            raise

