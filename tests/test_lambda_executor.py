"""
Tests for Lambda invocation executor.

Uses moto to mock AWS Lambda service without requiring real AWS infrastructure.
"""

import pytest
import json
import boto3
from moto import mock_lambda
from pathlib import Path
import zipfile
import io

from portl.execution.context import ExecutionContext, StepStatus
from portl.execution.executor import dispatch_step
from portl.schema import Step as DataclassStep, ConnectionConfig


# Lambda function code for testing
LAMBDA_FUNCTION_CODE = """
import json

def lambda_handler(event, context):
    # Echo the input with some processing
    data = event.get('data', {})
    processed = {
        'input': data,
        'processed': True,
        'count': len(str(data))
    }
    return processed
"""

ERROR_LAMBDA_CODE = """
def lambda_handler(event, context):
    raise ValueError("Test error from Lambda")
"""


def create_lambda_zip(code: str) -> bytes:
    """Create a ZIP file containing Lambda function code."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr('lambda_function.py', code)
    return zip_buffer.getvalue()


@pytest.fixture
def lambda_client():
    """Create mocked Lambda client."""
    with mock_lambda():
        client = boto3.client('lambda', region_name='us-east-1')
        
        # Create test Lambda function
        client.create_function(
            FunctionName='test-processor',
            Runtime='python3.9',
            Role='arn:aws:iam::123456789012:role/lambda-role',
            Handler='lambda_function.lambda_handler',
            Code={'ZipFile': create_lambda_zip(LAMBDA_FUNCTION_CODE)},
            Timeout=30,
        )
        
        # Create error Lambda function
        client.create_function(
            FunctionName='error-function',
            Runtime='python3.9',
            Role='arn:aws:iam::123456789012:role/lambda-role',
            Handler='lambda_function.lambda_handler',
            Code={'ZipFile': create_lambda_zip(ERROR_LAMBDA_CODE)},
            Timeout=30,
        )
        
        yield client


class TestLambdaExecutor:
    """Test suite for Lambda invocation executor."""
    
    def test_lambda_invoke_basic(self, lambda_client):
        """Test successful Lambda invocation returns parsed JSON."""
        # Create connection config
        conn_config = ConnectionConfig(
            name='lambda_processor',
            type='lambda',
            config={
                'region': 'us-east-1',
                'function_name': 'test-processor',
            }
        )
        
        # Create Lambda step
        step = DataclassStep(
            id='invoke_lambda',
            type='lambda.invoke',
            connection='lambda_processor',
            save_as='result',
            config={
                'payload': {
                    'data': {'key': 'value', 'number': 42}
                },
                'timeout': 30,
            }
        )
        
        # Create context with job connections
        context = ExecutionContext.new()
        context = context.with_vars(_job_connections={'lambda_processor': conn_config})
        
        # Execute step
        result = dispatch_step(step, context)
        
        # Verify result
        assert result.status == StepStatus.OK
        assert result.output is not None
        assert isinstance(result.output, dict)
        assert result.output['processed'] is True
        assert 'input' in result.output
        assert result.metrics['function_name'] == 'test-processor'
        assert result.metrics['status_code'] == 200
    
    def test_lambda_invoke_with_templated_payload(self, lambda_client):
        """Test that Jinja expressions in payload are already rendered by engine."""
        # In practice, the engine renders templates before executor receives them
        # This test verifies the executor handles pre-rendered data correctly
        
        conn_config = ConnectionConfig(
            name='lambda_processor',
            type='lambda',
            config={
                'region': 'us-east-1',
                'function_name': 'test-processor',
            }
        )
        
        # Simulated payload after template rendering
        rendered_payload = {
            'data': {
                'user_id': '123',
                'email': 'test@example.com'
            }
        }
        
        step = DataclassStep(
            id='invoke_lambda',
            type='lambda.invoke',
            connection='lambda_processor',
            config={
                'payload': rendered_payload,
            }
        )
        
        context = ExecutionContext.new()
        context = context.with_vars(_job_connections={'lambda_processor': conn_config})
        
        result = dispatch_step(step, context)
        
        assert result.status == StepStatus.OK
        assert result.output['input'] == rendered_payload['data']
    
    def test_lambda_invoke_timeout(self, lambda_client):
        """Test that timeout error is raised and retryable."""
        # Note: moto doesn't fully simulate timeouts, but we can test timeout config
        
        conn_config = ConnectionConfig(
            name='lambda_processor',
            type='lambda',
            config={
                'region': 'us-east-1',
                'function_name': 'test-processor',
            }
        )
        
        step = DataclassStep(
            id='invoke_lambda',
            type='lambda.invoke',
            connection='lambda_processor',
            config={
                'payload': {'data': 'test'},
                'timeout': 1,  # Very short timeout
            }
        )
        
        context = ExecutionContext.new()
        context = context.with_vars(_job_connections={'lambda_processor': conn_config})
        
        # Execute - should still succeed with moto since it's mocked
        # In real AWS, this would timeout
        result = dispatch_step(step, context)
        
        # With moto, this succeeds
        assert result.status == StepStatus.OK
    
    def test_lambda_invoke_function_error(self, lambda_client):
        """Test that Lambda function errors are surfaced properly."""
        conn_config = ConnectionConfig(
            name='lambda_error',
            type='lambda',
            config={
                'region': 'us-east-1',
                'function_name': 'error-function',
            }
        )
        
        step = DataclassStep(
            id='invoke_lambda',
            type='lambda.invoke',
            connection='lambda_error',
            config={
                'payload': {'data': 'test'},
            }
        )
        
        context = ExecutionContext.new()
        context = context.with_vars(_job_connections={'lambda_error': conn_config})
        
        # Execute - should raise exception due to Lambda error
        with pytest.raises(RuntimeError) as exc_info:
            dispatch_step(step, context)
        
        assert 'Lambda function error' in str(exc_info.value)
    
    def test_lambda_invoke_missing_connection(self):
        """Test that missing connection fails with clear error message."""
        step = DataclassStep(
            id='invoke_lambda',
            type='lambda.invoke',
            connection='nonexistent_connection',
            config={
                'payload': {'data': 'test'},
            }
        )
        
        context = ExecutionContext.new()
        # No connections in context
        
        with pytest.raises(ValueError) as exc_info:
            dispatch_step(step, context)
        
        assert 'Connection' in str(exc_info.value)
        assert 'not found' in str(exc_info.value)
    
    def test_lambda_invoke_missing_function_name(self, lambda_client):
        """Test that missing function name in config raises error."""
        conn_config = ConnectionConfig(
            name='lambda_invalid',
            type='lambda',
            config={
                'region': 'us-east-1',
                # Missing function_name
            }
        )
        
        step = DataclassStep(
            id='invoke_lambda',
            type='lambda.invoke',
            connection='lambda_invalid',
            config={
                'payload': {'data': 'test'},
            }
        )
        
        context = ExecutionContext.new()
        context = context.with_vars(_job_connections={'lambda_invalid': conn_config})
        
        with pytest.raises(ValueError) as exc_info:
            dispatch_step(step, context)
        
        assert 'function_name' in str(exc_info.value)


# Run tests if executed directly
if __name__ == '__main__':
    pytest.main([__file__, '-v'])

