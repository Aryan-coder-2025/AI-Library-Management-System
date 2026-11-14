"""
API routes for AI Library Copilot.
Handles authenticated conversational interactions with live catalogue grounding.
"""
from typing import Optional
import httpx
from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models import User
from app.schemas import CopilotChatRequest, CopilotChatResponse, VerifyKeyRequest, VerifyKeyResponse
from app.services import copilot as copilot_service

router = APIRouter(prefix="/api/copilot", tags=["AI Copilot"])


@router.post("/verify-key", response_model=VerifyKeyResponse, status_code=status.HTTP_200_OK)
def verify_custom_key(
    request: VerifyKeyRequest,
    current_user: User = Depends(get_current_active_user),
) -> VerifyKeyResponse:
    """
    Validates a student or teacher's custom API key (BYOK) against the provider.
    Returns whether the key is active and capable of generating responses.
    """
    key = request.api_key.strip()
    provider = request.provider.lower().strip()
    
    if provider == "gemini":
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
            payload = {
                "contents": [{"parts": [{"text": "Hello"}]}],
                "generationConfig": {"maxOutputTokens": 2},
            }
            res = httpx.post(url, json=payload, timeout=8.0)
            if res.status_code == 200:
                return VerifyKeyResponse(valid=True, provider="gemini", message="Gemini API Key verified and active.")
            else:
                err_data = res.json().get("error", {}) if res.headers.get("content-type", "").startswith("application/json") else {}
                err_msg = err_data.get("message") or f"HTTP {res.status_code}"
                return VerifyKeyResponse(valid=False, provider="gemini", message=f"Gemini API rejected key: {err_msg}")
        except Exception as e:
            return VerifyKeyResponse(valid=False, provider="gemini", message=f"Key test failed: {str(e)}")

    if provider == "groq":
        try:
            url = "https://api.groq.com/openai/v1/models"
            headers = {"Authorization": f"Bearer {key}"}
            res = httpx.get(url, headers=headers, timeout=8.0)
            if res.status_code == 200:
                return VerifyKeyResponse(valid=True, provider="groq", message="Groq LPU API Key verified and active (Llama 3.3 70B ready).")
            else:
                return VerifyKeyResponse(valid=False, provider="groq", message=f"Groq API rejected key: HTTP {res.status_code}")
        except Exception as e:
            return VerifyKeyResponse(valid=False, provider="groq", message=f"Groq test failed: {str(e)}")

    if provider in ["openai", "openai_compatible"]:
        try:
            url = "https://api.openai.com/v1/models"
            headers = {"Authorization": f"Bearer {key}"}
            res = httpx.get(url, headers=headers, timeout=8.0)
            if res.status_code == 200:
                return VerifyKeyResponse(valid=True, provider="openai", message="OpenAI API Key verified and active (GPT-4o ready).")
            else:
                return VerifyKeyResponse(valid=False, provider="openai", message=f"OpenAI rejected key: HTTP {res.status_code}")
        except Exception as e:
            return VerifyKeyResponse(valid=False, provider="openai", message=f"Key test failed: {str(e)}")

    if provider == "anthropic":
        try:
            url = "https://api.anthropic.com/v1/messages"
            headers = {
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            }
            payload = {
                "model": "claude-3-5-haiku-20241022",
                "max_tokens": 1,
                "messages": [{"role": "user", "content": "Hi"}],
            }
            res = httpx.post(url, headers=headers, json=payload, timeout=8.0)
            if res.status_code == 200:
                return VerifyKeyResponse(valid=True, provider="anthropic", message="Anthropic API Key verified and active (Claude 3.5 ready).")
            else:
                err_data = res.json().get("error", {}) if res.headers.get("content-type", "").startswith("application/json") else {}
                err_msg = err_data.get("message") or f"HTTP {res.status_code}"
                return VerifyKeyResponse(valid=False, provider="anthropic", message=f"Anthropic rejected key: {err_msg}")
        except Exception as e:
            return VerifyKeyResponse(valid=False, provider="anthropic", message=f"Anthropic test failed: {str(e)}")

    return VerifyKeyResponse(valid=False, provider=provider, message=f"Unsupported provider: {provider}")


@router.post("/chat", response_model=CopilotChatResponse, status_code=status.HTTP_200_OK)
def copilot_chat(
    request: CopilotChatRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    x_gemini_api_key: Optional[str] = Header(None, alias="X-Gemini-API-Key"),
    x_openai_api_key: Optional[str] = Header(None, alias="X-OpenAI-API-Key"),
    x_groq_api_key: Optional[str] = Header(None, alias="X-Groq-API-Key"),
    x_anthropic_api_key: Optional[str] = Header(None, alias="X-Anthropic-API-Key"),
) -> CopilotChatResponse:
    """
    Conversational Copilot query endpoint with Multi-Provider Intelligent Gateway Routing.
    - Grounded in live database facts (user's personal loans, book copy availability).
    - Uses verified library policy knowledge base.
    - Multi-tenant loan isolation: students can only access their own loan records.
    - Omnichannel Multi-Provider LLM Gateway: Groq, Gemini, OpenAI, Anthropic, or Fallback.
    - Anti-prompt-injection boundary protections.
    - Supports Bring-Your-Own-Key (BYOK) for patrons across all major AI providers.
    """
    keys_vault = {
        "gemini": (x_gemini_api_key or request.custom_api_key or "").strip(),
        "openai": (x_openai_api_key or "").strip(),
        "groq": (x_groq_api_key or "").strip(),
        "anthropic": (x_anthropic_api_key or "").strip(),
    }
    return copilot_service.process_copilot_chat(
        db=db,
        user=current_user,
        request=request,
        custom_api_key=keys_vault.get("gemini"),
        keys_vault=keys_vault,
    )

