
import os
import httpx
import logging
import json
from dotenv import load_dotenv

def setup_logger():
    """Sets up the logger to output to both console and a file."""
    logger = logging.getLogger("diagnostic_logger")
    logger.setLevel(logging.INFO)

    # Prevent duplicate handlers if the function is called multiple times
    if logger.hasHandlers():
        logger.handlers.clear()

    # File handler
    file_handler = logging.FileHandler("tests/diagnostics/logs/diagnostics.log", mode='a')
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Console handler
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_formatter = logging.Formatter('%(message)s')
    stream_handler.setFormatter(stream_formatter)
    logger.addHandler(stream_handler)

    return logger

def check_client():
    """
    Checks if the OAuth client configuration is working.
    """
    logger = setup_logger()
    load_dotenv()

    client_id = os.getenv("OAUTH_CLIENT_ID")
    client_secret = os.getenv("OAUTH_CLIENT_SECRET")
    validation_endpoint = os.getenv("OAUTH_VALIDATION_ENDPOINT")
    provider_url = os.getenv("OAUTH_PROVIDER_URL")

    if not all([client_id, client_secret, validation_endpoint, provider_url]):
        logger.error("Error: Missing one or more required OAuth variables in .env file.")
        logger.error("Required variables: OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET, OAUTH_VALIDATION_ENDPOINT, OAUTH_PROVIDER_URL")
        return

    logger.info("--- Starting OAuth Client Check ---")

    try:
        # 1. Get endpoints from discovery document
        discovery_url = f"{provider_url}/.well-known/openid-configuration"
        logger.info(f"Fetching discovery document from: {discovery_url}")
        with httpx.Client() as client:
            discovery_response = client.get(discovery_url)
            discovery_response.raise_for_status()
            discovery_data = discovery_response.json()
            token_endpoint = discovery_data.get("token_endpoint")
            introspection_endpoint = discovery_data.get("introspection_endpoint")
            userinfo_endpoint = discovery_data.get("userinfo_endpoint")

            if not token_endpoint:
                logger.error("Error: 'token_endpoint' not found in discovery document.")
                return
            logger.info(f"Token endpoint found: {token_endpoint}")

            validation_endpoint = introspection_endpoint or userinfo_endpoint
            if not validation_endpoint:
                logger.error("Error: No 'introspection_endpoint' or 'userinfo_endpoint' found in discovery document.")
                return
            logger.info(f"Using validation endpoint: {validation_endpoint}")

            # 2. Request an access token
            logger.info("Requesting access token using client credentials...")
            token_payload = {
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            }
            token_response = client.post(token_endpoint, data=token_payload)
            token_response.raise_for_status()
            token_data = token_response.json()
            access_token = token_data.get("access_token")
            if not access_token:
                logger.error("Error: 'access_token' not found in token response.")
                logger.error(f"Response: {token_data}")
                return
            logger.info("Access token received.")

            # 3. Validate the token
            logger.info(f"Validating access token at: {validation_endpoint}")
            
            validation_response = None
            if validation_endpoint == introspection_endpoint:
                # Introspection endpoint usually requires a POST with the token
                validation_payload = {"token": access_token}
                headers = {"Content-Type": "application/x-www-form-urlencoded"}
                auth = (client_id, client_secret)
                validation_response = client.post(validation_endpoint, data=validation_payload, headers=headers, auth=auth)
            else: # userinfo_endpoint
                headers = {"Authorization": f"Bearer {access_token}"}
                validation_response = client.get(validation_endpoint, headers=headers)

            if validation_response.status_code == 200:
                logger.info("Token validation successful.")
                logger.info(f"Validation response: {validation_response.json()}")
            else:
                logger.error(f"Token validation failed with status code: {validation_response.status_code}")
                logger.error(f"Validation response: {validation_response.text}")


    except httpx.RequestError as e:
        logger.error(f"An HTTP error occurred: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}")

    logger.info("--- OAuth Client Check Finished ---")


if __name__ == "__main__":
    check_client()
