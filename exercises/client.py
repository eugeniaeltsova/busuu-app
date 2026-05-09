"""
exercises/client.py

Azure OpenAI client for text generation
Kept as factory functions so config is always read fresh.
"""
from __future__ import annotations

from openai import AsyncAzureOpenAI
from config import settings


def get_client() -> AsyncAzureOpenAI:
    """Text client — GPT-4o for exercise generation and feedback."""
    return AsyncAzureOpenAI(
        api_key=settings.AZURE_OPENAI_API_KEY,
        azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
        api_version=settings.AZURE_OPENAI_API_VERSION,
    )



