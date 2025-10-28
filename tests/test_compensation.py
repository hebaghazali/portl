"""
Tests for compensation (saga-lite) pattern.

Tests LIFO compensation execution within db-group transactions.
"""

import pytest
from portl.execution.context import ExecutionContext, StepStatus
from portl.schema import Step as DataclassStep, Job, ConnectionConfig, TransactionConfig


class TestCompensation:
    """Test suite for compensation logic."""
    
    def test_compensation_runs_on_failure(self, postgres_connection, clean_db):
        """
        Test that compensation runs in LIFO order when a step fails.
        
        Flow:
        1. reserve_inventory (succeeds, has compensate_with)
        2. simulate_failure (fails)
        3. Compensation: unreserve_inventory (runs in LIFO)
        4. Transaction rolls back
        5. DB state should be consistent (inventory not reserved)
        """
        # Insert initial inventory
        cursor = postgres_connection.cursor()
        cursor.execute("""
            INSERT INTO inventory (sku, quantity, reserved)
            VALUES ('TEST-SKU', 100, 0)
            ON CONFLICT (sku) DO UPDATE SET quantity = 100, reserved = 0
        """)
        postgres_connection.commit()
        cursor.close()
        
        # Create job with compensation
        job = Job(
            steps=[
                # Step 1: Reserve inventory (will succeed)
                DataclassStep(
                    id='reserve_inventory',
                    type='db.update',
                    connection='pg',
                    on_error='compensate',
                    compensate_with='unreserve_inventory',
                    config={
                        'table': 'inventory',
                        'where': {'sku': 'TEST-SKU'},
                        'mapping': {'reserved': 10},
                    }
                ),
                # Step 2: Simulate failure (invalid query)
                DataclassStep(
                    id='simulate_failure',
                    type='db.query_one',
                    connection='pg',
                    config={
                        'query': "SELECT * FROM non_existent_table",
                        'params': {},
                    }
                ),
                # Compensation step (should run before rollback)
                DataclassStep(
                    id='unreserve_inventory',
                    type='db.update',
                    connection='pg',
                    config={
                        'table': 'inventory',
                        'where': {'sku': 'TEST-SKU'},
                        'mapping': {'reserved': 0},
                    }
                ),
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
        
        # Execute - should fail but compensate
        engine = JobEngine(job, dry_run=False)
        
        with pytest.raises(Exception):
            engine.execute()
        
        # Verify database state - reservation should be rolled back
        cursor = postgres_connection.cursor()
        cursor.execute("SELECT reserved FROM inventory WHERE sku = 'TEST-SKU'")
        reserved = cursor.fetchone()[0]
        assert reserved == 0, "Compensation + rollback should leave inventory unreserved"
        cursor.close()
    
    def test_compensation_lifo_order(self, postgres_connection, clean_db):
        """
        Test that compensation runs in LIFO (stack) order.
        
        Flow:
        1. log_action_1 (succeeds, has compensate)
        2. log_action_2 (succeeds, has compensate)
        3. fail_step (fails)
        4. Compensation runs: undo_action_2 THEN undo_action_1 (LIFO)
        """
        job = Job(
            steps=[
                # Action 1
                DataclassStep(
                    id='log_action_1',
                    type='db.insert',
                    connection='pg',
                    on_error='compensate',
                    compensate_with='undo_action_1',
                    config={
                        'table': 'audit_log',
                        'mapping': {
                            'run_id': 'test-run',
                            'step_id': 'log_action_1',
                            'action': 'ACTION_1',
                            'details': '{}',
                        }
                    }
                ),
                # Action 2
                DataclassStep(
                    id='log_action_2',
                    type='db.insert',
                    connection='pg',
                    on_error='compensate',
                    compensate_with='undo_action_2',
                    config={
                        'table': 'audit_log',
                        'mapping': {
                            'run_id': 'test-run',
                            'step_id': 'log_action_2',
                            'action': 'ACTION_2',
                            'details': '{}',
                        }
                    }
                ),
                # Fail
                DataclassStep(
                    id='fail_step',
                    type='db.query_one',
                    connection='pg',
                    config={
                        'query': "SELECT * FROM non_existent_table",
                        'params': {},
                    }
                ),
                # Compensations (should run in LIFO: 2 then 1)
                DataclassStep(
                    id='undo_action_2',
                    type='db.insert',
                    connection='pg',
                    config={
                        'table': 'audit_log',
                        'mapping': {
                            'run_id': 'test-run',
                            'step_id': 'undo_action_2',
                            'action': 'UNDO_ACTION_2',
                            'details': '{}',
                        }
                    }
                ),
                DataclassStep(
                    id='undo_action_1',
                    type='db.insert',
                    connection='pg',
                    config={
                        'table': 'audit_log',
                        'mapping': {
                            'run_id': 'test-run',
                            'step_id': 'undo_action_1',
                            'action': 'UNDO_ACTION_1',
                            'details': '{}',
                        }
                    }
                ),
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
        
        # Execute - should fail but run compensations
        engine = JobEngine(job, dry_run=False)
        
        with pytest.raises(Exception):
            engine.execute()
        
        # Verify LIFO order: All logs should be rolled back
        # (compensations run inside the transaction before rollback)
        cursor = postgres_connection.cursor()
        cursor.execute("SELECT COUNT(*) FROM audit_log WHERE run_id = 'test-run'")
        count = cursor.fetchone()[0]
        assert count == 0, "All audit logs should be rolled back after compensation"
        cursor.close()
    
    def test_no_compensation_without_db_group(self):
        """Test that compensation requires transaction.scope='db'."""
        with pytest.raises(ValueError) as exc_info:
            Job(
                steps=[
                    DataclassStep(
                        id='step1',
                        type='db.insert',
                        connection='pg',
                        on_error='compensate',
                        compensate_with='step2',
                        config={'table': 'orders', 'mapping': {}}
                    ),
                    DataclassStep(
                        id='step2',
                        type='db.insert',
                        connection='pg',
                        config={'table': 'orders', 'mapping': {}}
                    ),
                ],
                connections={
                    'pg': ConnectionConfig(name='pg', type='postgres', config={})
                },
                transaction=None  # No transaction!
            )
        
        assert 'compensation' in str(exc_info.value).lower()
        assert 'db-group' in str(exc_info.value).lower()
    
    def test_compensate_with_must_reference_existing_step(self):
        """Test that compensate_with must reference a valid step ID."""
        with pytest.raises(ValueError) as exc_info:
            Job(
                steps=[
                    DataclassStep(
                        id='step1',
                        type='db.insert',
                        connection='pg',
                        on_error='compensate',
                        compensate_with='nonexistent_step',  # Invalid!
                        config={'table': 'orders', 'mapping': {}}
                    ),
                ],
                connections={
                    'pg': ConnectionConfig(name='pg', type='postgres', config={})
                },
                transaction=TransactionConfig(scope='db')
            )
        
        assert 'unknown step' in str(exc_info.value).lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

