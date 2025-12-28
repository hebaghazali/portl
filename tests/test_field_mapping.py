"""
Tests for field mapping and transformation engine.

Tests the MappingEngine, TransformRegistry, and built-in transforms.
"""

import pytest
from datetime import datetime
from decimal import Decimal

from portl.execution.mapping import (
    MappingEngine,
    TransformRegistry,
    TransformError,
    get_mapping_engine,
)


class TestTransformRegistry:
    """Tests for TransformRegistry functionality."""
    
    def test_list_transforms_returns_all_registered(self):
        """Verify we can list all registered transforms."""
        transforms = TransformRegistry.list_transforms()
        
        # Check core transforms are registered
        assert 'lowercase' in transforms
        assert 'uppercase' in transforms
        assert 'trim' in transforms
        assert 'parse_date' in transforms
        assert 'parse_number' in transforms
        assert 'coalesce' in transforms
        assert 'hash_md5' in transforms
    
    def test_get_unknown_transform_raises(self):
        """Unknown transform name raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            TransformRegistry.get('nonexistent_transform')
        
        assert 'Unknown transform' in str(exc_info.value)
        assert 'nonexistent_transform' in str(exc_info.value)
    
    def test_is_registered(self):
        """is_registered returns correct boolean."""
        assert TransformRegistry.is_registered('lowercase') is True
        assert TransformRegistry.is_registered('nonexistent') is False


class TestBuiltinTransforms:
    """Tests for individual built-in transform functions."""
    
    def test_lowercase_transform(self):
        """Verify lowercase transform."""
        transform = TransformRegistry.get('lowercase')
        
        assert transform('HELLO', {}) == 'hello'
        assert transform('Hello World', {}) == 'hello world'
        assert transform(None, {}) is None
    
    def test_uppercase_transform(self):
        """Verify uppercase transform."""
        transform = TransformRegistry.get('uppercase')
        
        assert transform('hello', {}) == 'HELLO'
        assert transform('Hello World', {}) == 'HELLO WORLD'
        assert transform(None, {}) is None
    
    def test_trim_transform(self):
        """Verify trim transform."""
        transform = TransformRegistry.get('trim')
        
        assert transform('  hello  ', {}) == 'hello'
        assert transform('\t\ntest\n', {}) == 'test'
        assert transform(None, {}) is None
    
    def test_parse_date_with_default_format(self):
        """Verify date parsing with default format."""
        transform = TransformRegistry.get('parse_date')
        
        result = transform('2024-01-15', {})
        
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
    
    def test_parse_date_with_custom_format(self):
        """Verify date parsing with custom format."""
        transform = TransformRegistry.get('parse_date')
        
        result = transform('15/01/2024', {'format': '%d/%m/%Y'})
        
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
    
    def test_parse_date_invalid_format_raises(self):
        """Invalid date format raises ValueError."""
        transform = TransformRegistry.get('parse_date')
        
        with pytest.raises(ValueError) as exc_info:
            transform('not-a-date', {})
        
        assert 'Cannot parse date' in str(exc_info.value)
    
    def test_parse_number_handles_commas(self):
        """Verify '1,234.56' -> Decimal('1234.56')."""
        transform = TransformRegistry.get('parse_number')
        
        result = transform('1,234.56', {})
        
        assert result == Decimal('1234.56')
    
    def test_parse_number_with_decimal_places(self):
        """Verify decimal places rounding."""
        transform = TransformRegistry.get('parse_number')
        
        result = transform('123.456789', {'decimal_places': 2})
        
        assert result == Decimal('123.46')
    
    def test_parse_number_invalid_raises(self):
        """Invalid number raises ValueError."""
        transform = TransformRegistry.get('parse_number')
        
        with pytest.raises(ValueError) as exc_info:
            transform('not-a-number', {})
        
        assert 'Cannot parse number' in str(exc_info.value)
    
    def test_concat_with_prefix_suffix(self):
        """Verify concat with prefix and suffix."""
        transform = TransformRegistry.get('concat')
        
        result = transform('world', {'prefix': 'hello ', 'suffix': '!'})
        
        assert result == 'hello world!'
    
    def test_coalesce_with_default(self):
        """Null values replaced with default."""
        transform = TransformRegistry.get('coalesce')
        
        assert transform(None, {'default': 'N/A'}) == 'N/A'
        assert transform('', {'default': 'empty'}) == 'empty'
        assert transform('value', {'default': 'N/A'}) == 'value'
    
    def test_hash_md5(self):
        """Verify MD5 hashing."""
        transform = TransformRegistry.get('hash_md5')
        
        result = transform('hello', {})
        
        assert result == '5d41402abc4b2a76b9719d911017c592'
        assert transform(None, {}) is None
    
    def test_replace_transform(self):
        """Verify replace transform."""
        transform = TransformRegistry.get('replace')
        
        result = transform('hello world', {'old': 'world', 'new': 'there'})
        
        assert result == 'hello there'
    
    def test_substring_transform(self):
        """Verify substring transform."""
        transform = TransformRegistry.get('substring')
        
        assert transform('hello world', {'start': 0, 'end': 5}) == 'hello'
        assert transform('hello world', {'start': 6}) == 'world'
    
    def test_to_int_transform(self):
        """Verify to_int transform."""
        transform = TransformRegistry.get('to_int')
        
        assert transform('123', {}) == 123
        assert transform('123.45', {}) == 123
        assert transform('1,234', {}) == 1234
        assert transform(None, {}) is None
    
    def test_to_float_transform(self):
        """Verify to_float transform."""
        transform = TransformRegistry.get('to_float')
        
        assert transform('123.45', {}) == 123.45
        assert transform('1,234.56', {}) == 1234.56
        assert transform(None, {}) is None
    
    def test_to_bool_transform(self):
        """Verify to_bool transform."""
        transform = TransformRegistry.get('to_bool')
        
        assert transform('true', {}) is True
        assert transform('yes', {}) is True
        assert transform('1', {}) is True
        assert transform('false', {}) is False
        assert transform('no', {}) is False
        assert transform('0', {}) is False
        assert transform(None, {}) is None


class TestMappingEngine:
    """Tests for MappingEngine functionality."""
    
    def test_schema_mapping_renames_columns(self):
        """Verify column renaming works."""
        engine = MappingEngine(
            schema_mapping={'user_id': 'id', 'full_name': 'name'}
        )
        
        row = {'user_id': 1, 'full_name': 'Alice', 'email': 'alice@example.com'}
        result = engine.apply(row)
        
        assert result == {'id': 1, 'name': 'Alice', 'email': 'alice@example.com'}
    
    def test_schema_mapping_keeps_unmapped_columns(self):
        """Unmapped columns keep their original names."""
        engine = MappingEngine(
            schema_mapping={'old_col': 'new_col'}
        )
        
        row = {'old_col': 'value', 'other_col': 'other'}
        result = engine.apply(row)
        
        assert 'new_col' in result
        assert 'other_col' in result
        assert 'old_col' not in result
    
    def test_transform_applies_to_column(self):
        """Transforms are applied to specified column."""
        engine = MappingEngine(
            transformations=[
                {'column': 'email', 'operation': 'lowercase'}
            ]
        )
        
        row = {'email': 'TEST@EXAMPLE.COM'}
        result = engine.apply(row)
        
        assert result['email'] == 'test@example.com'
    
    def test_transform_chain_applies_in_order(self):
        """Multiple transforms on same column apply sequentially."""
        engine = MappingEngine(
            transformations=[
                {'column': 'text', 'operation': 'trim'},
                {'column': 'text', 'operation': 'lowercase'},
            ]
        )
        
        row = {'text': '  HELLO WORLD  '}
        result = engine.apply(row)
        
        assert result['text'] == 'hello world'
    
    def test_transform_with_parameters(self):
        """Transform parameters are passed correctly."""
        engine = MappingEngine(
            transformations=[
                {
                    'column': 'date', 
                    'operation': 'parse_date',
                    'parameters': {'format': '%m/%d/%Y'}
                }
            ]
        )
        
        row = {'date': '12/25/2024'}
        result = engine.apply(row)
        
        assert result['date'].month == 12
        assert result['date'].day == 25
        assert result['date'].year == 2024
    
    def test_on_error_fail_raises(self):
        """on_error='fail' raises on transform failure."""
        engine = MappingEngine(
            transformations=[
                {
                    'column': 'number',
                    'operation': 'parse_number',
                    'on_error': 'fail'
                }
            ]
        )
        
        row = {'number': 'not-a-number'}
        
        with pytest.raises(TransformError) as exc_info:
            engine.apply(row)
        
        assert exc_info.value.column == 'number'
        assert exc_info.value.operation == 'parse_number'
    
    def test_on_error_null_returns_none(self):
        """on_error='null' returns None on failure."""
        engine = MappingEngine(
            transformations=[
                {
                    'column': 'number',
                    'operation': 'parse_number',
                    'on_error': 'null'
                }
            ]
        )
        
        row = {'number': 'not-a-number'}
        result = engine.apply(row)
        
        assert result['number'] is None
    
    def test_on_error_skip_keeps_original(self):
        """on_error='skip' keeps original value."""
        engine = MappingEngine(
            transformations=[
                {
                    'column': 'number',
                    'operation': 'parse_number',
                    'on_error': 'skip'
                }
            ]
        )
        
        row = {'number': 'not-a-number'}
        result = engine.apply(row)
        
        assert result['number'] == 'not-a-number'
    
    def test_missing_column_skipped(self):
        """Transform on missing column is skipped silently."""
        engine = MappingEngine(
            transformations=[
                {'column': 'nonexistent', 'operation': 'lowercase'}
            ]
        )
        
        row = {'other': 'value'}
        result = engine.apply(row)
        
        assert result == {'other': 'value'}
    
    def test_batch_apply(self):
        """Batch processing works correctly."""
        engine = MappingEngine(
            transformations=[
                {'column': 'name', 'operation': 'uppercase'}
            ]
        )
        
        rows = [
            {'name': 'alice'},
            {'name': 'bob'},
            {'name': 'charlie'},
        ]
        
        results, errors = engine.apply_batch(rows)
        
        assert len(results) == 3
        assert len(errors) == 0
        assert results[0]['name'] == 'ALICE'
        assert results[1]['name'] == 'BOB'
        assert results[2]['name'] == 'CHARLIE'
    
    def test_batch_apply_collects_errors(self):
        """Batch processing with collect_errors gathers all errors."""
        engine = MappingEngine(
            transformations=[
                {'column': 'number', 'operation': 'parse_number'}
            ]
        )
        
        rows = [
            {'number': '123'},
            {'number': 'bad'},
            {'number': '456'},
        ]
        
        results, errors = engine.apply_batch(rows, collect_errors=True)
        
        # Row with 'bad' should have failed
        assert len(errors) == 1
        assert len(results) == 2
    
    def test_unknown_transform_raises_at_init(self):
        """Unknown transform name raises ValueError at init."""
        with pytest.raises(ValueError) as exc_info:
            MappingEngine(
                transformations=[
                    {'column': 'test', 'operation': 'nonexistent_transform'}
                ]
            )
        
        assert 'Unknown transform' in str(exc_info.value)
    
    def test_combined_mapping_and_transform(self):
        """Schema mapping and transforms work together."""
        engine = MappingEngine(
            schema_mapping={'user_email': 'email'},
            transformations=[
                {'column': 'email', 'operation': 'lowercase'},
                {'column': 'email', 'operation': 'trim'},
            ]
        )
        
        row = {'user_email': '  TEST@EXAMPLE.COM  '}
        result = engine.apply(row)
        
        # Column should be renamed AND transformed
        assert 'email' in result
        assert 'user_email' not in result
        assert result['email'] == 'test@example.com'


class TestGetMappingEngine:
    """Tests for get_mapping_engine helper."""
    
    def test_returns_none_when_no_config(self):
        """Returns None when no mappings or transforms specified."""
        engine = get_mapping_engine(None, None)
        assert engine is None
        
        engine = get_mapping_engine({}, [])
        assert engine is None
    
    def test_returns_engine_with_schema_mapping(self):
        """Returns MappingEngine when schema_mapping specified."""
        engine = get_mapping_engine({'a': 'b'}, None)
        assert engine is not None
        assert isinstance(engine, MappingEngine)
    
    def test_returns_engine_with_transforms(self):
        """Returns MappingEngine when transformations specified."""
        engine = get_mapping_engine(None, [{'column': 'x', 'operation': 'trim'}])
        assert engine is not None
        assert isinstance(engine, MappingEngine)


# Run tests if executed directly
if __name__ == '__main__':
    pytest.main([__file__, '-v'])

