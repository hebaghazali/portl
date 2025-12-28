"""
End-to-end integration tests for complete Portl workflows.

These tests validate that the full flow works from source to destination,
including HTTP and Lambda connections with proper connection pooling.
"""

import pytest
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import test utilities
try:
    from pytest_httpserver import HTTPServer
    HTTPSERVER_AVAILABLE = True
except ImportError:
    HTTPSERVER_AVAILABLE = False
    HTTPServer = None  # Placeholder for type hints

try:
    import boto3
    from moto import mock_lambda
    import zipfile
    import io
    MOTO_AVAILABLE = True
except ImportError:
    MOTO_AVAILABLE = False

from portl.execution.engine import JobEngine
from portl.execution.context import ExecutionContext, StepStatus
from portl.schema import (
    Job, Step as DataclassStep, ConnectionConfig, 
    TransactionConfig, BatchConfig
)
from portl.connectors.http import HTTPConnection
from portl.connectors.lambda_conn import LambdaConnection


# Lambda function code for testing
LAMBDA_FUNCTION_CODE = """
import json

def lambda_handler(event, context):
    data = event.get('data', {})
    return {
        'input': data,
        'processed': True,
        'processed_name': data.get('name', '').upper() if data.get('name') else 'UNKNOWN'
    }
"""


def create_lambda_zip(code: str) -> bytes:
    """Create a ZIP file containing Lambda function code."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr('lambda_function.py', code)
    return zip_buffer.getvalue()


class TestHTTPConnection:
    """Tests for HTTPConnection wrapper."""
    
    def test_http_connection_initialization(self):
        """Test HTTPConnection initializes with config."""
        config = {
            'base_url': 'https://api.example.com',
            'headers': {'Authorization': 'Bearer token123'},
            'timeout': 60
        }
        
        conn = HTTPConnection(config)
        
        assert conn.base_url == 'https://api.example.com'
        assert conn.default_headers == {'Authorization': 'Bearer token123'}
        assert conn.timeout == 60
        assert conn._client is None  # Lazy initialization
    
    def test_http_connection_client_reuse(self):
        """Test HTTPConnection reuses the same client."""
        config = {'base_url': 'https://api.example.com'}
        conn = HTTPConnection(config)
        
        client1 = conn.get_client()
        client2 = conn.get_client()
        
        assert client1 is client2
        conn.close()
    
    def test_http_connection_close(self):
        """Test HTTPConnection closes properly."""
        config = {'base_url': 'https://api.example.com'}
        conn = HTTPConnection(config)
        
        # Create client
        _ = conn.get_client()
        assert conn._client is not None
        
        # Close
        conn.close()
        assert conn._client is None
    
    def test_http_connection_context_manager(self):
        """Test HTTPConnection works as context manager."""
        config = {'base_url': 'https://api.example.com'}
        
        with HTTPConnection(config) as conn:
            _ = conn.get_client()
            assert conn._client is not None
        
        assert conn._client is None


class TestLambdaConnection:
    """Tests for LambdaConnection wrapper."""
    
    def test_lambda_connection_initialization(self):
        """Test LambdaConnection initializes with config."""
        config = {
            'region': 'us-west-2',
            'function_name': 'my-function',
            'timeout': 60,
        }
        
        conn = LambdaConnection(config)
        
        assert conn.region == 'us-west-2'
        assert conn.function_name == 'my-function'
        assert conn.timeout == 60
        assert conn._client is None
    
    def test_lambda_connection_requires_function_name(self):
        """Test LambdaConnection raises if function_name missing."""
        config = {'region': 'us-east-1'}
        
        with pytest.raises(ValueError, match="function_name"):
            LambdaConnection(config)
    
    @pytest.mark.skipif(not MOTO_AVAILABLE, reason="moto not installed")
    def test_lambda_connection_client_reuse(self):
        """Test LambdaConnection reuses the same boto3 client."""
        with mock_lambda():
            config = {
                'region': 'us-east-1',
                'function_name': 'test-function',
            }
            conn = LambdaConnection(config)
            
            client1 = conn.get_client()
            client2 = conn.get_client()
            
            assert client1 is client2
            conn.close()


class TestEngineConnectionWiring:
    """Tests for connection type wiring in JobEngine."""
    
    def test_engine_creates_http_connection(self, tmp_path):
        """Test JobEngine creates HTTPConnection for http type."""
        # Create a simple CSV file
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("id,name\n1,Test\n")
        
        # Create job with HTTP connection
        job = Job(
            steps=[
                DataclassStep(
                    id='read_csv',
                    type='csv.read',
                    save_as='data',
                    config={'path': str(csv_file)}
                ),
            ],
            connections={
                'api_notify': ConnectionConfig(
                    name='api_notify',
                    type='http',
                    config={
                        'base_url': 'https://api.example.com',
                        'headers': {'Authorization': 'Bearer test'},
                    }
                )
            }
        )
        
        engine = JobEngine(job, dry_run=True)
        
        # Get the HTTP connection
        conn = engine._get_connection('api_notify')
        
        assert isinstance(conn, HTTPConnection)
        assert conn.base_url == 'https://api.example.com'
        assert conn.default_headers == {'Authorization': 'Bearer test'}
    
    @pytest.mark.skipif(not MOTO_AVAILABLE, reason="moto not installed")
    def test_engine_creates_lambda_connection(self, tmp_path):
        """Test JobEngine creates LambdaConnection for lambda type."""
        with mock_lambda():
            # Create a simple CSV file
            csv_file = tmp_path / "data.csv"
            csv_file.write_text("id,name\n1,Test\n")
            
            # Create job with Lambda connection
            job = Job(
                steps=[
                    DataclassStep(
                        id='read_csv',
                        type='csv.read',
                        save_as='data',
                        config={'path': str(csv_file)}
                    ),
                ],
                connections={
                    'lambda_processor': ConnectionConfig(
                        name='lambda_processor',
                        type='lambda',
                        config={
                            'region': 'us-east-1',
                            'function_name': 'test-processor',
                        }
                    )
                }
            )
            
            engine = JobEngine(job, dry_run=True)
            
            # Get the Lambda connection
            conn = engine._get_connection('lambda_processor')
            
            assert isinstance(conn, LambdaConnection)
            assert conn.function_name == 'test-processor'
            assert conn.region == 'us-east-1'


class TestAPICallWithConnection:
    """Tests for api.call executor using HTTP connection."""
    
    @pytest.mark.skipif(not HTTPSERVER_AVAILABLE, reason="pytest-httpserver not installed")
    def test_api_call_uses_connection_base_url(self, httpserver, tmp_path):
        """Test api.call step uses connection's base_url."""
        # Set up mock HTTP endpoint
        httpserver.expect_request("/webhooks/notify", method="POST").respond_with_json(
            {"status": "received"},
            status=200
        )
        
        # Create CSV file
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("id,name\n1,TestUser\n")
        
        # Create job with HTTP connection
        job = Job(
            steps=[
                DataclassStep(
                    id='read_csv',
                    type='csv.read',
                    save_as='data',
                    config={'path': str(csv_file)}
                ),
                DataclassStep(
                    id='notify_api',
                    type='api.call',
                    connection='api_notify',
                    config={
                        'method': 'POST',
                        'url': '/webhooks/notify',  # Relative URL
                        'body': {'message': 'test'},
                    }
                ),
            ],
            connections={
                'api_notify': ConnectionConfig(
                    name='api_notify',
                    type='http',
                    config={
                        'base_url': httpserver.url_for(""),
                        'headers': {'X-Custom-Header': 'test-value'},
                    }
                )
            }
        )
        
        engine = JobEngine(job, dry_run=False)
        context = engine.execute()
        
        # Verify the API call was made
        assert context.has_step_result('notify_api')
        result = context.get_step_result('notify_api')
        assert result.status == StepStatus.OK
        assert result.output['status_code'] == 200
        assert result.output['body'] == {"status": "received"}
        assert result.metrics['used_connection'] is True
    
    @pytest.mark.skipif(not HTTPSERVER_AVAILABLE, reason="pytest-httpserver not installed")
    def test_api_call_merges_headers(self, httpserver, tmp_path):
        """Test api.call merges connection headers with step headers."""
        # Capture headers
        captured_headers = {}
        
        def handle_request(request):
            captured_headers.update(dict(request.headers))
            return json.dumps({"status": "ok"})
        
        httpserver.expect_request("/test", method="POST").respond_with_handler(handle_request)
        
        # Create CSV file
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("id\n1\n")
        
        job = Job(
            steps=[
                DataclassStep(
                    id='read_csv',
                    type='csv.read',
                    save_as='data',
                    config={'path': str(csv_file)}
                ),
                DataclassStep(
                    id='call_api',
                    type='api.call',
                    connection='api_conn',
                    config={
                        'method': 'POST',
                        'url': '/test',
                        'headers': {'X-Step-Header': 'step-value'},  # Step-level header
                        'body': {},
                    }
                ),
            ],
            connections={
                'api_conn': ConnectionConfig(
                    name='api_conn',
                    type='http',
                    config={
                        'base_url': httpserver.url_for(""),
                        'headers': {
                            'X-Connection-Header': 'conn-value',
                            'Authorization': 'Bearer token123',
                        },
                    }
                )
            }
        )
        
        engine = JobEngine(job, dry_run=False)
        context = engine.execute()
        
        result = context.get_step_result('call_api')
        assert result.status == StepStatus.OK
        # Both headers should be present
        assert 'X-Connection-Header' in captured_headers or 'x-connection-header' in captured_headers
        assert 'X-Step-Header' in captured_headers or 'x-step-header' in captured_headers


class TestCSVToAPIFlow:
    """Test complete CSV -> API workflow."""
    
    @pytest.mark.skipif(not HTTPSERVER_AVAILABLE, reason="pytest-httpserver not installed")
    def test_csv_to_api_batch_flow(self, httpserver, tmp_path):
        """Test reading CSV and making API calls for each row."""
        # Track API calls
        api_calls = []
        
        def capture_call(request):
            body = request.get_json()
            api_calls.append(body)
            return json.dumps({"received": True, "id": len(api_calls)})
        
        httpserver.expect_request("/records", method="POST").respond_with_handler(capture_call)
        
        # Create CSV with multiple rows
        csv_file = tmp_path / "records.csv"
        csv_file.write_text("id,name,email\n1,Alice,alice@test.com\n2,Bob,bob@test.com\n3,Carol,carol@test.com\n")
        
        job = Job(
            steps=[
                DataclassStep(
                    id='read_csv',
                    type='csv.read',
                    save_as='csv_data',
                    config={'path': str(csv_file)}
                ),
                DataclassStep(
                    id='notify_each',
                    type='api.call',
                    connection='api_service',
                    batch=BatchConfig(from_='steps.read_csv.rows', as_='row'),
                    config={
                        'method': 'POST',
                        'url': '/records',
                        'body': {'id': '{{ row.id }}', 'name': '{{ row.name }}'},
                    }
                ),
            ],
            connections={
                'api_service': ConnectionConfig(
                    name='api_service',
                    type='http',
                    config={
                        'base_url': httpserver.url_for(""),
                    }
                )
            }
        )
        
        engine = JobEngine(job, dry_run=False, job_file=str(tmp_path / "job.yaml"))
        context = engine.execute()
        
        # Verify all 3 API calls were made
        assert len(api_calls) == 3
        result = context.get_step_result('notify_each')
        assert result.status == StepStatus.OK
        assert result.metrics['batch_size'] == 3


@pytest.mark.skipif(not MOTO_AVAILABLE, reason="moto not installed")
class TestLambdaWithConnection:
    """Tests for lambda.invoke executor using Lambda connection."""
    
    @pytest.fixture
    def setup_lambda(self):
        """Create mock Lambda function."""
        with mock_lambda():
            client = boto3.client('lambda', region_name='us-east-1')
            
            client.create_function(
                FunctionName='test-processor',
                Runtime='python3.9',
                Role='arn:aws:iam::123456789012:role/lambda-role',
                Handler='lambda_function.lambda_handler',
                Code={'ZipFile': create_lambda_zip(LAMBDA_FUNCTION_CODE)},
                Timeout=30,
            )
            
            yield client
    
    def test_lambda_invoke_uses_connection_wrapper(self, setup_lambda, tmp_path):
        """Test lambda.invoke uses LambdaConnection from engine."""
        # Create CSV file
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("id,name\n1,TestItem\n")
        
        job = Job(
            steps=[
                DataclassStep(
                    id='read_csv',
                    type='csv.read',
                    save_as='csv_data',
                    config={'path': str(csv_file)}
                ),
                DataclassStep(
                    id='process_lambda',
                    type='lambda.invoke',
                    connection='lambda_processor',
                    save_as='lambda_result',
                    config={
                        'payload': {'data': {'name': 'test'}},
                    }
                ),
            ],
            connections={
                'lambda_processor': ConnectionConfig(
                    name='lambda_processor',
                    type='lambda',
                    config={
                        'region': 'us-east-1',
                        'function_name': 'test-processor',
                    }
                )
            }
        )
        
        engine = JobEngine(job, dry_run=False, job_file=str(tmp_path / "job.yaml"))
        context = engine.execute()
        
        # Verify Lambda was invoked successfully
        assert 'process_lambda' in context.steps
        result = context.steps['process_lambda']
        assert result.status == StepStatus.OK
        assert result.output['processed'] is True
        assert result.metrics['used_connection'] is True


class TestConnectionCleanup:
    """Tests for proper connection cleanup."""
    
    def test_engine_cleans_up_http_connections(self, tmp_path):
        """Test JobEngine properly closes HTTP connections on cleanup."""
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("id\n1\n")
        
        job = Job(
            steps=[
                DataclassStep(
                    id='read_csv',
                    type='csv.read',
                    save_as='data',
                    config={'path': str(csv_file)}
                ),
            ],
            connections={
                'api': ConnectionConfig(
                    name='api',
                    type='http',
                    config={'base_url': 'https://example.com'}
                )
            }
        )
        
        engine = JobEngine(job, dry_run=True)
        
        # Create a connection
        conn = engine._get_connection('api')
        _ = conn.get_client()  # Force client creation
        assert conn._client is not None
        
        # Cleanup
        engine._cleanup_connections()
        
        # Connection should be closed
        assert conn._client is None
        assert len(engine._connections) == 0


class TestAPICallWithoutConnection:
    """Tests for api.call executor without HTTP connection (standalone mode)."""
    
    @pytest.mark.skipif(not HTTPSERVER_AVAILABLE, reason="pytest-httpserver not installed")
    def test_api_call_standalone_mode(self, httpserver, tmp_path):
        """Test api.call works without connection (absolute URL)."""
        httpserver.expect_request("/standalone", method="GET").respond_with_json(
            {"data": "standalone"}, status=200
        )
        
        csv_file = tmp_path / "data.csv"
        csv_file.write_text("id\n1\n")
        
        # Job without HTTP connection - uses absolute URL
        job = Job(
            steps=[
                DataclassStep(
                    id='read_csv',
                    type='csv.read',
                    save_as='data',
                    config={'path': str(csv_file)}
                ),
                DataclassStep(
                    id='call_api',
                    type='api.call',
                    # No connection specified
                    config={
                        'method': 'GET',
                        'url': httpserver.url_for("/standalone"),  # Absolute URL
                    }
                ),
            ],
        )
        
        engine = JobEngine(job, dry_run=False)
        context = engine.execute()
        
        result = context.get_step_result('call_api')
        assert result.status == StepStatus.OK
        assert result.output['body'] == {"data": "standalone"}
        assert result.metrics['used_connection'] is False

