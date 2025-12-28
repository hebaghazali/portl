"""
Lambda invocation step executor.

Invokes AWS Lambda functions synchronously with payload and returns parsed response.
Uses LambdaConnection wrapper when available for client caching.
"""

import json
import logging
from typing import Dict, Any, Optional

from ..executor import register_executor
from ..context import ExecutionContext, StepResult, StepStatus
from ...schema import BaseStep
from ...connectors.lambda_conn import LambdaConnection

logger = logging.getLogger(__name__)


@register_executor("lambda.invoke")
class LambdaInvokeExecutor:
    """Executor for lambda.invoke step type."""
    
    def execute(self, step: BaseStep, context: ExecutionContext) -> StepResult:
        """
        Execute Lambda invocation.
        
        Uses LambdaConnection wrapper if available for client caching,
        otherwise falls back to creating a new boto3 client.
        
        Args:
            step: Lambda invocation step configuration
            context: Execution context
            
        Returns:
            StepResult with Lambda response payload
        """
        # Check for Lambda connection wrapper in context (preferred path)
        lambda_conn: Optional[LambdaConnection] = None
        connection = context.current_vars.get('_connection')
        if isinstance(connection, LambdaConnection):
            lambda_conn = connection
        
        # Get step configuration
        if hasattr(step, 'config') and isinstance(step.config, dict):
            # Dataclass Step
            config = step.config
        else:
            # Pydantic Step - convert to dict
            config = {}
            if hasattr(step, 'payload'):
                config['payload'] = step.payload
            if hasattr(step, 'timeout'):
                config['timeout'] = step.timeout
        
        # Get payload from config
        payload = config.get('payload', {})
        
        if lambda_conn:
            # Use the connection wrapper (preferred - has cached client)
            return self._invoke_via_connection(step, lambda_conn, payload)
        else:
            # Fall back to creating client from job connections
            return self._invoke_via_job_config(step, context, config, payload)
    
    def _invoke_via_connection(
        self,
        step: BaseStep,
        lambda_conn: LambdaConnection,
        payload: Dict[str, Any]
    ) -> StepResult:
        """
        Invoke Lambda using the connection wrapper.
        
        Args:
            step: Step configuration
            lambda_conn: Lambda connection wrapper with cached client
            payload: Payload to send to the function
            
        Returns:
            StepResult with Lambda response
        """
        logger.info(f"Invoking Lambda via connection: {lambda_conn.function_name}")
        
        try:
            result = lambda_conn.invoke(payload)
            
            return StepResult(
                step_id=step.id,
                status=StepStatus.OK,
                output=result['payload'],
                metrics={
                    'status_code': result['status_code'],
                    'function_name': lambda_conn.function_name,
                    'region': lambda_conn.region,
                    'used_connection': True,
                },
            )
        
        except RuntimeError as e:
            logger.error(f"Lambda invocation failed: {e}")
            raise
    
    def _invoke_via_job_config(
        self,
        step: BaseStep,
        context: ExecutionContext,
        config: Dict[str, Any],
        payload: Dict[str, Any]
    ) -> StepResult:
        """
        Invoke Lambda by creating a new client from job connection config.
        
        This is the fallback path when no LambdaConnection wrapper is available.
        
        Args:
            step: Step configuration
            context: Execution context
            config: Step config dict
            payload: Payload to send to the function
            
        Returns:
            StepResult with Lambda response
        """
        import boto3
        import boto3.session
        from botocore.exceptions import ClientError
        
        # Get connection name from step
        connection_name = step.connection
        if not connection_name:
            raise ValueError("lambda.invoke step requires a 'connection' field")
        
        # Get connection config from job
        job_connections = context.current_vars.get('_job_connections')
        if not job_connections or connection_name not in job_connections:
            raise ValueError(f"Connection '{connection_name}' not found in job configuration")
        
        conn_config = job_connections[connection_name].config
        
        # Extract Lambda config
        region = conn_config.get('region', 'us-east-1')
        function_name = conn_config.get('function_name')
        
        if not function_name:
            raise ValueError("Lambda connection requires 'function_name' in config")
        
        # Get AWS credentials (optional - can use IAM role or env vars)
        aws_access_key_id = conn_config.get('aws_access_key_id')
        aws_secret_access_key = conn_config.get('aws_secret_access_key')
        
        # Get timeout
        timeout = config.get('timeout', 30)
        
        logger.info(f"Invoking Lambda function (new client): {function_name} in region {region}")
        
        try:
            # Create boto3 Lambda client
            client_kwargs = {
                'region_name': region,
                'config': boto3.session.Config(
                    read_timeout=timeout,
                    connect_timeout=10,
                )
            }
            
            # Add credentials if provided
            if aws_access_key_id and aws_secret_access_key:
                client_kwargs['aws_access_key_id'] = aws_access_key_id
                client_kwargs['aws_secret_access_key'] = aws_secret_access_key
            
            lambda_client = boto3.client('lambda', **client_kwargs)
            
            # Serialize payload to JSON
            payload_bytes = json.dumps(payload).encode('utf-8')
            
            # Invoke Lambda synchronously
            response = lambda_client.invoke(
                FunctionName=function_name,
                InvocationType='RequestResponse',
                Payload=payload_bytes
            )
            
            # Check for function error
            if 'FunctionError' in response:
                error_type = response['FunctionError']
                error_payload = response['Payload'].read().decode('utf-8')
                logger.error(f"Lambda function error ({error_type}): {error_payload}")
                raise RuntimeError(f"Lambda function error: {error_type} - {error_payload}")
            
            # Parse response payload
            response_payload = response['Payload'].read().decode('utf-8')
            
            try:
                parsed_response = json.loads(response_payload)
            except json.JSONDecodeError:
                # If not JSON, return as string
                parsed_response = response_payload
            
            status_code = response.get('StatusCode', 200)
            
            logger.info(f"Lambda invocation successful (status: {status_code})")
            
            return StepResult(
                step_id=step.id,
                status=StepStatus.OK,
                output=parsed_response,
                metrics={
                    'status_code': status_code,
                    'function_name': function_name,
                    'region': region,
                    'used_connection': False,
                },
            )
        
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f"AWS error invoking Lambda: {error_code} - {error_message}")
            raise RuntimeError(f"Lambda invocation failed: {error_code} - {error_message}")
        
        except Exception as e:
            logger.error(f"Lambda invocation failed: {e}")
            raise
