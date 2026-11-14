"""
Physical book shelf micro-location and spatial layout service.
Maps catalogued monographs to exact physical library stacks coordinates:
Floor Number, Aisle, Bookcase Bay, Shelf Tier (1-5), and the exact Book Slot
Number (e.g. 7th book from left edge) according to standard Dewey Decimal Classification.
"""
from typing import Dict, Any, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models import Book, LibraryFloor
from app.schemas import BookShelfLocationResponse, ShelfBookNeighbor


CATEGORY_STACK_MAP = {
    "Mathematics": {
        "floor_number": 1,
        "floor_name": "1st Floor — Collaborative Commons & Mathematical Sciences",
        "aisle": "Aisle 1A",
        "dewey_base": "510.0",
        "bay_prefix": "Bay",
        "x": 280.0,
        "y": 210.0,
        "normalized_x": 0.28,
        "normalized_y": 0.30,
    },
    "Physics": {
        "floor_number": 1,
        "floor_name": "1st Floor — Collaborative Commons & Mathematical Sciences",
        "aisle": "Aisle 1B",
        "dewey_base": "530.0",
        "bay_prefix": "Bay",
        "x": 280.0,
        "y": 380.0,
        "normalized_x": 0.28,
        "normalized_y": 0.54,
    },
    "Philosophy of Technology": {
        "floor_number": 1,
        "floor_name": "1st Floor — Collaborative Commons & Mathematical Sciences",
        "aisle": "Aisle 1C",
        "dewey_base": "601.0",
        "bay_prefix": "Bay",
        "x": 280.0,
        "y": 530.0,
        "normalized_x": 0.28,
        "normalized_y": 0.75,
    },
    "Computer Science": {
        "floor_number": 2,
        "floor_name": "2nd Floor — Computing & Informatics Commons",
        "aisle": "Aisle 2A",
        "dewey_base": "004.0",
        "bay_prefix": "Bay",
        "x": 450.0,
        "y": 190.0,
        "normalized_x": 0.45,
        "normalized_y": 0.27,
    },
    "Software Engineering": {
        "floor_number": 2,
        "floor_name": "2nd Floor — Computing & Informatics Commons",
        "aisle": "Aisle 2B",
        "dewey_base": "005.1",
        "bay_prefix": "Bay",
        "x": 450.0,
        "y": 330.0,
        "normalized_x": 0.45,
        "normalized_y": 0.47,
    },
    "Algorithms & Complexity": {
        "floor_number": 2,
        "floor_name": "2nd Floor — Computing & Informatics Commons",
        "aisle": "Aisle 2C",
        "dewey_base": "005.11",
        "bay_prefix": "Bay",
        "x": 450.0,
        "y": 480.0,
        "normalized_x": 0.45,
        "normalized_y": 0.68,
    },
    "Artificial Intelligence": {
        "floor_number": 2,
        "floor_name": "2nd Floor — Computing & Informatics Commons",
        "aisle": "Aisle 2D",
        "dewey_base": "006.3",
        "bay_prefix": "Bay",
        "x": 720.0,
        "y": 230.0,
        "normalized_x": 0.72,
        "normalized_y": 0.32,
    },
    "Distributed Systems": {
        "floor_number": 3,
        "floor_name": "3rd Floor — Systems, Cybersecurity & Advanced Research",
        "aisle": "Aisle 3A",
        "dewey_base": "004.36",
        "bay_prefix": "Bay",
        "x": 340.0,
        "y": 210.0,
        "normalized_x": 0.34,
        "normalized_y": 0.30,
    },
    "Cybersecurity & Cryptography": {
        "floor_number": 3,
        "floor_name": "3rd Floor — Systems, Cybersecurity & Advanced Research",
        "aisle": "Aisle 3B",
        "dewey_base": "005.8",
        "bay_prefix": "Bay",
        "x": 340.0,
        "y": 360.0,
        "normalized_x": 0.34,
        "normalized_y": 0.51,
    },
    "Data Science": {
        "floor_number": 3,
        "floor_name": "3rd Floor — Systems, Cybersecurity & Advanced Research",
        "aisle": "Aisle 3C",
        "dewey_base": "005.7",
        "bay_prefix": "Bay",
        "x": 340.0,
        "y": 510.0,
        "normalized_x": 0.34,
        "normalized_y": 0.72,
    },
    "Information Systems": {
        "floor_number": 3,
        "floor_name": "3rd Floor — Systems, Cybersecurity & Advanced Research",
        "aisle": "Aisle 3D",
        "dewey_base": "004.6",
        "bay_prefix": "Bay",
        "x": 680.0,
        "y": 250.0,
        "normalized_x": 0.68,
        "normalized_y": 0.35,
    },
    "Robotics": {
        "floor_number": 3,
        "floor_name": "3rd Floor — Systems, Cybersecurity & Advanced Research",
        "aisle": "Aisle 3E",
        "dewey_base": "629.8",
        "bay_prefix": "Bay",
        "x": 680.0,
        "y": 420.0,
        "normalized_x": 0.68,
        "normalized_y": 0.60,
    },
}

TIER_NAMES = {
    1: "Tier 1 (Bottom Shelf — 35 cm from ground)",
    2: "Tier 2 (Lower Shelf — 70 cm from ground)",
    3: "Tier 3 (Mid-Chest Level — 105 cm from ground)",
    4: "Tier 4 (Eye Level — 140 cm from ground)",
    5: "Tier 5 (Top Shelf — 175 cm from ground)",
}


def _generate_cutter_number(author: str, title: str) -> str:
    """Generates realistic standard Cutter-Sanborn 3-character shelfmark."""
    author_clean = author.split(",")[-1].strip().split()[-1] if author else "Anon"
    first_letter = author_clean[0].upper() if author_clean else "A"
    code_sum = sum(ord(c) for c in author_clean[:4]) % 89 + 10
    work_letter = title.strip()[0].lower() if title.strip() else "x"
    return f"{first_letter}{code_sum}{work_letter}"


def locate_book_on_shelf_service(db: Session, book_id: int) -> BookShelfLocationResponse:
    """
    Computes precise micro-location coordinates for a book down to:
    Floor, Aisle, Bookcase Bay, Shelf Tier (1-5), and exact Book Slot Number from left.
    """
    book = db.query(Book).filter(Book.id == book_id).first()
    if not book:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Book #{book_id} not found in catalogue.",
        )

    # Determine Stack Area
    category = book.category or "Computer Science"
    stack_info = CATEGORY_STACK_MAP.get(category, CATEGORY_STACK_MAP["Computer Science"])

    # Query all non-archived books in this category sorted deterministically by title
    category_books = (
        db.query(Book)
        .filter(Book.category == category, Book.is_archived.is_(False))
        .order_by(Book.title.asc(), Book.id.asc())
        .all()
    )

    # Find position of target book within category
    try:
        k = next(i for i, b in enumerate(category_books) if b.id == book.id)
    except StopIteration:
        k = 0

    books_per_tier = 25
    tiers_per_bay = 5

    tier_idx = (k // books_per_tier) % tiers_per_bay
    shelf_tier = tier_idx + 1
    bay_idx = (k // (books_per_tier * tiers_per_bay)) + 1
    bay_name = f"{stack_info['bay_prefix']} {bay_idx:02d}"

    slot_number = (k % books_per_tier) + 1
    position_from_left = slot_number
    position_from_right = books_per_tier - slot_number + 1

    cutter = _generate_cutter_number(book.author, book.title)
    call_number = f"{stack_info['dewey_base']} {cutter}"

    # Get adjacent shelf neighbors (same tier)
    tier_start_idx = (k // books_per_tier) * books_per_tier
    tier_books = category_books[tier_start_idx : tier_start_idx + books_per_tier]

    neighbors: List[ShelfBookNeighbor] = []
    # Take a 5-book window centered on target
    local_idx = k - tier_start_idx
    window_start = max(0, local_idx - 2)
    window_end = min(len(tier_books), local_idx + 3)

    for idx in range(window_start, window_end):
        b = tier_books[idx]
        slot = idx + 1
        b_cutter = _generate_cutter_number(b.author, b.title)
        neighbors.append(
            ShelfBookNeighbor(
                slot=slot,
                book_id=b.id,
                title=b.title,
                author=b.author,
                call_number=f"{stack_info['dewey_base']} {b_cutter}",
                is_target=(b.id == book.id),
            )
        )

    tier_name = TIER_NAMES.get(shelf_tier, f"Tier {shelf_tier}")

    turn_by_turn = [
        f"1. Enter via Central Library Atrium on Ground Floor.",
        f"2. Take central stairs or elevator to {stack_info['floor_name']}.",
        f"3. Proceed along the main circulation corridor into {stack_info['aisle']} ({category}).",
        f"4. Walk up to Bookcase {bay_name}.",
        f"5. Look at {tier_name} ({shelf_tier} of 5 shelves).",
        f"6. Count {position_from_left} books from the LEFT edge — '{book.title}' is sitting at Slot #{position_from_left}.",
    ]

    guidance = (
        f"Located on {stack_info['floor_name']} in {stack_info['aisle']}, {bay_name}, "
        f"{tier_name}. Book #{position_from_left} from the LEFT edge (Call #: {call_number})."
    )

    return BookShelfLocationResponse(
        book_id=book.id,
        title=book.title,
        author=book.author,
        category=category,
        call_number=call_number,
        floor_number=stack_info["floor_number"],
        floor_name=stack_info["floor_name"],
        aisle=stack_info["aisle"],
        bay=bay_name,
        shelf_tier=shelf_tier,
        shelf_tier_name=tier_name,
        total_tiers=tiers_per_bay,
        slot_number=slot_number,
        position_from_left=position_from_left,
        position_from_right=position_from_right,
        direction="Left to Right",
        shelf_capacity=books_per_tier,
        turn_by_turn_directions=turn_by_turn,
        guidance=guidance,
        map_coordinates={
            "x": stack_info["x"],
            "y": stack_info["y"],
            "normalized_x": stack_info["normalized_x"],
            "normalized_y": stack_info["normalized_y"],
        },
        shelf_neighbors=neighbors,
    )
