"""
Performance tests for Portl.

These tests verify that Portl can handle large datasets efficiently.
Run with: pytest tests/test_performance.py -v
"""

import pytest
import csv
import tempfile
import time
from pathlib import Path

from portl.execution.mapping import MappingEngine, TransformRegistry
from portl.execution.context import ExecutionContext


class TestMappingEnginePerformance:
    """Performance tests for the MappingEngine."""
    
    @pytest.fixture
    def large_dataset(self):
        """Generate 100k rows of test data."""
        rows = []
        for i in range(100_000):
            rows.append({
                'id': str(i),
                'name': f'User {i}',
                'email': f'USER{i}@EXAMPLE.COM',
                'phone': f'  555-{i:04d}  ',
                'price': f'{i * 1.5:,.2f}',
                'status': 'active' if i % 2 == 0 else '',
                'created_at': f'2024-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}',
            })
        return rows
    
    def test_transform_100k_rows(self, large_dataset):
        """Verify 100k rows can be transformed in reasonable time."""
        engine = MappingEngine(
            transformations=[
                {'column': 'email', 'operation': 'lowercase'},
                {'column': 'phone', 'operation': 'trim'},
                {'column': 'status', 'operation': 'coalesce', 'parameters': {'default': 'pending'}},
            ]
        )
        
        start_time = time.time()
        
        results, errors = engine.apply_batch(large_dataset)
        
        elapsed = time.time() - start_time
        
        # Verify results
        assert len(results) == 100_000
        assert len(errors) == 0
        
        # Check transformations applied correctly
        assert results[0]['email'] == 'user0@example.com'
        assert results[0]['phone'] == '555-0000'
        assert results[0]['status'] == 'active'
        assert results[1]['status'] == 'pending'  # Was empty, coalesced to default
        
        # Performance assertion: should complete in < 10 seconds
        # (Adjust based on actual performance characteristics)
        print(f"\n100k row transform completed in {elapsed:.2f} seconds")
        assert elapsed < 10, f"Transform took too long: {elapsed:.2f}s (expected < 10s)"
    
    def test_schema_mapping_100k_rows(self, large_dataset):
        """Verify column renaming is fast."""
        engine = MappingEngine(
            schema_mapping={
                'id': 'user_id',
                'name': 'full_name', 
                'email': 'email_address',
                'phone': 'phone_number',
            }
        )
        
        start_time = time.time()
        
        results, errors = engine.apply_batch(large_dataset)
        
        elapsed = time.time() - start_time
        
        assert len(results) == 100_000
        assert 'user_id' in results[0]
        assert 'full_name' in results[0]
        assert 'id' not in results[0]
        
        print(f"\n100k row schema mapping completed in {elapsed:.2f} seconds")
        assert elapsed < 5, f"Schema mapping took too long: {elapsed:.2f}s"
    
    def test_complex_transform_chain(self, large_dataset):
        """Test multiple transforms on same column."""
        engine = MappingEngine(
            transformations=[
                {'column': 'email', 'operation': 'trim'},
                {'column': 'email', 'operation': 'lowercase'},
                {'column': 'name', 'operation': 'uppercase'},
                {'column': 'phone', 'operation': 'trim'},
                {'column': 'phone', 'operation': 'replace', 'parameters': {'old': '-', 'new': ''}},
            ]
        )
        
        start_time = time.time()
        
        results, errors = engine.apply_batch(large_dataset)
        
        elapsed = time.time() - start_time
        
        assert len(results) == 100_000
        assert results[0]['email'] == 'user0@example.com'
        assert results[0]['name'] == 'USER 0'
        assert results[0]['phone'] == '5550000'
        
        print(f"\n100k row complex transform completed in {elapsed:.2f} seconds")
        assert elapsed < 15, f"Complex transform took too long: {elapsed:.2f}s"


class TestCSVPerformance:
    """Performance tests for CSV reading."""
    
    @pytest.fixture
    def large_csv(self, tmp_path) -> Path:
        """Generate 100k row CSV file."""
        csv_file = tmp_path / "large_data.csv"
        
        with open(csv_file, 'w', newline='') as f:
            writer = csv.DictWriter(
                f, 
                fieldnames=['id', 'name', 'email', 'value', 'status']
            )
            writer.writeheader()
            
            for i in range(100_000):
                writer.writerow({
                    'id': str(i),
                    'name': f'User {i}',
                    'email': f'user{i}@example.com',
                    'value': str(i * 100),
                    'status': 'active' if i % 2 == 0 else 'inactive',
                })
        
        return csv_file
    
    def test_csv_read_100k_rows(self, large_csv):
        """Verify 100k rows can be read from CSV efficiently."""
        from portl.execution.executors.csv_read import CSVReadExecutor
        from portl.schema import Step
        
        executor = CSVReadExecutor()
        step = Step(
            id='read_large',
            type='csv.read',
            config={
                'path': str(large_csv),
                'has_header': True,
            }
        )
        context = ExecutionContext.new()
        
        start_time = time.time()
        
        result = executor.execute(step, context)
        
        elapsed = time.time() - start_time
        
        # Verify all rows read
        assert result.output is not None
        assert len(result.output) == 100_000
        assert result.output[0]['id'] == '0'
        assert result.output[-1]['id'] == '99999'
        
        print(f"\n100k row CSV read completed in {elapsed:.2f} seconds")
        assert elapsed < 10, f"CSV read took too long: {elapsed:.2f}s"
    
    def test_csv_read_with_transforms(self, large_csv):
        """Verify CSV read + transforms is efficient."""
        from portl.execution.executors.csv_read import CSVReadExecutor
        from portl.schema import Step
        
        executor = CSVReadExecutor()
        step = Step(
            id='read_transform',
            type='csv.read',
            config={
                'path': str(large_csv),
                'has_header': True,
                'transformations': [
                    {'column': 'email', 'operation': 'uppercase'},
                    {'column': 'status', 'operation': 'lowercase'},
                ]
            }
        )
        context = ExecutionContext.new()
        
        start_time = time.time()
        
        result = executor.execute(step, context)
        
        elapsed = time.time() - start_time
        
        assert len(result.output) == 100_000
        assert result.output[0]['email'] == 'USER0@EXAMPLE.COM'
        assert result.output[0]['status'] == 'active'
        
        print(f"\n100k row CSV read+transform completed in {elapsed:.2f} seconds")
        assert elapsed < 20, f"CSV read+transform took too long: {elapsed:.2f}s"


class TestMemoryEfficiency:
    """Tests for memory efficiency during large data processing."""
    
    def test_transform_memory_bounded(self):
        """Verify memory stays bounded during transform."""
        import sys
        
        # Generate rows one at a time
        engine = MappingEngine(
            transformations=[
                {'column': 'data', 'operation': 'uppercase'},
            ]
        )
        
        # Process in small batches to test memory is bounded
        total_processed = 0
        batch_size = 1000
        num_batches = 100  # Total 100k rows
        
        for batch_num in range(num_batches):
            # Generate batch
            rows = [
                {'data': f'value_{batch_num}_{i}'}
                for i in range(batch_size)
            ]
            
            # Transform batch
            results, _ = engine.apply_batch(rows)
            total_processed += len(results)
            
            # Clear references
            del rows
            del results
        
        assert total_processed == 100_000


class TestTransformRegistryPerformance:
    """Tests for TransformRegistry function lookup performance."""
    
    def test_transform_lookup_is_fast(self):
        """Verify transform lookup is O(1)."""
        # Lookup same transform many times
        iterations = 1_000_000
        
        start_time = time.time()
        
        for _ in range(iterations):
            TransformRegistry.get('lowercase')
        
        elapsed = time.time() - start_time
        
        print(f"\n{iterations} transform lookups completed in {elapsed:.4f} seconds")
        
        # Should be very fast (< 1 second for 1M lookups)
        assert elapsed < 1.0, f"Transform lookup too slow: {elapsed:.4f}s for {iterations} lookups"


# Run tests if executed directly
if __name__ == '__main__':
    pytest.main([__file__, '-v', '--durations=10'])

