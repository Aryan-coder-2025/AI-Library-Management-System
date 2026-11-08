"""
OpenAlex Academic API Adapter.
Endpoint: https://api.openalex.org/works
Official documentation: https://docs.openalex.org/
"""
import logging
from typing import Any, Dict, List, Optional
import httpx

from app.schemas import AcademicPaperResult

logger = logging.getLogger("athenaeum.research.openalex")

OPENALEX_WORKS_URL = "https://api.openalex.org/works"
DEFAULT_TIMEOUT = 6.0


def reconstruct_inverted_index(inverted_index: Optional[Dict[str, List[int]]]) -> Optional[str]:
    """Reconstructs raw abstract text from OpenAlex's inverted index structure."""
    if not inverted_index or not isinstance(inverted_index, dict):
        return None
    try:
        word_positions: List[tuple[int, str]] = []
        for word, positions in inverted_index.items():
            for pos in positions:
                word_positions.append((pos, word))
        word_positions.sort(key=lambda x: x[0])
        return " ".join(word for _, word in word_positions)
    except Exception:
        return None


class OpenAlexAdapter:
    """Client for OpenAlex scholarly works catalogue."""

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
        year: Optional[int] = None,
        is_oa: Optional[bool] = None,
    ) -> List[AcademicPaperResult]:
        """Queries OpenAlex works and returns normalized results."""
        params: Dict[str, Any] = {
            "search": query,
            "per_page": min(limit, 50),
            "page": max(page, 1),
        }

        filters = []
        if year is not None:
            filters.append(f"publication_year:{year}")
        if is_oa is True:
            filters.append("is_oa:true")

        if filters:
            params["filter"] = ",".join(filters)

        try:
            with httpx.Client(timeout=self.timeout, headers=self.headers) as client:
                resp = client.get(OPENALEX_WORKS_URL, params=params)
                if resp.status_code != 200:
                    logger.warning("OpenAlex returned status %s: %s", resp.status_code, resp.text[:200])
                    return []
                data = resp.json()

            results: List[AcademicPaperResult] = []
            for item in data.get("results", []):
                authors = [
                    a["author"]["display_name"]
                    for a in item.get("authorships", [])
                    if a.get("author") and a["author"].get("display_name")
                ]

                primary_loc = item.get("primary_location") or {}
                source_obj = primary_loc.get("source") or {}
                venue = source_obj.get("display_name")

                oa_info = item.get("open_access") or {}
                open_access = bool(oa_info.get("is_oa", False))

                abstract = reconstruct_inverted_index(item.get("abstract_inverted_index"))

                doi = item.get("doi")
                url = doi or primary_loc.get("landing_page_url") or item.get("id")

                results.append(
                    AcademicPaperResult(
                        id=str(item.get("id") or f"openalex:{item.get('doi', '')}"),
                        title=item.get("title") or "Untitled Document",
                        authors=authors,
                        abstract=abstract,
                        publication_year=item.get("publication_year"),
                        doi=doi,
                        arxiv_id=None,
                        venue=venue,
                        source_provider="openalex",
                        open_access=open_access,
                        url=url,
                        citation_count=item.get("cited_by_count"),
                    )
                )

            return results
        except httpx.TimeoutException:
            logger.warning("OpenAlex API request timed out after %.1fs", self.timeout)
            return []
        except Exception as exc:
            logger.error("Error querying OpenAlex API: %s", type(exc).__name__)
            return []


openalex_adapter = OpenAlexAdapter()

