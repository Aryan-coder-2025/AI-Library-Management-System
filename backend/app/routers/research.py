"""
Academic Research Discovery Router.
Serves external scholarly research querying across OpenAlex, arXiv, and Crossref.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_active_user
from app.models import User
from app.schemas import AcademicSearchResponse, VisionResearchResponse
from app.services.research.aggregator import academic_research_service
from app.services.vision_research import analyze_academic_image_service

router = APIRouter(prefix="/api/research", tags=["Academic Research Discovery"])


@router.get("/search", response_model=AcademicSearchResponse, summary="Search external scholarly papers")
def search_academic_research(
    q: str = Query(..., min_length=1, max_length=500, description="Scholarly search terms, title, topic or author"),
    limit: int = Query(15, ge=1, le=50, description="Maximum results to return"),
    page: int = Query(1, ge=1, description="Pagination page index"),
    providers: Optional[str] = Query(None, description="Comma-separated providers (e.g. 'openalex,arxiv,crossref')"),
    year: Optional[int] = Query(None, ge=1800, le=2100, description="Filter by publication year"),
    is_oa: Optional[bool] = Query(None, description="Filter by Open Access availability"),
):
    """
    Queries open academic research sources (OpenAlex, arXiv, Crossref).
    Aggregates and deduplicates results into a unified schema with provider provenance.
    """
    provider_list: Optional[List[str]] = None
    if providers:
        provider_list = [p.strip().lower() for p in providers.split(",") if p.strip()]

    return academic_research_service.search_papers(
        query=q,
        limit=limit,
        page=page,
        providers=provider_list,
        year=year,
        is_oa=is_oa,
    )


@router.get("/providers", summary="List academic research discovery providers")
def list_research_providers():
    """Returns available scholarly providers, API attribution, and capabilities."""
    return {
        "providers": [
            {
                "id": "openalex",
                "name": "OpenAlex",
                "description": "Comprehensive scholarly metadata catalog covering 250M+ global publications.",
                "url": "https://openalex.org",
                "features": ["doi", "citations", "open_access_status", "abstracts"],
            },
            {
                "id": "arxiv",
                "name": "arXiv",
                "description": "Open-access preprints repository curated by Cornell University across physics, mathematics, and CS.",
                "url": "https://arxiv.org",
                "features": ["preprints", "abstracts", "open_access", "arxiv_id"],
            },
            {
                "id": "crossref",
                "name": "Crossref",
                "description": "Official global DOI registration agency metadata for peer-reviewed academic publishers.",
                "url": "https://crossref.org",
                "features": ["doi", "citations", "venues", "peer_reviewed"],
            },
        ]
    }


@router.post(
    "/vision-search",
    response_model=VisionResearchResponse,
    summary="Multimodal Vision Research & Discovery",
)
async def vision_research_search(
    file: UploadFile = File(...),
    query: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Analyzes an academic image (diagram, equation, textbook snippet, paper abstract)
    using Gemini Multimodal Vision, then retrieves matching library monographs
    and arXiv/OpenAlex research papers.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must be a valid image (PNG, JPEG, WEBP).",
        )

    image_bytes = await file.read()
    if len(image_bytes) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image size exceeds 10MB limit.",
        )

    return analyze_academic_image_service(
        db=db,
        image_bytes=image_bytes,
        mime_type=file.content_type,
        user_prompt=query,
    )

