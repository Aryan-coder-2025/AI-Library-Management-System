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

    if provider in ["openai", "openai_compatible"]:
        try:
            url = "https://api.openai.com/v1/models"
            headers = {"Authorization": f"Bearer {key}"}
            res = httpx.get(url, headers=headers, timeout=8.0)
            if res.status_code == 200:
                return VerifyKeyResponse(valid=True, provider="openai", message="OpenAI API Key verified and active.")
            else:
                return VerifyKeyResponse(valid=False, provider="openai", message=f"OpenAI rejected key: HTTP {res.status_code}")
        except Exception as e:
            return VerifyKeyResponse(valid=False, provider="openai", message=f"Key test failed: {str(e)}")

    return VerifyKeyResponse(valid=False, provider=provider, message=f"Unsupported provider: {provider}")


@router.post("/chat", response_model=CopilotChatResponse, status_code=status.HTTP_200_OK)
def copilot_chat(
    request: CopilotChatRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    x_gemini_api_key: Optional[str] = Header(None, alias="X-Gemini-API-Key"),
) -> CopilotChatResponse:
    """
    Conversational Copilot query endpoint.
    - Grounded in live database facts (user's personal loans, book copy availability).
    - Uses verified library policy knowledge base.
    - Multi-tenant loan isolation: students can only access their own loan records.
    - Configurable LLM provider with graceful deterministic fallback.
    - Anti-prompt-injection boundary protections.
    - Supports Bring-Your-Own-Key (BYOK) for patrons via header or payload.
    """
    custom_key = request.custom_api_key or x_gemini_api_key
    return copilot_service.process_copilot_chat(
        db=db,
        user=current_user,
        request=request,
        custom_api_key=custom_key,
    )

