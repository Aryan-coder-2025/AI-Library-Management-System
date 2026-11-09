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


def clean_scholarly_query(q: str) -> str:
    """
    Strips conversational chat filler (e.g. 'ok can you tell me about some famous research papers on ...')
    to prevent external title keyword engines (Crossref, arXiv, OpenAlex) from searching for
    literal words like 'can you tell me'.
    """
    cleaned = q.strip()
    cleaned = re.sub(r"[\?\.!]+$", "", cleaned).strip()

    patterns = [
        r"^(?:ok|okay|hey|hi|hello|please)[\s,]+",
        r"^(?:can|could|would)\s+you\s+(?:please\s+)?(?:tell|show|give|provide|find|search|recommend|suggest)\s+(?:me\s+)?(?:about\s+)?",
        r"^(?:tell|show|give|provide|find|search)\s+(?:me\s+)?(?:about\s+)?",
        r"^(?:research\s+)?notes\s+(?:for\s+the\s+topic|for|on|about|regarding)\s+",
        r"^(?:what\s+are\s+(?:some\s+)?(?:famous|the\s+best|top|the\s+latest|popular|major)\s+)?(?:research\s+)?(?:papers|articles|studies|publications|books|notes)\s+(?:on|about|regarding|in)\s+",
        r"^(?:some\s+)?(?:famous|best|top|latest|popular|major)\s+(?:research\s+)?(?:papers|articles|studies|publications)\s+(?:on|about|regarding|in)\s+",
        r"^(?:papers|articles|studies|publications)\s+(?:on|about|regarding|in)\s+",
        r"^(?:looking\s+for|search\s+for|find)\s+(?:papers|articles|studies)?\s*(?:on|about|regarding)?\s+",
        r"^(?:the\s+topic\s+is|topic\s+is|topic\s*:)\s+",
        r"^(?:is|are|can|could|why|how|what)\s+",
        r"\b(?:really|actually|simply|truly)\b\s*",
        r"\bat\s+any\s+stage\b",
    ]
    changed = True
    while changed:
        changed = False
        for p in patterns:
            new_q = re.sub(p, "", cleaned, flags=re.IGNORECASE).strip()
            if new_q and new_q != cleaned:
                cleaned = new_q
                changed = True
    return cleaned if cleaned else q.strip()


def generate_ai_research_notes_and_keywords(user_query: str) -> Tuple[Optional[str], Optional[str]]:
    """
    If the query asks for study notes, synthesis, or is phrased as a research question,
    invokes Gemini to generate an academic briefing and extract precise indexing keywords.
    """
    q_lower = user_query.lower()
    needs_notes = any(kw in q_lower for kw in ["notes", "explain", "is it", "is ", "why ", "how ", "curable", "cure", "summary", "synthesize", "overview", "can you", "what are"]) or len(user_query.split()) >= 6
    if not needs_notes:
        return None, None

    try:
        from app.services.copilot import get_llm_provider
        provider, _ = get_llm_provider()
        prompt = (
            f"The user has submitted an academic research inquiry: {user_query!r}\n"
            f"1. On the very first line, output: KEYWORDS: <2 to 4 high-precision academic search terms in English, e.g. cancer curability stage oncology>\n"
            f"2. Then output:\nNOTES:\n<Concise, high-yield academic study notes in markdown synthesizing the current consensus in peer-reviewed literature, including definitions, mechanisms, and key conclusions>\n"
        )
        res = provider.generate(prompt, "You are a distinguished university research librarian and academic literature synthesizer.", 12.0)
        if not res:
            return None, None

        keywords: Optional[str] = None
        notes: Optional[str] = None

        if "KEYWORDS:" in res:
            parts = res.split("KEYWORDS:", 1)[1]
            if "NOTES:" in parts:
                kw_part, notes_part = parts.split("NOTES:", 1)
                keywords = kw_part.strip()
                notes = notes_part.strip()
            else:
                keywords = parts.strip()
        elif "NOTES:" in res:
            notes = res.split("NOTES:", 1)[1].strip()
        else:
            notes = res.strip()

        return notes, keywords
    except Exception as exc:
        logger.warning("AI research notes generation skipped: %s", type(exc).__name__)
        return None, None


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
        skip_ai_notes: bool = False,
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

        scholarly_query = clean_scholarly_query(clean_query)
        ai_notes: Optional[str] = None
        focused_topic: Optional[str] = None

        # Check if user query is a research question or asks for notes/synthesis
        q_lower = clean_query.lower()
        needs_ai_brief = (
            not skip_ai_notes and (
                any(w in q_lower for w in ["notes", "explain", "is it", "is ", "why ", "how ", "curable", "cure", "summary", "synthesize", "can you", "what are", "what is"])
                or len(clean_query.split()) >= 6
            )
        )
        if needs_ai_brief:
            ai_notes, extracted_kw = generate_ai_research_notes_and_keywords(clean_query)
            if extracted_kw:
                focused_topic = extracted_kw
                scholarly_query = clean_scholarly_query(extracted_kw)

        if not focused_topic and scholarly_query != clean_query:
            focused_topic = scholarly_query

        if scholarly_query != clean_query:
            logger.info("Sanitized conversational scholarly query: %r -> %r (focused_topic: %r)", clean_query, scholarly_query, focused_topic)

        target_providers = [p.lower() for p in providers] if providers else ["openalex", "arxiv", "crossref"]
        valid_providers = [p for p in target_providers if p in self.providers]

        cache_key = f"{scholarly_query.lower()}|{limit}|{page}|{','.join(sorted(valid_providers))}|{year}|{is_oa}"
        now = datetime.utcnow()

        if use_cache and cache_key in _RESEARCH_CACHE:
            cached_time, cached_res = _RESEARCH_CACHE[cache_key]
            if now - cached_time < CACHE_TTL:
                return cached_res

        active_providers: List[str] = []
        raw_results: List[AcademicPaperResult] = []

        per_provider_limit = max(10, limit // len(valid_providers) + 4) if valid_providers else limit

        # Query OpenAlex
        if "openalex" in valid_providers:
            try:
                oa_papers = self.providers["openalex"].search(
                    query=scholarly_query,
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
                    query=scholarly_query,
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
                    query=scholarly_query,
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

        # Sort results: prioritize high citation counts and authoritative papers
        deduped.sort(key=lambda p: (p.citation_count or 0), reverse=True)
        final_results = deduped[:limit]

        response = AcademicSearchResponse(
            query=clean_query,
            total_results=len(deduped),
            page=page,
            page_size=limit,
            providers_queried=valid_providers,
            active_providers=active_providers,
            results=final_results,
            ai_research_notes=ai_notes,
            focused_topic=focused_topic,
        )

        _RESEARCH_CACHE[cache_key] = (now, response)
        return response


academic_research_service = AcademicResearchService()

