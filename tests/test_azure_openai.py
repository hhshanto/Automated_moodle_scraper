"""
test_azure_openai.py

Tests the Azure OpenAI endpoint by sending a simple completion request.
Verifies that the credentials, endpoint, and deployment name in .env are valid
and that the API responds correctly.

Run with:
    python tests/test_azure_openai.py
"""

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import AzureOpenAI

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
)


def load_azure_openai_config() -> dict:
    """
    Loads Azure OpenAI configuration values from the .env file.

    Returns:
        A dict with keys: api_key, endpoint, deployment, api_version.

    Raises:
        SystemExit: If any required variable is missing.
    """
    env_path = Path(__file__).parent.parent / ".env"
    load_dotenv(dotenv_path=env_path)

    required_keys = [
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_DEPLOYMENT",
        "AZURE_OPENAI_API_VERSION",
    ]

    missing_keys = [key for key in required_keys if not os.getenv(key)]
    if missing_keys:
        logging.error("Missing required environment variables: %s", missing_keys)
        sys.exit(1)

    return {
        "api_key": os.environ["AZURE_OPENAI_API_KEY"],
        "endpoint": os.environ["AZURE_OPENAI_ENDPOINT"],
        "deployment": os.environ["AZURE_OPENAI_DEPLOYMENT"],
        "api_version": os.environ["AZURE_OPENAI_API_VERSION"],
    }


def build_azure_openai_client(config: dict) -> AzureOpenAI:
    """
    Creates and returns an authenticated AzureOpenAI client.

    Args:
        config: Dict containing api_key, endpoint, and api_version.

    Returns:
        An AzureOpenAI client instance ready to make requests.
    """
    return AzureOpenAI(
        api_key=config["api_key"],
        azure_endpoint=config["endpoint"],
        api_version=config["api_version"],
    )


def send_test_message(client: AzureOpenAI, deployment_name: str) -> str:
    """
    Sends a simple test message to the Azure OpenAI deployment.

    Args:
        client: An authenticated AzureOpenAI client.
        deployment_name: The name of the deployment to target.

    Returns:
        The text content of the model's response.

    Raises:
        Exception: If the API call fails.
    """
    response = client.chat.completions.create(
        model=deployment_name,
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant. Respond briefly.",
            },
            {
                "role": "user",
                "content": (
                    "Reply with exactly this sentence and nothing else: "
                    "Azure OpenAI connection is working correctly."
                ),
            },
        ],
        max_tokens=3000,
        temperature=0,
    )
    return response.choices[0].message.content.strip()


def run_endpoint_test() -> None:
    """
    Runs the full Azure OpenAI endpoint test and logs the result.

    Loads config, builds the client, sends a test message, and logs
    whether the endpoint responded as expected.
    """
    logging.info("Loading Azure OpenAI config from .env ...")
    config = load_azure_openai_config()

    logging.info("Endpoint  : %s", config["endpoint"])
    logging.info("Deployment: %s", config["deployment"])
    logging.info("API version: %s", config["api_version"])

    logging.info("Building Azure OpenAI client ...")
    client = build_azure_openai_client(config)

    logging.info("Sending test message to deployment '%s' ...", config["deployment"])
    try:
        response_text = send_test_message(client, config["deployment"])
    except Exception as error:
        logging.error("Azure OpenAI request failed: %s", error)
        sys.exit(1)

    logging.info("Response received: %s", response_text)

    expected_phrase = "Azure OpenAI connection is working correctly"
    if expected_phrase in response_text:
        logging.info("Test PASSED -- endpoint is reachable and responding correctly.")
    else:
        logging.warning(
            "Test WARNING -- endpoint responded but content was unexpected. "
            "Expected phrase: '%s'",
            expected_phrase,
        )


if __name__ == "__main__":
    run_endpoint_test()
