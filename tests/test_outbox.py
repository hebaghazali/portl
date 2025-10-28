"""
Tests for transactional outbox pattern.

Tests outbox enqueue, sync flush, and idempotency.
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from portl.execution.context import StepStatus
from portl.schema import Step as DataclassStep, Job, ConnectionConfig, TransactionConfig


class TestOutbox:
    """Test suite for outbox pattern."""
    
    def test_outbox_enqueue_inside_transaction(self, postgres_connection, clean_db):
        """
        Test that api.call with delivery='outbox' writes to outbox table.
        
        The event should be created inside the transaction and only
        become visible after commit.
        """
        job = Job(
            steps=[
                DataclassStep(
                    id='api_notify',
                    type='api.call',
                    connection='pg',
                    config={
                        'delivery': 'outbox',
                        'method': 'POST',
                        'url': 'https://api.example.com/webhooks/test',
                        'body': {'message': 'Hello from outbox'},
                        'idempotency_key': 'test-idempotency-key',
                    }
                )
            ],
            connections={
                'pg': ConnectionConfig(
                    name='pg',
                    type='postgres',
                    config={
                        'host': 'localhost',
                        'port': 5433,
                        'database': 'portl_test',
                        'username': 'portl_test',
                        'password': 'portl_test',
                    }
                )
            },
            transaction=TransactionConfig(scope='db')
        )
        
        # Execute
        from portl.execution.engine import JobEngine
        engine = JobEngine(job, dry_run=False)
        context = engine.execute()
        
        # Verify step result
        result = context.get_step_result('api_notify')
        assert result.status == StepStatus.OK
        assert 'outbox_id' in result.output
        assert result.output['status'] == 'enqueued'
        
        # Verify outbox record exists
        cursor = postgres_connection.cursor()
        cursor.execute("""
            SELECT delivery_type, payload, idempotency_key, status
            FROM portl_outbox
            WHERE id = %s
        """, (result.output['outbox_id'],))
        
        row = cursor.fetchone()
        assert row is not None
        delivery_type, payload_json, idempotency_key, status = row
        
        assert delivery_type == 'api.call'
        assert idempotency_key == 'test-idempotency-key'
        assert status == 'pending'
        
        payload = json.loads(payload_json)
        assert payload['method'] == 'POST'
        assert payload['url'] == 'https://api.example.com/webhooks/test'
        assert payload['body'] == {'message': 'Hello from outbox'}
        
        cursor.close()
    
    @patch('httpx.request')
    def test_outbox_sync_flush_delivers_events(self, mock_request, postgres_connection, clean_db):
        """
        Test that flush_for_run delivers outbox events via HTTP.
        
        Mock httpx.request to verify HTTP call is made with correct parameters.
        """
        # Create pending outbox event manually
        cursor = postgres_connection.cursor()
        cursor.execute("""
            INSERT INTO portl_outbox (run_id, step_id, delivery_type, payload, idempotency_key, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            'test-run-123',
            'api_notify',
            'api.call',
            json.dumps({
                'method': 'POST',
                'url': 'https://api.example.com/webhooks/delivered',
                'headers': {},
                'body': {'event': 'test'},
            }),
            'test-idempotency-456',
            'pending'
        ))
        event_id = cursor.fetchone()[0]
        postgres_connection.commit()
        cursor.close()
        
        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response
        
        # Flush outbox
        from portl.services.outbox_dispatcher import OutboxDispatcher
        from portl.connectors.postgres import PostgresConnector
        
        connector = PostgresConnector({
            'type': 'postgres',
            'host': 'localhost',
            'port': 5433,
            'database': 'portl_test',
            'username': 'portl_test',
            'password': 'portl_test',
        })
        connector.connect()
        
        dispatcher = OutboxDispatcher(connector)
        dispatcher.flush_for_run('test-run-123')
        
        # Verify HTTP call was made
        mock_request.assert_called_once()
        call_args = mock_request.call_args
        
        assert call_args.kwargs['method'] == 'POST'
        assert call_args.kwargs['url'] == 'https://api.example.com/webhooks/delivered'
        assert call_args.kwargs['headers']['Idempotency-Key'] == 'test-idempotency-456'
        assert call_args.kwargs['json'] == {'event': 'test'}
        
        # Verify event marked as delivered
        cursor = postgres_connection.cursor()
        cursor.execute("SELECT status, delivered_at FROM portl_outbox WHERE id = %s", (event_id,))
        status, delivered_at = cursor.fetchone()
        
        assert status == 'delivered'
        assert delivered_at is not None
        
        cursor.close()
        connector.disconnect()
    
    @patch('httpx.request')
    def test_outbox_flush_handles_failure(self, mock_request, postgres_connection, clean_db):
        """
        Test that flush_for_run marks events as failed when HTTP call fails.
        """
        # Create pending outbox event
        cursor = postgres_connection.cursor()
        cursor.execute("""
            INSERT INTO portl_outbox (run_id, step_id, delivery_type, payload, idempotency_key, status)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            'test-run-456',
            'api_notify',
            'api.call',
            json.dumps({
                'method': 'POST',
                'url': 'https://api.example.com/webhooks/fail',
                'headers': {},
                'body': {},
            }),
            'test-idempotency-789',
            'pending'
        ))
        event_id = cursor.fetchone()[0]
        postgres_connection.commit()
        cursor.close()
        
        # Mock failed HTTP response
        mock_request.side_effect = Exception("Connection timeout")
        
        # Flush outbox (should handle error gracefully)
        from portl.services.outbox_dispatcher import OutboxDispatcher
        from portl.connectors.postgres import PostgresConnector
        
        connector = PostgresConnector({
            'type': 'postgres',
            'host': 'localhost',
            'port': 5433,
            'database': 'portl_test',
            'username': 'portl_test',
            'password': 'portl_test',
        })
        connector.connect()
        
        dispatcher = OutboxDispatcher(connector)
        dispatcher.flush_for_run('test-run-456')
        
        # Verify event marked as failed
        cursor = postgres_connection.cursor()
        cursor.execute("""
            SELECT status, retry_count, last_error
            FROM portl_outbox
            WHERE id = %s
        """, (event_id,))
        
        status, retry_count, last_error = cursor.fetchone()
        
        assert status == 'failed'
        assert retry_count == 1
        assert 'Connection timeout' in last_error
        
        cursor.close()
        connector.disconnect()
    
    def test_api_call_direct_mode_skips_outbox(self, postgres_connection, clean_db):
        """
        Test that api.call with delivery='direct' makes immediate HTTP call.
        
        Should NOT write to outbox table.
        """
        with patch('httpx.request') as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {'success': True}
            mock_response.raise_for_status = MagicMock()
            mock_request.return_value = mock_response
            
            job = Job(
                steps=[
                    DataclassStep(
                        id='api_direct',
                        type='api.call',
                        connection='pg',
                        config={
                            'delivery': 'direct',  # Direct mode
                            'method': 'GET',
                            'url': 'https://api.example.com/status',
                            'idempotency_key': 'direct-key-123',
                        }
                    )
                ],
                connections={
                    'pg': ConnectionConfig(
                        name='pg',
                        type='postgres',
                        config={
                            'host': 'localhost',
                            'port': 5433,
                            'database': 'portl_test',
                            'username': 'portl_test',
                            'password': 'portl_test',
                        }
                    )
                }
            )
            
            # Execute
            from portl.execution.engine import JobEngine
            engine = JobEngine(job, dry_run=False)
            context = engine.execute()
            
            # Verify HTTP call was made
            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert call_args.kwargs['method'] == 'GET'
            assert call_args.kwargs['url'] == 'https://api.example.com/status'
            assert call_args.kwargs['headers']['Idempotency-Key'] == 'direct-key-123'
            
            # Verify NO outbox record
            cursor = postgres_connection.cursor()
            cursor.execute("SELECT COUNT(*) FROM portl_outbox")
            count = cursor.fetchone()[0]
            assert count == 0, "Direct mode should not create outbox records"
            cursor.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

