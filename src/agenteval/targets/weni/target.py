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


class WeniTarget(BaseTarget):
    """A target encapsulating a Weni agent."""

    def __init__(
        self,
        weni_project_uuid: Optional[str] = None,
        weni_bearer_token: Optional[str] = None,
        language: str = "en-US",
        timeout: int = 240,
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
            print(f"Invoking contact URN: {self.contact_urn} with prompt: {prompt}")
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
            logger.error(f"Error invoking Weni agent: {str(e)}")
            raise

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
        final_response = None
        start_time = time.time()
        ws_error = None
        
        def on_message(ws, message):
            """Handle incoming WebSocket messages."""
            nonlocal final_response
            try:
                data = json.loads(message)
                logger.debug(f"Received WebSocket message: {json.dumps(data, indent=2)[:200]}...")
                
                # Check for preview message format
                if data.get("type") == "preview":
                    message = data.get("message", {})
                    if message.get("type") == "preview":
                        content = message.get("content", {})
                        if content.get("type") == "broadcast" and "message" in content:
                            message_content = content["message"]

                            # Handle both string and array formats
                            if isinstance(message_content, str):
                                # Simple string format
                                final_response = message_content
                            elif isinstance(message_content, list) and len(message_content) > 0:
                                # Array format - concatenate all text messages
                                text_parts = []
                                for msg in message_content:
                                    if isinstance(msg, dict) and "msg" in msg:
                                        msg_obj = msg["msg"]
                                        if isinstance(msg_obj, dict) and "text" in msg_obj:
                                            text_parts.append(msg_obj["text"])

                                if text_parts:
                                    final_response = "\n".join(text_parts)
                            
                            if final_response:
                                logger.debug(f"Received preview broadcast message: {final_response[:100]}...")
                                ws.close()

            except json.JSONDecodeError:
                logger.warning(f"Failed to decode WebSocket message: {message[:100]}...")
            except Exception as e:
                logger.error(f"Error processing WebSocket message: {str(e)}")

        def on_error(ws, error):
            """Handle WebSocket errors."""
            nonlocal ws_error
            ws_error = error
            logger.error(f"WebSocket error: {error}")

        def on_close(ws, close_status_code, close_msg):
            """Handle WebSocket closure."""
            logger.debug(f"WebSocket closed with code {close_status_code}: {close_msg}")

        def on_open(ws):
            """Handle WebSocket connection open."""
            logger.debug("WebSocket connection established")

        def on_ping(ws, message):
            """Handle WebSocket ping."""
            logger.debug("Received WebSocket ping")

        def on_pong(ws, message):
            """Handle WebSocket pong."""
            logger.debug("Received WebSocket pong")

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
        
        # Create WebSocket connection
        ws = websocket.WebSocketApp(
            self.ws_endpoint,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_ping=on_ping,
            on_pong=on_pong,
            header=headers
        )
        
        # Run WebSocket in a separate thread
        ws_thread = threading.Thread(target=ws.run_forever)
        ws_thread.daemon = True
        ws_thread.start()
        
        # Wait for response with timeout
        while final_response is None and (time.time() - start_time) < self.timeout:
            if ws_error:
                raise RuntimeError(f"WebSocket error occurred: {ws_error}")
            time.sleep(0.1)
        
        # Ensure WebSocket is closed
        try:
            ws.close()
        except:
            pass
        
        # Wait for thread to finish
        ws_thread.join(timeout=1)
        
        if final_response is None:
            raise TimeoutError(
                f"No response received from Weni agent within {self.timeout} seconds"
            )
        
        return final_response
