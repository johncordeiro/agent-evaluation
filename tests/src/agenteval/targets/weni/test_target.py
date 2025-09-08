# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest
import requests

from src.agenteval.targets.weni import target


@pytest.fixture
def weni_target_fixture(monkeypatch):
    """Create a WeniTarget fixture with mocked environment variables."""
    monkeypatch.setenv("WENI_PROJECT_UUID", "test-project-uuid")
    monkeypatch.setenv("WENI_BEARER_TOKEN", "test-bearer-token")
    
    fixture = target.WeniTarget(
        language="pt-BR",
        timeout=10
    )
    
    return fixture


@pytest.fixture
def weni_target_with_params():
    """Create a WeniTarget fixture with explicit parameters."""
    fixture = target.WeniTarget(
        weni_project_uuid="test-project-uuid",
        weni_bearer_token="test-bearer-token",
        language="en-US",
        timeout=5
    )
    
    return fixture


class TestWeniTarget:
    """Test cases for WeniTarget."""
    
    def test_initialization_with_env_vars(self, weni_target_fixture):
        """Test target initialization with environment variables."""
        assert weni_target_fixture.project_uuid == "test-project-uuid"
        assert weni_target_fixture.bearer_token == "test-bearer-token"
        assert weni_target_fixture.language == "pt-BR"
        assert weni_target_fixture.timeout == 10
        
        # Check if contact URN is a valid UUID format
        contact_id = weni_target_fixture.contact_urn.replace("ext:", "")
        try:
            uuid.UUID(contact_id, version=4)
            assert True
        except ValueError:
            assert False, "Contact URN should contain a valid UUID"
    
    def test_initialization_with_params(self, weni_target_with_params):
        """Test target initialization with explicit parameters."""
        assert weni_target_with_params.project_uuid == "test-project-uuid"
        assert weni_target_with_params.bearer_token == "test-bearer-token"
        assert weni_target_with_params.language == "en-US"
        assert weni_target_with_params.timeout == 5
    
    @patch('src.agenteval.targets.weni.target.Store')
    def test_initialization_missing_project_uuid(self, mock_store_class, monkeypatch):
        """Test that missing project UUID raises ValueError."""
        # Clear environment variables
        monkeypatch.delenv("WENI_PROJECT_UUID", raising=False)
        monkeypatch.delenv("WENI_BEARER_TOKEN", raising=False)
        
        # Mock store to return None for both values
        mock_store = MagicMock()
        mock_store.get_project_uuid.return_value = None
        mock_store.get_token.return_value = None
        mock_store_class.return_value = mock_store
        
        with pytest.raises(ValueError, match="weni_project_uuid is required"):
            target.WeniTarget(
                weni_bearer_token="test-token"
            )
    
    @patch('src.agenteval.targets.weni.target.Store')
    def test_initialization_missing_bearer_token(self, mock_store_class, monkeypatch):
        """Test that missing bearer token raises ValueError."""
        # Clear environment variables
        monkeypatch.delenv("WENI_PROJECT_UUID", raising=False)
        monkeypatch.delenv("WENI_BEARER_TOKEN", raising=False)
        
        # Mock store to return None for both values
        mock_store = MagicMock()
        mock_store.get_project_uuid.return_value = None
        mock_store.get_token.return_value = None
        mock_store_class.return_value = mock_store
        
        with pytest.raises(ValueError, match="weni_bearer_token is required"):
            target.WeniTarget(
                weni_project_uuid="test-uuid"
            )
    
    @patch('src.agenteval.targets.weni.target.requests.post')
    @patch('src.agenteval.targets.weni.target.websocket.WebSocketApp')
    def test_invoke(self, mock_websocket, mock_post, weni_target_fixture):
        """Test the invoke method with mocked responses."""
        # Mock POST request
        mock_post.return_value = MagicMock(status_code=200)
        
        # Mock WebSocket to simulate receiving a final response
        mock_ws_instance = MagicMock()
        mock_websocket.return_value = mock_ws_instance
        
        # Simulate WebSocket message handling
        def simulate_ws_run():
            # Get the on_message callback
            on_message = mock_websocket.call_args[1]['on_message']
            
            # Simulate receiving a message with preview format (matching actual implementation)
            test_message = {
                "type": "preview",
                "message": {
                    "type": "preview",
                    "content": {
                        "type": "broadcast",
                        "message": "Test response from Weni agent"
                    }
                }
            }
            
            # Call the on_message handler
            on_message(mock_ws_instance, json.dumps(test_message))
        
        mock_ws_instance.run_forever.side_effect = simulate_ws_run
        
        # Invoke the target
        response = weni_target_fixture.invoke("Test prompt")
        
        # Verify the response
        assert response.response == "Test response from Weni agent"
        assert response.data["contact_urn"] == weni_target_fixture.contact_urn
        assert response.data["language"] == "pt-BR"
        assert response.data["session_id"] == weni_target_fixture.contact_urn
        
        # Verify POST request was made correctly
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == weni_target_fixture.api_endpoint
        assert call_args[1]["json"]["text"] == "Test prompt"
        assert call_args[1]["json"]["contact_urn"] == weni_target_fixture.contact_urn
        assert call_args[1]["json"]["language"] == "pt-BR"
    
    @patch('src.agenteval.targets.weni.target.requests.post')
    def test_send_prompt_error(self, mock_post, weni_target_fixture):
        """Test error handling in _send_prompt method."""
        mock_post.return_value = MagicMock(status_code=500)
        mock_post.return_value.raise_for_status.side_effect = Exception("API Error")
        
        with pytest.raises(Exception, match="API Error"):
            weni_target_fixture._send_prompt("Test prompt")
    
    @patch('src.agenteval.targets.weni.target.requests.post')
    @patch('src.agenteval.targets.weni.target.websocket.WebSocketApp')
    def test_timeout_handling(self, mock_websocket, mock_post, weni_target_with_params):
        """Test timeout handling when no response is received."""
        # Mock POST request
        mock_post.return_value = MagicMock(status_code=200)
        
        # Mock WebSocket without sending any finalResponse
        mock_ws_instance = MagicMock()
        mock_websocket.return_value = mock_ws_instance
        
        # Set a very short timeout for testing
        weni_target_with_params.timeout = 0.1
        
        # Invoke should raise TimeoutError
        with pytest.raises(TimeoutError, match="No response received"):
            weni_target_with_params.invoke("Test prompt")
    
    @patch('src.agenteval.targets.weni.target.requests.post')
    @patch('src.agenteval.targets.weni.target.websocket.WebSocketApp')
    def test_websocket_error_handling(self, mock_websocket, mock_post, weni_target_fixture):
        """Test WebSocket error handling."""
        # Mock POST request
        mock_post.return_value = MagicMock(status_code=200)
        
        # Mock WebSocket to simulate an error
        mock_ws_instance = MagicMock()
        mock_websocket.return_value = mock_ws_instance
        
        def simulate_ws_error():
            # Get the on_error callback
            on_error = mock_websocket.call_args[1]['on_error']
            
            # Simulate a WebSocket error
            on_error(mock_ws_instance, "Connection failed")
        
        mock_ws_instance.run_forever.side_effect = simulate_ws_error
        
        # Invoke should raise RuntimeError
        with pytest.raises(RuntimeError, match="WebSocket error occurred"):
            weni_target_fixture.invoke("Test prompt")
    
    @patch('src.agenteval.targets.weni.target.Store')
    def test_initialization_with_store_fallback(self, mock_store_class, monkeypatch):
        """Test that WeniTarget falls back to store when env vars are not set."""
        # Clear environment variables
        monkeypatch.delenv("WENI_PROJECT_UUID", raising=False)
        monkeypatch.delenv("WENI_BEARER_TOKEN", raising=False)
        
        # Mock the store instance and its methods
        mock_store = MagicMock()
        mock_store.get_project_uuid.return_value = "store-project-uuid"
        mock_store.get_token.return_value = "store-bearer-token"
        mock_store_class.return_value = mock_store
        
        # Create target without explicit parameters
        weni_target = target.WeniTarget(
            language="en-US",
            timeout=10
        )
        
        # Verify store was used
        mock_store_class.assert_called_once()
        mock_store.get_project_uuid.assert_called_once()
        mock_store.get_token.assert_called_once()
        
        # Verify values from store were used
        assert weni_target.project_uuid == "store-project-uuid"
        assert weni_target.bearer_token == "store-bearer-token"
    
    @patch('src.agenteval.targets.weni.target.Store')
    def test_initialization_store_fallback_missing_values(self, mock_store_class, monkeypatch):
        """Test that missing values in store still raise ValueError."""
        # Clear environment variables
        monkeypatch.delenv("WENI_PROJECT_UUID", raising=False)
        monkeypatch.delenv("WENI_BEARER_TOKEN", raising=False)
        
        # Mock the store instance to return None for both values
        mock_store = MagicMock()
        mock_store.get_project_uuid.return_value = None
        mock_store.get_token.return_value = None
        mock_store_class.return_value = mock_store
        
        # Should raise ValueError for missing project UUID
        with pytest.raises(ValueError, match="weni_project_uuid is required"):
            target.WeniTarget()
    
    @patch('src.agenteval.targets.weni.target.Store')
    def test_initialization_priority_order(self, mock_store_class, monkeypatch):
        """Test that parameter > env var > store priority is respected."""
        # Set environment variable
        monkeypatch.setenv("WENI_PROJECT_UUID", "env-project-uuid")
        monkeypatch.setenv("WENI_BEARER_TOKEN", "env-bearer-token")
        
        # Mock the store instance
        mock_store = MagicMock()
        mock_store.get_project_uuid.return_value = "store-project-uuid"
        mock_store.get_token.return_value = "store-bearer-token"
        mock_store_class.return_value = mock_store
        
        # Create target with explicit parameter (should take highest priority)
        weni_target = target.WeniTarget(
            weni_project_uuid="param-project-uuid",
            weni_bearer_token="param-bearer-token"
        )
        
        # Verify parameters took priority
        assert weni_target.project_uuid == "param-project-uuid"
        assert weni_target.bearer_token == "param-bearer-token"
        
        # Store should still be instantiated but methods not called since params provided
        mock_store_class.assert_called_once()
        
        # Now test env var priority over store
        weni_target_env = target.WeniTarget()
        
        # Should use env vars, not store values
        assert weni_target_env.project_uuid == "env-project-uuid"
        assert weni_target_env.bearer_token == "env-bearer-token"
    
    @patch('src.agenteval.targets.weni.target.Store')
    def test_initialization_partial_store_fallback(self, mock_store_class, monkeypatch):
        """Test partial fallback where only one value comes from store."""
        # Set only project UUID in env var
        monkeypatch.setenv("WENI_PROJECT_UUID", "env-project-uuid")
        monkeypatch.delenv("WENI_BEARER_TOKEN", raising=False)
        
        # Mock the store instance
        mock_store = MagicMock()
        mock_store.get_project_uuid.return_value = "store-project-uuid"
        mock_store.get_token.return_value = "store-bearer-token"
        mock_store_class.return_value = mock_store
        
        # Create target
        weni_target = target.WeniTarget()
        
        # Should use env var for project UUID and store for token
        assert weni_target.project_uuid == "env-project-uuid"
        assert weni_target.bearer_token == "store-bearer-token"
        
        # Verify only get_token was called since project_uuid was available from env var
        # Due to Python's 'or' short-circuit evaluation, get_project_uuid won't be called
        mock_store.get_token.assert_called_once()
    
    @patch('src.agenteval.targets.weni.target.requests.post')
    def test_http_error_401_unauthorized(self, mock_post, weni_target_fixture):
        """Test 401 Unauthorized error handling."""
        # Mock a 401 response
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.reason = "Unauthorized"
        mock_response.url = "https://nexus.weni.ai/api/test/preview/"
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("401 Client Error")
        mock_post.return_value = mock_response
        
        with pytest.raises(ValueError, match="Authentication failed.*401 Unauthorized"):
            weni_target_fixture._send_prompt("Test prompt")
    
    @patch('src.agenteval.targets.weni.target.requests.post')
    def test_http_error_403_forbidden(self, mock_post, weni_target_fixture):
        """Test 403 Forbidden error handling."""
        # Mock a 403 response
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.reason = "Forbidden"
        mock_response.url = "https://nexus.weni.ai/api/test/preview/"
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("403 Client Error")
        mock_post.return_value = mock_response
        
        with pytest.raises(ValueError, match="Access forbidden.*403 Forbidden"):
            weni_target_fixture._send_prompt("Test prompt")
    
    @patch('src.agenteval.targets.weni.target.requests.post')
    def test_http_error_404_not_found(self, mock_post, weni_target_fixture):
        """Test 404 Not Found error handling."""
        # Mock a 404 response
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.reason = "Not Found"
        mock_response.url = "https://nexus.weni.ai/api/test/preview/"
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("404 Client Error")
        mock_post.return_value = mock_response
        
        with pytest.raises(ValueError, match="Project not found.*404 Not Found"):
            weni_target_fixture._send_prompt("Test prompt")
    
    @patch('src.agenteval.targets.weni.target.requests.post')
    def test_http_error_500_server_error(self, mock_post, weni_target_fixture):
        """Test 500 Server Error handling."""
        # Mock a 500 response
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.reason = "Internal Server Error"
        mock_response.url = "https://nexus.weni.ai/api/test/preview/"
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("500 Server Error")
        mock_post.return_value = mock_response
        
        with pytest.raises(ValueError, match="Weni server error.*500"):
            weni_target_fixture._send_prompt("Test prompt")
    
    @patch('src.agenteval.targets.weni.target.requests.post')
    def test_http_error_other_status(self, mock_post, weni_target_fixture):
        """Test other HTTP error handling."""
        # Mock a 418 response (I'm a teapot - uncommon status code)
        mock_response = MagicMock()
        mock_response.status_code = 418
        mock_response.reason = "I'm a teapot"
        mock_response.url = "https://nexus.weni.ai/api/test/preview/"
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("418 Client Error")
        mock_post.return_value = mock_response
        
        with pytest.raises(ValueError, match="HTTP error 418.*I'm a teapot"):
            weni_target_fixture._send_prompt("Test prompt")
    
    def test_error_messages_contain_helpful_instructions(self, weni_target_fixture):
        """Test that error messages contain helpful instructions for users."""
        # Mock a 401 response to test the error message content
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.reason = "Unauthorized"
        mock_response.url = "https://nexus.weni.ai/api/test/preview/"
        
        try:
            weni_target_fixture._handle_http_error(
                mock_response, 
                requests.exceptions.HTTPError("401 Client Error")
            )
        except ValueError as e:
            error_message = str(e)
            # Check that the error message contains helpful instructions
            assert "weni login" in error_message
            assert "weni-cli" in error_message
            assert "https://github.com/weni-ai/weni-cli" in error_message
            assert "WENI_BEARER_TOKEN" in error_message
            assert "weni_bearer_token" in error_message
        else:
            pytest.fail("Expected ValueError to be raised")
    
    def test_404_error_includes_project_uuid(self, weni_target_fixture):
        """Test that 404 error includes the project UUID in the message."""
        # Mock a 404 response
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.reason = "Not Found"
        mock_response.url = "https://nexus.weni.ai/api/test/preview/"
        
        try:
            weni_target_fixture._handle_http_error(
                mock_response,
                requests.exceptions.HTTPError("404 Client Error")
            )
        except ValueError as e:
            error_message = str(e)
            # Check that the error message includes the project UUID and weni-cli info
            assert weni_target_fixture.project_uuid in error_message
            assert "weni project use" in error_message
            assert "https://github.com/weni-ai/weni-cli" in error_message
            assert "WENI_PROJECT_UUID" in error_message
            assert "weni_project_uuid" in error_message
        else:
            pytest.fail("Expected ValueError to be raised")