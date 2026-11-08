"""
Knowledge Representation Seed Data.
Builds genuine, curated subject-topic-concept hierarchies across library domains
and connects monographs in the collection to knowledge representations.
"""
from typing import Dict, List
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Book,
    BookConcept,
    BookSubject,
    BookTopic,
    Concept,
    Subject,
    Topic,
)
from app.utils.date import get_utc_now


CURATED_KNOWLEDGE_TREE = [
    {
        "name": "Computer Science & Engineering",
        "code": "CS",
        "description": "Computational theory, software systems, algorithms, and artificial intelligence.",
        "topics": [
            {
                "name": "Artificial Intelligence & Machine Learning",
                "description": "Statistical learning, neural networks, computer vision, and NLP.",
                "concepts": [
                    {"name": "Neural Networks", "description": "Layered architectures for representation learning."},
                    {"name": "Natural Language Processing", "description": "Computational processing of human language."},
                    {"name": "Reinforcement Learning", "description": "Agent training via reward-driven optimization."},
                    {"name": "Transformers & Attention", "description": "Self-attention mechanisms for sequence modelling."},
                ],
            },
            {
                "name": "Algorithms & Data Structures",
                "description": "Fundamental computing primitives, computational complexity, and optimization.",
                "concepts": [
                    {"name": "Graph Traversal & Dijkstra", "description": "Shortest-path algorithms and tree traversals."},
                    {"name": "Dynamic Programming", "description": "Optimization via overlapping sub-problem memoization."},
                    {"name": "Computational Complexity", "description": "P, NP, asymptotic bounds, and tractability."},
                ],
            },
            {
                "name": "Software Engineering & Architecture",
                "description": "Design patterns, distributed systems, concurrent programming, and databases.",
                "concepts": [
                    {"name": "Distributed Systems", "description": "Consensus, CAP theorem, and partition tolerance."},
                    {"name": "Relational Database Theory", "description": "ACID transactions, B-Trees, and relational algebra."},
                    {"name": "Microservices & Cloud", "description": "Decoupled service architectures and containerization."},
                ],
            },
        ],
    },
    {
        "name": "Mathematics & Statistics",
        "code": "MATH",
        "description": "Pure mathematics, applied statistics, calculus, and linear algebra.",
        "topics": [
            {
                "name": "Linear Algebra & Optimization",
                "description": "Vector spaces, matrix decompositions, and convex optimization.",
                "concepts": [
                    {"name": "Matrix Decomposition", "description": "SVD, QR, and spectral eigenvalue factorization."},
                    {"name": "Vector Spaces", "description": "Inner products, orthogonal bases, and linear projections."},
                ],
            },
            {
                "name": "Probability & Stochastic Processes",
                "description": "Random variables, Bayesian inference, and Markov chains.",
                "concepts": [
                    {"name": "Bayesian Inference", "description": "Posterior updating under prior beliefs and likelihood."},
                    {"name": "Markov Chains", "description": "Memoryless state transition systems."},
                ],
            },
        ],
    },
    {
        "name": "Social Sciences & Information Studies",
        "code": "INFO",
        "description": "Information architecture, digital humanities, and library science.",
        "topics": [
            {
                "name": "Information Retrieval & Organization",
                "description": "Indexing, cataloging, knowledge taxonomies, and vector spaces.",
                "concepts": [
                    {"name": "Reciprocal Rank Fusion", "description": "Rank aggregation across heterogeneous search channels."},
                    {"name": "Knowledge Taxonomies", "description": "Hierarchical classification of academic disciplines."},
                ],
            },
        ],
    },
]


def seed_knowledge_representation(db: Session) -> Dict[str, int]:
    """
    Populates curated subject, topic, and concept hierarchies and links existing books.
    Idempotent: skips existing entries.
    """
    now = get_utc_now()
    existing_subjects = {s.code: s for s in db.execute(select(Subject)).scalars().all()}

    subjects_created = 0
    topics_created = 0
    concepts_created = 0

    topics_by_name: Dict[str, Topic] = {}
    concepts_by_name: Dict[str, Concept] = {}

    for s_data in CURATED_KNOWLEDGE_TREE:
        subj = existing_subjects.get(s_data["code"])
        if not subj:
            subj = Subject(
                name=s_data["name"],
                code=s_data["code"],
                description=s_data["description"],
                created_at=now,
                updated_at=now,
            )
            db.add(subj)
            db.flush()
            subjects_created += 1

        for t_data in s_data.get("topics", []):
            topic_stmt = select(Topic).where(Topic.subject_id == subj.id, Topic.name == t_data["name"])
            topic = db.execute(topic_stmt).scalars().first()
            if not topic:
                topic = Topic(
                    subject_id=subj.id,
                    name=t_data["name"],
                    description=t_data["description"],
                    created_at=now,
                    updated_at=now,
                )
                db.add(topic)
                db.flush()
                topics_created += 1
            topics_by_name[topic.name] = topic

            for c_data in t_data.get("concepts", []):
                concept_stmt = select(Concept).where(Concept.topic_id == topic.id, Concept.name == c_data["name"])
                concept = db.execute(concept_stmt).scalars().first()
                if not concept:
                    concept = Concept(
                        topic_id=topic.id,
                        name=c_data["name"],
                        description=c_data["description"],
                        created_at=now,
                    )
                    db.add(concept)
                    db.flush()
                    concepts_created += 1
                concepts_by_name[concept.name] = concept

    # Associate existing books with subjects based on category/keywords
    books = db.execute(select(Book)).scalars().all()
    associations_created = 0

    for b in books:
        title_lower = b.title.lower()
        cat_lower = b.category.lower()

        target_subject_code = "CS"
        if "math" in cat_lower or "algebra" in title_lower or "statistics" in title_lower:
            target_subject_code = "MATH"
        elif "library" in cat_lower or "history" in cat_lower or "literature" in cat_lower:
            target_subject_code = "INFO"

        subj = existing_subjects.get(target_subject_code) or db.execute(select(Subject).where(Subject.code == target_subject_code)).scalars().first()
        if subj:
            exists = db.execute(select(BookSubject).where(BookSubject.book_id == b.id, BookSubject.subject_id == subj.id)).scalars().first()
            if not exists:
                db.add(BookSubject(book_id=b.id, subject_id=subj.id, relevance_score=1.0, created_at=now))
                associations_created += 1

        # Link specific topics
        for t_name, topic in topics_by_name.items():
            if any(term in title_lower for term in t_name.lower().split() if len(term) > 3):
                exists_t = db.execute(select(BookTopic).where(BookTopic.book_id == b.id, BookTopic.topic_id == topic.id)).scalars().first()
                if not exists_t:
                    db.add(BookTopic(book_id=b.id, topic_id=topic.id, relevance_score=0.9, created_at=now))

    db.flush()
    return {
        "subjects": subjects_created,
        "topics": topics_created,
        "concepts": concepts_created,
        "associations": associations_created,
    }

