"""
Academic Research Discovery Subsystem for Athenaeum.
Integrates OpenAlex, arXiv, and Crossref public scholarly APIs.
"""
from app.services.research.aggregator import academic_research_service

__all__ = ["academic_research_service"]

