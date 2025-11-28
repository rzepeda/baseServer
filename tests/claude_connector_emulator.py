
import httpx
import logging
import json
from dotenv import dotenv_values
from urllib.parse import urlparse, urlunparse

def setup_logger():
    """Sets up a logger for diagnostic output."""
    logger = logging.getLogger("claude_emulator_logger")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        stream_handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    return logger

def run_emulator():
    """
    Emulates the Claude-side OAuth flow to diagnose configuration and server access,
    following the correct MCP authentication discovery specification.
    """
    logger = setup_logger()
    logger.info("--- Starting Claude OAuth Emulator (MCP-compliant) ---")
    
    # 1. Load Configuration - Note: OAUTH_PROVIDER_URL is NOT used by the emulator anymore.
    logger.info("Loading client configuration directly from .env file...")
    config = dotenv_values(".env")
    
    client_id = config.get("OAUTH_CLIENT_ID")
    client_secret = config.get("OAUTH_CLIENT_SECRET")
    mcp_full_url = config.get("CLOUDFLARE_TUNNEL_URL")

    required_vars = {
        "OAUTH_CLIENT_ID": client_id,
        "OAUTH_CLIENT_SECRET": client_secret,
        "CLOUDFLARE_TUNNEL_URL": mcp_full_url,
    }

    missing_vars = [key for key, value in required_vars.items() if not value]
    if missing_vars:
        logger.error(f"Error: Missing required variables in .env file: {', '.join(missing_vars)}")
        logger.info("--- Emulator Finished with Errors ---")
        return

    parsed_url = urlparse(mcp_full_url)
    base_server_url = urlunparse((parsed_url.scheme, parsed_url.netloc, '', '', '', ''))

    logger.info("--- Configuration Values Used by Emulator ---")
    logger.info(f"Base Server URL (from CLOUDFLARE_TUNNEL_URL): {base_server_url}")
    logger.info(f"OAuth Client ID: {client_id}")
    logger.info("---------------------------------------------")

    # 2. Pre-check: Verify server is running
    health_check_url = f"{base_server_url}/health"
    logger.info(f"Performing pre-check: Pinging server health endpoint at {health_check_url}")
    try:
        with httpx.Client() as health_client:
            response = health_client.get(health_check_url)
            response.raise_for_status()
        logger.info("Server is running and responsive.")
    except httpx.RequestError as e:
        logger.error(f"Fatal: Server is not responding at {base_server_url}.")
        logger.error(f"Error details: {e}")
        logger.info("--- Emulator Finished with Errors ---")
        return

    # 3. MCP Auth Discovery & Token Endpoint extraction in one step
    token_endpoint = None
    try:
        with httpx.Client() as client:
            discovery_endpoint = f"{base_server_url}/.well-known/oauth-authorization-server"
            logger.info(f"MCP Auth Discovery: Attempting to GET {discovery_endpoint}")
            
            response = client.get(discovery_endpoint)
            response.raise_for_status()
            
            metadata = response.json()
            logger.info("Full discovery document received: %s", metadata)
            token_endpoint = metadata.get("token_endpoint")
            authorization_endpoint = metadata.get("authorization_endpoint")

            if not token_endpoint:
                logger.error("Fatal: Server metadata at %s is missing the 'token_endpoint' field.", discovery_endpoint)
                logger.info("--- Emulator Finished with Errors ---")
                return

            if not authorization_endpoint:
                logger.warning("Warning: Server metadata is missing 'authorization_endpoint' - required for authorization_code flow (Claude.ai)")
            else:
                logger.info("MCP Auth Discovery: authorization_endpoint found: %s", authorization_endpoint)

            logger.info("MCP Auth Discovery: Successfully discovered token_endpoint: %s", token_endpoint)

    except httpx.HTTPStatusError as e:
        logger.error(f"Fatal: An HTTP error occurred during MCP auth discovery: {e}")
        logger.info("--- Emulator Finished with Errors ---")
        return
    except Exception as e:
        logger.error(f"Fatal: An unexpected error occurred during MCP auth discovery: {e}")
        logger.info("--- Emulator Finished with Errors ---")
        return

    # 4. Obtain Access Token
    access_token = None
    try:
        with httpx.Client() as client:
            logger.info("Requesting access token using client credentials...")
            token_payload = {
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            }
            token_response = client.post(token_endpoint, data=token_payload)
            token_response.raise_for_status()
            access_token = token_response.json().get("access_token")

            if not access_token:
                logger.error("Fatal: 'access_token' not found in the response from the token endpoint.")
                logger.info("--- Emulator Finished with Errors ---")
                return
            
            logger.info("Successfully obtained access token.")

    except Exception as e:
        logger.error(f"An unexpected error occurred during token acquisition: {e}")
        logger.info("--- Emulator Finished with Errors ---")
        return

    # 5. Access Protected MCP Server Endpoint
    if access_token:
        protected_endpoint = f"{base_server_url}/tools/list"
        logger.info(f"Attempting to access protected endpoint: {protected_endpoint}")
        # ... (rest of the logic remains the same)
        try:
            with httpx.Client() as server_client:
                headers = {"Authorization": f"Bearer {access_token}"}
                response = server_client.get(protected_endpoint, headers=headers)

                if response.status_code == 200:
                    logger.info("SUCCESS: Successfully accessed the protected endpoint.")
                    logger.info(f"Server response JSON: {response.json()}")
                else:
                    logger.error("FAILURE: Failed to access the protected endpoint.")
                    logger.error(f"Server responded with status code: {response.status_code}")
                    logger.error(f"Server response body: {response.text}")

        except httpx.RequestError as e:
            logger.error(f"FAILURE: An HTTP error occurred while contacting the server at {base_server_url}.")
            logger.error(f"Error: {e}")

    logger.info("--- Claude OAuth Emulator Finished ---")

if __name__ == "__main__":
    run_emulator()
