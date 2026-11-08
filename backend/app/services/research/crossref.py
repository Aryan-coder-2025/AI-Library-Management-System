"""
Crossref Academic API Adapter.
Endpoint: https://api.crossref.org/works
Official documentation: https://api.crossref.org/swagger-ui/index.html
"""
import logging
import re
from typing import Any, Dict, List, Optional
import httpx

from app.schemas import AcademicPaperResult

logger = logging.getLogger("athenaeum.research.crossref")

CROSSREF_API_URL = "https://api.crossref.org/works"
DEFAULT_TIMEOUT = 6.0


def clean_jats_abstract(raw: Optional[str]) -> Optional[str]:
    """Strips XML/JATS tags from Crossref abstract fields (e.g., <jats:p>...</jats:p>)."""
    if not raw:
        return None
    cleaned = re.sub(r"<[^>]+>", "", raw)
    return re.sub(r"\s+", " ", cleaned).strip()


class CrossrefAdapter:
    """Client for Crossref DOI metadata registry."""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "AthenaeumAcademicPlatform/1.0 (mailto:athenaeum@university.edu)",
            "Accept": "application/json",
        }

    def search(
        self,
        query: str,
        limit: int = 10,
        page: int = 1,
    ) -> List[AcademicPaperResult]:
        """Queries Crossref works and returns normalized results."""
        offset = max(page - 1, 0) * limit
        params: Dict[str, Any] = {
            "query": query,
            "rows": min(limit, 50),
            "offset": offset,
        }

        try:
            with httpx.Client(timeout=self.timeout, headers=self.headers) as client:
                resp = client.get(CROSSREF_API_URL, params=params)
                if resp.status_code != 200:
                    logger.warning("Crossref returned status %s", resp.status_code)
                    return []
                data = resp.json()

            items = data.get("message", {}).get("items", [])
            results: List[AcademicPaperResult] = []

            for item in items:
                title_list = item.get("title") or []
                title = title_list[0] if title_list else "Untitled"

                authors = []
                for a in item.get("author", []):
                    given = a.get("given", "").strip()
                    family = a.get("family", "").strip()
                    full = f"{given} {family}".strip() if given or family else a.get("name", "")
                    if full:
                        authors.append(full)

                # Extract publication year
                pub_year = None
                date_parts = (
                    item.get("published-print", {}).get("date-parts")
                    or item.get("published-online", {}).get("date-parts")
                    or item.get("created", {}).get("date-parts")
                )
                if date_parts and date_parts[0] and date_parts[0][0]:
                    try:
                        pub_year = int(date_parts[0][0])
                    except (ValueError, TypeError):
                        pass

                doi = item.get("DOI")
                venue_list = item.get("container-title") or []
                venue = venue_list[0] if venue_list else None

                abstract = clean_jats_abstract(item.get("abstract"))

                url = item.get("URL") or (f"https://doi.org/{doi}" if doi else None)

                results.append(
                    AcademicPaperResult(
                        id=f"crossref:{doi or item.get('URL', '')}",
                        title=title,
                        authors=authors,
                        abstract=abstract,
                        publication_year=pub_year,
                        doi=doi,
                        arxiv_id=None,
                        venue=venue,
                        source_provider="crossref",
                        open_access=False,
                        url=url,
                        citation_count=item.get("is-referenced-by-count"),
                    )
                )

            return results
        except httpx.TimeoutException:
            logger.warning("Crossref API request timed out after %.1fs", self.timeout)
            return []
        except Exception as exc:
            logger.error("Error querying Crossref API: %s", type(exc).__name__)
            return []


crossref_adapter = CrossrefAdapter()

