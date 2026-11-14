"""
Test suite for physical shelf micro-location and slot position navigator.
Verifies deterministic mapping to Floor, Aisle, Bay, Shelf Tier, and exact Book Number from left.
"""
import pytest
from sqlalchemy.orm import Session
from app.models import Book
from app.database import atomic_write


def test_book_shelf_location_success(client, db: Session):
    """Verifies that an existing book returns complete physical micro-location coordinates."""
    with atomic_write(db):
        test_book = Book(
            title="Introduction to Quantum Algorithms",
            author="David Deutsch",
            category="Algorithms & Complexity",
            description="Quantum computing algorithms and complexity.",
        )
        db.add(test_book)
        db.flush()
        book_id = test_book.id

    resp = client.get(f"/api/books/{book_id}/shelf-location")
    assert resp.status_code == 200
    data = resp.json()

    assert data["book_id"] == book_id
    assert data["title"] == "Introduction to Quantum Algorithms"
    assert data["category"] == "Algorithms & Complexity"
    assert data["floor_number"] == 2
    assert "Aisle" in data["aisle"]
    assert "Bay" in data["bay"]
    assert 1 <= data["shelf_tier"] <= 5
    assert 1 <= data["position_from_left"] <= 25
    assert 1 <= data["position_from_right"] <= 25
    assert data["position_from_left"] + data["position_from_right"] == 26
    assert data["direction"] == "Left to Right"
    assert len(data["turn_by_turn_directions"]) >= 4
    assert len(data["shelf_neighbors"]) >= 1

    # Check target flag in neighbors
    target_neighbor = next((n for n in data["shelf_neighbors"] if n["is_target"]), None)
    assert target_neighbor is not None
    assert target_neighbor["book_id"] == book_id


def test_book_shelf_location_not_found(client):
    """Verifies that querying a non-existent book returns 404."""
    resp = client.get("/api/books/9999999/shelf-location")
    assert resp.status_code == 404
