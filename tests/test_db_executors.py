"""
Tests for database executors (insert, update, query_one).

Tests both happy paths and error cases with real Postgres.
"""

import pytest
from portl.execution.context import ExecutionContext, StepStatus
from portl.schema import Step as DataclassStep, Job, ConnectionConfig, TransactionConfig
from portl.execution.engine import JobEngine


class TestDBExecutors:
    """Test suite for database executors."""
    
    def test_db_insert_basic(self, postgres_connection, clean_db):
        """Test basic db.insert operation."""
        # Create job with insert step
        job = Job(
            steps=[
                DataclassStep(
                    id='insert_order',
                    type='db.insert',
                    connection='pg',
                    config={
                        'table': 'orders',
                        'mapping': {
                            'order_number': 'ORD-001',
                            'user_id': 'user-123',
                            'amount': 99.99,
                            'status': 'pending',
                        }
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
        engine = JobEngine(job, dry_run=False)
        context = engine.execute()
        
        # Verify
        assert context.has_step_result('insert_order')
        result = context.get_step_result('insert_order')
        assert result.status == StepStatus.OK
        assert result.output['row_count'] == 1
        assert 'record' in result.output
        
        # Verify in database
        cursor = postgres_connection.cursor()
        cursor.execute("SELECT * FROM orders WHERE order_number = 'ORD-001'")
        row = cursor.fetchone()
        assert row is not None
        cursor.close()
    
    def test_db_update_with_where(self, postgres_connection, clean_db):
        """Test db.update with WHERE clause."""
        # Insert test data first
        cursor = postgres_connection.cursor()
        cursor.execute("""
            INSERT INTO orders (order_number, user_id, amount, status)
            VALUES ('ORD-002', 'user-456', 50.00, 'pending')
        """)
        postgres_connection.commit()
        cursor.close()
        
        # Create job with update step
        job = Job(
            steps=[
                DataclassStep(
                    id='update_order',
                    type='db.update',
                    connection='pg',
                    config={
                        'table': 'orders',
                        'where': {'order_number': 'ORD-002'},
                        'mapping': {'status': 'shipped'},
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
        engine = JobEngine(job, dry_run=False)
        context = engine.execute()
        
        # Verify
        result = context.get_step_result('update_order')
        assert result.status == StepStatus.OK
        assert result.output['row_count'] == 1
        
        # Verify in database
        cursor = postgres_connection.cursor()
        cursor.execute("SELECT status FROM orders WHERE order_number = 'ORD-002'")
        status = cursor.fetchone()[0]
        assert status == 'shipped'
        cursor.close()
    
    def test_db_query_one_found(self, postgres_connection, clean_db):
        """Test db.query_one when record exists."""
        # Insert test data
        cursor = postgres_connection.cursor()
        cursor.execute("""
            INSERT INTO orders (order_number, user_id, amount, status)
            VALUES ('ORD-003', 'user-789', 75.50, 'completed')
        """)
        postgres_connection.commit()
        cursor.close()
        
        # Create job with query step
        job = Job(
            steps=[
                DataclassStep(
                    id='query_order',
                    type='db.query_one',
                    connection='pg',
                    config={
                        'query': "SELECT * FROM orders WHERE order_number = %(order_num)s",
                        'params': {'order_num': 'ORD-003'},
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
        engine = JobEngine(job, dry_run=False)
        context = engine.execute()
        
        # Verify
        result = context.get_step_result('query_order')
        assert result.status == StepStatus.OK
        assert result.output['record'] is not None
        assert result.output['record']['order_number'] == 'ORD-003'
        assert result.output['record']['user_id'] == 'user-789'
    
    def test_db_query_one_not_found(self, postgres_connection, clean_db):
        """Test db.query_one when no record exists."""
        job = Job(
            steps=[
                DataclassStep(
                    id='query_order',
                    type='db.query_one',
                    connection='pg',
                    config={
                        'query': "SELECT * FROM orders WHERE order_number = %(order_num)s",
                        'params': {'order_num': 'DOES-NOT-EXIST'},
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
        engine = JobEngine(job, dry_run=False)
        context = engine.execute()
        
        # Verify
        result = context.get_step_result('query_order')
        assert result.status == StepStatus.OK
        assert result.output['record'] is None
    
    def test_db_insert_unique_violation_fails(self, postgres_connection, clean_db):
        """Test that unique constraint violations are not retried."""
        # Insert initial record
        cursor = postgres_connection.cursor()
        cursor.execute("""
            INSERT INTO orders (order_number, user_id, amount)
            VALUES ('ORD-UNIQUE', 'user-999', 100.00)
        """)
        postgres_connection.commit()
        cursor.close()
        
        # Try to insert duplicate (should fail)
        job = Job(
            steps=[
                DataclassStep(
                    id='insert_duplicate',
                    type='db.insert',
                    connection='pg',
                    config={
                        'table': 'orders',
                        'mapping': {
                            'order_number': 'ORD-UNIQUE',  # Duplicate!
                            'user_id': 'user-888',
                            'amount': 50.00,
                        }
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
        
        # Execute - should fail
        engine = JobEngine(job, dry_run=False)
        
        with pytest.raises(Exception) as exc_info:
            engine.execute()
        
        # Verify it's a unique violation
        assert 'unique' in str(exc_info.value).lower() or 'duplicate' in str(exc_info.value).lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

