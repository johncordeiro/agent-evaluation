# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open

import pytest

from src.agenteval.utils.store import Store, STORE_TOKEN_KEY, STORE_PROJECT_UUID_KEY


class TestStore:
    """Test cases for Store utility class."""
    
    def test_get_with_valid_file(self):
        """Test getting values from a valid store file."""
        test_data = {
            STORE_TOKEN_KEY: "test-token-123",
            STORE_PROJECT_UUID_KEY: "test-uuid-456",
            "other_key": "other_value"
        }
        
        with patch("builtins.open", mock_open(read_data=json.dumps(test_data))):
            with patch("os.path.exists", return_value=True):
                store = Store()
                
                assert store.get(STORE_TOKEN_KEY) == "test-token-123"
                assert store.get(STORE_PROJECT_UUID_KEY) == "test-uuid-456"
                assert store.get("other_key") == "other_value"
                assert store.get("nonexistent_key") is None
                assert store.get("nonexistent_key", "default") == "default"
    
    def test_get_with_nonexistent_file(self):
        """Test getting values when store file doesn't exist."""
        with patch("os.path.exists", return_value=False):
            store = Store()
            
            assert store.get(STORE_TOKEN_KEY) is None
            assert store.get(STORE_PROJECT_UUID_KEY) is None
            assert store.get("any_key", "default") == "default"
    
    def test_get_with_empty_file(self):
        """Test getting values from an empty store file."""
        with patch("builtins.open", mock_open(read_data="")):
            with patch("os.path.exists", return_value=True):
                store = Store()
                
                assert store.get(STORE_TOKEN_KEY) is None
                assert store.get(STORE_PROJECT_UUID_KEY) is None
                assert store.get("any_key", "default") == "default"
    
    def test_get_with_invalid_json(self):
        """Test getting values from a file with invalid JSON."""
        with patch("builtins.open", mock_open(read_data="invalid json")):
            with patch("os.path.exists", return_value=True):
                store = Store()
                
                # Should return default values when JSON is invalid
                assert store.get(STORE_TOKEN_KEY) is None
                assert store.get(STORE_PROJECT_UUID_KEY) is None
                assert store.get("any_key", "default") == "default"
    
    def test_get_with_io_error(self):
        """Test getting values when file I/O fails."""
        with patch("builtins.open", side_effect=IOError("File read error")):
            with patch("os.path.exists", return_value=True):
                store = Store()
                
                # Should return default values when I/O fails
                assert store.get(STORE_TOKEN_KEY) is None
                assert store.get(STORE_PROJECT_UUID_KEY) is None
                assert store.get("any_key", "default") == "default"
    
    def test_get_token(self):
        """Test the convenience method for getting token."""
        test_data = {STORE_TOKEN_KEY: "test-token-123"}
        
        with patch("builtins.open", mock_open(read_data=json.dumps(test_data))):
            with patch("os.path.exists", return_value=True):
                store = Store()
                assert store.get_token() == "test-token-123"
    
    def test_get_project_uuid(self):
        """Test the convenience method for getting project UUID."""
        test_data = {STORE_PROJECT_UUID_KEY: "test-uuid-456"}
        
        with patch("builtins.open", mock_open(read_data=json.dumps(test_data))):
            with patch("os.path.exists", return_value=True):
                store = Store()
                assert store.get_project_uuid() == "test-uuid-456"
    
    def test_store_file_path(self):
        """Test that store file path is correctly constructed."""
        store = Store()
        expected_path = f"{Path.home()}{os.sep}.weni_cli"
        assert store.file_path == expected_path
    
    def test_convenience_methods_with_missing_values(self):
        """Test convenience methods when values are not in store."""
        test_data = {"other_key": "other_value"}
        
        with patch("builtins.open", mock_open(read_data=json.dumps(test_data))):
            with patch("os.path.exists", return_value=True):
                store = Store()
                assert store.get_token() is None
                assert store.get_project_uuid() is None
    
    @patch("src.agenteval.utils.store.logger")
    def test_logging_behavior(self, mock_logger):
        """Test that appropriate log messages are generated."""
        # Test with nonexistent file
        with patch("os.path.exists", return_value=False):
            store = Store()
            store.get("test_key")
            mock_logger.debug.assert_called_with(f"Store file does not exist at {store.file_path}")
        
        # Test with empty file
        mock_logger.reset_mock()
        with patch("builtins.open", mock_open(read_data="")):
            with patch("os.path.exists", return_value=True):
                store = Store()
                store.get("test_key")
                mock_logger.debug.assert_called_with("Store file is empty")
        
        # Test with valid data (should log retrieved value, masking tokens)
        mock_logger.reset_mock()
        test_data = {STORE_TOKEN_KEY: "secret-token", "normal_key": "normal_value"}
        with patch("builtins.open", mock_open(read_data=json.dumps(test_data))):
            with patch("os.path.exists", return_value=True):
                store = Store()
                store.get(STORE_TOKEN_KEY)
                store.get("normal_key")
                
                # Should mask token values in logs
                calls = mock_logger.debug.call_args_list
                token_call = [call for call in calls if "Retrieved value for key 'token'" in str(call)]
                assert len(token_call) == 1
                assert "***" in str(token_call[0])
                
                # Should show normal values in logs
                normal_call = [call for call in calls if "Retrieved value for key 'normal_key'" in str(call)]
                assert len(normal_call) == 1
                assert "normal_value" in str(normal_call[0])
