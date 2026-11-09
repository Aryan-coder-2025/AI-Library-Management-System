"""
API router for Stage 10.6 AI Knowledge, Intelligence & Comparison Subsystems.
Provides endpoints for:
- PILLAR 1: Knowledge representation (Subject-Topic-Concept hierarchy, seed populate)
- PILLAR 2: Search-based conceptual navigation
- PILLAR 3 & 5: Enhanced Tool-Calling Librarian Agent & RAG
- PILLAR 4: Modern AI Comparison
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db, get_write_db
from app.dependencies import get_current_active_user, require_role
from app.models import User
from app.schemas import (
    AgentChatRequest,
    EnhancedCopilotResponse,
    KnowledgeSearchResponse,
    ModelComparisonRequest,
    ModelComparisonResponse,
    SubjectDetailResponse,
    SubjectTreeResponse,
)
from app.seed_data.knowledge_seed import seed_knowledge_representation
from app.services.ai_comparison import compare_models_service
from app.services.copilot_agent import execute_librarian_agent_rag
from app.services.knowledge import (
    get_subject_detail_service,
    get_subject_hierarchy_service,
    search_knowledge_service,
)

router = APIRouter(prefix="/api/knowledge", tags=["AI Knowledge & Intelligence Subsystem"])


# ── PILLAR 1: Knowledge Representation ────────────────────────────────────────

@router.get("/subjects/tree", response_model=List[SubjectTreeResponse])
def get_subject_tree(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Retrieves full subject, topic, and concept hierarchical tree."""
    return get_subject_hierarchy_service(db=db)


@router.get("/subjects/{subject_id}", response_model=SubjectDetailResponse)
def get_subject_detail(
    subject_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Retrieves a single subject with its topics, concepts, and linked books."""
    detail = get_subject_detail_service(db=db, subject_id=subject_id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject ID {subject_id} not found.",
        )
    return detail


@router.post("/seed", status_code=status.HTTP_201_CREATED)
def seed_knowledge(
    db: Session = Depends(get_write_db),
    current_user: User = Depends(require_role("librarian", "admin")),
):
    """Populates curated academic subjects, topics, concepts, and book links."""
    return seed_knowledge_representation(db=db)


# ── PILLAR 2: Search-Based Navigation ─────────────────────────────────────────

@router.get("/search", response_model=KnowledgeSearchResponse)
def search_knowledge(
    q: str = Query(..., min_length=1, description="Knowledge exploration query"),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Searches subjects, topics, concepts, and contextual academic pathways."""
    return search_knowledge_service(db=db, query=q, limit=limit)


# ── PILLAR 3 & 5: Enhanced Agentic Copilot & RAG ──────────────────────────────

@router.post("/agent/chat", response_model=EnhancedCopilotResponse)
def agent_chat(
    payload: AgentChatRequest,
    db: Session = Depends(get_write_db),
    current_user: User = Depends(get_current_active_user),
    x_gemini_api_key: Optional[str] = Header(None, alias="X-Gemini-API-Key"),
):
    """
    Intelligent Librarian Agent endpoint.
    Executes tool-calling, multi-step RAG context ranking, spatial guidance, and grounded recommendations.
    Accepts bounded multi-turn conversation history for coreference resolution and conversational context.
    Supports Bring-Your-Own-Key (BYOK) for student and teacher Gemini API keys.
    """
    custom_key = payload.custom_api_key or x_gemini_api_key
    return execute_librarian_agent_rag(
        db=db,
        query=payload.message,
        current_user=current_user,
        conversation_history=payload.conversation_history,
        custom_api_key=custom_key,
    )


# ── PILLAR 4: Modern AI Comparison ────────────────────────────────────────────

@router.post("/comparison/evaluate", response_model=ModelComparisonResponse)
async def evaluate_models(
    request: ModelComparisonRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role("librarian", "admin")),
):
    """
    Side-by-side prompt execution and factual grounding comparison across models.
    Measures latency, token usage, and grounding overlap with library knowledge.
    """
    context = None
    if request.include_rag_context:
        # Pre-retrieve top relevant catalog knowledge for factual grounding
        knowledge_res = search_knowledge_service(db=db, query=request.prompt, limit=3)
        context = " ".join([f"{k.title}: {k.description}" for k in knowledge_res.results])

    return await compare_models_service(req=request, context=context)

