"""
Scholarly Research Aggregator Service.
Coordinates OpenAlex, arXiv, and Crossref adapters.
Features:
- Multi-provider parallel/sequential dispatch with timeout isolation.
- Cross-provider DOI and title deduplication.
- Safe in-memory caching to avoid abusive outbound polling.
- Provider status tracking: distinguishes operational vs degraded sources.
"""
from datetime import datetime, timedelta
import logging
import re
from typing import Dict, List, Optional, Set, Tuple

from app.schemas import AcademicPaperResult, AcademicSearchResponse
from app.services.research.arxiv import arxiv_adapter
from app.services.research.crossref import crossref_adapter
from app.services.research.openalex import openalex_adapter

logger = logging.getLogger("athenaeum.research.aggregator")

# In-memory query cache: key -> (timestamp, AcademicSearchResponse)
_RESEARCH_CACHE: Dict[str, Tuple[datetime, AcademicSearchResponse]] = {}
CACHE_TTL = timedelta(minutes=5)


def normalize_title_key(title: str) -> str:
    """Creates a normalized string key for cross-provider title deduplication."""
    return re.sub(r"[^a-z0-9]", "", title.lower())


class AcademicResearchService:
    """Aggregates and deduplicates scholarly papers across OpenAlex, arXiv, and Crossref."""

    def __init__(self):
        self.providers = {
            "openalex": openalex_adapter,
            "arxiv": arxiv_adapter,
            "crossref": crossref_adapter,
        }

    def search_papers(
        self,
        query: str,
        limit: int = 15,
        page: int = 1,
        providers: Optional[List[str]] = None,
        year: Optional[int] = None,
        is_oa: Optional[bool] = None,
        use_cache: bool = True,
    ) -> AcademicSearchResponse:
        """
        Executes search across requested providers and returns unified, deduplicated results.
        If a provider fails or times out, its absence is tracked in active_providers.
        """
        clean_query = query.strip()
        if not clean_query:
            return AcademicSearchResponse(
                query="",
                total_results=0,
                page=page,
                page_size=limit,
                providers_queried=[],
                active_providers=[],
                results=[],
            )

        target_providers = [p.lower() for p in providers] if providers else ["openalex", "arxiv", "crossref"]
        valid_providers = [p for p in target_providers if p in self.providers]

        cache_key = f"{clean_query.lower()}|{limit}|{page}|{','.join(sorted(valid_providers))}|{year}|{is_oa}"
        now = datetime.utcnow()

        if use_cache and cache_key in _RESEARCH_CACHE:
            cached_time, cached_res = _RESEARCH_CACHE[cache_key]
            if now - cached_time < CACHE_TTL:
                return cached_res

        active_providers: List[str] = []
        raw_results: List[AcademicPaperResult] = []

        per_provider_limit = max(5, limit // len(valid_providers) + 2) if valid_providers else limit

        # Query OpenAlex
        if "openalex" in valid_providers:
            try:
                oa_papers = self.providers["openalex"].search(
                    query=clean_query,
                    limit=per_provider_limit,
                    page=page,
                    year=year,
                    is_oa=is_oa,
                )
                raw_results.extend(oa_papers)
                active_providers.append("openalex")
            except Exception as exc:
                logger.warning("OpenAlex provider execution failed: %s", type(exc).__name__)

        # Query arXiv
        if "arxiv" in valid_providers:
            try:
                arxiv_papers = self.providers["arxiv"].search(
                    query=clean_query,
                    limit=per_provider_limit,
                    page=page,
                )
                # Apply local open access & year filter if requested
                if year is not None:
                    arxiv_papers = [p for p in arxiv_papers if p.publication_year == year]
                raw_results.extend(arxiv_papers)
                active_providers.append("arxiv")
            except Exception as exc:
                logger.warning("arXiv provider execution failed: %s", type(exc).__name__)

        # Query Crossref
        if "crossref" in valid_providers:
            try:
                crossref_papers = self.providers["crossref"].search(
                    query=clean_query,
                    limit=per_provider_limit,
                    page=page,
                )
                if year is not None:
                    crossref_papers = [p for p in crossref_papers if p.publication_year == year]
                if is_oa is True:
                    crossref_papers = [p for p in crossref_papers if p.open_access is True]
                raw_results.extend(crossref_papers)
                active_providers.append("crossref")
            except Exception as exc:
                logger.warning("Crossref provider execution failed: %s", type(exc).__name__)

        # Deduplicate results across providers
        seen_dois: Set[str] = set()
        seen_titles: Set[str] = set()
        deduped: List[AcademicPaperResult] = []

        for paper in raw_results:
            doi_norm = paper.doi.strip().lower() if paper.doi else None
            title_norm = normalize_title_key(paper.title)

            if doi_norm and doi_norm in seen_dois:
                continue
            if title_norm and len(title_norm) > 10 and title_norm in seen_titles:
                continue

            if doi_norm:
                seen_dois.add(doi_norm)
            if title_norm and len(title_norm) > 10:
                seen_titles.add(title_norm)

            deduped.append(paper)

        final_results = deduped[:limit]

        response = AcademicSearchResponse(
            query=clean_query,
            total_results=len(deduped),
            page=page,
            page_size=limit,
            providers_queried=valid_providers,
            active_providers=active_providers,
            results=final_results,
        )

        _RESEARCH_CACHE[cache_key] = (now, response)
        return response


academic_research_service = AcademicResearchService()

