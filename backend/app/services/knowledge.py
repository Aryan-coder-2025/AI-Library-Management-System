"""
Service module for PILLAR 1 (Knowledge Representation) & PILLAR 2 (Search-Based Navigation).
Provides hierarchical subject exploration, concept navigation, and knowledge-guided hybrid retrieval.
"""
import difflib
import re
from typing import List, Optional
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Book,
    BookConcept,
    BookSubject,
    BookTopic,
    Concept,
    Subject,
    Topic,
)
from app.schemas import (
    BookKnowledgeAssociationResponse,
    ConceptResponse,
    KnowledgeSearchResponse,
    KnowledgeSearchResult,
    SubjectDetailResponse,
    SubjectTreeResponse,
    TopicResponse,
)


def get_subject_hierarchy_service(db: Session) -> List[SubjectTreeResponse]:
    """Retrieves full hierarchical subject-topic tree."""
    stmt = (
        select(Subject)
        .where(Subject.parent_id.is_(None))
        .options(
            selectinload(Subject.topics).selectinload(Topic.concepts),
            selectinload(Subject.children),
        )
        .order_by(Subject.name.asc())
    )
    subjects = db.execute(stmt).scalars().all()

    def build_tree(s: Subject) -> SubjectTreeResponse:
        return SubjectTreeResponse(
            id=s.id,
            name=s.name,
            code=s.code,
            description=s.description,
            parent_id=s.parent_id,
            children=[build_tree(child) for child in s.children],
            topics=[
                TopicResponse(
                    id=t.id,
                    subject_id=t.subject_id,
                    name=t.name,
                    description=t.description,
                    concepts=[ConceptResponse.model_validate(c) for c in t.concepts],
                    created_at=t.created_at,
                )
                for t in s.topics
            ],
            created_at=s.created_at,
        )

    return [build_tree(s) for s in subjects]


def get_subject_detail_service(db: Session, subject_id: int) -> Optional[SubjectDetailResponse]:
    """Retrieves subject details with its topics, concepts, and associated books."""
    subj = db.get(Subject, subject_id)
    if not subj:
        return None

    # Load associated books
    book_stmt = (
        select(Book)
        .join(BookSubject, BookSubject.book_id == Book.id)
        .where(BookSubject.subject_id == subject_id)
        .limit(50)
    )
    books = db.execute(book_stmt).scalars().all()

    book_res = [
        BookKnowledgeAssociationResponse(
            book_id=b.id,
            book_title=b.title,
            author=b.author,
            isbn=b.isbn,
            category=b.category,
            subjects=[subj.name],
            topics=[],
            concepts=[],
        )
        for b in books
    ]

    return SubjectDetailResponse(
        id=subj.id,
        name=subj.name,
        code=subj.code,
        description=subj.description,
        parent_id=subj.parent_id,
        topics=[
            TopicResponse(
                id=t.id,
                subject_id=t.subject_id,
                name=t.name,
                description=t.description,
                concepts=[ConceptResponse.model_validate(c) for c in t.concepts],
                created_at=t.created_at,
            )
            for t in subj.topics
        ],
        associated_books=book_res,
    )


def search_knowledge_service(db: Session, query: str, limit: int = 20) -> KnowledgeSearchResponse:
    """
    Search-based navigation: Searches across subjects, topics, concepts, and linked books.
    Provides explainable results showing the full conceptual pathway.
    Supports multi-token decomposition, singular/plural stemming, and fuzzy typo tolerance (e.g. 'djikstras algorithm').
    """
    cleaned = query.strip()
    if not cleaned:
        return KnowledgeSearchResponse(query=query, results=[], total=0)

    # 1. Gather all concepts, topics, subjects for multi-token & fuzzy matching
    all_subjects = db.execute(select(Subject)).scalars().all()
    all_topics = db.execute(select(Topic).join(Subject)).scalars().all()
    all_concepts = db.execute(select(Concept).join(Topic).join(Subject)).scalars().all()

    # Pre-build vocabulary of all terms in the taxonomy
    vocab: dict = {}
    for s in all_subjects:
        for w in re.findall(r"\w+", s.name.lower()):
            if len(w) >= 3:
                vocab[w] = s
    for t in all_topics:
        for w in re.findall(r"\w+", t.name.lower()):
            if len(w) >= 3:
                vocab[w] = t
    for c in all_concepts:
        for w in re.findall(r"\w+", c.name.lower()):
            if len(w) >= 3:
                vocab[w] = c

    # Extract query tokens and expand with typo-corrected & stemmed variants
    raw_tokens = [w.lower() for w in re.findall(r"\w+", cleaned) if len(w) >= 2]
    candidate_tokens = set(raw_tokens)
    for t in raw_tokens:
        if len(t) > 3 and t.endswith("s"):
            candidate_tokens.add(t[:-1])  # e.g. algorithms -> algorithm, djikstras -> djikstra
        close = difflib.get_close_matches(t, list(vocab.keys()), n=2, cutoff=0.6)
        candidate_tokens.update(close)

    pattern_lower = cleaned.lower()
    results_map: dict = {}

    def add_result(res: KnowledgeSearchResult):
        key = (res.item_type, res.id)
        if key not in results_map or results_map[key].relevance_score < res.relevance_score:
            results_map[key] = res

    # 1. Search Concepts
    for c in all_concepts:
        c_name = c.name.lower()
        c_desc = (c.description or "").lower()
        t_name = c.topic.name.lower()
        s_name = c.topic.subject.name.lower()
        full_text = f"{c_name} {c_desc} {t_name} {s_name}"

        # Exact phrase match in concept name
        if pattern_lower in c_name:
            add_result(KnowledgeSearchResult(
                item_type="concept",
                id=c.id,
                title=c.name,
                description=c.description,
                relevance_score=1.0,
                explanation=f"Exact match for concept '{c.name}'",
                context_path=f"{c.topic.subject.name} > {c.topic.name} > {c.name}",
                associated_books_count=0,
            ))
            continue

        # Token matches
        matched_tokens = [tok for tok in candidate_tokens if tok in c_name or tok in full_text]
        if matched_tokens:
            base_score = 0.82 + (0.12 * min(1.0, len(matched_tokens) / max(1, len(raw_tokens))))
            if any(tok in c_name for tok in candidate_tokens):
                base_score += 0.05
            add_result(KnowledgeSearchResult(
                item_type="concept",
                id=c.id,
                title=c.name,
                description=c.description,
                relevance_score=round(min(0.99, base_score), 2),
                explanation=f"Matches concept '{c.name}' under {c.topic.name}",
                context_path=f"{c.topic.subject.name} > {c.topic.name} > {c.name}",
                associated_books_count=0,
            ))

    # 2. Search Topics
    for t in all_topics:
        t_name = t.name.lower()
        t_desc = (t.description or "").lower()
        if pattern_lower in t_name:
            book_count = db.execute(select(func.count(BookTopic.id)).where(BookTopic.topic_id == t.id)).scalar() or 0
            add_result(KnowledgeSearchResult(
                item_type="topic",
                id=t.id,
                title=t.name,
                description=t.description,
                relevance_score=0.95,
                explanation=f"Curated topic under {t.subject.name}",
                context_path=f"{t.subject.name} > {t.name}",
                associated_books_count=book_count,
            ))
            continue

        matched_tokens = [tok for tok in candidate_tokens if tok in t_name or tok in t_desc]
        if matched_tokens:
            book_count = db.execute(select(func.count(BookTopic.id)).where(BookTopic.topic_id == t.id)).scalar() or 0
            base_score = 0.78 + (0.12 * min(1.0, len(matched_tokens) / max(1, len(raw_tokens))))
            add_result(KnowledgeSearchResult(
                item_type="topic",
                id=t.id,
                title=t.name,
                description=t.description,
                relevance_score=round(min(0.93, base_score), 2),
                explanation=f"Topic under {t.subject.name}",
                context_path=f"{t.subject.name} > {t.name}",
                associated_books_count=book_count,
            ))

    # 3. Search Subjects
    for s in all_subjects:
        s_name = s.name.lower()
        s_desc = (s.description or "").lower()
        if pattern_lower in s_name or any(tok in s_name for tok in candidate_tokens):
            book_count = db.execute(select(func.count(BookSubject.id)).where(BookSubject.subject_id == s.id)).scalar() or 0
            score = 1.0 if pattern_lower in s_name else 0.8
            add_result(KnowledgeSearchResult(
                item_type="subject",
                id=s.id,
                title=s.name,
                description=s.description,
                relevance_score=score,
                explanation=f"Matches academic discipline '{s.name}' ({s.code})",
                context_path=s.name,
                associated_books_count=book_count,
            ))

    results = list(results_map.values())
    results.sort(key=lambda x: (x.relevance_score, x.associated_books_count), reverse=True)
    return KnowledgeSearchResponse(query=query, results=results[:limit], total=len(results))

