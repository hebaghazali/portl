"""
Google Sheets source and destination connectors.

Uses Google Sheets API v4 for reading and writing spreadsheet data.
Supports both service account and Application Default Credentials authentication.
"""

import os
import logging
from typing import Dict, Any, List, Optional, Iterator
from contextlib import contextmanager

from .base import BaseSourceConnector, BaseDestinationConnector
from ..schema import GoogleSheetsConfig

logger = logging.getLogger(__name__)

# Scopes required for reading and writing sheets
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


class GoogleSheetsConnectorMixin:
    """Mixin class with common Google Sheets functionality."""
    
    def __init__(self, config: GoogleSheetsConfig):
        """Initialize with Google Sheets configuration."""
        super().__init__(config.__dict__)
        self.sheets_config = config
        self._service = None
        self._credentials = None
        
        # Validate that this is a google_sheets config
        if config.type != 'google_sheets':
            raise ValueError(f"Expected google_sheets config, got {config.type}")
    
    def _authenticate(self) -> None:
        """
        Authenticate with Google Sheets API.
        
        Supports two authentication methods:
        1. Service account from credentials file (credentials_path)
        2. Application Default Credentials (ADC)
        """
        try:
            from google.oauth2 import service_account
            from google.auth import default
        except ImportError:
            raise ImportError(
                "google-auth package is required for Google Sheets connector. "
                "Install with: pip install google-auth google-api-python-client"
            )
        
        creds_path = self.sheets_config.credentials_path
        
        if creds_path:
            # Service account from file
            if not os.path.exists(creds_path):
                raise FileNotFoundError(f"Credentials file not found: {creds_path}")
            
            self._credentials = service_account.Credentials.from_service_account_file(
                creds_path, 
                scopes=SCOPES
            )
            logger.info(f"Authenticated with service account from: {creds_path}")
        else:
            # Try Application Default Credentials
            try:
                self._credentials, project = default(scopes=SCOPES)
                logger.info(f"Authenticated with Application Default Credentials (project: {project})")
            except Exception as e:
                raise RuntimeError(
                    f"Failed to authenticate with Google: {e}. "
                    "Set GOOGLE_APPLICATION_CREDENTIALS or provide credentials_path."
                )
    
    def _build_service(self) -> Any:
        """Build the Sheets API service."""
        try:
            from googleapiclient.discovery import build
        except ImportError:
            raise ImportError(
                "google-api-python-client is required for Google Sheets connector. "
                "Install with: pip install google-api-python-client"
            )
        
        return build('sheets', 'v4', credentials=self._credentials)
    
    def connect(self) -> None:
        """Establish connection to Google Sheets API."""
        try:
            self._authenticate()
            self._service = self._build_service()
            logger.info(f"Connected to Google Sheets (spreadsheet: {self.sheets_config.spreadsheet_id})")
        except Exception as e:
            logger.error(f"Failed to connect to Google Sheets: {e}")
            raise ConnectionError(f"Google Sheets connection failed: {e}")
    
    def disconnect(self) -> None:
        """Close Google Sheets connection."""
        self._service = None
        self._credentials = None
        logger.info("Disconnected from Google Sheets")
    
    def test_connection(self) -> bool:
        """Test connection by fetching spreadsheet metadata."""
        try:
            with self.connection_context():
                self._service.spreadsheets().get(
                    spreadsheetId=self.sheets_config.spreadsheet_id
                ).execute()
                return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    def _build_range(self, include_header: bool = True) -> str:
        """
        Build A1 notation range for data.
        
        Args:
            include_header: If True, include header row (row 1)
            
        Returns:
            A1 notation range string
        """
        sheet_name = self.sheets_config.sheet_name or 'Sheet1'
        
        if self.sheets_config.range_name:
            return f"{sheet_name}!{self.sheets_config.range_name}"
        
        return sheet_name


class GoogleSheetsSourceConnector(GoogleSheetsConnectorMixin, BaseSourceConnector):
    """Google Sheets source connector for reading spreadsheet data."""
    
    def get_schema(self) -> Dict[str, str]:
        """
        Get column headers as schema.
        
        Note: Google Sheets doesn't have strict types, so all columns
        are returned as 'string' type.
        """
        sheet_name = self.sheets_config.sheet_name or 'Sheet1'
        range_name = f"{sheet_name}!1:1"
        
        try:
            result = self._service.spreadsheets().values().get(
                spreadsheetId=self.sheets_config.spreadsheet_id,
                range=range_name,
            ).execute()
            
            headers = result.get('values', [[]])[0]
            return {h: 'string' for h in headers}
        
        except Exception as e:
            logger.error(f"Failed to get schema: {e}")
            raise
    
    def get_row_count(self) -> int:
        """Get total row count (excluding header)."""
        try:
            all_rows = self.read_all()
            return len(all_rows)
        except Exception as e:
            logger.error(f"Failed to get row count: {e}")
            raise
    
    def read_all(self) -> List[Dict[str, Any]]:
        """
        Read all data from spreadsheet.
        
        Returns:
            List of row dicts with column headers as keys
        """
        range_name = self._build_range()
        
        try:
            from googleapiclient.errors import HttpError
        except ImportError:
            HttpError = Exception
        
        try:
            result = self._service.spreadsheets().values().get(
                spreadsheetId=self.sheets_config.spreadsheet_id,
                range=range_name,
            ).execute()
            
            values = result.get('values', [])
            
            if not values:
                logger.info("No data found in spreadsheet")
                return []
            
            # First row is headers
            headers = values[0]
            rows = []
            
            for row_values in values[1:]:
                # Pad short rows with empty strings
                padded = row_values + [''] * (len(headers) - len(row_values))
                rows.append(dict(zip(headers, padded)))
            
            logger.info(f"Read {len(rows)} rows from {self.sheets_config.sheet_name}")
            return rows
            
        except HttpError as e:
            logger.error(f"Google Sheets API error: {e}")
            raise
    
    def read_data(self, batch_size: int = 1000, offset: int = 0) -> Iterator[List[Dict[str, Any]]]:
        """
        Read data in batches.
        
        Note: Google Sheets doesn't support server-side pagination efficiently,
        so we read all data and yield in batches client-side.
        """
        all_rows = self.read_all()
        
        # Apply offset
        all_rows = all_rows[offset:]
        
        # Yield in batches
        for i in range(0, len(all_rows), batch_size):
            yield all_rows[i:i + batch_size]


class GoogleSheetsDestinationConnector(GoogleSheetsConnectorMixin, BaseDestinationConnector):
    """Google Sheets destination connector for writing data."""
    
    def get_schema(self) -> Dict[str, str]:
        """Get destination sheet schema (headers)."""
        sheet_name = self.sheets_config.sheet_name or 'Sheet1'
        range_name = f"{sheet_name}!1:1"
        
        try:
            result = self._service.spreadsheets().values().get(
                spreadsheetId=self.sheets_config.spreadsheet_id,
                range=range_name,
            ).execute()
            
            headers = result.get('values', [[]])[0]
            return {h: 'string' for h in headers}
        
        except Exception as e:
            logger.warning(f"Could not get schema (sheet may be empty): {e}")
            return {}
    
    def create_table_if_not_exists(self, schema: Dict[str, str]) -> None:
        """
        Create header row if sheet is empty.
        
        Args:
            schema: Column names to use as headers
        """
        if not schema:
            raise ValueError("Cannot create headers without schema definition")
        
        sheet_name = self.sheets_config.sheet_name or 'Sheet1'
        
        try:
            # Check if headers already exist
            existing_schema = self.get_schema()
            if existing_schema:
                logger.info("Headers already exist, skipping creation")
                return
            
            # Write headers
            headers = list(schema.keys())
            body = {'values': [headers]}
            
            self._service.spreadsheets().values().update(
                spreadsheetId=self.sheets_config.spreadsheet_id,
                range=f"{sheet_name}!A1",
                valueInputOption='RAW',
                body=body,
            ).execute()
            
            logger.info(f"Created headers in {sheet_name}")
            
        except Exception as e:
            logger.error(f"Failed to create headers: {e}")
            raise
    
    def write_batch(
        self, 
        rows: List[Dict[str, Any]], 
        conflict_strategy: str = 'overwrite',
        key_columns: Optional[List[str]] = None
    ) -> int:
        """
        Append rows to sheet.
        
        Note: Google Sheets append always adds to the end.
        Conflict strategies are not fully supported for Sheets.
        
        Args:
            rows: List of row dicts to append
            conflict_strategy: Not fully supported, defaults to append
            key_columns: Not used for Sheets
            
        Returns:
            Number of rows appended
        """
        if not rows:
            return 0
        
        try:
            from googleapiclient.errors import HttpError
        except ImportError:
            HttpError = Exception
        
        sheet_name = self.sheets_config.sheet_name or 'Sheet1'
        
        # Get headers from schema or first row
        try:
            existing_schema = self.get_schema()
            if existing_schema:
                headers = list(existing_schema.keys())
            else:
                headers = list(rows[0].keys())
        except Exception:
            headers = list(rows[0].keys())
        
        # Convert dicts to value arrays (in header order)
        values = []
        for row in rows:
            row_values = [str(row.get(h, '')) for h in headers]
            values.append(row_values)
        
        body = {'values': values}
        
        try:
            result = self._service.spreadsheets().values().append(
                spreadsheetId=self.sheets_config.spreadsheet_id,
                range=sheet_name,
                valueInputOption='USER_ENTERED',
                insertDataOption='INSERT_ROWS',
                body=body,
            ).execute()
            
            updates = result.get('updates', {})
            updated_rows = updates.get('updatedRows', 0)
            
            logger.info(f"Appended {updated_rows} rows to {sheet_name}")
            return updated_rows
            
        except HttpError as e:
            logger.error(f"Google Sheets API error: {e}")
            raise
    
    def clear_sheet(self, preserve_headers: bool = True) -> None:
        """
        Clear all data from sheet.
        
        Args:
            preserve_headers: If True, only clears data rows (keeps header)
        """
        sheet_name = self.sheets_config.sheet_name or 'Sheet1'
        
        if preserve_headers:
            # Clear from row 2 onwards
            range_name = f"{sheet_name}!A2:ZZ"
        else:
            # Clear everything
            range_name = sheet_name
        
        try:
            self._service.spreadsheets().values().clear(
                spreadsheetId=self.sheets_config.spreadsheet_id,
                range=range_name,
            ).execute()
            
            logger.info(f"Cleared data from {sheet_name} (preserve_headers={preserve_headers})")
            
        except Exception as e:
            logger.error(f"Failed to clear sheet: {e}")
            raise
    
    def begin_transaction(self) -> None:
        """
        Begin transaction (no-op for Sheets).
        
        Google Sheets doesn't support transactions.
        """
        logger.debug("begin_transaction called (no-op for Sheets)")
    
    def commit_transaction(self) -> None:
        """
        Commit transaction (no-op for Sheets).
        
        Google Sheets doesn't support transactions.
        """
        logger.debug("commit_transaction called (no-op for Sheets)")
    
    def rollback_transaction(self) -> None:
        """
        Rollback transaction (no-op for Sheets).
        
        Google Sheets doesn't support transactions.
        All writes are immediately persisted.
        """
        logger.warning("rollback_transaction called but Sheets doesn't support rollback")

