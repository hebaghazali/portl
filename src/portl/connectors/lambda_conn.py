"""
AWS Lambda connection wrapper for Portl.

Provides a connection wrapper that caches the boto3 Lambda client
for efficient reuse across multiple invocations in batch processing.
"""

import boto3
import boto3.session
import json
import logging
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class LambdaConnection:
    """
    Lambda connection wrapper with cached boto3 client.
    
    Caches the boto3 Lambda client for reuse across multiple invocations,
    which improves performance for batch Lambda calls.
    
    Attributes:
        region: AWS region for the Lambda function
        function_name: Name or ARN of the Lambda function
        timeout: Read timeout for Lambda invocation in seconds
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Lambda connection from configuration.
        
        Args:
            config: Configuration dictionary with keys:
                - region: AWS region (default: 'us-east-1')
                - function_name: Lambda function name or ARN (required)
                - timeout: Read timeout in seconds (default: 30)
                - aws_access_key_id: Optional AWS access key
                - aws_secret_access_key: Optional AWS secret key
        """
        self.region = config.get('region', 'us-east-1')
        self.function_name = config.get('function_name')
        self.timeout = config.get('timeout', 30)
        self.aws_access_key_id = config.get('aws_access_key_id')
        self.aws_secret_access_key = config.get('aws_secret_access_key')
        self._client = None
        
        if not self.function_name:
            raise ValueError("Lambda connection requires 'function_name' in config")
        
        logger.debug(f"Initialized Lambda connection: function={self.function_name}, region={self.region}")
    
    def get_client(self):
        """
        Get or create the boto3 Lambda client.
        
        Returns:
            Configured boto3 Lambda client
        """
        if self._client is None:
            client_kwargs = {
                'region_name': self.region,
                'config': boto3.session.Config(
                    read_timeout=self.timeout,
                    connect_timeout=10,
                )
            }
            
            # Add credentials if provided
            if self.aws_access_key_id and self.aws_secret_access_key:
                client_kwargs['aws_access_key_id'] = self.aws_access_key_id
                client_kwargs['aws_secret_access_key'] = self.aws_secret_access_key
            
            self._client = boto3.client('lambda', **client_kwargs)
            logger.debug(f"Created boto3 Lambda client for {self.function_name} in {self.region}")
        
        return self._client
    
    def invoke(
        self,
        payload: Dict[str, Any],
        invocation_type: str = 'RequestResponse'
    ) -> Dict[str, Any]:
        """
        Invoke the Lambda function.
        
        Args:
            payload: JSON-serializable payload to send to the function
            invocation_type: 'RequestResponse' (sync) or 'Event' (async)
            
        Returns:
            Dictionary with:
                - status_code: HTTP status code from Lambda
                - payload: Parsed response payload (dict or string)
                
        Raises:
            RuntimeError: If Lambda invocation fails
        """
        client = self.get_client()
        
        logger.info(f"Invoking Lambda function: {self.function_name}")
        
        try:
            # Serialize payload to JSON bytes
            payload_bytes = json.dumps(payload).encode('utf-8')
            
            # Invoke Lambda synchronously
            response = client.invoke(
                FunctionName=self.function_name,
                InvocationType=invocation_type,
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
            
            return {
                'status_code': status_code,
                'payload': parsed_response,
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            logger.error(f"AWS error invoking Lambda: {error_code} - {error_message}")
            raise RuntimeError(f"Lambda invocation failed: {error_code} - {error_message}")
    
    def close(self) -> None:
        """
        Close the Lambda client.
        
        Note: boto3 clients don't require explicit closing, but this method
        is provided for consistency with other connection types.
        """
        if self._client is not None:
            # boto3 clients don't have a close method, but we can clear the reference
            self._client = None
            logger.debug(f"Cleared Lambda client for {self.function_name}")
    
    def __enter__(self) -> "LambdaConnection":
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit."""
        self.close()
    
    def __repr__(self) -> str:
        return f"LambdaConnection(function={self.function_name!r}, region={self.region!r})"

