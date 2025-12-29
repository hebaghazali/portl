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


class TestUpsertConflictStrategies:
    """Test suite for db.upsert conflict resolution strategies."""
    
    def test_upsert_overwrite_strategy(self, postgres_connection, clean_db):
        """Test default overwrite strategy replaces all values."""
        # Insert initial data
        cursor = postgres_connection.cursor()
        cursor.execute("""
            INSERT INTO inventory (sku, quantity, reserved, updated_at)
            VALUES ('TEST-SKU', 100, 10, NOW() - INTERVAL '1 day')
        """)
        postgres_connection.commit()
        cursor.close()
        
        # Upsert with overwrite (default)
        job = Job(
            steps=[
                DataclassStep(
                    id='upsert_inventory',
                    type='db.upsert',
                    connection='pg',
                    config={
                        'table': 'inventory',
                        'key': ['sku'],
                        'conflict': 'overwrite',
                        'mapping': {
                            'sku': 'TEST-SKU',
                            'quantity': 200,
                            'reserved': 20,
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
        
        engine = JobEngine(job, dry_run=False)
        context = engine.execute()
        
        result = context.get_step_result('upsert_inventory')
        assert result.status == StepStatus.OK
        
        # Verify values were overwritten
        cursor = postgres_connection.cursor()
        cursor.execute("SELECT quantity, reserved FROM inventory WHERE sku = 'TEST-SKU'")
        row = cursor.fetchone()
        assert row[0] == 200  # quantity overwritten
        assert row[1] == 20   # reserved overwritten
        cursor.close()
    
    def test_upsert_skip_strategy(self, postgres_connection, clean_db):
        """Test skip strategy does nothing on conflict."""
        # Insert initial data
        cursor = postgres_connection.cursor()
        cursor.execute("""
            INSERT INTO inventory (sku, quantity, reserved)
            VALUES ('SKIP-SKU', 100, 10)
        """)
        postgres_connection.commit()
        cursor.close()
        
        # Upsert with skip - should not update
        job = Job(
            steps=[
                DataclassStep(
                    id='upsert_skip',
                    type='db.upsert',
                    connection='pg',
                    config={
                        'table': 'inventory',
                        'key': ['sku'],
                        'conflict': 'skip',
                        'mapping': {
                            'sku': 'SKIP-SKU',
                            'quantity': 999,  # Should NOT be applied
                            'reserved': 99,   # Should NOT be applied
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
        
        engine = JobEngine(job, dry_run=False)
        context = engine.execute()
        
        result = context.get_step_result('upsert_skip')
        assert result.status == StepStatus.OK
        
        # Verify original values are preserved
        cursor = postgres_connection.cursor()
        cursor.execute("SELECT quantity, reserved FROM inventory WHERE sku = 'SKIP-SKU'")
        row = cursor.fetchone()
        assert row[0] == 100  # Original quantity preserved
        assert row[1] == 10   # Original reserved preserved
        cursor.close()
    
    def test_upsert_skip_inserts_new_record(self, postgres_connection, clean_db):
        """Test skip strategy still inserts new records."""
        # Upsert with skip for non-existent record
        job = Job(
            steps=[
                DataclassStep(
                    id='upsert_skip_new',
                    type='db.upsert',
                    connection='pg',
                    config={
                        'table': 'inventory',
                        'key': ['sku'],
                        'conflict': 'skip',
                        'mapping': {
                            'sku': 'NEW-SKU',
                            'quantity': 50,
                            'reserved': 5,
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
        
        engine = JobEngine(job, dry_run=False)
        context = engine.execute()
        
        result = context.get_step_result('upsert_skip_new')
        assert result.status == StepStatus.OK
        
        # Verify new record was inserted
        cursor = postgres_connection.cursor()
        cursor.execute("SELECT quantity, reserved FROM inventory WHERE sku = 'NEW-SKU'")
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == 50
        assert row[1] == 5
        cursor.close()
    
    def test_upsert_merge_non_null_strategy(self, postgres_connection, clean_db):
        """Test merge_non_null strategy keeps existing values when new is null."""
        # Insert initial data
        cursor = postgres_connection.cursor()
        cursor.execute("""
            INSERT INTO inventory (sku, quantity, reserved)
            VALUES ('MERGE-SKU', 100, 10)
        """)
        postgres_connection.commit()
        cursor.close()
        
        # Upsert with merge_non_null - only update quantity, keep reserved
        job = Job(
            steps=[
                DataclassStep(
                    id='upsert_merge',
                    type='db.upsert',
                    connection='pg',
                    config={
                        'table': 'inventory',
                        'key': ['sku'],
                        'conflict': 'merge_non_null',
                        'mapping': {
                            'sku': 'MERGE-SKU',
                            'quantity': 200,      # New value - should update
                            'reserved': None,     # Null - should keep existing
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
        
        engine = JobEngine(job, dry_run=False)
        context = engine.execute()
        
        result = context.get_step_result('upsert_merge')
        assert result.status == StepStatus.OK
        
        # Verify: quantity updated, reserved preserved
        cursor = postgres_connection.cursor()
        cursor.execute("SELECT quantity, reserved FROM inventory WHERE sku = 'MERGE-SKU'")
        row = cursor.fetchone()
        assert row[0] == 200  # Updated to new value
        assert row[1] == 10   # Preserved (was null in mapping)
        cursor.close()
    
    def test_upsert_merge_newer_strategy(self, postgres_connection, clean_db):
        """Test merge_newer strategy only updates if new updated_at is more recent."""
        import datetime
        
        # Insert initial data with old timestamp
        old_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)
        cursor = postgres_connection.cursor()
        cursor.execute("""
            INSERT INTO inventory (sku, quantity, reserved, updated_at)
            VALUES ('NEWER-SKU', 100, 10, %s)
        """, (old_time,))
        postgres_connection.commit()
        cursor.close()
        
        # Upsert with merge_newer - new timestamp should win
        new_time = datetime.datetime.now(datetime.timezone.utc)
        job = Job(
            steps=[
                DataclassStep(
                    id='upsert_newer',
                    type='db.upsert',
                    connection='pg',
                    config={
                        'table': 'inventory',
                        'key': ['sku'],
                        'conflict': 'merge_newer',
                        'mapping': {
                            'sku': 'NEWER-SKU',
                            'quantity': 200,
                            'reserved': 20,
                            'updated_at': new_time.isoformat(),
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
        
        engine = JobEngine(job, dry_run=False)
        context = engine.execute()
        
        result = context.get_step_result('upsert_newer')
        assert result.status == StepStatus.OK
        
        # Verify values were updated (newer timestamp wins)
        cursor = postgres_connection.cursor()
        cursor.execute("SELECT quantity, reserved FROM inventory WHERE sku = 'NEWER-SKU'")
        row = cursor.fetchone()
        assert row[0] == 200  # Updated
        assert row[1] == 20   # Updated
        cursor.close()
    
    def test_upsert_merge_newer_old_timestamp_ignored(self, postgres_connection, clean_db):
        """Test merge_newer strategy ignores updates with older timestamp."""
        import datetime
        
        # Insert initial data with recent timestamp
        new_time = datetime.datetime.now(datetime.timezone.utc)
        cursor = postgres_connection.cursor()
        cursor.execute("""
            INSERT INTO inventory (sku, quantity, reserved, updated_at)
            VALUES ('OLDER-SKU', 100, 10, %s)
        """, (new_time,))
        postgres_connection.commit()
        cursor.close()
        
        # Upsert with merge_newer using OLD timestamp - should NOT update
        old_time = new_time - datetime.timedelta(days=1)
        job = Job(
            steps=[
                DataclassStep(
                    id='upsert_older',
                    type='db.upsert',
                    connection='pg',
                    config={
                        'table': 'inventory',
                        'key': ['sku'],
                        'conflict': 'merge_newer',
                        'mapping': {
                            'sku': 'OLDER-SKU',
                            'quantity': 999,  # Should NOT update
                            'reserved': 99,   # Should NOT update
                            'updated_at': old_time.isoformat(),
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
        
        engine = JobEngine(job, dry_run=False)
        context = engine.execute()
        
        result = context.get_step_result('upsert_older')
        assert result.status == StepStatus.OK
        
        # Verify original values preserved (older timestamp loses)
        cursor = postgres_connection.cursor()
        cursor.execute("SELECT quantity, reserved FROM inventory WHERE sku = 'OLDER-SKU'")
        row = cursor.fetchone()
        assert row[0] == 100  # Original preserved
        assert row[1] == 10   # Original preserved
        cursor.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

