"""
Service module for PILLAR 1 (Knowledge Representation) & PILLAR 2 (Search-Based Navigation).
Provides hierarchical subject exploration, concept navigation, and knowledge-guided hybrid retrieval.
"""
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
    """
    cleaned = query.strip()
    if not cleaned:
        return KnowledgeSearchResponse(query=query, results=[], total=0)

    pattern = f"%{cleaned}%"
    results: List[KnowledgeSearchResult] = []

    # 1. Search Subjects
    subjects = db.execute(
        select(Subject).where(or_(Subject.name.ilike(pattern), Subject.description.ilike(pattern))).limit(limit)
    ).scalars().all()

    for s in subjects:
        book_count = db.execute(
            select(func.count(BookSubject.id)).where(BookSubject.subject_id == s.id)
        ).scalar() or 0
        results.append(
            KnowledgeSearchResult(
                item_type="subject",
                id=s.id,
                title=s.name,
                description=s.description,
                relevance_score=1.0,
                explanation=f"Matches academic subject '{s.name}' ({s.code})",
                context_path=s.name,
                associated_books_count=book_count,
            )
        )

    # 2. Search Topics
    topics = db.execute(
        select(Topic).join(Subject).where(or_(Topic.name.ilike(pattern), Topic.description.ilike(pattern))).limit(limit)
    ).scalars().all()

    for t in topics:
        book_count = db.execute(
            select(func.count(BookTopic.id)).where(BookTopic.topic_id == t.id)
        ).scalar() or 0
        results.append(
            KnowledgeSearchResult(
                item_type="topic",
                id=t.id,
                title=t.name,
                description=t.description,
                relevance_score=0.9,
                explanation=f"Curated topic under {t.subject.name}",
                context_path=f"{t.subject.name} > {t.name}",
                associated_books_count=book_count,
            )
        )

    # 3. Search Concepts
    concepts = db.execute(
        select(Concept).join(Topic).join(Subject).where(
            or_(Concept.name.ilike(pattern), Concept.description.ilike(pattern))
        ).limit(limit)
    ).scalars().all()

    for c in concepts:
        results.append(
            KnowledgeSearchResult(
                item_type="concept",
                id=c.id,
                title=c.name,
                description=c.description,
                relevance_score=0.8,
                explanation=f"Fundamental concept under {c.topic.name}",
                context_path=f"{c.topic.subject.name} > {c.topic.name} > {c.name}",
                associated_books_count=0,
            )
        )

    results.sort(key=lambda x: x.relevance_score, reverse=True)
    return KnowledgeSearchResponse(query=query, results=results[:limit], total=len(results))

