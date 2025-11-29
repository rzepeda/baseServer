import json
import logging
import os

import httpx
from dotenv import load_dotenv


def setup_logger():
    """Sets up the logger to output to both console and a file."""
    logger = logging.getLogger("diagnostic_logger")
    logger.setLevel(logging.INFO)

    # Prevent duplicate handlers if the function is called multiple times
    if logger.hasHandlers():
        logger.handlers.clear()

    # File handler
    file_handler = logging.FileHandler("tests/diagnostics/logs/diagnostics.log")
    file_handler.setLevel(logging.INFO)
    file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # Console handler
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_formatter = logging.Formatter("%(message)s")
    stream_handler.setFormatter(stream_formatter)
    logger.addHandler(stream_handler)

    return logger


def check_issuer():
    """
    Checks if the OAuth issuer is working by fetching the OpenID Connect discovery document.
    """
    logger = setup_logger()
    load_dotenv()

    issuer_url = os.getenv("OAUTH_PROVIDER_URL")
    if not issuer_url:
        logger.error("Error: OAUTH_PROVIDER_URL not found in .env file.")
        return

    discovery_url = f"{issuer_url}/.well-known/openid-configuration"
    logger.info(f"Attempting to fetch OpenID Connect discovery document from: {discovery_url}")

    try:
        with httpx.Client() as client:
            response = client.get(discovery_url)
            response.raise_for_status()  # Raise an exception for bad status codes

            logger.info("Successfully fetched discovery document.")
            try:
                discovery_data = response.json()
                logger.info("Successfully parsed discovery document as JSON.")
                logger.info("Issuer configuration appears to be correct.")
                logger.info("\nDiscovery Document:")
                logger.info(json.dumps(discovery_data, indent=2))

            except ValueError:
                logger.error("Error: Could not parse response as JSON.")
                logger.error("Response text:")
                logger.error(response.text)

    except httpx.RequestError as e:
        logger.error(f"Error fetching discovery document: {e}")


if __name__ == "__main__":
    check_issuer()
