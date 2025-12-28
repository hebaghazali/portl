"""
Lambda invocation step executor.

Invokes AWS Lambda functions synchronously with payload and returns parsed response.
"""

import boto3
import json
import logging
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError

from ..executor import register_executor
from ..context import ExecutionContext, StepResult, StepStatus
from ...schema import BaseStep

logger = logging.getLogger(__name__)


@register_executor("lambda.invoke")
class LambdaInvokeExecutor:
    """Executor for lambda.invoke step type."""
    
    def execute(self, step: BaseStep, context: ExecutionContext) -> StepResult:
        """
        Execute Lambda invocation.
        
        Args:
            step: Lambda invocation step configuration
            context: Execution context
            
        Returns:
            StepResult with Lambda response payload
        """
        # Get connection from context
        connection_name = step.connection
        if not connection_name:
            raise ValueError("lambda.invoke step requires a 'connection' field")
        
        # Get connection config
        if not hasattr(context, 'globals') or 'connections' not in context.globals:
            # Try to get from job connections
            job_connections = context.current_vars.get('_job_connections')
            if not job_connections or connection_name not in job_connections:
                raise ValueError(f"Connection '{connection_name}' not found in job configuration")
            conn_config = job_connections[connection_name].config
        else:
            connections = context.globals.get('connections', {})
            if connection_name not in connections:
                raise ValueError(f"Connection '{connection_name}' not defined in job")
            conn_config = connections[connection_name].config
        
        # Extract Lambda config
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
        
        # Get Lambda function configuration
        region = conn_config.get('region', 'us-east-1')
        function_name = conn_config.get('function_name')
        
        if not function_name:
            raise ValueError("Lambda connection requires 'function_name' in config")
        
        # Get AWS credentials (optional - can use IAM role or env vars)
        aws_access_key_id = conn_config.get('aws_access_key_id')
        aws_secret_access_key = conn_config.get('aws_secret_access_key')
        
        # Get payload and timeout
        payload = config.get('payload', {})
        timeout = config.get('timeout', 30)
        
        logger.info(f"Invoking Lambda function: {function_name} in region {region}")
        
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

