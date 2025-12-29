"""
Tests for SQL file loader and db.query_many executor.

Tests security validation, caching, and query execution.
"""

import pytest
import tempfile
import time
from pathlib import Path

from portl.execution.sql_loader import (
    SQLFileLoader,
    SecurityError,
    ValidationError,
    get_sql_loader,
)


class TestSQLFileLoader:
    """Tests for SQLFileLoader security and functionality."""
    
    @pytest.fixture
    def tmp_job_dir(self, tmp_path):
        """Create a temporary job directory with SQL files."""
        # Create queries subdirectory
        queries_dir = tmp_path / "queries"
        queries_dir.mkdir()
        
        # Create sample SQL files
        (queries_dir / "simple.sql").write_text("SELECT * FROM users WHERE id = %(id)s")
        (queries_dir / "complex.sql").write_text("""
            SELECT u.*, o.total
            FROM users u
            LEFT JOIN orders o ON o.user_id = u.id
            WHERE u.status = %(status)s
            AND u.created_at > %(since)s
            ORDER BY u.created_at DESC
            LIMIT %(limit)s
        """)
        (queries_dir / "template.sql").write_text(
            "SELECT * FROM {{ table_name }} WHERE status = '{{ status }}'"
        )
        
        return tmp_path
    
    def test_load_basic_query(self, tmp_job_dir):
        """Loads SQL file and returns content."""
        loader = SQLFileLoader(tmp_job_dir)
        content = loader.load("queries/simple.sql")
        
        assert "SELECT * FROM users" in content
        assert "%(id)s" in content
    
    def test_load_complex_query(self, tmp_job_dir):
        """Loads multi-line SQL file."""
        loader = SQLFileLoader(tmp_job_dir)
        content = loader.load("queries/complex.sql")
        
        assert "LEFT JOIN orders" in content
        assert "ORDER BY" in content
    
    def test_missing_file_raises_file_not_found(self, tmp_job_dir):
        """Missing file raises FileNotFoundError at load time."""
        loader = SQLFileLoader(tmp_job_dir)
        
        with pytest.raises(FileNotFoundError) as exc_info:
            loader.load("queries/nonexistent.sql")
        
        assert "sql_file not found" in str(exc_info.value)
    
    def test_path_traversal_blocked_dotdot(self, tmp_job_dir):
        """Path with .. is rejected."""
        loader = SQLFileLoader(tmp_job_dir)
        
        with pytest.raises(SecurityError) as exc_info:
            loader.load("../secrets.sql")
        
        assert "path not permitted" in str(exc_info.value)
        assert "traversal" in str(exc_info.value)
    
    def test_path_traversal_blocked_hidden(self, tmp_job_dir):
        """Path with .. hidden in middle is rejected."""
        loader = SQLFileLoader(tmp_job_dir)
        
        with pytest.raises(SecurityError) as exc_info:
            loader.load("queries/../../../etc/passwd")
        
        assert "path not permitted" in str(exc_info.value)
    
    def test_absolute_path_blocked(self, tmp_job_dir):
        """Absolute path is rejected."""
        loader = SQLFileLoader(tmp_job_dir)
        
        with pytest.raises(SecurityError) as exc_info:
            loader.load("/etc/passwd")
        
        assert "path not permitted" in str(exc_info.value)
        assert "absolute" in str(exc_info.value)
    
    def test_empty_path_blocked(self, tmp_job_dir):
        """Empty path is rejected."""
        loader = SQLFileLoader(tmp_job_dir)
        
        with pytest.raises(SecurityError) as exc_info:
            loader.load("")
        
        assert "cannot be empty" in str(exc_info.value)
    
    def test_size_guard(self, tmp_job_dir):
        """File over 256KB is rejected."""
        large_file = tmp_job_dir / "large.sql"
        # Create a file larger than 256KB
        large_file.write_text("SELECT 1;\n" * 30000)  # ~300KB
        
        loader = SQLFileLoader(tmp_job_dir)
        
        with pytest.raises(ValidationError) as exc_info:
            loader.load("large.sql")
        
        assert "exceeds size limit" in str(exc_info.value)
    
    def test_caching_works(self, tmp_job_dir):
        """File is cached after first load."""
        loader = SQLFileLoader(tmp_job_dir)
        
        # First load
        content1 = loader.load("queries/simple.sql")
        
        # Second load should hit cache
        content2 = loader.load("queries/simple.sql")
        
        assert content1 == content2
        
        # Verify cache stats
        stats = loader.get_cache_stats()
        assert stats['cached_files'] == 1
    
    def test_cache_invalidates_on_change(self, tmp_job_dir):
        """Cache invalidates when file mtime changes."""
        sql_file = tmp_job_dir / "cached.sql"
        sql_file.write_text("SELECT 1")
        
        loader = SQLFileLoader(tmp_job_dir)
        v1 = loader.load("cached.sql")
        assert "SELECT 1" in v1
        
        # Modify file (need to wait a bit for mtime change)
        time.sleep(0.1)
        sql_file.write_text("SELECT 2")
        
        v2 = loader.load("cached.sql")
        assert "SELECT 2" in v2
        assert v1 != v2
    
    def test_clear_cache(self, tmp_job_dir):
        """Cache can be cleared."""
        loader = SQLFileLoader(tmp_job_dir)
        loader.load("queries/simple.sql")
        
        assert loader.get_cache_stats()['cached_files'] == 1
        
        loader.clear_cache()
        
        assert loader.get_cache_stats()['cached_files'] == 0
    
    def test_render_template(self, tmp_job_dir):
        """SQL template is rendered with context."""
        loader = SQLFileLoader(tmp_job_dir)
        
        rendered = loader.render("queries/template.sql", {
            'table_name': 'customers',
            'status': 'active'
        })
        
        assert "FROM customers" in rendered
        assert "status = 'active'" in rendered
    
    def test_render_missing_variable(self, tmp_job_dir):
        """Missing template variable raises error."""
        loader = SQLFileLoader(tmp_job_dir)
        
        # StrictUndefined should raise on missing variables
        with pytest.raises(ValidationError):
            loader.render("queries/template.sql", {
                # Missing 'table_name' and 'status'
            })


class TestSQLLoaderSecuritySandbox:
    """Tests for Jinja template security sandbox."""
    
    @pytest.fixture
    def tmp_job_dir(self, tmp_path):
        """Create temp dir with malicious SQL templates."""
        return tmp_path
    
    def test_template_blocks_class_introspection(self, tmp_job_dir):
        """Jinja introspection is blocked in SQL files."""
        sql_file = tmp_job_dir / "evil.sql"
        sql_file.write_text("{{ ''.__class__.__mro__ }}")
        
        loader = SQLFileLoader(tmp_job_dir)
        
        with pytest.raises(Exception):  # Sandbox blocks this
            loader.render("evil.sql", {})
    
    def test_template_blocks_import(self, tmp_job_dir):
        """Cannot import modules in templates."""
        sql_file = tmp_job_dir / "evil2.sql"
        sql_file.write_text("{% import os %}{{ os.system('ls') }}")
        
        loader = SQLFileLoader(tmp_job_dir)
        
        with pytest.raises(Exception):
            loader.render("evil2.sql", {})
    
    def test_template_blocks_private_attrs(self, tmp_job_dir):
        """Cannot access private attributes."""
        sql_file = tmp_job_dir / "evil3.sql"
        sql_file.write_text("{{ config._secret_key }}")
        
        loader = SQLFileLoader(tmp_job_dir)
        
        with pytest.raises(Exception):
            loader.render("evil3.sql", {'config': {}})


class TestGetSQLLoader:
    """Tests for get_sql_loader helper."""
    
    def test_returns_loader_with_cwd_by_default(self):
        """Returns loader with cwd when no path specified."""
        loader = get_sql_loader()
        
        assert loader.job_file_dir == Path.cwd()
    
    def test_returns_loader_with_custom_path(self, tmp_path):
        """Returns loader with specified path."""
        loader = get_sql_loader(tmp_path)
        
        assert loader.job_file_dir == tmp_path


class TestDBQueryMany:
    """Unit tests for db.query_many executor."""
    
    def test_query_many_requires_connection(self):
        """Executor raises if no connection in context."""
        from portl.execution.executors.db_query_many import DBQueryManyExecutor
        from portl.execution.context import ExecutionContext
        from portl.schema import Step
        
        executor = DBQueryManyExecutor()
        step = Step(id='test', type='db.query_many', config={'query': 'SELECT 1'})
        context = ExecutionContext.new()
        
        with pytest.raises(ValueError) as exc_info:
            executor.execute(step, context)
        
        assert "requires a database connection" in str(exc_info.value)
    
    def test_query_many_validates_sql_xor_sql_file(self):
        """Cannot specify both query and sql_file."""
        from portl.execution.executors.db_query_many import DBQueryManyExecutor
        from portl.execution.context import ExecutionContext
        from portl.schema import Step
        from unittest.mock import MagicMock
        
        executor = DBQueryManyExecutor()
        step = Step(
            id='test', 
            type='db.query_many', 
            config={'query': 'SELECT 1', 'sql_file': 'test.sql'}
        )
        
        # Mock connection
        mock_conn = MagicMock()
        context = ExecutionContext.new().with_vars(_connection=mock_conn)
        
        with pytest.raises(ValueError) as exc_info:
            executor.execute(step, context)
        
        assert "Cannot specify both" in str(exc_info.value)
    
    def test_query_many_requires_query_or_sql_file(self):
        """Must specify either query or sql_file."""
        from portl.execution.executors.db_query_many import DBQueryManyExecutor
        from portl.execution.context import ExecutionContext
        from portl.schema import Step
        from unittest.mock import MagicMock
        
        executor = DBQueryManyExecutor()
        step = Step(id='test', type='db.query_many', config={})
        
        mock_conn = MagicMock()
        context = ExecutionContext.new().with_vars(_connection=mock_conn)
        
        with pytest.raises(ValueError) as exc_info:
            executor.execute(step, context)
        
        assert "Must specify either" in str(exc_info.value)


# Run tests if executed directly
if __name__ == '__main__':
    pytest.main([__file__, '-v'])


