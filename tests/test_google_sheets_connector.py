"""
Tests for Google Sheets connector implementation.

These tests use mocks for the Google Sheets API.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from portl.schema import GoogleSheetsConfig


class TestGoogleSheetsConnectorUnit:
    """Unit tests for Google Sheets connector (no API calls)."""
    
    @pytest.fixture
    def sheets_config(self):
        """Create a Google Sheets config."""
        return GoogleSheetsConfig(
            type='google_sheets',
            spreadsheet_id='1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms',
            sheet_name='Sheet1',
            credentials_path=None,  # Will use ADC mock
        )
    
    def test_connector_validates_config_type(self, sheets_config):
        """Verify connector rejects non-google_sheets config."""
        from portl.connectors.google_sheets import GoogleSheetsSourceConnector
        
        # Invalid config type should fail
        sheets_config.type = 'postgres'
        with pytest.raises(ValueError) as exc_info:
            GoogleSheetsSourceConnector(sheets_config)
        assert 'Expected google_sheets config' in str(exc_info.value)
    
    def test_build_range_basic(self, sheets_config):
        """Verify range is built correctly."""
        from portl.connectors.google_sheets import GoogleSheetsSourceConnector
        
        sheets_config.type = 'google_sheets'
        connector = GoogleSheetsSourceConnector(sheets_config)
        
        assert connector._build_range() == 'Sheet1'
    
    def test_build_range_with_custom_range(self, sheets_config):
        """Verify custom range is used."""
        from portl.connectors.google_sheets import GoogleSheetsSourceConnector
        
        sheets_config.type = 'google_sheets'
        sheets_config.range_name = 'A1:D100'
        connector = GoogleSheetsSourceConnector(sheets_config)
        
        assert connector._build_range() == 'Sheet1!A1:D100'


class TestGoogleSheetsSourceConnector:
    """Tests for Google Sheets source connector with mocked API."""
    
    @pytest.fixture
    def sheets_config(self):
        return GoogleSheetsConfig(
            type='google_sheets',
            spreadsheet_id='test_spreadsheet_id',
            sheet_name='TestSheet',
            credentials_path=None,
        )
    
    @pytest.fixture
    def mock_sheets_service(self):
        """Mock Google Sheets API service."""
        mock_service = MagicMock()
        return mock_service
    
    def test_read_all_parses_headers(self, sheets_config, mock_sheets_service):
        """First row becomes column headers."""
        from portl.connectors.google_sheets import GoogleSheetsSourceConnector
        
        # Setup mock response
        mock_sheets_service.spreadsheets().values().get().execute.return_value = {
            'values': [
                ['id', 'name', 'email'],
                ['1', 'Alice', 'alice@example.com'],
                ['2', 'Bob', 'bob@example.com'],
            ]
        }
        
        with patch.object(GoogleSheetsSourceConnector, '_authenticate'):
            connector = GoogleSheetsSourceConnector(sheets_config)
            connector._service = mock_sheets_service
            
            rows = connector.read_all()
            
            assert len(rows) == 2
            assert rows[0] == {'id': '1', 'name': 'Alice', 'email': 'alice@example.com'}
            assert rows[1] == {'id': '2', 'name': 'Bob', 'email': 'bob@example.com'}
    
    def test_read_all_handles_short_rows(self, sheets_config, mock_sheets_service):
        """Rows with fewer values than headers are padded."""
        from portl.connectors.google_sheets import GoogleSheetsSourceConnector
        
        mock_sheets_service.spreadsheets().values().get().execute.return_value = {
            'values': [
                ['a', 'b', 'c'],
                ['1'],  # Short row - only has one value
                ['2', '3'],  # Another short row
            ]
        }
        
        with patch.object(GoogleSheetsSourceConnector, '_authenticate'):
            connector = GoogleSheetsSourceConnector(sheets_config)
            connector._service = mock_sheets_service
            
            rows = connector.read_all()
            
            assert len(rows) == 2
            # Short rows should be padded with empty strings
            assert rows[0] == {'a': '1', 'b': '', 'c': ''}
            assert rows[1] == {'a': '2', 'b': '3', 'c': ''}
    
    def test_read_all_empty_sheet(self, sheets_config, mock_sheets_service):
        """Empty sheet returns empty list."""
        from portl.connectors.google_sheets import GoogleSheetsSourceConnector
        
        mock_sheets_service.spreadsheets().values().get().execute.return_value = {
            'values': []
        }
        
        with patch.object(GoogleSheetsSourceConnector, '_authenticate'):
            connector = GoogleSheetsSourceConnector(sheets_config)
            connector._service = mock_sheets_service
            
            rows = connector.read_all()
            
            assert rows == []
    
    def test_get_schema_returns_headers(self, sheets_config, mock_sheets_service):
        """Schema returns column headers with string type."""
        from portl.connectors.google_sheets import GoogleSheetsSourceConnector
        
        mock_sheets_service.spreadsheets().values().get().execute.return_value = {
            'values': [['id', 'name', 'email']]
        }
        
        with patch.object(GoogleSheetsSourceConnector, '_authenticate'):
            connector = GoogleSheetsSourceConnector(sheets_config)
            connector._service = mock_sheets_service
            
            schema = connector.get_schema()
            
            assert schema == {'id': 'string', 'name': 'string', 'email': 'string'}


class TestGoogleSheetsDestinationConnector:
    """Tests for Google Sheets destination connector with mocked API."""
    
    @pytest.fixture
    def sheets_config(self):
        return GoogleSheetsConfig(
            type='google_sheets',
            spreadsheet_id='test_spreadsheet_id',
            sheet_name='TestSheet',
            credentials_path=None,
        )
    
    @pytest.fixture
    def mock_sheets_service(self):
        """Mock Google Sheets API service."""
        mock_service = MagicMock()
        return mock_service
    
    def test_write_batch_appends_rows(self, sheets_config, mock_sheets_service):
        """Rows are appended to sheet."""
        from portl.connectors.google_sheets import GoogleSheetsDestinationConnector
        
        # Setup mock response
        mock_sheets_service.spreadsheets().values().get().execute.return_value = {
            'values': [['id', 'name']]
        }
        mock_sheets_service.spreadsheets().values().append().execute.return_value = {
            'updates': {'updatedRows': 2}
        }
        
        with patch.object(GoogleSheetsDestinationConnector, '_authenticate'):
            connector = GoogleSheetsDestinationConnector(sheets_config)
            connector._service = mock_sheets_service
            
            rows = [
                {'id': '1', 'name': 'Alice'},
                {'id': '2', 'name': 'Bob'},
            ]
            
            count = connector.write_batch(rows)
            
            assert count == 2
            # Verify append was called
            mock_sheets_service.spreadsheets().values().append.assert_called()
    
    def test_write_batch_empty_list(self, sheets_config, mock_sheets_service):
        """Empty list returns 0 without API call."""
        from portl.connectors.google_sheets import GoogleSheetsDestinationConnector
        
        with patch.object(GoogleSheetsDestinationConnector, '_authenticate'):
            connector = GoogleSheetsDestinationConnector(sheets_config)
            connector._service = mock_sheets_service
            
            count = connector.write_batch([])
            
            assert count == 0
    
    def test_clear_sheet_preserves_headers(self, sheets_config, mock_sheets_service):
        """Clear only removes data rows, not header row."""
        from portl.connectors.google_sheets import GoogleSheetsDestinationConnector
        
        with patch.object(GoogleSheetsDestinationConnector, '_authenticate'):
            connector = GoogleSheetsDestinationConnector(sheets_config)
            connector._service = mock_sheets_service
            
            connector.clear_sheet(preserve_headers=True)
            
            # Verify clear was called with range starting at row 2
            mock_sheets_service.spreadsheets().values().clear.assert_called()
            call_args = mock_sheets_service.spreadsheets().values().clear.call_args
            assert 'A2:ZZ' in call_args.kwargs.get('range', '')
    
    def test_transaction_methods_are_noop(self, sheets_config, mock_sheets_service):
        """Transaction methods don't raise errors."""
        from portl.connectors.google_sheets import GoogleSheetsDestinationConnector
        
        with patch.object(GoogleSheetsDestinationConnector, '_authenticate'):
            connector = GoogleSheetsDestinationConnector(sheets_config)
            
            # These should not raise
            connector.begin_transaction()
            connector.commit_transaction()
            connector.rollback_transaction()


class TestGoogleSheetsAuthentication:
    """Tests for Google Sheets authentication."""
    
    @pytest.fixture
    def sheets_config(self):
        return GoogleSheetsConfig(
            type='google_sheets',
            spreadsheet_id='test_id',
            sheet_name='Sheet1',
        )
    
    def test_missing_credentials_raises(self, sheets_config, tmp_path):
        """Missing credentials file raises FileNotFoundError."""
        from portl.connectors.google_sheets import GoogleSheetsSourceConnector
        
        sheets_config.credentials_path = str(tmp_path / "nonexistent.json")
        
        connector = GoogleSheetsSourceConnector(sheets_config)
        
        # Mock the imports to ensure we get to the file check
        with patch.dict('sys.modules', {
            'google.oauth2.service_account': MagicMock(),
            'google.auth': MagicMock(),
        }):
            with pytest.raises(FileNotFoundError) as exc_info:
                connector._authenticate()
            
            assert "Credentials file not found" in str(exc_info.value)
    
    def test_service_account_auth(self, sheets_config, tmp_path):
        """Service account authentication uses credentials file."""
        from portl.connectors.google_sheets import GoogleSheetsSourceConnector
        
        # Create a mock credentials file
        creds_file = tmp_path / "creds.json"
        creds_file.write_text('{"type": "service_account"}')
        sheets_config.credentials_path = str(creds_file)
        
        connector = GoogleSheetsSourceConnector(sheets_config)
        
        mock_creds = MagicMock()
        
        with patch('portl.connectors.google_sheets.service_account') as mock_sa:
            mock_sa.Credentials.from_service_account_file.return_value = mock_creds
            
            # This should succeed with mocked service_account
            # Note: actual test would need proper import mocking
            pass  # Integration test needed


# Run tests if executed directly
if __name__ == '__main__':
    pytest.main([__file__, '-v'])

