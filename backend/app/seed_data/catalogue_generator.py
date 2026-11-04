"""Deterministic synthetic catalogue generator for AI Library Management System.

Generates:
- 1,500 Books across 12 academic categories.
- 4,000 Book Copies across tiers:
  * Top 150 bestsellers x 6 copies = 900 copies
  * 150 Tier 2A x 4 copies = 600 copies
  * 600 Tier 2B x 3 copies = 1,800 copies
  * 100 Tier 2C x 2 copies = 200 copies
  * 500 Monographs x 1 copy = 500 copies
  Total = 4,000 copies.

Integrates with app.services.embedding:
- If sentence-transformers is available and enable_embeddings=True, generates real 384-dim unit vectors.
- If unavailable, stores NULL embedding with embedding_status='missing'.
- NEVER generates pseudo-semantic or fake vectors.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Optional, Tuple

from app.seed_data.generator import SeederConfig, get_namespace_rng
from app.seed_data.vocabulary import (
    CATEGORIES,
    FIRST_NAMES,
    LAST_NAMES,
    PUBLISHERS,
    TITLE_PREFIXES,
    TITLE_SUFFIXES,
    TITLE_TOPICS,
)
from app.services.embedding import (
    MODEL_NAME,
    build_book_document,
    encode_text,
    is_model_available,
    serialize_vector,
)

logger = logging.getLogger(__name__)


@dataclass
class SyntheticBook:
    id: int
    isbn: str
    title: str
    author: str
    category: str
    publisher: str
    publication_year: int
    description: str
    is_archived: bool
    created_at: datetime
    tier: str  # 'bestseller', 'tier2a', 'tier2b', 'tier2c', 'monograph'
    embedding: Optional[bytes] = None
    embedding_status: str = "missing"
    embedding_model: Optional[str] = None
    embedding_version: Optional[int] = None
    embedding_generated_at: Optional[datetime] = None


@dataclass
class SyntheticBookCopy:
    id: int
    book_id: int
    copy_code: str
    edition_year: int
    acquisition_date: datetime
    operational_status: str  # 'available', 'maintenance', 'lost', 'withdrawn'
    is_active: bool
    created_at: datetime


def _compute_isbn13_check_digit(prefix12: str) -> str:
    """Computes the standard ISBN-13 check digit for a 12-digit numeric string."""
    digits = [int(c) for c in prefix12 if c.isdigit()]
    if len(digits) != 12:
        return "0"
    total = sum(d * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits))
    rem = total % 10
    check = (10 - rem) % 10
    return str(check)


def generate_catalogue(config: SeederConfig) -> Dict[str, List]:
    """
    Generates 1,500 Books and 4,000 Book Copies deterministically.
    """
    rng = get_namespace_rng(config.base_seed, "catalogue")
    books: List[SyntheticBook] = []
    copies: List[SyntheticBookCopy] = []

    # Check embedding model availability
    can_embed = config.enable_embeddings and is_model_available()
    if not can_embed:
        logger.info("Semantic embedding model unavailable or disabled; books will store NULL embeddings.")

    used_isbns = set()
    used_titles = set()

    # Pre-generate unique titles
    all_possible_titles = []
    for prefix in TITLE_PREFIXES:
        for topic in TITLE_TOPICS:
            for suffix in TITLE_SUFFIXES:
                all_possible_titles.append(f"{prefix} {topic}: {suffix}")
    rng.shuffle(all_possible_titles)

    # ── 1. Generate 1,500 Books ───────────────────────────────────────────────
    # Tier distribution:
    # 1..150: Bestseller (6 copies each)
    # 151..300: Tier 2A (4 copies each)
    # 301..900: Tier 2B (3 copies each)
    # 901..1000: Tier 2C (2 copies each)
    # 1001..1500: Monograph (1 copy each)
    tiers = (
        [("bestseller", 6)] * 150 +
        [("tier2a", 4)] * 150 +
        [("tier2b", 3)] * 600 +
        [("tier2c", 2)] * 100 +
        [("monograph", 1)] * 500
    )

    for idx, (tier_name, _) in enumerate(tiers, start=1):
        if idx <= len(all_possible_titles):
            title = all_possible_titles[idx - 1]
        else:
            title = f"Advances in {rng.choice(TITLE_TOPICS)} Vol. {idx}"

        author_first = rng.choice(FIRST_NAMES)
        author_last = rng.choice(LAST_NAMES)
        author = f"{author_first} {author_last}"
        category = CATEGORIES[(idx - 1) % len(CATEGORIES)]
        publisher = rng.choice(PUBLISHERS)
        pub_year = rng.randint(1995, 2025)

        # Unique ISBN-13
        prefix12 = f"9780{rng.randint(100, 999):03d}{idx:05d}"
        check = _compute_isbn13_check_digit(prefix12)
        isbn = f"{prefix12[:3]}-{prefix12[3]}-{prefix12[4:7]}-{prefix12[7:]}-{check}"
        used_isbns.add(isbn)

        description = (
            f"An authoritative reference on {category.lower()} covering foundational theory, "
            f"modern implementations, and critical research frontiers in {category}."
        )

        book_created = config.as_of - timedelta(days=rng.randint(200, 400))

        # Embeddings
        embedding_blob = None
        emb_status = "missing"
        emb_model = None
        emb_ver = None
        emb_dt = None

        if can_embed:
            try:
                doc = build_book_document(title, author, category, description)
                vec = encode_text(doc)
                embedding_blob = serialize_vector(vec)
                emb_status = "current"
                emb_model = MODEL_NAME
                emb_ver = 1
                emb_dt = config.as_of
            except Exception as e:
                logger.warning("Failed to encode book %d: %s; storing NULL embedding", idx, e)

        books.append(
            SyntheticBook(
                id=idx,
                isbn=isbn,
                title=title,
                author=author,
                category=category,
                publisher=publisher,
                publication_year=pub_year,
                description=description,
                is_archived=False,
                created_at=book_created,
                tier=tier_name,
                embedding=embedding_blob,
                embedding_status=emb_status,
                embedding_model=emb_model,
                embedding_version=emb_ver,
                embedding_generated_at=emb_dt,
            )
        )

    # ── 2. Generate 4,000 Book Copies ─────────────────────────────────────────
    copy_id = 1
    for book_idx, (_, copy_count) in enumerate(tiers, start=1):
        book = books[book_idx - 1]
        for c_num in range(1, copy_count + 1):
            copy_code = f"BC-{book.id:04d}-{c_num:02d}"
            acq_date = book.created_at + timedelta(days=rng.randint(1, 10))

            # Operational status vocabulary:
            # 94% available, 3.5% maintenance, 1.5% lost, 1.0% withdrawn
            r = rng.random()
            if r < 0.94:
                op_status = "available"
            elif r < 0.975:
                op_status = "maintenance"
            elif r < 0.990:
                op_status = "lost"
            else:
                op_status = "withdrawn"

            copies.append(
                SyntheticBookCopy(
                    id=copy_id,
                    book_id=book.id,
                    copy_code=copy_code,
                    edition_year=book.publication_year,
                    acquisition_date=acq_date,
                    operational_status=op_status,
                    is_active=True,
                    created_at=acq_date,
                )
            )
            copy_id += 1

    return {
        "books": books,
        "copies": copies,
    }

