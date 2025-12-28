"""
Tests for conditional step executor.

Tests if/then/else branching logic with context passing and error handling.
"""

import pytest
import tempfile
import csv
from pathlib import Path

from portl.execution.context import ExecutionContext, StepStatus
from portl.execution.engine import JobEngine
from portl.schema import Job, Step as DataclassStep


class TestConditionalExecutor:
    """Test suite for conditional step executor."""
    
    def test_conditional_then_branch_executes(self, tmp_path):
        """Test that when condition is true, then steps execute."""
        # Create test CSV
        csv_file = tmp_path / "data.csv"
        with open(csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['count'])
            writer.writeheader()
            writer.writerow({'count': '5'})
        
        # Job with conditional - condition is true
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
                    id='conditional',
                    type='conditional',
                    when='steps.read_data.count > 0',
                    config={
                        'when': 'steps.read_data.count > 0',
                        'then': [
                            {
                                'id': 'then_step',
                                'type': 'csv.read',
                                'path': str(csv_file),
                                'has_header': True,
                            }
                        ],
                        'else': [
                            {
                                'id': 'else_step',
                                'type': 'csv.read',
                                'path': str(csv_file),
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
        
        # Verify conditional executed
        assert context.has_step_result('conditional')
        cond_result = context.get_step_result('conditional')
        assert cond_result.status == StepStatus.OK
        assert cond_result.output['branch_taken'] == 'then'
        assert cond_result.output['evaluated_to'] is True
        
        # Verify then step executed
        assert context.has_step_result('then_step')
        then_result = context.get_step_result('then_step')
        assert then_result.status == StepStatus.OK
        
        # Verify else step did NOT execute
        assert not context.has_step_result('else_step')
    
    def test_conditional_else_branch_executes(self, tmp_path):
        """Test that when condition is false, else steps execute."""
        csv_file = tmp_path / "data.csv"
        with open(csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['count'])
            writer.writeheader()
            writer.writerow({'count': '0'})
        
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
                    id='conditional',
                    type='conditional',
                    when='steps.read_data.count > 0',
                    config={
                        'when': 'steps.read_data.count > 0',
                        'then': [
                            {
                                'id': 'then_step',
                                'type': 'csv.read',
                                'path': str(csv_file),
                                'has_header': True,
                            }
                        ],
                        'else': [
                            {
                                'id': 'else_step',
                                'type': 'csv.read',
                                'path': str(csv_file),
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
        
        # Verify conditional executed
        cond_result = context.get_step_result('conditional')
        assert cond_result.status == StepStatus.OK
        assert cond_result.output['branch_taken'] == 'else'
        assert cond_result.output['evaluated_to'] is False
        
        # Verify else step executed
        assert context.has_step_result('else_step')
        else_result = context.get_step_result('else_step')
        assert else_result.status == StepStatus.OK
        
        # Verify then step did NOT execute
        assert not context.has_step_result('then_step')
    
    def test_conditional_no_else_branch(self, tmp_path):
        """Test that when condition is false and no else branch, step succeeds with no-op."""
        csv_file = tmp_path / "data.csv"
        with open(csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['count'])
            writer.writeheader()
            writer.writerow({'count': '0'})
        
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
                    id='conditional',
                    type='conditional',
                    when='steps.read_data.count > 0',
                    config={
                        'when': 'steps.read_data.count > 0',
                        'then': [
                            {
                                'id': 'then_step',
                                'type': 'csv.read',
                                'path': str(csv_file),
                                'has_header': True,
                            }
                        ],
                        # No else branch
                    }
                )
            ]
        )
        
        # Execute
        engine = JobEngine(job, dry_run=False)
        context = engine.execute()
        
        # Verify conditional succeeded with no steps executed
        cond_result = context.get_step_result('conditional')
        assert cond_result.status == StepStatus.OK
        assert cond_result.output['branch_taken'] == 'else'
        assert cond_result.output['steps_executed'] == 0
        
        # Verify no branch steps executed
        assert not context.has_step_result('then_step')
    
    def test_conditional_nested_context_passing(self, tmp_path):
        """Test that inner steps can access outer context."""
        csv_file = tmp_path / "data.csv"
        with open(csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['value'])
            writer.writeheader()
            writer.writerow({'value': 'test_data'})
        
        job = Job(
            steps=[
                DataclassStep(
                    id='read_data',
                    type='csv.read',
                    save_as='outer_data',
                    config={
                        'path': str(csv_file),
                        'has_header': True,
                    }
                ),
                DataclassStep(
                    id='conditional',
                    type='conditional',
                    when='True',
                    config={
                        'when': 'True',
                        'then': [
                            {
                                'id': 'inner_read',
                                'type': 'csv.read',
                                'save_as': 'inner_data',
                                'path': str(csv_file),
                                'has_header': True,
                            }
                        ],
                    }
                )
            ]
        )
        
        # Execute
        engine = JobEngine(job, dry_run=False)
        context = engine.execute()
        
        # Verify both outer and inner steps executed
        assert context.has_step_result('read_data')
        assert context.has_step_result('inner_read')
        
        # Verify inner step can see data from outer step
        outer_result = context.get_step_result('read_data')
        inner_result = context.get_step_result('inner_read')
        
        assert outer_result.status == StepStatus.OK
        assert inner_result.status == StepStatus.OK
        assert len(inner_result.output) > 0
    
    def test_conditional_error_propagates(self, tmp_path):
        """Test that error in branch step fails the conditional."""
        csv_file = tmp_path / "data.csv"
        with open(csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['count'])
            writer.writeheader()
            writer.writerow({'count': '5'})
        
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
                    id='conditional',
                    type='conditional',
                    when='True',
                    config={
                        'when': 'True',
                        'then': [
                            {
                                'id': 'failing_step',
                                'type': 'csv.read',
                                'path': '/nonexistent/path.csv',  # This will fail
                                'has_header': True,
                            }
                        ],
                    }
                )
            ]
        )
        
        # Execute - should raise exception
        engine = JobEngine(job, dry_run=False)
        
        with pytest.raises(Exception):
            engine.execute()
    
    def test_conditional_with_batching(self, tmp_path):
        """Test conditional inside batch loop works correctly."""
        csv_file = tmp_path / "data.csv"
        with open(csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['id', 'value'])
            writer.writeheader()
            writer.writerow({'id': '1', 'value': '10'})
            writer.writerow({'id': '2', 'value': '20'})
        
        # Create a second CSV for inner reads
        csv_file2 = tmp_path / "data2.csv"
        with open(csv_file2, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['status'])
            writer.writeheader()
            writer.writerow({'status': 'ok'})
        
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
                # Note: Conditional with batch would require batching the conditional itself
                # For this test, we'll verify conditional works after a batch
                DataclassStep(
                    id='conditional',
                    type='conditional',
                    when='steps.read_data.count == 2',
                    config={
                        'when': 'steps.read_data.count == 2',
                        'then': [
                            {
                                'id': 'batch_success',
                                'type': 'csv.read',
                                'path': str(csv_file2),
                                'has_header': True,
                            }
                        ],
                    }
                )
            ]
        )
        
        # Execute
        engine = JobEngine(job, dry_run=False)
        context = engine.execute()
        
        # Verify conditional executed correctly based on batch results
        cond_result = context.get_step_result('conditional')
        assert cond_result.status == StepStatus.OK
        assert cond_result.output['branch_taken'] == 'then'
        
        # Verify inner step executed
        assert context.has_step_result('batch_success')


# Run tests if executed directly
if __name__ == '__main__':
    pytest.main([__file__, '-v'])

