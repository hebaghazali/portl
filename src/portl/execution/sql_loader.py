"""
SQL file loader with security validation and caching.

This module provides secure loading and rendering of SQL files for use
in db.query_one and db.query_many step types.
"""

import os
import logging
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass

from .templating import get_template_engine

logger = logging.getLogger(__name__)

# Configuration constants
MAX_SQL_FILE_SIZE = 256 * 1024  # 256 KB
ALLOWED_EXTENSIONS = {'.sql'}


class SecurityError(Exception):
    """Raised when SQL file path is not permitted."""
    pass


class ValidationError(Exception):
    """Raised when SQL file fails validation."""
    pass


@dataclass
class CachedSQL:
    """Cached SQL file with compiled template."""
    path: str
    mtime: float
    size: int
    content: str
    compiled_template: Any  # Jinja Template object


class SQLFileLoader:
    """
    Loads and caches SQL files with security validation.
    
    Security measures:
    - Path traversal prevention (no ..)
    - Absolute path rejection
    - Size limit enforcement (256 KB)
    - UTF-8 encoding only
    
    Caching:
    - Files are cached by absolute path
    - Cache invalidates on mtime/size change
    - Compiled Jinja templates are cached for performance
    
    Example:
        loader = SQLFileLoader(Path('/path/to/job'))
        sql = loader.load('queries/customers.sql')
        rendered = loader.render('queries/customers.sql', {'limit': 100})
    """
    
    def __init__(self, job_file_dir: Path):
        """
        Initialize SQL file loader.
        
        Args:
            job_file_dir: Directory containing the job file (base for relative paths)
        """
        self.job_file_dir = Path(job_file_dir) if job_file_dir else Path.cwd()
        self._cache: Dict[str, CachedSQL] = {}
        self._template_engine = get_template_engine()
    
    def load(self, sql_file: str) -> str:
        """
        Load SQL file content (raw, unrendered).
        
        Args:
            sql_file: Relative path to SQL file
            
        Returns:
            SQL content string
            
        Raises:
            SecurityError: Path traversal or absolute path
            FileNotFoundError: File doesn't exist
            ValidationError: File too large or invalid encoding
        """
        # Validate path security
        self._validate_path(sql_file)
        
        # Resolve full path
        full_path = self.job_file_dir / sql_file
        
        if not full_path.exists():
            raise FileNotFoundError(f"sql_file not found: {sql_file}")
        
        # Check cache
        cache_key = str(full_path.resolve())
        stat = full_path.stat()
        
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            if cached.mtime == stat.st_mtime and cached.size == stat.st_size:
                logger.debug(f"SQL cache hit: {sql_file}")
                return cached.content
        
        # Validate size
        if stat.st_size > MAX_SQL_FILE_SIZE:
            raise ValidationError(
                f"sql_file exceeds size limit ({MAX_SQL_FILE_SIZE // 1024} KB): {sql_file}"
            )
        
        # Read file
        try:
            content = full_path.read_text(encoding='utf-8')
        except UnicodeDecodeError as e:
            raise ValidationError(f"sql_file must be UTF-8 encoded: {sql_file} ({e})")
        
        # Compile template
        try:
            compiled = self._template_engine.compile_template(content)
        except Exception as e:
            raise ValidationError(f"Failed to compile SQL template: {sql_file} ({e})")
        
        # Cache the result
        self._cache[cache_key] = CachedSQL(
            path=sql_file,
            mtime=stat.st_mtime,
            size=stat.st_size,
            content=content,
            compiled_template=compiled,
        )
        
        logger.info(f"Loaded SQL file: {sql_file} ({stat.st_size} bytes)")
        return content
    
    def render(self, sql_file: str, context: Dict[str, Any]) -> str:
        """
        Load and render SQL with Jinja context.
        
        Args:
            sql_file: Relative path to SQL file
            context: Template context for Jinja rendering
            
        Returns:
            Rendered SQL string
            
        Raises:
            SecurityError: Path not permitted
            FileNotFoundError: File doesn't exist
            ValidationError: Template rendering failed
        """
        # Ensure file is loaded and cached
        self.load(sql_file)
        
        # Get from cache
        cache_key = str((self.job_file_dir / sql_file).resolve())
        cached = self._cache[cache_key]
        
        # Render template
        try:
            return self._template_engine.render_template(
                cached.compiled_template, 
                context
            )
        except Exception as e:
            raise ValidationError(f"Failed to render SQL template: {sql_file} ({e})")
    
    def _validate_path(self, sql_file: str) -> None:
        """
        Validate path is safe to load.
        
        Args:
            sql_file: Path to validate
            
        Raises:
            SecurityError: If path is not permitted
        """
        # Reject empty paths
        if not sql_file or not sql_file.strip():
            raise SecurityError("sql_file path cannot be empty")
        
        # Reject absolute paths
        if os.path.isabs(sql_file):
            raise SecurityError(
                f"sql_file path not permitted (absolute path): {sql_file}"
            )
        
        # Normalize and check for path traversal
        normalized = os.path.normpath(sql_file)
        
        # Check for .. traversal
        if '..' in normalized.split(os.sep):
            raise SecurityError(
                f"sql_file path not permitted (path traversal): {sql_file}"
            )
        
        # Also check for .. in the original path (handles different separators)
        if '..' in sql_file:
            raise SecurityError(
                f"sql_file path not permitted (path traversal): {sql_file}"
            )
        
        # Check for leading slash after normalization
        if normalized.startswith(os.sep) or normalized.startswith('/'):
            raise SecurityError(
                f"sql_file path not permitted (leading slash): {sql_file}"
            )
        
        # Validate file extension (optional, but good practice)
        ext = os.path.splitext(sql_file)[1].lower()
        if ext and ext not in ALLOWED_EXTENSIONS:
            logger.warning(
                f"sql_file has non-standard extension: {sql_file} (expected .sql)"
            )
    
    def clear_cache(self) -> None:
        """Clear the SQL file cache."""
        self._cache.clear()
        logger.debug("SQL file cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            'cached_files': len(self._cache),
            'total_size': sum(c.size for c in self._cache.values()),
            'files': list(self._cache.keys()),
        }


def get_sql_loader(job_file_dir: Optional[Path] = None) -> SQLFileLoader:
    """
    Get an SQL file loader instance.
    
    Args:
        job_file_dir: Directory containing the job file
        
    Returns:
        SQLFileLoader instance
    """
    return SQLFileLoader(job_file_dir or Path.cwd())

