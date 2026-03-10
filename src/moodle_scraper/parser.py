"""
parser.py

All Azure OpenAI interactions live here. No other module calls the Azure OpenAI
client directly -- everything goes through this single wrapper.

Provides one function: call_azure_openai, which sends messages (with optional
tool definitions) and returns the model response. The agent loop in agent.py
uses this to decide which tool to call next.

Token usage is logged at INFO level after every call and accumulated in the
module-level TOKEN_USAGE counter so callers can inspect the running total.
"""

import logging
import os

from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

logger = logging.getLogger(__name__)

_azure_client: AzureOpenAI | None = None

# Running totals across all calls in the current session.
TOKEN_USAGE = {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0,
}


def _get_client() -> AzureOpenAI:
    """
    Return the module-level AzureOpenAI client, creating it on first call.

    Returns:
        A ready-to-use AzureOpenAI client instance.
    """
    global _azure_client
    if _azure_client is None:
        _azure_client = AzureOpenAI(
            api_key=os.environ["AZURE_OPENAI_API_KEY"],
            azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
            api_version=os.environ["AZURE_OPENAI_API_VERSION"],
        )
    return _azure_client


def _get_deployment_name() -> str:
    """
    Return the Azure OpenAI deployment name from environment variables.

    Returns:
        The deployment name string.
    """
    return os.environ["AZURE_OPENAI_DEPLOYMENT"]


def call_azure_openai(messages: list, tools: list | None = None) -> object:
    """
    Send a chat completion request to Azure OpenAI and return the response.

    This is the single entry point for all LLM calls in the project.

    Args:
        messages: The conversation history as a list of message dicts.
        tools:    Optional list of tool definitions for function calling.

    Returns:
        The full ChatCompletion response object from the Azure OpenAI SDK.
    """
    client = _get_client()
    deployment = _get_deployment_name()

    request_kwargs = {
        "model": deployment,
        "messages": messages,
        "temperature": 0,
    }

    if tools:
        request_kwargs["tools"] = tools

    try:
        response = client.chat.completions.create(**request_kwargs)

        if response.usage:
            TOKEN_USAGE["prompt_tokens"] += response.usage.prompt_tokens
            TOKEN_USAGE["completion_tokens"] += response.usage.completion_tokens
            TOKEN_USAGE["total_tokens"] += response.usage.total_tokens
            logger.info(
                "Token usage -- this call: prompt=%d completion=%d total=%d | "
                "session totals: prompt=%d completion=%d total=%d",
                response.usage.prompt_tokens,
                response.usage.completion_tokens,
                response.usage.total_tokens,
                TOKEN_USAGE["prompt_tokens"],
                TOKEN_USAGE["completion_tokens"],
                TOKEN_USAGE["total_tokens"],
            )

        return response
    except Exception as error:
        logger.error("Azure OpenAI request failed: %s", error)
        raise
