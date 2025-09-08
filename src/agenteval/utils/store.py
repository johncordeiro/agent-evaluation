# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import os
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

STORE_TOKEN_KEY = "token"
STORE_PROJECT_UUID_KEY = "project_uuid"
STORE_WENI_BASE_URL = "weni_base_url"
STORE_NEXUS_BASE_URL = "nexus_base_url"
STORE_KEYCLOAK_URL = "keycloak_url"
STORE_KEYCLOAK_REALM = "keycloak_realm"
STORE_KEYCLOAK_CLIENT_ID = "keycloak_client_id"
STORE_CLI_BASE_URL = "cli_base_url"


class Store:
    """
    A utility class to interact with the Weni CLI cache file.
    
    This class provides methods to read configuration values (like tokens and project UUIDs)
    from the Weni CLI cache file, which is typically stored at ~/.weni_cli
    """
    
    def __init__(self):
        self.file_path = f"{Path.home()}{os.sep}.weni_cli"
        logger.debug(f"Store initialized with file path: {self.file_path}")

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get a value from the store by key.
        
        Args:
            key (str): The key to look up
            default (Optional[str]): Default value if key is not found
            
        Returns:
            Optional[str]: The value associated with the key, or default if not found
        """
        try:
            if not os.path.exists(self.file_path):
                logger.debug(f"Store file does not exist at {self.file_path}")
                return default
                
            with open(self.file_path, "r") as file:
                content = file.read().strip()
                if not content:
                    logger.debug("Store file is empty")
                    return default
                    
                data = json.loads(content)
                value = data.get(key, default)
                logger.debug(f"Retrieved value for key '{key}': {'***' if 'token' in key.lower() else value}")
                return value
                
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Error reading from store file: {e}")
            return default

    def get_token(self) -> Optional[str]:
        """
        Get the Weni authentication token from the store.
        
        Returns:
            Optional[str]: The authentication token, or None if not found
        """
        return self.get(STORE_TOKEN_KEY)

    def get_project_uuid(self) -> Optional[str]:
        """
        Get the Weni project UUID from the store.
        
        Returns:
            Optional[str]: The project UUID, or None if not found
        """
        return self.get(STORE_PROJECT_UUID_KEY)
