"""
arXiv Academic API Adapter.
Endpoint: http://export.arxiv.org/api/query
Official documentation: https://info.arxiv.org/help/api/user-manual.html
"""
import logging
import re
from typing import List, Optional
import xml.etree.ElementTree as ET
import httpx

from app.schemas import AcademicPaperResult

logger = logging.getLogger("athenaeum.research.arxiv")

ARXIV_API_URL = "https://export.arxiv.org/api/query"
DEFAULT_TIMEOUT = 5.0
ATOM_NS = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"


class ArxivAdapter:
    """Client for arXiv Open Access Preprints repository."""

    def __init__(self, timeout: float = DEFAULT_TIMEOUT):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "AthenaeumAcademicPlatform/1.0 (mailto:athenaeum@university.edu)",
        }

    def search(
        self,
        query: str,
        limit: int = 10,
        page: int = 1,
    ) -> List[AcademicPaperResult]:
        """Queries arXiv and parses Atom XML entries into unified paper records."""
        clean_query = query.strip()
        offset = max(page - 1, 0) * limit

        params = {
            "search_query": f"all:{clean_query}",
            "start": offset,
            "max_results": min(limit, 50),
            "sortBy": "relevance",
            "sortOrder": "descending",
        }

        try:
            with httpx.Client(timeout=self.timeout, headers=self.headers, follow_redirects=True) as client:
                resp = client.get(ARXIV_API_URL, params=params)
                if resp.status_code != 200:
                    logger.warning("arXiv API returned status %s", resp.status_code)
                    return []
                xml_content = resp.text

            root = ET.fromstring(xml_content)
            entries = root.findall(f"{ATOM_NS}entry")

            results: List[AcademicPaperResult] = []
            for entry in entries:
                title_elem = entry.find(f"{ATOM_NS}title")
                title = title_elem.text.strip().replace("\n", " ") if title_elem is not None and title_elem.text else "Untitled"
                title = re.sub(r"\s+", " ", title)

                summary_elem = entry.find(f"{ATOM_NS}summary")
                abstract = summary_elem.text.strip() if summary_elem is not None and summary_elem.text else None
                if abstract:
                    abstract = re.sub(r"\s+", " ", abstract)

                id_elem = entry.find(f"{ATOM_NS}id")
                raw_id = id_elem.text.strip() if id_elem is not None and id_elem.text else ""
                arxiv_id = raw_id.split("/abs/")[-1] if "/abs/" in raw_id else raw_id

                published_elem = entry.find(f"{ATOM_NS}published")
                pub_year = None
                if published_elem is not None and published_elem.text and len(published_elem.text) >= 4:
                    try:
                        pub_year = int(published_elem.text[:4])
                    except ValueError:
                        pass

                authors = []
                for author_elem in entry.findall(f"{ATOM_NS}author"):
                    name_elem = author_elem.find(f"{ATOM_NS}name")
                    if name_elem is not None and name_elem.text:
                        authors.append(name_elem.text.strip())

                doi_elem = entry.find(f"{ARXIV_NS}doi")
                doi = doi_elem.text.strip() if doi_elem is not None and doi_elem.text else None

                results.append(
                    AcademicPaperResult(
                        id=f"arxiv:{arxiv_id}",
                        title=title,
                        authors=authors,
                        abstract=abstract,
                        publication_year=pub_year,
                        doi=doi,
                        arxiv_id=arxiv_id,
                        venue="arXiv preprint",
                        source_provider="arxiv",
                        open_access=True,  # All arXiv papers are publicly accessible
                        url=raw_id or f"https://arxiv.org/abs/{arxiv_id}",
                        citation_count=None,
                    )
                )

            return results
        except httpx.TimeoutException:
            logger.warning("arXiv API request timed out after %.1fs", self.timeout)
            return []
        except Exception as exc:
            logger.error("Error querying arXiv API: %s", type(exc).__name__)
            return []


arxiv_adapter = ArxivAdapter()

