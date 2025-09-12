# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import json
import os
import uuid
import time
import logging
import threading
from typing import Optional

import requests
import websocket

from agenteval.targets import BaseTarget, TargetResponse
from agenteval.utils import Store

logger = logging.getLogger(__name__)


class WebSocketConnectionManager:
    """Manages WebSocket connections with ping/pong and reconnection logic."""
    
    def __init__(self, endpoint: str, headers: dict, timeout: int):
        self.endpoint = endpoint
        self.headers = headers
        self.timeout = timeout
        self.ws = None
        self.ws_thread = None
        self.final_response = None
        self.ws_error = None
        self.connection_lost = False
        self.ping_interval = 30  # Send ping every 30 seconds
        self.last_ping_time = 0
        self.last_pong_time = 0
        self.max_reconnect_attempts = 3
        self.reconnect_delay = 2  # seconds
        self.ping_timeout = 10  # seconds to wait for pong response
        self._lock = threading.Lock()
        
    def connect(self) -> bool:
        """Establish WebSocket connection with retry logic."""
        for attempt in range(self.max_reconnect_attempts):
            try:
                logger.debug(f"WebSocket connection attempt {attempt + 1}/{self.max_reconnect_attempts}")
                
                self.ws = websocket.WebSocketApp(
                    self.endpoint,
                    on_open=self._on_open,
                    on_message=self._on_message,
                    on_error=self._on_error,
                    on_close=self._on_close,
                    on_ping=self._on_ping,
                    on_pong=self._on_pong,
                    header=self.headers
                )
                
                # Run WebSocket in a separate thread
                self.ws_thread = threading.Thread(target=self._run_with_ping)
                self.ws_thread.daemon = True
                self.ws_thread.start()
                
                # Wait a bit for connection to establish
                time.sleep(1)
                
                if self.ws and not self.connection_lost:
                    logger.debug("WebSocket connection established successfully")
                    return True
                    
            except Exception as e:
                logger.warning(f"WebSocket connection attempt {attempt + 1} failed: {e}")
                
            if attempt < self.max_reconnect_attempts - 1:
                logger.debug(f"Retrying connection in {self.reconnect_delay} seconds...")
                time.sleep(self.reconnect_delay)
        
        logger.error("Failed to establish WebSocket connection after all attempts")
        return False
    
    def _run_with_ping(self):
        """Run WebSocket with automatic ping mechanism."""
        try:
            # Start the WebSocket connection
            self.ws.run_forever()
        except Exception as e:
            logger.error(f"WebSocket run_forever failed: {e}")
            self.ws_error = e
    
    def _send_ping(self):
        """Send ping message to keep connection alive."""
        if self.ws and not self.connection_lost:
            try:
                ping_message = {"type": "ping", "message": {}}
                self.ws.send(json.dumps(ping_message))
                self.last_ping_time = time.time()
                logger.debug("Sent ping message")
            except Exception as e:
                logger.warning(f"Failed to send ping: {e}")
                self.connection_lost = True
    
    def _check_connection_health(self):
        """Check if connection is healthy based on ping/pong timing."""
        current_time = time.time()
        
        # Send ping if interval has passed
        if current_time - self.last_ping_time > self.ping_interval:
            self._send_ping()
        
        # Check if we haven't received pong in time
        if (self.last_ping_time > 0 and 
            self.last_pong_time < self.last_ping_time and 
            current_time - self.last_ping_time > self.ping_timeout):
            logger.warning("Ping timeout - connection may be lost")
            with self._lock:
                self.connection_lost = True
    
    def _on_open(self, ws):
        """Handle WebSocket connection open."""
        with self._lock:
            self.connection_lost = False
            self.last_ping_time = time.time()
            self.last_pong_time = time.time()
        logger.debug("WebSocket connection established")
    
    def _on_message(self, ws, message):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(message)
            logger.debug(f"Received WebSocket message: {json.dumps(data, indent=2)[:200]}...")
            
            # Handle pong messages
            if data.get("type") == "pong":
                with self._lock:
                    self.last_pong_time = time.time()
                logger.debug("Received pong response")
                return
            
            # Check for preview message format
            if data.get("type") == "preview":
                message_data = data.get("message", {})
                if message_data.get("type") == "preview":
                    content = message_data.get("content", {})
                    if content.get("type") == "broadcast" and "message" in content:
                        message_content = content["message"]

                        # Handle both string and array formats
                        if isinstance(message_content, str):
                            # Simple string format
                            self.final_response = message_content
                        elif isinstance(message_content, list) and len(message_content) > 0:
                            # Array format - concatenate all text messages
                            text_parts = []
                            for msg in message_content:
                                if isinstance(msg, dict) and "msg" in msg:
                                    msg_obj = msg["msg"]
                                    if isinstance(msg_obj, dict) and "text" in msg_obj:
                                        text_parts.append(msg_obj["text"])

                            if text_parts:
                                self.final_response = "\n".join(text_parts)
                        
                        if self.final_response:
                            logger.debug(f"Received preview broadcast message: {self.final_response[:100]}...")

        except json.JSONDecodeError:
            logger.warning(f"Failed to decode WebSocket message: {message[:100]}...")
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {str(e)}")
    
    def _on_error(self, ws, error):
        """Handle WebSocket errors."""
        with self._lock:
            self.ws_error = error
            self.connection_lost = True
        logger.error(f"WebSocket error: {error}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket closure."""
        with self._lock:
            self.connection_lost = True
        logger.debug(f"WebSocket closed with code {close_status_code}: {close_msg}")
    
    def _on_ping(self, ws, message):
        """Handle WebSocket ping from server."""
        logger.debug("Received WebSocket ping from server")
    
    def _on_pong(self, ws, message):
        """Handle WebSocket pong from server."""
        with self._lock:
            self.last_pong_time = time.time()
        logger.debug("Received WebSocket pong from server")
    
    def wait_for_response(self) -> Optional[str]:
        """Wait for response with connection health monitoring and reconnection."""
        start_time = time.time()
        
        while self.final_response is None and (time.time() - start_time) < self.timeout:
            # Check connection health and send pings
            self._check_connection_health()
            
            # Handle connection loss with reconnection
            if self.connection_lost and self.final_response is None:
                logger.warning("Connection lost, attempting to reconnect...")
                self.close()
                
                if not self.connect():
                    break
            
            # Check for WebSocket errors
            if self.ws_error:
                logger.error(f"WebSocket error occurred: {self.ws_error}")
                return None  # Let the timeout handling deal with this
            
            time.sleep(0.1)
        
        # Close connection when we have a response or timeout
        if self.final_response is not None:
            logger.debug("Response received, closing WebSocket connection")
            self.close()
        
        return self.final_response
    
    def close(self):
        """Close WebSocket connection and cleanup."""
        try:
            if self.ws:
                self.ws.close()
        except:
            pass
        
        # Only join thread if we're not calling from within the WebSocket thread itself
        if self.ws_thread and self.ws_thread.is_alive():
            current_thread = threading.current_thread()
            if current_thread != self.ws_thread:
                self.ws_thread.join(timeout=1)
            else:
                # If called from within the WebSocket thread, just mark it for cleanup
                logger.debug("Close called from WebSocket thread, skipping thread join")


class WeniTarget(BaseTarget):
    """A target encapsulating a Weni agent."""

    def __init__(
        self,
        weni_project_uuid: Optional[str] = None,
        weni_bearer_token: Optional[str] = None,
        language: str = "en-US",
        timeout: int = 480,
        **kwargs
    ):
        """Initialize the target.

        Args:
            weni_project_uuid (Optional[str]): The Weni project UUID. 
                If not provided, will be read from WENI_PROJECT_UUID env var or weni-cli cache.
            weni_bearer_token (Optional[str]): The Weni bearer token. 
                If not provided, will be read from WENI_BEARER_TOKEN env var or weni-cli cache.
            language (str): The language for the conversation. Defaults to "pt-BR".
            timeout (int): Maximum time to wait for agent response in seconds. Defaults to 30.
        """
        super().__init__()
        
        # Try multiple sources for project_uuid and bearer_token:
        # 1. Direct parameter
        # 2. Environment variable
        # 3. Weni CLI cache (fallback)
        store = Store()
        
        self.project_uuid = (
            weni_project_uuid or 
            os.environ.get("WENI_PROJECT_UUID") or 
            store.get_project_uuid()
        )
        self.bearer_token = (
            weni_bearer_token or 
            os.environ.get("WENI_BEARER_TOKEN") or 
            store.get_token()
        )
        self.language = language
        self.timeout = timeout
        
        if not self.project_uuid:
            raise ValueError(
                "weni_project_uuid is required. Please:\n"
                "1. Install and use Weni CLI (recommended): 'pip install weni-cli && weni login && weni project use [project-uuid]'\n"
                "   Get Weni CLI at: https://github.com/weni-ai/weni-cli\n"
                "2. Or set WENI_PROJECT_UUID environment variable\n"
                "3. Or provide 'weni_project_uuid' in your test configuration"
            )
        if not self.bearer_token:
            raise ValueError(
                "weni_bearer_token is required. Please:\n"
                "1. Install and use Weni CLI (recommended): 'pip install weni-cli && weni login'\n"
                "   Get Weni CLI at: https://github.com/weni-ai/weni-cli\n"
                "2. Or set WENI_BEARER_TOKEN environment variable\n"
                "3. Or provide 'weni_bearer_token' in your test configuration"
            )
        
        # Generate unique contact URN for this test session
        # This ensures each test case has its own conversation history
        self.contact_urn = f"ext:{uuid.uuid4().hex}"
        
        # API endpoints
        self.api_base_url = "https://nexus.weni.ai"
        self.api_endpoint = f"{self.api_base_url}/api/{self.project_uuid}/preview/"
        self.ws_endpoint = (
            f"wss://nexus.weni.ai/ws/preview/{self.project_uuid}/"
            f"?Token={self.bearer_token}"
        )
        
        logger.debug(f"Initialized WeniTarget with project UUID: {self.project_uuid}")
        logger.debug(f"Using contact URN: {self.contact_urn}")

    def invoke(self, prompt: str) -> TargetResponse:
        """Invoke the target with a prompt.

        Args:
            prompt (str): The prompt as a string.

        Returns:
            TargetResponse
        """
        try:
            logger.debug(f"Invoking Weni agent with prompt: {prompt}")
            
            # Send the prompt via POST request
            self._send_prompt(prompt)
            
            # Connect to WebSocket and wait for response
            response_text = self._wait_for_response()
            
            return TargetResponse(
                response=response_text,
                data={
                    "contact_urn": self.contact_urn,
                    "language": self.language,
                    "session_id": self.contact_urn
                }
            )
            
        except Exception as e:
            # Handle any unexpected errors gracefully
            error_message = (
                f"UNEXPECTED ERROR: {str(e)} - "
                f"An unexpected error occurred while invoking the Weni agent. "
                f"Test case marked as failed."
            )
            logger.error(f"Error invoking Weni agent: {error_message}")

            # Return error response instead of raising exception
            return TargetResponse(
                response=error_message,
                data={
                    "contact_urn": self.contact_urn,
                    "language": self.language,
                    "session_id": self.contact_urn,
                    "error": True
                }
            )

    def _send_prompt(self, prompt: str) -> None:
        """Send a prompt to the Weni API.

        Args:
            prompt (str): The message to send.

        Raises:
            requests.HTTPError: If the API request fails.
        """
        headers = {
            "accept": "application/json, text/plain, */*",
            "accept-language": "en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7,es;q=0.6,nl;q=0.5,fr;q=0.4",
            "authorization": f"Bearer {self.bearer_token}",
            "content-type": "application/json",
            "origin": "https://intelligence-next.weni.ai",
            "priority": "u=1, i",
            "referer": "https://intelligence-next.weni.ai/agents",
            "sec-ch-ua": '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/139.0.0.0 Safari/537.36"
            )
        }
        
        data = {
            "text": prompt,
            "attachments": [],
            "contact_urn": self.contact_urn,
            "language": self.language
        }
        
        logger.debug(f"Sending POST request to {self.api_endpoint}")
        
        response = requests.post(
            self.api_endpoint,
            headers=headers,
            json=data,
            timeout=10
        )
        
        try:
            response.raise_for_status()
            logger.debug(f"Successfully sent prompt to Weni API. Status: {response.status_code}")
        except requests.exceptions.HTTPError as e:
            self._handle_http_error(response, e)

    def _handle_http_error(self, response: requests.Response, error: requests.exceptions.HTTPError) -> None:
        """Handle HTTP errors with helpful error messages.
        
        Args:
            response: The HTTP response object
            error: The original HTTPError
            
        Raises:
            ValueError: With a helpful error message based on the status code
        """
        status_code = response.status_code
        
        if status_code == 401:
            # Unauthorized - likely invalid token
            error_msg = (
                f"Authentication failed (401 Unauthorized). "
                f"The bearer token is invalid or expired.\n\n"
                f"To fix this issue:\n"
                f"1. Install and use Weni CLI (recommended): 'pip install weni-cli && weni login'\n"
                f"   Get Weni CLI at: https://github.com/weni-ai/weni-cli\n"
                f"2. Or set a valid token in environment variable: WENI_BEARER_TOKEN=your_token\n"
                f"3. Or provide 'weni_bearer_token' in your test configuration\n\n"
                f"Get your token manually from: https://intelligence.weni.ai (User menu > API Token)"
            )
            raise ValueError(error_msg) from error
            
        elif status_code == 403:
            # Forbidden - likely no access to project
            error_msg = (
                f"Access forbidden (403 Forbidden). "
                f"You don't have permission to access this project.\n\n"
                f"To fix this issue:\n"
                f"1. Verify the project UUID is correct: {self.project_uuid}\n"
                f"2. Ensure you have access to this project in Weni\n"
                f"3. Contact your project administrator if needed"
            )
            raise ValueError(error_msg) from error
            
        elif status_code == 404:
            # Not found - likely invalid project UUID
            error_msg = (
                f"Project not found (404 Not Found). "
                f"The project UUID '{self.project_uuid}' does not exist or is invalid.\n\n"
                f"To fix this issue:\n"
                f"1. Use Weni CLI to select the correct project (recommended): 'weni project use [project-uuid]'\n"
                f"   Get Weni CLI at: https://github.com/weni-ai/weni-cli\n"
                f"2. Or set the correct UUID in environment variable: WENI_PROJECT_UUID=your_uuid\n"
                f"3. Or provide 'weni_project_uuid' in your test configuration\n\n"
                f"Find your project UUID manually at: https://intelligence.weni.ai (Project Settings > General)"
            )
            raise ValueError(error_msg) from error
            
        elif status_code >= 500:
            # Server error
            error_msg = (
                f"Weni server error ({status_code}). "
                f"The Weni API is experiencing issues.\n\n"
                f"To fix this issue:\n"
                f"1. Wait a few minutes and try again\n"
                f"2. Check Weni status page for known issues\n"
                f"3. Contact Weni support if the problem persists"
            )
            raise ValueError(error_msg) from error
            
        else:
            # Other HTTP errors
            error_msg = (
                f"HTTP error {status_code}: {response.reason}\n"
                f"URL: {response.url}\n\n"
                f"Please check your configuration and try again."
            )
            raise ValueError(error_msg) from error

    def _wait_for_response(self) -> str:
        """Connect to WebSocket and wait for the agent's final response.

        Returns:
            str: The agent's final response text.

        Raises:
            TimeoutError: If no response is received within the timeout period.
        """
        # Configure WebSocket headers
        headers = {
            "Origin": "https://intelligence-next.weni.ai",
            "Accept-Language": "en-US,en;q=0.9,pt-BR;q=0.8,pt;q=0.7,es;q=0.6,nl;q=0.5,fr;q=0.4",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/139.0.0.0 Safari/537.36"
            )
        }
        
        logger.debug(f"Connecting to WebSocket: {self.ws_endpoint[:50]}...")
        
        # Create connection manager with ping/pong and reconnection support
        connection_manager = WebSocketConnectionManager(
            endpoint=self.ws_endpoint,
            headers=headers,
            timeout=self.timeout
        )
        
        # Establish initial connection
        if not connection_manager.connect():
            error_message = (
                f"CONNECTION ERROR: Failed to establish WebSocket connection after multiple attempts. "
                f"This could indicate network connectivity issues, invalid credentials, or server problems. "
                f"Test case marked as failed."
            )
            logger.error(error_message)
            return error_message
        
        try:
            # Wait for response with automatic reconnection and ping/pong
            final_response = connection_manager.wait_for_response()
            
            if final_response is None:
                # Instead of raising an exception, return an error response
                # This allows the test to continue with other test cases
                error_message = (
                    f"TIMEOUT ERROR: No response received from Weni agent within {self.timeout} seconds. "
                    f"This could indicate network issues, agent processing delays, or WebSocket connection problems. "
                    f"Test case marked as failed."
                )
                logger.error(error_message)
                return error_message
            
            return final_response
            
        finally:
            # Ensure WebSocket is properly closed
            connection_manager.close()
