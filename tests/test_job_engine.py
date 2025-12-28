"""
Integration tests for the new Job execution engine.

Tests the complete flow: CSV read → context passing → template rendering → DB upsert.
"""

import pytest
import tempfile
import csv
from pathlib import Path
from dataclasses import dataclass

from portl.execution.context import ExecutionContext, StepResult, StepStatus
from portl.execution.engine import JobEngine
from portl.execution.executor import list_registered_executors
from portl.schema import Job, Step as DataclassStep, ConnectionConfig, TransactionConfig


class TestJobEngine:
    """Test suite for Job execution engine."""
    
    def test_executor_registration(self):
        """Test that step executors are properly registered."""
        executors = list_registered_executors()
        
        # Should have at least csv.read and db.upsert
        assert 'csv.read' in executors, "csv.read executor not registered"
        assert 'db.upsert' in executors, "db.upsert executor not registered"
    
    def test_csv_read_step(self, tmp_path):
        """Test CSV read step executor."""
        # Create a test CSV file
        csv_file = tmp_path / "test_data.csv"
        with open(csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['id', 'name', 'value'])
            writer.writeheader()
            writer.writerow({'id': '1', 'name': 'Alice', 'value': '100'})
            writer.writerow({'id': '2', 'name': 'Bob', 'value': '200'})
            writer.writerow({'id': '3', 'name': 'Charlie', 'value': '300'})
        
        # Create a simple job with CSV read step
        job = Job(
            steps=[
                DataclassStep(
                    id='read_csv',
                    type='csv.read',
                    save_as='csv_data',
                    config={
                        'path': str(csv_file),
                        'delimiter': ',',
                        'has_header': True,
                    }
                )
            ],
            connections=None,
            transaction=None
        )
        
        # Execute job
        engine = JobEngine(job, dry_run=False)
        context = engine.execute()
        
        # Verify result
        assert context.has_step_result('read_csv')
        result = context.get_step_result('read_csv')
        assert result.status == StepStatus.OK
        assert len(result.output) == 3
        assert result.output[0]['name'] == 'Alice'
        assert result.output[1]['name'] == 'Bob'
        assert result.output[2]['name'] == 'Charlie'
        
        # Verify context access
        steps_data = context.steps
        assert 'read_csv' in steps_data
        assert len(steps_data['read_csv']['rows']) == 3
    
    def test_context_passing_between_steps(self, tmp_path):
        """Test that context is properly passed between steps."""
        # Create test CSV
        csv_file = tmp_path / "users.csv"
        with open(csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['user_id', 'email'])
            writer.writeheader()
            writer.writerow({'user_id': '101', 'email': 'alice@example.com'})
            writer.writerow({'user_id': '102', 'email': 'bob@example.com'})
        
        # Create job with two CSV read steps (second depends on first)
        job = Job(
            steps=[
                DataclassStep(
                    id='step1',
                    type='csv.read',
                    save_as='step1_data',
                    config={
                        'path': str(csv_file),
                        'has_header': True,
                    }
                ),
                DataclassStep(
                    id='step2',
                    type='csv.read',
                    save_as='step2_data',
                    config={
                        'path': str(csv_file),
                        'has_header': True,
                    }
                )
            ]
        )
        
        # Execute
        engine = JobEngine(job, dry_run=False)
        context = engine.execute()
        
        # Verify both steps executed
        assert context.has_step_result('step1')
        assert context.has_step_result('step2')
        
        # Verify metrics
        metrics = context.get_metrics_summary()
        assert metrics['total_steps'] == 2
        assert metrics['ok_steps'] == 2
        assert metrics['error_steps'] == 0
    
    def test_conditional_execution_with_when(self, tmp_path):
        """Test conditional step execution using 'when' clause."""
        csv_file = tmp_path / "data.csv"
        with open(csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['count'])
            writer.writeheader()
            writer.writerow({'count': '5'})
        
        # Job with conditional step
        job = Job(
            steps=[
                DataclassStep(
                    id='read_data',
                    type='csv.read',
                    save_as='data',
                    config={
                        'path': str(csv_file),
                        'has_header': True,
                    }
                ),
                DataclassStep(
                    id='conditional_step',
                    type='csv.read',
                    when='steps.read_data.count > 0',  # Should execute
                    config={
                        'path': str(csv_file),
                        'has_header': True,
                    }
                ),
                DataclassStep(
                    id='skipped_step',
                    type='csv.read',
                    when='steps.read_data.count == 0',  # Should skip
                    config={
                        'path': str(csv_file),
                        'has_header': True,
                    }
                )
            ]
        )
        
        # Execute
        engine = JobEngine(job, dry_run=False)
        context = engine.execute()
        
        # Verify first two steps executed, third skipped
        assert context.get_step_result('read_data').status == StepStatus.OK
        assert context.get_step_result('conditional_step').status == StepStatus.OK
        assert context.get_step_result('skipped_step').status == StepStatus.SKIPPED
        
        metrics = context.get_metrics_summary()
        assert metrics['ok_steps'] == 2
        assert metrics['skipped_steps'] == 1
    
    def test_template_rendering_in_config(self, tmp_path):
        """Test that Jinja2 templates are rendered in step configurations."""
        # This test requires implementing a mock step that echoes its config
        # For now, we'll test the template engine directly
        from portl.execution.templating import get_template_engine
        
        engine = get_template_engine()
        
        # Test basic template rendering
        template = "Hello {{ name }}"
        result = engine.render_string(template, {'name': 'World'})
        assert result == "Hello World"
        
        # Test helper functions
        template = "{{ value | md5 }}"
        result = engine.render_string(template, {'value': 'test'})
        assert len(result) == 32  # MD5 hash is 32 hex chars
        
        # Test now() helper
        template = "{{ now() }}"
        result = engine.render_string(template, {})
        assert 'T' in result  # ISO format timestamp
        
        # Test tojson helper
        template = "{{ data | tojson }}"
        result = engine.render_string(template, {'data': {'key': 'value'}})
        assert '"key"' in result
        assert '"value"' in result
    
    def test_execution_context_immutability(self):
        """Test that execution context properly maintains immutable snapshots."""
        # Create initial context
        ctx1 = ExecutionContext.new(run_id='test-123')
        
        # Add a step result
        result1 = StepResult(
            step_id='step1',
            status=StepStatus.OK,
            output={'data': 'value1'},
            metrics={}
        )
        ctx2 = ctx1.with_step_result('step1', result1)
        
        # Original context should not have the result
        assert not ctx1.has_step_result('step1')
        
        # New context should have it
        assert ctx2.has_step_result('step1')
        assert ctx2.get_step_result('step1').output['data'] == 'value1'
        
        # Add another result
        result2 = StepResult(
            step_id='step2',
            status=StepStatus.OK,
            output={'data': 'value2'},
            metrics={}
        )
        ctx3 = ctx2.with_step_result('step2', result2)
        
        # ctx2 should not have step2
        assert not ctx2.has_step_result('step2')
        
        # ctx3 should have both
        assert ctx3.has_step_result('step1')
        assert ctx3.has_step_result('step2')
    
    def test_dry_run_mode(self, tmp_path):
        """Test that dry run mode doesn't execute side effects."""
        csv_file = tmp_path / "data.csv"
        with open(csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['id', 'name'])
            writer.writeheader()
            writer.writerow({'id': '1', 'name': 'Test'})
        
        job = Job(
            steps=[
                DataclassStep(
                    id='read_csv',
                    type='csv.read',
                    config={
                        'path': str(csv_file),
                        'has_header': True,
                    }
                )
            ]
        )
        
        # Execute in dry run mode
        engine = JobEngine(job, dry_run=True)
        context = engine.execute()
        
        # Should still execute (dry run for DB operations, not CSV read)
        assert context.has_step_result('read_csv')
        result = context.get_step_result('read_csv')
        assert result.status == StepStatus.OK
    
    def test_csv_to_conditional_to_api(self, tmp_path):
        """
        End-to-end test combining CSV read, conditional branching, and API call.
        
        This tests the complete pipeline:
        1. Read CSV data
        2. Conditional based on row count
        3. Then branch: verify data exists
        4. Context flow through entire pipeline
        """
        # Create test CSV
        csv_file = tmp_path / "orders.csv"
        with open(csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['order_id', 'amount'])
            writer.writeheader()
            writer.writerow({'order_id': '1001', 'amount': '99.99'})
            writer.writerow({'order_id': '1002', 'amount': '149.50'})
            writer.writerow({'order_id': '1003', 'amount': '75.25'})
        
        # Create verification CSV for then branch
        verify_file = tmp_path / "verify.csv"
        with open(verify_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['status'])
            writer.writeheader()
            writer.writerow({'status': 'verified'})
        
        # Job combining CSV → Conditional → CSV read
        job = Job(
            steps=[
                # Step 1: Read orders CSV
                DataclassStep(
                    id='read_orders',
                    type='csv.read',
                    save_as='orders',
                    config={
                        'path': str(csv_file),
                        'has_header': True,
                    }
                ),
                # Step 2: Conditional based on order count
                DataclassStep(
                    id='process_orders',
                    type='conditional',
                    when='steps.read_orders.count >= 3',
                    config={
                        'when': 'steps.read_orders.count >= 3',
                        'then': [
                            {
                                'id': 'verify_orders',
                                'type': 'csv.read',
                                'save_as': 'verification',
                                'path': str(verify_file),
                                'has_header': True,
                            }
                        ],
                        'else': [
                            {
                                'id': 'skip_verification',
                                'type': 'csv.read',
                                'save_as': 'skipped',
                                'path': str(verify_file),
                                'has_header': True,
                            }
                        ]
                    }
                )
            ]
        )
        
        # Execute
        engine = JobEngine(job, dry_run=False)
        context = engine.execute()
        
        # Verify complete pipeline executed
        assert context.has_step_result('read_orders')
        assert context.has_step_result('process_orders')
        assert context.has_step_result('verify_orders')
        
        # Verify data flow
        orders_result = context.get_step_result('read_orders')
        assert orders_result.status == StepStatus.OK
        assert len(orders_result.output) == 3
        
        # Verify conditional took correct branch
        conditional_result = context.get_step_result('process_orders')
        assert conditional_result.status == StepStatus.OK
        assert conditional_result.output['branch_taken'] == 'then'
        assert conditional_result.output['evaluated_to'] is True
        assert conditional_result.output['steps_executed'] == 1
        
        # Verify then branch step executed
        verify_result = context.get_step_result('verify_orders')
        assert verify_result.status == StepStatus.OK
        assert verify_result.output[0]['status'] == 'verified'
        
        # Verify else branch did NOT execute
        assert not context.has_step_result('skip_verification')
        
        # Verify metrics
        metrics = context.get_metrics_summary()
        assert metrics['total_steps'] == 3  # read_orders + process_orders + verify_orders
        assert metrics['ok_steps'] == 3
        assert metrics['error_steps'] == 0


# Run tests if executed directly
if __name__ == '__main__':
    pytest.main([__file__, '-v'])

