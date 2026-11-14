"""
Tests for Multi-Provider AI Gateway & Intelligent Model Routing.
Validates Groq, OpenAI, Anthropic, Gemini, and Local Fallback provider routing.
"""
import pytest
from app.services.copilot import (
    get_llm_provider,
    GroqProvider,
    AnthropicProvider,
    OpenAICompatibleProvider,
    GeminiProvider,
    DeterministicFallbackProvider,
)
from app.routers.copilot import verify_custom_key
from app.schemas import VerifyKeyRequest
from app.models import User


def test_gateway_routing_priority():
    # 1. Groq takes top priority when supplied (fastest text/tools)
    provider, name = get_llm_provider(keys_vault={"groq": "gsk_test123", "gemini": "AIzaSyTest"})
    assert name == "groq"
    assert isinstance(provider, GroqProvider)

    # 2. OpenAI takes precedence when Groq is absent
    provider, name = get_llm_provider(keys_vault={"openai": "sk-test123", "gemini": "AIzaSyTest"})
    assert name == "openai"
    assert isinstance(provider, OpenAICompatibleProvider)

    # 3. Anthropic takes precedence when Groq & OpenAI are absent
    provider, name = get_llm_provider(keys_vault={"anthropic": "sk-ant-test123", "gemini": "AIzaSyTest"})
    assert name == "anthropic"
    assert isinstance(provider, AnthropicProvider)

    # 4. Gemini is used when only Gemini is supplied
    provider, name = get_llm_provider(keys_vault={"gemini": "AIzaSyTest"})
    assert name == "gemini"
    assert isinstance(provider, GeminiProvider)

    # 5. Empty vault falls back to configured env or deterministic RAG
    provider, name = get_llm_provider(keys_vault={}, custom_api_key="")
    assert name in ["gemini", "fallback"]


def test_verify_key_unsupported_provider():
    test_user = User(id=1, email="test@uni.edu", full_name="Tester", role="student", is_active=True)
    req = VerifyKeyRequest(api_key="random-key-12345", provider="cohere")
    res = verify_custom_key(request=req, current_user=test_user)
    assert res.valid is False
    assert "Unsupported provider" in res.message
