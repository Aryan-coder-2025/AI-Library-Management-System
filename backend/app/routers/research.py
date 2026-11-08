"""
Academic Research Discovery Router.
Serves external scholarly research querying across OpenAlex, arXiv, and Crossref.
"""
from typing import List, Optional
from fastapi import APIRouter, Query, status

from app.schemas import AcademicSearchResponse
from app.services.research.aggregator import academic_research_service

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

