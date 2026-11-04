"""
API routes for AI Library Copilot.
Handles authenticated conversational interactions with live catalogue grounding.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models import User
from app.schemas import CopilotChatRequest, CopilotChatResponse
from app.services import copilot as copilot_service

router = APIRouter(prefix="/api/copilot", tags=["AI Copilot"])


@router.post("/chat", response_model=CopilotChatResponse, status_code=status.HTTP_200_OK)
def copilot_chat(
    request: CopilotChatRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> CopilotChatResponse:
    """
    Conversational Copilot query endpoint.
    - Grounded in live database facts (user's personal loans, book copy availability).
    - Uses verified library policy knowledge base.
    - Multi-tenant loan isolation: students can only access their own loan records.
    - Configurable LLM provider with graceful deterministic fallback.
    - Anti-prompt-injection boundary protections.
    """
    return copilot_service.process_copilot_chat(
        db=db,
        user=current_user,
        request=request,
    )

