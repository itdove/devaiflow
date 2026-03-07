"""SSL verification helper for HTTP requests.

This module provides utilities to get SSL verification settings from config
or environment variables for use with requests library.
"""

import os
from typing import Union


def get_ssl_verify_setting() -> Union[bool, str]:
    """Get SSL verification setting from config or environment variable.

    Priority order:
    1. Environment variable DAF_SSL_VERIFY
    2. Configuration (http_client.ssl_verify)
    3. Default: True (secure by default)

    Returns:
        - True: Verify using system certificates (default, secure)
        - False: Disable SSL verification (INSECURE - for development/testing only)
        - str: Path to CA bundle file (for custom internal CAs)

    Environment variable format:
        - DAF_SSL_VERIFY=true or DAF_SSL_VERIFY=1 → True
        - DAF_SSL_VERIFY=false or DAF_SSL_VERIFY=0 → False
        - DAF_SSL_VERIFY=/path/to/ca-bundle.crt → Path to CA bundle
    """
    # Check environment variable first (highest priority)
    ssl_verify_env = os.getenv('DAF_SSL_VERIFY')
    if ssl_verify_env is not None:
        # Parse environment variable
        ssl_verify_lower = ssl_verify_env.lower()
        if ssl_verify_lower in ('true', '1', 'yes'):
            return True
        elif ssl_verify_lower in ('false', '0', 'no'):
            return False
        else:
            # Treat as path to CA bundle
            return ssl_verify_env

    # Try to load from config
    try:
        from devflow.config.loader import ConfigLoader
        config_loader = ConfigLoader()
        config = config_loader.load_config()

        # Check if http_client config exists
        if hasattr(config, 'http_client') and config.http_client:
            return config.http_client.ssl_verify

    except Exception:
        # If config loading fails, fall through to default
        pass

    # Default to secure behavior (verify SSL)
    return True


def get_request_timeout() -> int:
    """Get request timeout setting from config or environment variable.

    Priority order:
    1. Environment variable DAF_REQUEST_TIMEOUT
    2. Configuration (http_client.timeout)
    3. Default: 10 seconds

    Returns:
        Timeout in seconds
    """
    # Check environment variable first
    timeout_env = os.getenv('DAF_REQUEST_TIMEOUT')
    if timeout_env is not None:
        try:
            return int(timeout_env)
        except ValueError:
            pass  # Fall through to config or default

    # Try to load from config
    try:
        from devflow.config.loader import ConfigLoader
        config_loader = ConfigLoader()
        config = config_loader.load_config()

        # Check if http_client config exists
        if hasattr(config, 'http_client') and config.http_client:
            return config.http_client.timeout

    except Exception:
        # If config loading fails, fall through to default
        pass

    # Default timeout
    return 10
