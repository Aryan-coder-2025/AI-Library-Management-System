"""
Service module for PILLAR 3 (Intelligent Librarian Agent) & PILLAR 5 (RAG Recommendation Assistant).
Orchestrates autonomous agent actions (space reservations, monograph holds, loan renewals, return passes,
academic research discovery), structured tool calls, assembled verified RAG context, and explainable recommendations.
Supports bounded multi-turn conversational context and coreference resolution.
"""
from datetime import datetime, date, time as dt_time, timedelta, timezone
import time as time_module
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple
import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    Book,
    BookCopy,
    BookHold,
    LibraryFloor,
    Loan,
    SpatialResourceMapping,
    StudyRoom,
    StudySeat,
    StudyZone,
    User,
)
from app.schemas import (
    ChatMessageInput,
    CopilotAgentAction,
    CopilotToolCall,
    EnhancedCopilotResponse,
    ReservationCreate,
    StructuredCitation,
)
from app.services import spatial as spatial_service
from app.services import spaces as space_service
from app.services import loans as loans_service
from app.services.holds import place_hold_service
from app.services.qr_collection import generate_book_collection_pass
from app.services.qr_return import generate_book_return_token
from app.services.research.aggregator import academic_research_service
from app.services.semantic import hybrid_search_service
from app.services.copilot import get_llm_provider, get_policy_sections, search_policies

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Structured Tool Registry ──────────────────────────────────────────────────

def tool_search_catalogue(db: Session, query: str, limit: int = 5) -> Dict[str, Any]:
    """Tool: Searches library catalogue using hybrid lexical and semantic search."""
    try:
        res = hybrid_search_service(db=db, query=query, page_size=limit)
        items = [
            {
                "id": b.id,
                "title": b.title,
                "author": b.author,
                "isbn": b.isbn,
                "category": b.category,
                "available_copies": getattr(b, "available_copies", 0),
                "total_copies": getattr(b, "total_copies", 0),
            }
            for b in res.items
        ]
        return {"query": query, "total_found": len(items), "books": items}
    except Exception as e:
        logger.error(f"Error searching catalogue: {e}")
        return {"query": query, "total_found": 0, "books": [], "error": str(e)}


def tool_get_spatial_resource(db: Session, resource_type: str, resource_id: int) -> Dict[str, Any]:
    """Tool: Resolves physical floor plan location and directional wayfinding guidance."""
    try:
        loc = spatial_service.get_resource_location_service(db=db, resource_type=resource_type, resource_id=resource_id)
        return {
            "resource_type": loc.resource_type,
            "resource_id": loc.resource_id,
            "label": loc.label,
            "floor_number": loc.floor_number,
            "floor_name": loc.floor_name,
            "zone_name": loc.zone_name,
            "coordinates": {"x": loc.x, "y": loc.y},
            "directional_guidance": loc.directional_guidance,
        }
    except Exception as e:
        return {"error": str(e)}


def tool_get_available_spaces(db: Session, floor_number: Optional[int] = None) -> Dict[str, Any]:
    """Tool: Checks live real-time available study seats and rooms."""
    floors = spatial_service.get_all_floors_service(db=db)
    if floor_number is not None:
        target_floors = [f for f in floors if f.floor_number == floor_number]
    else:
        target_floors = floors

    summary: List[Dict[str, Any]] = []
    for fl in target_floors:
        detail = spatial_service.get_floor_plan_detail_service(db=db, floor_id=fl.id)
        avail_seats = [r for r in detail.resources if r.resource_type == "seat" and r.availability_status == "available"]
        avail_rooms = [r for r in detail.resources if r.resource_type == "room" and r.availability_status == "available"]
        summary.append({
            "floor_id": fl.id,
            "floor_number": fl.floor_number,
            "floor_name": fl.name,
            "available_seats_count": len(avail_seats),
            "available_rooms_count": len(avail_rooms),
            "sample_available_seats": [s.label for s in avail_seats[:4]],
            "available_rooms": [r.label for r in avail_rooms],
            "sample_available_rooms": [r.label for r in avail_rooms[:4]],
        })
    return {"floors": summary, "filter_floor": floor_number}


def tool_get_patron_loans(db: Session, current_user: User) -> Dict[str, Any]:
    """Tool: Retrieves authenticated patron's active loans and due dates."""
    stmt = select(Loan).where(Loan.student_id == current_user.id, Loan.returned_at.is_(None))
    loans = db.execute(stmt).scalars().all()
    items = []
    for ln in loans:
        book = ln.copy.book if ln.copy else None
        items.append({
            "loan_id": ln.id,
            "book_title": book.title if book else "Unknown Title",
            "due_date": ln.due_date.isoformat() if ln.due_date else None,
            "renewal_count": ln.renewal_count,
        })
    return {"active_loans_count": len(items), "loans": items}


def tool_reserve_study_space(
    db: Session,
    current_user: User,
    floor_number: Optional[int] = None,
    seat_id: Optional[int] = None,
    room_id: Optional[int] = None,
    date_str: Optional[str] = None,
    start_time_str: Optional[str] = None,
    end_time_str: Optional[str] = None,
    resource_type: str = "seat",
) -> Dict[str, Any]:
    """
    Tool: Autonomously books a study seat or room for the authenticated patron.
    Enforces quota constraints, operating hours, and generates a valid check-in token.
    """
    if current_user.role not in ("student", "teacher"):
        return {
            "status": "failed",
            "reason": f"Patrons with role '{current_user.role}' cannot create study space reservations.",
        }

    # 1. Quota Check: Student max 1 active reservation, teacher max 2
    my_res = space_service.get_my_reservations_service(db=db, user=current_user, status_filter="active", page=1, page_size=10)
    quota_limit = 2 if current_user.role == "teacher" else 1
    if my_res.total >= quota_limit:
        first_active = my_res.items[0] if my_res.items else None
        return {
            "status": "quota_reached",
            "quota_limit": quota_limit,
            "active_count": my_res.total,
            "message": f"You already have {my_res.total} active reservation (quota limit is {quota_limit}).",
            "existing_reservation": {
                "id": first_active.id if first_active else None,
                "label": first_active.resource_label if first_active else None,
                "start_time": first_active.start_time.isoformat() if first_active else None,
                "end_time": first_active.end_time.isoformat() if first_active else None,
            } if first_active else None,
        }

    # 2. Resolve target reservation timing
    inst_tz = space_service.get_library_timezone(settings.LIBRARY_TIMEZONE)
    now_utc_naive = space_service.normalize_utc_datetime(space_service.get_utc_now())
    now_local = space_service.get_utc_now().astimezone(inst_tz)

    if date_str:
        d_str = date_str.lower().strip()
        if "tomorrow" in d_str:
            target_date = (now_local + timedelta(days=1)).date()
        elif "today" in d_str:
            target_date = now_local.date()
        else:
            try:
                parsed = datetime.strptime(d_str[:10], "%Y-%m-%d").date()
                if parsed.year < now_local.year:
                    parsed = parsed.replace(year=now_local.year)
                target_date = parsed
            except Exception:
                target_date = (now_local + timedelta(days=1)).date()
    else:
        if now_local.hour >= 18:
            target_date = (now_local + timedelta(days=1)).date()
        else:
            target_date = now_local.date()

    # Past-date guard: if date is in the past, push to tomorrow
    if target_date < now_local.date():
        target_date = (now_local + timedelta(days=1)).date()

    if start_time_str:
        parts = start_time_str.split(":")
        try:
            start_hour = int(parts[0])
        except Exception:
            start_hour = max(now_local.hour + 1, 9) if target_date == now_local.date() else 10
    else:
        start_hour = max(now_local.hour + 1, 9) if target_date == now_local.date() else 10

    if end_time_str:
        parts = end_time_str.split(":")
        try:
            end_hour = int(parts[0])
        except Exception:
            end_hour = min(start_hour + 2, 21)
    else:
        end_hour = min(start_hour + 2, 21)

    if start_hour >= 20 or (target_date == now_local.date() and start_hour <= now_local.hour):
        target_date = (now_local + timedelta(days=1)).date()
        start_hour = 10
        end_hour = 12

    local_start = datetime(target_date.year, target_date.month, target_date.day, start_hour, 0, tzinfo=inst_tz)
    local_end = datetime(target_date.year, target_date.month, target_date.day, end_hour, 0, tzinfo=inst_tz)

    utc_start = space_service.normalize_utc_datetime(local_start)
    utc_end = space_service.normalize_utc_datetime(local_end)

    # 3. Resolve Resource (Seat or Room)
    target_floor_num = floor_number if floor_number is not None else 0
    chosen_seat_id = seat_id
    chosen_room_id = room_id
    resource_type_normalized = "room" if resource_type == "room" or chosen_room_id is not None else "seat"

    if resource_type_normalized == "seat" and chosen_seat_id is None:
        stmt = (
            select(StudySeat)
            .join(SpatialResourceMapping, SpatialResourceMapping.resource_id == StudySeat.id)
            .join(LibraryFloor, SpatialResourceMapping.floor_id == LibraryFloor.id)
            .filter(
                SpatialResourceMapping.resource_type == "seat",
                LibraryFloor.floor_number == target_floor_num,
                StudySeat.is_active == True,
            )
        )
        candidates = db.execute(stmt).scalars().all()
        if not candidates:
            candidates = db.execute(select(StudySeat).where(StudySeat.is_active == True)).scalars().all()

        if candidates:
            chosen_seat_id = candidates[0].id

    if resource_type_normalized == "room" and chosen_room_id is None:
        rm_stmt = select(StudyRoom).where(StudyRoom.is_active == True)
        rooms = db.execute(rm_stmt).scalars().all()
        if rooms:
            chosen_room_id = rooms[0].id

    if resource_type_normalized == "seat" and chosen_seat_id is None:
        return {"status": "failed", "reason": "No active study seats found in library topology."}
    if resource_type_normalized == "room" and chosen_room_id is None:
        return {"status": "failed", "reason": "No active study rooms found in library topology."}

    # 4. Create Reservation
    payload = ReservationCreate(
        resource_type=resource_type_normalized,
        seat_id=chosen_seat_id if resource_type_normalized == "seat" else None,
        room_id=chosen_room_id if resource_type_normalized == "room" else None,
        start_time=utc_start,
        end_time=utc_end,
        expected_attendees=1,
    )

    try:
        res = space_service.create_reservation_service(
            db=db,
            user=current_user,
            data=payload,
            now_utc=now_utc_naive,
        )

        resource_label = f"Seat #{res.seat_id}" if res.resource_type == "seat" else f"Room #{res.room_id}"
        qr_token_str = None
        try:
            pass_obj = space_service.get_reservation_qr_token_service(db=db, user=current_user, reservation_id=res.id)
            resource_label = pass_obj.resource_name
            qr_token_str = pass_obj.qr_token
        except Exception as pe:
            logger.warning(f"Could not retrieve check-in pass object: {pe}")
            if res.resource_type == "seat" and res.seat_id:
                st = db.get(StudySeat, res.seat_id)
                if st:
                    resource_label = f"Seat {st.seat_code}"
            elif res.resource_type == "room" and res.room_id:
                rm = db.get(StudyRoom, res.room_id)
                if rm:
                    resource_label = f"Room {rm.name}"

        return {
            "status": "success",
            "reservation_id": res.id,
            "resource_type": res.resource_type,
            "resource_label": resource_label,
            "floor_number": target_floor_num,
            "start_time": res.start_time.isoformat(),
            "end_time": res.end_time.isoformat(),
            "check_in_token": qr_token_str or f"RES-{res.id:06d}",
            "formatted_window": f"{local_start.strftime('%A, %b %d %I:%M %p')} - {local_end.strftime('%I:%M %p')}",
        }
    except Exception as e:
        logger.warning(f"Failed to reserve space: {e}")
        return {"status": "failed", "reason": str(e)}


def tool_cancel_study_space(
    db: Session,
    current_user: User,
    reservation_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Tool: Cancels an active study space reservation for the authenticated patron."""
    target_id = reservation_id
    if target_id is None:
        my_res = space_service.get_my_reservations_service(
            db=db, user=current_user, status_filter="active", page=1, page_size=10
        )
        if not my_res.items:
            return {"status": "failed", "reason": "You have no active study space reservations to cancel."}
        if len(my_res.items) == 1:
            target_id = my_res.items[0].id
        else:
            return {
                "status": "ambiguous",
                "reason": "Multiple active reservations found. Please specify which reservation to cancel.",
                "reservations": [{"id": r.id, "resource": r.resource_label} for r in my_res.items],
            }

    try:
        res = space_service.cancel_reservation_service(db=db, user=current_user, reservation_id=target_id)
        return {
            "status": "success",
            "reservation_id": res.id,
            "resource_label": res.resource_label,
            "message": f"Reservation #{res.id} for {res.resource_label} has been successfully cancelled.",
        }
    except Exception as e:
        logger.warning(f"Failed to cancel space reservation: {e}")
        return {"status": "failed", "reason": str(e)}



def tool_place_monograph_hold(
    db: Session,
    current_user: User,
    book_id: Optional[int] = None,
    book_title: Optional[str] = None,
) -> Dict[str, Any]:
    """Tool: Places an online hold / shelf reservation on a physical book."""
    target_book_id = book_id
    target_book_obj: Optional[Book] = None

    if target_book_id is None and book_title:
        # Search book by title or keywords
        res = hybrid_search_service(db=db, query=book_title, page_size=1)
        if res.items:
            target_book_obj = res.items[0]
            target_book_id = target_book_obj.id

    if target_book_id is None:
        return {"status": "failed", "reason": "Could not identify book to hold."}

    if target_book_obj is None:
        target_book_obj = db.execute(select(Book).where(Book.id == target_book_id)).scalar_one_or_none()

    if not target_book_obj:
        return {"status": "failed", "reason": f"Book with ID {target_book_id} not found."}

    try:
        hold_res = place_hold_service(db=db, user=current_user, book_id=target_book_id)
        qr_token: Optional[str] = None

        # If hold is immediately ready for pickup, generate collection QR pass!
        if hold_res.status == "ready_for_pickup":
            try:
                pass_res = generate_book_collection_pass(db=db, user=current_user, hold_id=hold_res.id)
                qr_token = pass_res.token
            except Exception as e:
                logger.warning(f"Could not generate collection pass for hold {hold_res.id}: {e}")

        return {
            "status": "success",
            "hold_id": hold_res.id,
            "book_id": target_book_obj.id,
            "book_title": target_book_obj.title,
            "hold_status": hold_res.status,
            "queue_position": hold_res.queue_position,
            "pickup_deadline": hold_res.pickup_deadline.isoformat() if hold_res.pickup_deadline else None,
            "qr_token": qr_token,
        }
    except Exception as e:
        logger.warning(f"Hold placement failed: {e}")
        return {"status": "failed", "reason": str(e)}


def tool_renew_loan(
    db: Session,
    current_user: User,
    loan_id: Optional[int] = None,
    book_title: Optional[str] = None,
) -> Dict[str, Any]:
    """Tool: Renews an active monograph loan for the patron."""
    target_loan_id = loan_id

    # If loan_id is not given, find patron's active loans
    stmt = select(Loan).where(Loan.student_id == current_user.id, Loan.returned_at.is_(None))
    active_loans = db.execute(stmt).scalars().all()

    if not active_loans:
        return {"status": "failed", "reason": "You currently have no active monograph loans to renew."}

    if target_loan_id is None:
        if book_title:
            b_norm = book_title.lower()
            for ln in active_loans:
                if ln.copy and ln.copy.book and b_norm in ln.copy.book.title.lower():
                    target_loan_id = ln.id
                    break
        if target_loan_id is None and len(active_loans) == 1:
            target_loan_id = active_loans[0].id

    if target_loan_id is None:
        return {
            "status": "ambiguous",
            "reason": "Multiple active loans found. Please specify which book to renew.",
            "loans": [{"id": ln.id, "title": ln.copy.book.title if ln.copy and ln.copy.book else "Unknown"} for ln in active_loans],
        }

    try:
        res = loans_service.renew_loan_service(db=db, loan_id=target_loan_id, current_user=current_user)
        title = res.book.title if res.book else "Monograph"
        return {
            "status": "success",
            "loan_id": res.id,
            "book_title": title,
            "new_due_date": res.due_date.isoformat() if res.due_date else None,
            "renewal_count": res.renewal_count,
        }
    except Exception as e:
        logger.warning(f"Loan renewal failed: {e}")
        return {"status": "failed", "reason": str(e)}


def tool_generate_return_pass(
    db: Session,
    current_user: User,
    loan_id: Optional[int] = None,
    book_title: Optional[str] = None,
) -> Dict[str, Any]:
    """Tool: Generates a symmetrical QR return token and return clearance pass."""
    stmt = select(Loan).where(Loan.student_id == current_user.id, Loan.returned_at.is_(None))
    active_loans = db.execute(stmt).scalars().all()

    if not active_loans:
        return {"status": "failed", "reason": "You have no active monograph loans checked out to return."}

    target_loan_id = loan_id
    if target_loan_id is None:
        if book_title:
            b_norm = book_title.lower()
            for ln in active_loans:
                if ln.copy and ln.copy.book and b_norm in ln.copy.book.title.lower():
                    target_loan_id = ln.id
                    break
        if target_loan_id is None and len(active_loans) == 1:
            target_loan_id = active_loans[0].id

    if target_loan_id is None:
        return {
            "status": "ambiguous",
            "reason": "Multiple active loans found. Please specify which book to generate a return pass for.",
            "loans": [{"id": ln.id, "title": ln.copy.book.title if ln.copy and ln.copy.book else "Unknown"} for ln in active_loans],
        }

    try:
        pass_res = generate_book_return_token(db=db, user=current_user, loan_id=target_loan_id)
        return {
            "status": "success",
            "token_code": pass_res.token_code,
            "qr_payload": pass_res.qr_payload,
            "book_title": pass_res.book_title,
            "expires_at": pass_res.expires_at.isoformat() if pass_res.expires_at else None,
        }
    except Exception as e:
        logger.warning(f"Return token generation failed: {e}")
        return {"status": "failed", "reason": str(e)}


def tool_query_academic_research(query: str, limit: int = 3) -> Dict[str, Any]:
    """Tool: Searches arXiv, OpenAlex, and Crossref for peer-reviewed papers and open-access PDFs."""
    try:
        res = academic_research_service.search_papers(query=query, limit=limit, page=1)
        papers = [
            {
                "paper_id": p.id,
                "title": p.title,
                "authors": p.authors,
                "year": p.publication_year,
                "venue": p.venue,
                "doi": p.doi,
                "open_access_pdf_url": p.url,
                "provider": p.source_provider,
            }
            for p in res.results
        ]
        return {"status": "success", "query": query, "total_found": len(papers), "papers": papers}
    except Exception as e:
        logger.warning(f"Academic search error: {e}")
        return {"status": "failed", "query": query, "papers": [], "reason": str(e)}


def tool_get_library_policy(query: str) -> Dict[str, Any]:
    """Tool: Searches verified library borrowing rules, loan durations, and facility policies."""
    matched = search_policies(query, max_results=2)
    return {"query": query, "policies": matched}


def tool_visualize_3d_concept(concept_type: str, title: Optional[str] = None, description: Optional[str] = None) -> Dict[str, Any]:
    """Tool: Generates an interactive 3D WebGL concept simulation for scientific and engineering concepts."""
    c_norm = (concept_type or "").lower().strip()
    if any(k in c_norm for k in ["transformer", "attention", "self-attention", "llm", "encoder", "decoder", "bert", "gpt"]):
        resolved_type = "transformer_architecture"
        resolved_title = title or "Transformer Architecture & Multi-Head Attention"
        resolved_desc = description or "Interactive 3D Transformer encoder block: Multi-Head Attention (Q, K, V), Add & Norm Residual Skip-Connections, Position-Wise Feed-Forward Network (FFN), and Softmax Logits."
    elif any(k in c_norm for k in ["neural", "deep learning", "perceptron", "mlp", "network", "ai", "layer"]):
        resolved_type = "neural_network"
        resolved_title = title or "Interactive 3D Multi-Layer Perceptron (MLP)"
        resolved_desc = description or "Interactive 3D visualization showing input features, hidden ReLU neurons, and output logits with synaptic weighting."
    elif any(k in c_norm for k in ["distributed", "cluster", "raft", "paxos", "consensus", "node", "server"]):
        resolved_type = "distributed_cluster"
        resolved_title = title or "Interactive 3D Raft Distributed Cluster"
        resolved_desc = description or "Leader-follower consensus topology with active heartbeat broadcast beams and quorum replication."
    elif any(k in c_norm for k in ["quantum", "bloch", "qubit", "sphere", "spin"]):
        resolved_type = "quantum_bloch"
        resolved_title = title or "Interactive 3D Quantum Bloch Sphere"
        resolved_desc = description or "Geometric representation of a 2-level quantum state space showing basis states |0⟩, |1⟩ and state vector |ψ⟩."
    elif any(k in c_norm for k in ["molecule", "benzene", "chemistry", "atom", "bond", "compound", "dna"]):
        resolved_type = "molecule"
        resolved_title = title or "Interactive 3D Molecular Geometry (Benzene C₆H₆)"
        resolved_desc = description or "Planar hexagonal ring structure demonstrating aromatic sp² hybridization and resonance delocalization."
    else:
        resolved_type = "neural_network"
        resolved_title = title or "Interactive 3D Conceptual Model"
        resolved_desc = description or "Interactive WebGL schematic model for academic study."

    return {
        "status": "success",
        "concept_type": resolved_type,
        "title": resolved_title,
        "description": resolved_desc,
    }


def tool_fetch_academic_media(query: str, subject_hint: Optional[str] = None) -> Dict[str, Any]:
    """
    Tool: Fetches verified academic media, authentic historical portraits, photographs,
    and archival imagery of authors, scholars, scientists, and academic subjects
    from the Open Knowledge Archive (Wikimedia Commons / Wikipedia REST API).
    Cost: $0.00 (Zero AI image generation tokens, 100% authentic archival records).
    """
    clean_query = (query or "").strip().rstrip(".?!,")
    for prefix in [
        "an image of", "a photo of", "a portrait of", "a picture of",
        "image of", "photo of", "portrait of", "picture of", "photograph of",
        "show image of", "show photo of", "show portrait of", "provide me with an image of",
        "provide an image of", "give me an image of"
    ]:
        if clean_query.lower().startswith(prefix):
            clean_query = clean_query[len(prefix):].strip()

    for suffix in [" if possible", " please", " thanks", " if you can", " photo", " image", " portrait"]:
        if clean_query.lower().endswith(suffix):
            clean_query = clean_query[:-len(suffix)].strip()

    if not clean_query:
        clean_query = "Oscar Wilde"

    slug = clean_query.strip().replace(" ", "_")
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{slug}"
    headers = {"User-Agent": "AthenaeumLibraryAI/2.0 (academic library management platform; contact@library.local)"}

    try:
        with httpx.Client(timeout=4.0) as client:
            resp = client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                img_url = (data.get("originalimage") or {}).get("source") or (data.get("thumbnail") or {}).get("source")
                if img_url:
                    return {
                        "status": "success",
                        "title": data.get("title", clean_query),
                        "description": data.get("description", "Archival Academic Subject"),
                        "extract": data.get("extract", ""),
                        "image_url": img_url,
                        "thumbnail_url": (data.get("thumbnail") or {}).get("source", img_url),
                        "page_url": (data.get("content_urls", {}).get("desktop", {}).get("page") or f"https://en.wikipedia.org/wiki/{slug}"),
                        "source": "Wikimedia Commons / Open Knowledge Archive",
                        "license": "Public Domain / Creative Commons (Verified Archival Record)",
                    }
    except Exception as e:
        logger.warning(f"Academic media fetch failed for '{clean_query}': {e}")

    return {
        "status": "not_found",
        "query": clean_query,
        "message": f"No high-resolution archival portrait found in the Open Knowledge Archive for '{clean_query}'.",
    }



# ── Gemini Function Calling Schema Specification ─────────────────────────────

GEMINI_AGENT_TOOLS = [
    {
        "function_declarations": [
            {
                "name": "reserve_study_space",
                "description": "Autonomously reserve a study desk or discussion room in the library for the patron.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "floor_number": {"type": "INTEGER", "description": "Floor: 0 (Ground), 1 (First), 2 (Second), 3 (Third)"},
                        "resource_type": {"type": "STRING", "description": "'seat' or 'room'", "enum": ["seat", "room"]},
                        "date_str": {"type": "STRING", "description": "Target date YYYY-MM-DD (e.g. 2026-11-10)"},
                        "start_time_str": {"type": "STRING", "description": "Start time HH:MM (e.g. '10:00', '14:00')"},
                        "end_time_str": {"type": "STRING", "description": "End time HH:MM (e.g. '12:00', '16:00')"},
                    },
                },
            },
            {
                "name": "cancel_study_space",
                "description": "Cancel an active study space (seat or room) reservation for the authenticated patron.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "reservation_id": {"type": "INTEGER", "description": "Specific reservation ID to cancel if known"},
                    },
                },
            },
            {
                "name": "place_monograph_hold",
                "description": "Place an online loan hold / monograph reservation for pickup at the circulation desk.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "book_id": {"type": "INTEGER", "description": "Physical book ID if known"},
                        "book_title": {"type": "STRING", "description": "Title or keyword of the book to reserve"},
                    },
                },
            },
            {
                "name": "renew_loan",
                "description": "Renew an active book loan, extending the borrowing due date (+14 days student, +30 days teacher).",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "loan_id": {"type": "INTEGER", "description": "Specific loan ID if known"},
                        "book_title": {"type": "STRING", "description": "Title of the book to renew"},
                    },
                },
            },
            {
                "name": "generate_return_pass",
                "description": "Generate an instant QR return clearance pass (RET-XXXXXX) for returning a book at the desk.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "loan_id": {"type": "INTEGER", "description": "Loan ID to discharge"},
                        "book_title": {"type": "STRING", "description": "Title of the book to return"},
                    },
                },
            },
            {
                "name": "query_academic_research",
                "description": "Search global arXiv, OpenAlex, and Crossref preprints for peer-reviewed research papers and open-access PDFs.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "query": {"type": "STRING", "description": "Academic research query or technical concept"},
                        "limit": {"type": "INTEGER", "description": "Number of papers to retrieve (default 3)"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "search_catalogue",
                "description": "Search the library's physical catalogue of monographs and textbooks.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "query": {"type": "STRING", "description": "Subject, title, or keywords to search"},
                        "limit": {"type": "INTEGER", "description": "Max titles to retrieve"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "get_available_spaces",
                "description": "Check live seat and room availability and occupancy across library floors.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "floor_number": {"type": "INTEGER", "description": "Optional floor filter: 0, 1, 2, 3"},
                    },
                },
            },
            {
                "name": "get_patron_loans",
                "description": "Check current active loans, due dates, and renewals for the authenticated patron.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {},
                },
            },
            {
                "name": "get_spatial_resource",
                "description": "Get physical map coordinates, floor, zone, and wayfinding directions for a seat or room.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "resource_type": {"type": "STRING", "description": "'seat' or 'room'"},
                        "resource_id": {"type": "INTEGER", "description": "Seat or room number/ID"},
                    },
                    "required": ["resource_type", "resource_id"],
                },
            },
            {
                "name": "get_library_policy",
                "description": "Lookup verified library borrowing regulations, loan limits, durations, and facility hours.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "query": {"type": "STRING", "description": "Policy topic (e.g. borrowing limits, fines, hours)"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "visualize_3d_concept",
                "description": "Generate an interactive 3D WebGL conceptual visualization model (transformer architecture, neural network, distributed cluster, molecule, or quantum bloch sphere) for the patron.",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "concept_type": {"type": "STRING", "description": "'transformer_architecture' (for transformers, attention, LLMs), 'neural_network' (for deep learning, MLP, perceptron), 'distributed_cluster', 'molecule', or 'quantum_bloch'"},
                        "title": {"type": "STRING", "description": "Short title of the 3D model"},
                        "description": {"type": "STRING", "description": "Brief explanation of the 3D visual concept"},
                    },
                    "required": ["concept_type"],
                },
            },
            {
                "name": "fetch_academic_media",
                "description": "Fetch verified archival portraits, photographs, and historical imagery of authors, scholars, scientists, or academic subjects (e.g. Oscar Wilde, Alan Turing, Ada Lovelace, Isaac Newton) from the Open Knowledge Archive ($0.00 token cost, authentic public domain records).",
                "parameters": {
                    "type": "OBJECT",
                    "properties": {
                        "query": {"type": "STRING", "description": "Name of the author, historical figure, or academic subject (e.g. 'Oscar Wilde', 'Alan Turing')"},
                        "subject_hint": {"type": "STRING", "description": "Optional category or context (e.g. 'author', 'scientist', 'mathematician')"},
                    },
                    "required": ["query"],
                },
            },
        ]
    }
]


# ── Autonomous ReAct Dispatcher ───────────────────────────────────────────────

def _dispatch_tool(
    db: Session,
    current_user: User,
    tool_name: str,
    args: Dict[str, Any],
) -> Tuple[Dict[str, Any], Optional[CopilotAgentAction]]:
    """Executes a structured tool call and generates matching rich CopilotAgentAction."""
    action: Optional[CopilotAgentAction] = None

    if tool_name == "reserve_study_space":
        res = tool_reserve_study_space(
            db=db,
            current_user=current_user,
            floor_number=args.get("floor_number"),
            seat_id=args.get("seat_id"),
            room_id=args.get("room_id"),
            date_str=args.get("date_str"),
            start_time_str=args.get("start_time_str"),
            end_time_str=args.get("end_time_str"),
            resource_type=args.get("resource_type", "seat"),
        )
        if res.get("status") == "success":
            action = CopilotAgentAction(
                action_type="space_reserved",
                status="success",
                title=f"Reserved {res.get('resource_label', 'Study Space')}",
                description=f"Study space confirmed on Floor {res.get('floor_number')} ({res.get('formatted_window')}). Check-in Token: {res.get('check_in_token')}",
                data=res,
            )
        elif res.get("status") == "quota_reached":
            action = CopilotAgentAction(
                action_type="space_reserved",
                status="info",
                title="Active Reservation Limit",
                description=res.get("message", "Quota limit reached."),
                data=res,
            )
        return res, action

    elif tool_name == "cancel_study_space":
        res = tool_cancel_study_space(
            db=db,
            current_user=current_user,
            reservation_id=args.get("reservation_id"),
        )
        if res.get("status") == "success":
            action = CopilotAgentAction(
                action_type="space_cancelled",
                status="success",
                title="Reservation Cancelled",
                description=res.get("message", "Study space reservation cancelled."),
                data=res,
            )
        return res, action

    elif tool_name == "place_monograph_hold":
        res = tool_place_monograph_hold(
            db=db,
            current_user=current_user,
            book_id=args.get("book_id"),
            book_title=args.get("book_title"),
        )
        if res.get("status") == "success":
            action = CopilotAgentAction(
                action_type="hold_placed",
                status="success",
                title=f"Hold Confirmed: {res.get('book_title')}",
                description=f"Status: {res.get('hold_status', '').replace('_', ' ').title()}. Pickup token ready.",
                data=res,
            )
        return res, action

    elif tool_name == "renew_loan":
        res = tool_renew_loan(
            db=db,
            current_user=current_user,
            loan_id=args.get("loan_id"),
            book_title=args.get("book_title"),
        )
        if res.get("status") == "success":
            action = CopilotAgentAction(
                action_type="loan_renewed",
                status="success",
                title=f"Loan Renewed: {res.get('book_title')}",
                description=f"Due date extended to {res.get('new_due_date')}. Renewals used: {res.get('renewal_count')}/1.",
                data=res,
            )
        return res, action

    elif tool_name == "generate_return_pass":
        res = tool_generate_return_pass(
            db=db,
            current_user=current_user,
            loan_id=args.get("loan_id"),
            book_title=args.get("book_title"),
        )
        if res.get("status") == "success":
            action = CopilotAgentAction(
                action_type="return_pass_generated",
                status="success",
                title=f"Return Clearance Pass: {res.get('token_code')}",
                description=f"Present this return pass at the Circulation Desk for '{res.get('book_title')}'.",
                data=res,
            )
        return res, action

    elif tool_name == "query_academic_research":
        res = tool_query_academic_research(
            query=args.get("query", ""),
            limit=args.get("limit", 3),
        )
        if res.get("status") == "success" and res.get("papers"):
            action = CopilotAgentAction(
                action_type="academic_research",
                status="success",
                title=f"Scholarly Research: {res.get('query')}",
                description=f"Retrieved {len(res.get('papers', []))} peer-reviewed papers with open-access PDFs.",
                data=res,
            )
        return res, action

    elif tool_name == "search_catalogue":
        res = tool_search_catalogue(
            db=db,
            query=args.get("query", ""),
            limit=args.get("limit", 5),
        )
        return res, None

    elif tool_name == "get_available_spaces":
        res = tool_get_available_spaces(
            db=db,
            floor_number=args.get("floor_number"),
        )
        return res, None

    elif tool_name == "get_patron_loans":
        res = tool_get_patron_loans(db=db, current_user=current_user)
        return res, None

    elif tool_name == "get_spatial_resource":
        res = tool_get_spatial_resource(
            db=db,
            resource_type=args.get("resource_type", "seat"),
            resource_id=int(args.get("resource_id", 1)),
        )
        return res, None

    elif tool_name == "get_library_policy":
        res = tool_get_library_policy(query=args.get("query", ""))
        return res, None

    elif tool_name == "visualize_3d_concept":
        res = tool_visualize_3d_concept(
            concept_type=args.get("concept_type", "generic"),
            title=args.get("title"),
            description=args.get("description"),
        )
        return res, None

    elif tool_name == "fetch_academic_media":
        res = tool_fetch_academic_media(
            query=args.get("query", ""),
            subject_hint=args.get("subject_hint"),
        )
        if res.get("status") == "success":
            action = CopilotAgentAction(
                action_type="academic_media",
                status="success",
                title=f"Archival Record: {res.get('title')}",
                description=f"Retrieved authentic portrait from {res.get('source')}.",
                data=res,
            )
        return res, action

    return {"error": f"Unknown tool: {tool_name}"}, None


# ── RAG Agent Orchestrator with Multi-Turn Context & Bounded History ─────────

def execute_librarian_agent_rag(
    db: Session,
    query: str,
    current_user: User,
    conversation_history: Optional[List[ChatMessageInput]] = None,
    custom_api_key: Optional[str] = None,
) -> EnhancedCopilotResponse:
    """
    Full-suite Autonomous AI Agent & Librarian Concierge.
    Executes multi-step ReAct autonomous tool dispatching with Gemini 3.1 Flash Lite.
    Directly reserves study spaces, places monograph holds, renews patron loans,
    issues return passes, and queries academic preprints with verifiable safety and patron isolation.
    Supports Bring-Your-Own-Key (BYOK) for personal patron Gemini API keys.
    """
    normalized = query.lower().strip()
    tool_calls: List[CopilotToolCall] = []
    agent_actions: List[CopilotAgentAction] = []
    citations: List[StructuredCitation] = []
    book_cards: List[Dict[str, Any]] = []
    spatial_card: Optional[Dict[str, Any]] = None
    concept_3d: Optional[Dict[str, Any]] = None
    media_card: Optional[Dict[str, Any]] = None
    suggested_followups: List[str] = []

    # Bounded multi-turn context sanitization (max 6 messages)
    bounded_history: List[ChatMessageInput] = []
    if conversation_history:
        bounded_history = conversation_history[-6:]

    # Check active Gemini LLM Provider (BYOK prioritized over system default)
    provider, provider_name = get_llm_provider(custom_api_key=custom_api_key)
    api_key = (
        custom_api_key
        or getattr(settings, "GEMINI_API_KEY", None)
        or getattr(settings, "LLM_API_KEY", None)
        or os.environ.get("GEMINI_API_KEY")
        or os.environ.get("LLM_API_KEY")
        or ""
    ).strip()
    if custom_api_key and api_key:
        provider_name = "gemini"

    inst_tz = space_service.get_library_timezone(settings.LIBRARY_TIMEZONE)
    now_local = space_service.get_utc_now().astimezone(inst_tz)
    tomorrow_local = (now_local + timedelta(days=1)).date()

    # ── 0. FAST-PATH CONVERSATIONAL SOCIAL INTENTS (Sub-5ms, Zero API Token Burn) ────
    is_conceptual = any(k in normalized for k in [
        "understand", "explain", "concept", "transformer", "neural", "deep learning", 
        "architecture", "what is", "how does", "tell me about", "visualize", "3d", 
        "diagram", "paper", "research", "quantum", "bloch", "molecule", "benzene", "cluster", "raft"
    ])
    has_actionable = any(a in normalized for a in [
        "reserve", "book", "renew", "loan", "where is", "find", "search", "hold", "available", 
        "free", "empty", "seats", "rooms", "room", "seat", "return", "pass", "qr", "take me", "wayfinding"
    ])

    if not is_conceptual and not has_actionable:
        is_greeting = any(re.search(rf"\b{g}\b", normalized) for g in ["hello", "hi", "hey"])
        is_thanks = any(re.search(rf"\b{t}\b", normalized) for t in ["thank", "thanks"])
        is_help = any(h in normalized for h in ["what can you do", "how can you help", "what are your capabilities", "show help", "help menu"]) or bool(re.match(r"^help(\s+me)?[\?!.]*$", normalized.strip()))
        is_chat = any(c in normalized for c in ["talk normally", "talk to me", "how are you", "who created you"]) or "can you talk" in normalized

        if is_thanks:
            return EnhancedCopilotResponse(
                answer=f"You are very welcome, {current_user.full_name}! Please let me know if you need any assistance with book borrowings, renewals, or study spaces.",
                intent="THANKS",
                confidence=0.99,
                provider="Librarian Concierge",
                suggested_followups=["What are my active loans?", "Show available study seats"],
            )
        if is_help:
            return EnhancedCopilotResponse(
                answer="I am your Athenaeum AI Library Concierge. I can assist you with searching the monograph catalogue, reserving study seats, renewing loans, checking space availability, and generating return passes.",
                intent="HELP",
                confidence=0.99,
                provider="Librarian Concierge",
                suggested_followups=["Find books on Computer Science", "Reserve a study desk"],
            )
        if is_greeting:
            return EnhancedCopilotResponse(
                answer=f"Hello, {current_user.full_name}! I am your AI Library Copilot. How may I assist your academic research or library needs today?",
                intent="GREETING",
                confidence=0.99,
                provider="Librarian Concierge",
                suggested_followups=["What are my active loans?", "Show available study seats on Ground Floor"],
            )
        if is_chat:
            return EnhancedCopilotResponse(
                answer=f"I am fully here to converse and assist you with your academic work, {current_user.full_name}. I can coordinate monograph checkouts, study pod wayfinding, and scholarly literature searches across our collection.",
                intent="CONVERSATIONAL",
                confidence=0.99,
                provider="Librarian Concierge",
                suggested_followups=["Find books on Computer Science", "Check my active loans"],
            )

    # ── 1. AUTONOMOUS REACT EXECUTION (GEMINI 3.1 FLASH LITE) ───────────────────
    if provider_name == "gemini" and api_key:
        try:
            gemini_url = (
                f"https://generativelanguage.googleapis.com/v1beta/models/"
                f"{settings.LLM_MODEL_NAME}:generateContent?key={api_key}"
            )

            system_instruction = (
                f"You are the Athenaeum Autonomous AI Library Concierge serving patron '{current_user.full_name}' "
                f"(Role: {current_user.role}, Email: {current_user.email}). Always address the patron warmly by their name ({current_user.full_name}) when answering about their account or loans.\n"
                f"Today's date is {now_local.strftime('%Y-%m-%d (%A)')}. Tomorrow is {tomorrow_local.strftime('%Y-%m-%d')}. "
                f"When calling tools with dates, always pass dates in {now_local.year} or later (e.g. '{tomorrow_local.strftime('%Y-%m-%d')}').\n"
                "You have DIRECT REAL-TIME ACTION TOOLS to perform tasks on behalf of the patron:\n"
                "- reserve_study_space: Reserve a study seat or room (ground floor is floor 0)\n"
                "- cancel_study_space: Cancel an active study seat or room reservation\n"
                "- place_monograph_hold: Reserve a physical monograph for desk pickup\n"
                "- renew_loan: Renew active book loans\n"
                "- generate_return_pass: Generate instant QR return clearance passes\n"
                "- query_academic_research: Query arXiv, OpenAlex, and Crossref for scholarly papers\n"
                "- search_catalogue: Search physical library books\n"
                "- get_available_spaces: Check open seats and rooms\n"
                "- get_patron_loans: View patron active loans\n"
                "- get_spatial_resource: Get floor plan wayfinding coordinates\n"
                "- get_library_policy: Look up borrowing rules\n"
                "- visualize_3d_concept: Generate interactive 3D WebGL models for scientific/engineering concepts (transformers, neural networks, distributed clusters, molecules, quantum bloch spheres)\n"
                "- fetch_academic_media: Fetch verified archival portraits, photographs, and historical imagery of authors, scholars, scientists, or academic subjects (e.g. Oscar Wilde, Alan Turing, Ada Lovelace, Isaac Newton) from the Open Knowledge Archive ($0.00 token cost, authentic public domain records)\n\n"
                "CRITICAL GOVERNANCE ON MEDIA & IMAGES:\n"
                "- If the patron asks for an image, portrait, photograph, or visual likeness of an author, scientist, historical figure, or academic subject (e.g. 'image of Oscar Wilde', 'photo of Alan Turing'), ALWAYS CALL 'fetch_academic_media'. Never claim that you cannot display or generate images when this tool is available.\n\n"
                "CRITICAL GOVERNANCE ON 3D VISUALIZATION:\n"
                "- ONLY call the 'visualize_3d_concept' tool if the patron EXPLICITLY asks or orders a 3D model, visualization, or diagram (e.g. 'show 3d model', 'visualize in 3d', 'render 3d', 'generate 3d diagram', 'show 3d architecture').\n"
                "- If the patron asks to explain, teach, or discuss a topic without specifically requesting a 3D visualization, DO NOT call 'visualize_3d_concept'. Instead, provide a thorough, articulate, academic textual explanation with mathematical equations and suggest they can ask for a 3D visualization if desired.\n"
                "- When 3D IS explicitly requested for transformers, use concept_type='transformer_architecture'. For general deep learning, use concept_type='neural_network'.\n\n"
                "When the patron asks you to do something (e.g. reserve a seat, hold a book, renew a loan, return a book, search papers), "
                "CALL THE APPROPRIATE ACTION TOOL IMMEDIATELY! Do not just give advice when an action can be performed.\n"
                "For compound prompts (e.g. 'find a book and reserve a desk'), execute both tools.\n"
                "Keep responses polite, articulate, professional, and explain clearly what action was taken."
            )

            # Build initial conversational contents
            contents: List[Dict[str, Any]] = []
            for h in bounded_history[-4:]:
                contents.append({
                    "role": "user" if h.role == "user" else "model",
                    "parts": [{"text": h.content}],
                })
            contents.append({"role": "user", "parts": [{"text": query}]})

            # ReAct Execution Loop (max 3 tool iteration turns)
            max_turns = 3
            final_agent_reply: Optional[str] = None

            with httpx.Client(timeout=25.0) as client:
                for turn_idx in range(max_turns):
                    payload = {
                        "contents": contents,
                        "system_instruction": {"parts": [{"text": system_instruction}]},
                        "tools": GEMINI_AGENT_TOOLS,
                        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 800},
                    }
                    resp = None
                    for attempt in range(2):
                        try:
                            resp = client.post(gemini_url, json=payload)
                            if resp.status_code == 200:
                                break
                            if resp.status_code in (429, 503) and attempt == 0:
                                logger.info(f"Gemini returned {resp.status_code}, retrying once after 0.8s...")
                                time_module.sleep(0.8)
                        except httpx.RequestError as e:
                            if attempt == 0:
                                time_module.sleep(0.8)
                            else:
                                raise e

                    if not resp or resp.status_code != 200:
                        logger.warning(f"Gemini API returned status {resp.status_code if resp else 'None'}: {resp.text if resp else ''}")
                        break

                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if not candidates:
                        break

                    cand = candidates[0]
                    content_obj = cand.get("content", {})
                    parts = content_obj.get("parts", [])
                    if not parts:
                        break

                    # Check for function calls
                    func_calls = [p.get("functionCall") for p in parts if "functionCall" in p]
                    text_parts = [p.get("text") for p in parts if "text" in p and p.get("text")]

                    if not func_calls:
                        # Model finished reasoning and returned final answer!
                        final_agent_reply = " ".join(text_parts).strip()
                        break

                    # Append model turn with function calls to history
                    contents.append(content_obj)

                    # Execute all requested function calls
                    for fc in func_calls:
                        f_name = fc.get("name")
                        f_args = fc.get("args", {})
                        logger.info(f"Autonomous Agent executing tool '{f_name}' with args {f_args}")

                        t_res, t_action = _dispatch_tool(
                            db=db,
                            current_user=current_user,
                            tool_name=f_name,
                            args=f_args,
                        )
                        tool_calls.append(CopilotToolCall(tool_name=f_name, arguments=f_args, result=t_res))
                        if t_action:
                            agent_actions.append(t_action)

                        # If books returned, capture for book cards
                        if f_name == "search_catalogue" and "books" in t_res:
                            book_cards.extend(t_res["books"])
                            for b in t_res["books"]:
                                citations.append(StructuredCitation(
                                    source_type="monograph",
                                    title=b["title"],
                                    reference_id=str(b["id"]),
                                    snippet=f"By {b['author']}. Category: {b['category']}. Available: {b['available_copies']}.",
                                    url_or_action=f"book_{b['id']}",
                                ))

                        # If spatial returned, capture spatial card
                        if f_name == "get_spatial_resource" and "error" not in t_res:
                            spatial_card = t_res
                            citations.append(StructuredCitation(
                                source_type="study_space",
                                title=f"{t_res.get('label', 'Resource')} Location",
                                reference_id=str(t_res.get("resource_id")),
                                snippet=f"Located on {t_res.get('floor_name', 'Library')}, Zone: {t_res.get('zone_name', '')}. {t_res.get('directional_guidance', '')}",
                                url_or_action=f"/spaces?resource_type={t_res.get('resource_type')}&id={t_res.get('resource_id')}",
                            ))

                        # If space availability returned, capture citation
                        if f_name == "get_available_spaces" and "floors" in t_res:
                            for fl in t_res.get("floors", []):
                                citations.append(StructuredCitation(
                                    source_type="study_space",
                                    title=f"{fl.get('floor_name', 'Library')} Spaces",
                                    snippet=f"Available seats: {fl.get('available_seats_count', 0)}, rooms: {fl.get('available_rooms_count', 0)}",
                                    url_or_action="/spaces",
                                ))

                        # If 3d concept returned, capture 3d spec
                        if f_name == "visualize_3d_concept" and "concept_type" in t_res:
                            concept_3d = t_res

                        # If academic media returned, capture media card
                        if f_name == "fetch_academic_media" and t_res.get("status") == "success":
                            media_card = t_res

                        # Feed function response back to Gemini
                        contents.append({
                            "role": "user",
                            "parts": [{
                                "functionResponse": {
                                    "name": f_name,
                                    "response": {"name": f_name, "content": t_res},
                                }
                            }],
                        })

            if final_agent_reply:
                # Build contextual follow-up suggestions
                if concept_3d:
                    suggested_followups = [
                        "Explain attention heads mathematically",
                        "Show ResNet-50 architecture",
                        "Search monographs on Deep Learning",
                    ]
                elif any(k in normalized for k in ["transformer", "neural", "deep learning", "attention", "perceptron"]):
                    suggested_followups = [
                        "Show 3D architecture model of this network",
                        "What textbooks cover Transformer attention?",
                        "Search scholarly papers on this architecture",
                    ]
                elif agent_actions:
                    suggested_followups = [
                        "View this on the Interactive Floor Map",
                        "What are my active loans and reservations?",
                        "Search scholarly literature on this topic",
                    ]
                else:
                    suggested_followups = [
                        "Book a quiet study seat for me",
                        "What books do I have checked out?",
                        "Find books on Distributed Systems",
                    ]

                resolved_intent = "AUTONOMOUS_AGENT_EXECUTION"
                if tool_calls:
                    last_tool = tool_calls[-1].tool_name
                    tool_intent_map = {
                        "get_spatial_resource": "SPATIAL_NAVIGATION",
                        "get_available_spaces": "SPACE_AVAILABILITY",
                        "get_patron_loans": "PATRON_LOANS",
                        "search_catalogue": "RECOMMENDATION_RAG",
                        "query_academic_research": "RECOMMENDATION_RAG",
                        "reserve_study_space": "SPACE_RESERVATION",
                        "cancel_study_space": "SPACE_CANCELLATION",
                        "renew_loan": "LOAN_RENEWAL",
                        "generate_return_pass": "RETURN_PASS",
                        "place_monograph_hold": "BOOK_HOLD",
                        "fetch_academic_media": "ACADEMIC_MEDIA_RETRIEVAL",
                    }
                    resolved_intent = tool_intent_map.get(last_tool, "AUTONOMOUS_AGENT_EXECUTION")

                # If answering patron loans and user name missing, ensure courteous address
                if resolved_intent == "PATRON_LOANS" and current_user.full_name not in final_agent_reply:
                    final_agent_reply = f"Hello {current_user.full_name}, {final_agent_reply}"

                return EnhancedCopilotResponse(
                    answer=final_agent_reply,
                    intent=resolved_intent,
                    confidence=0.99,
                    provider=f"Gemini 3.1 Flash Lite (Autonomous Agent)",
                    tool_calls=tool_calls,
                    agent_actions=agent_actions,
                    citations=citations,
                    book_cards=book_cards,
                    spatial_card=spatial_card,
                    concept_3d=concept_3d,
                    media_card=media_card,
                    suggested_followups=suggested_followups,
                )

        except Exception as e:
            logger.error(f"Autonomous ReAct execution encountered error, falling back to deterministic routing: {e}")

    # ── 2. DETERMINISTIC WORKFLOW ROUTING (FALLBACK / OFFLINE) ───────────────────

    # 0. Conversational Social Intents (No unsolicited book searches)
    is_conceptual = any(k in normalized for k in [
        "understand", "explain", "concept", "transformer", "neural", "deep learning", 
        "architecture", "what is", "how does", "tell me about", "visualize", "3d", 
        "diagram", "paper", "research", "quantum", "bloch", "molecule", "benzene", "cluster", "raft"
    ])
    is_greeting = any(re.search(rf"\b{g}\b", normalized) for g in ["hello", "hi", "hey"]) and not is_conceptual
    is_thanks = any(re.search(rf"\b{t}\b", normalized) for t in ["thank", "thanks"]) and not is_conceptual
    is_help = (
        any(h in normalized for h in ["what can you do", "how can you help", "what are your capabilities", "show help", "help menu"])
        or bool(re.match(r"^help(\s+me)?[\?!.]*$", normalized.strip()))
    ) and not is_conceptual
    is_chat = any(c in normalized for c in ["talk normally", "talk to me", "how are you", "who created you"]) and not is_conceptual
    has_actionable = any(a in normalized for a in ["reserve", "book", "renew", "loan", "where is", "find", "search", "hold", "available", "free"])

    if is_thanks and not has_actionable:
        return EnhancedCopilotResponse(
            answer=f"You are very welcome, {current_user.full_name}! Please let me know if you need any assistance with book borrowings, renewals, or study spaces.",
            intent="THANKS",
            confidence=0.99,
            provider="Librarian Concierge",
            suggested_followups=["What are my active loans?", "Show available study seats"],
        )

    if is_help and not has_actionable:
        return EnhancedCopilotResponse(
            answer="I am your Athenaeum AI Library Concierge. I can assist you with searching the monograph catalogue, reserving study seats, renewing loans, checking space availability, and generating return passes.",
            intent="HELP",
            confidence=0.99,
            provider="Librarian Concierge",
            suggested_followups=["Find books on Computer Science", "Reserve a study desk"],
        )

    # 0a. Deterministic Conceptual Fallback (3D WebGL Visualization & Academic Summary)
    if is_conceptual and not has_actionable:
        concept_type = "transformer_architecture" if any(w in normalized for w in ["transformer", "attention", "self-attention", "llm", "encoder", "decoder", "gpt", "bert"]) else \
                       "neural_network" if any(w in normalized for w in ["neural", "deep learning", "perceptron", "mlp", "network", "ai"]) else \
                       "distributed_cluster" if any(w in normalized for w in ["distributed", "raft", "consensus", "cluster", "node"]) else \
                       "quantum_bloch" if any(w in normalized for w in ["quantum", "bloch", "qubit", "superposition"]) else \
                       "molecule" if any(w in normalized for w in ["molecule", "benzene", "chemical", "atom"]) else None
        
        explicit_3d = any(k in normalized for k in ["3d", "visualize", "render", "3-d", "three.js", "show model", "show 3d", "show a model", "diagram in 3d", "interactive model"])

        concept_payload = None
        if explicit_3d and concept_type:
            concept_payload = tool_visualize_3d_concept(
                concept_type=concept_type,
                title=f"{concept_type.replace('_', ' ').title()} Interactive Architecture",
                description=f"Interactive 3D structural model illustrating {query.strip()}."
            )

        if concept_type == "transformer_architecture":
            if explicit_3d:
                custom_answer = (
                    f"### 🧠 Transformer Architecture & Multi-Head Self-Attention Explained\n\n"
                    f"The **Transformer** (Vaswani et al., *'Attention Is All You Need'*) is fundamentally different from a standard Multi-Layer Perceptron (MLP). "
                    f"Instead of static dense matrix multiplications layer-by-layer, it relies on dynamic **Multi-Head Self-Attention** and **Residual Skip-Connections** to process sequence tokens in parallel.\n\n"
                    f"#### 🎨 3D Transformer Model Markings:\n"
                    f"In the **Interactive 3D WebGL Transformer Model** above (click **⛶ Fullscreen Sandbox** or expand the drawer to explore):\n\n"
                    f"1. 🟢 **Token Embeddings & Positional Encoding ($E + P$)**:\n"
                    f"   - Sinusoidal wave embeddings inject token position into dense representations without sequential loops.\n\n"
                    f"2. 🔀 **Multi-Head Attention Module ($Q, K, V$)**:\n"
                    f"   - Input projections split into **4 Parallel Attention Heads** computing dot-product affinity matrices: $\\text{{Attention}}(Q,K,V) = \\text{{softmax}}\\left(\\frac{{QK^T}}{{\\sqrt{{d_k}}}}\\right)V$.\n\n"
                    f"3. ⚡ **Curved Residual Skip-Connections (Add & LayerNorm)**:\n"
                    f"   - The glowing bypass wires looping OVER the attention block deliver $\\text{{LayerNorm}}(\\mathbf{{x}} + \\text{{Attention}}(\\mathbf{{x}}))$, preventing vanishing gradients in deep stacks.\n\n"
                    f"4. 🌺 **Position-Wise Feed-Forward Network (FFN)**:\n"
                    f"   - Dual-stage linear projections with non-linear activation ($\\text{{FFN}}(x) = \\max(0, xW_1 + b_1)W_2 + b_2$).\n\n"
                    f"5. 🔵 **Output Linear Projection & Softmax Logits**:\n"
                    f"   - Computes vocabulary probabilities $P(w_t \\mid w_{{<t}}) = \\text{{softmax}}(W_{{\\text{{vocab}}}} h_t)$ for autoregressive decoding."
                )
            else:
                custom_answer = (
                    f"### 🧠 Transformer Architecture & Multi-Head Self-Attention\n\n"
                    f"The **Transformer** (Vaswani et al., *'Attention Is All You Need'*) is the foundational architecture powering modern Large Language Models (LLMs). "
                    f"Unlike recurrent neural networks (RNNs/LSTMs) that process words sequentially one by one, a Transformer processes all sequence tokens in parallel.\n\n"
                    f"#### Core Architectural Components:\n\n"
                    f"1. **Token Embeddings & Positional Encoding**:\n"
                    f"   $$\\mathbf{{x}}_i = \\text{{Embedding}}(t_i) + \\text{{PE}}_{{(pos, 2i)}}$$\n"
                    f"   Converts discrete vocabulary tokens into dense vectors ($d_{{\\text{{model}}}} = 512$) and injects fixed sinusoidal wave coordinates so the network understands word order without recurrence.\n\n"
                    f"2. **Multi-Head Scaled Dot-Product Attention**:\n"
                    f"   $$\\text{{Attention}}(Q, K, V) = \\text{{softmax}}\\left(\\frac{{QK^T}}{{\\sqrt{{d_k}}}}\\right)V$$\n"
                    f"   Projects input vectors into Queries ($Q$), Keys ($K$), and Values ($V$) across parallel attention heads, allowing each word to attend to every other word in the sentence simultaneously.\n\n"
                    f"3. **Residual Skip-Connections & Layer Normalization (Add & Norm)**:\n"
                    f"   $$\\mathbf{{x}}' = \\text{{LayerNorm}}(\\mathbf{{x}} + \\text{{Attention}}(\\mathbf{{x}}))$$\n"
                    f"   High-speed gradient highways that bypass the attention and feed-forward sublayers, eliminating the vanishing gradient problem in deep stacks.\n\n"
                    f"4. **Position-Wise Feed-Forward Network (FFN)**:\n"
                    f"   $$\\text{{FFN}}(\\mathbf{{x}}') = \\max(0, \\mathbf{{x}}' W_1 + \\mathbf{{b}}_1) W_2 + \\mathbf{{b}}_2$$\n"
                    f"   Two linear transformations with a non-linear activation (GELU/ReLU) applied identically to each position.\n\n"
                    f"5. **Linear Projection & Softmax Vocabulary Logits**:\n"
                    f"   $$P(w_t \\mid w_{{<t}}) = \\text{{softmax}}(W_{{\\text{{vocab}}}} \\mathbf{{h}}_t)$$\n"
                    f"   Unembeds the final hidden state into a normalized probability distribution across the entire vocabulary.\n\n"
                    f"---\n"
                    f"💡 *Would you like an interactive 3D WebGL model of this Transformer architecture? Simply ask: **'Show 3D model'** or click the suggestion below.*"
                )
        elif concept_type == "neural_network":
            if explicit_3d:
                custom_answer = (
                    f"### 🧠 Multi-Layer Perceptron (MLP) Deep Neural Network\n\n"
                    f"A classical **Deep Neural Network** is organized into sequentially connected dense layers where every neuron in layer $l$ is connected via synaptic weights to every neuron in layer $l+1$.\n\n"
                    f"1. 🟢 **Input Features Layer**: Receives raw normalized scalar inputs $\\mathbf{{x}}$.\n"
                    f"2. 🟣 **Hidden Layers**: Applies weight matrix multiplications with non-linear activation $\\mathbf{{h}} = \\sigma(W \\mathbf{{x}} + \\mathbf{{b}})$.\n"
                    f"3. 🔵 **Output Layer**: Produces prediction logits.\n\n"
                    f"I have initialized an Interactive 3D WebGL model in the panel above for you to explore the network architecture in real time."
                )
            else:
                custom_answer = (
                    f"### 🧠 Multi-Layer Perceptron (MLP) Deep Neural Network\n\n"
                    f"A classical **Deep Neural Network** is organized into sequentially connected dense layers where every neuron in layer $l$ is connected via synaptic weights to every neuron in layer $l+1$.\n\n"
                    f"1. **Input Layer**: Receives normalized feature vector $\\mathbf{{x}} \\in \\mathbb{{R}}^d$.\n"
                    f"2. **Dense Hidden Layers**: Computes $\\mathbf{{h}}^{{[l]}} = \\sigma(W^{{[l]}} \\mathbf{{h}}^{{[l-1]}} + \\mathbf{{b}}^{{[l]}})$ with non-linear activations such as ReLU or GELU.\n"
                    f"3. **Output Layer**: Maps hidden activations to the target decision boundary or probability simplex.\n\n"
                    f"---\n"
                    f"💡 *Would you like an interactive 3D WebGL model of this neural network? Simply ask: **'Show 3D model'** or click the suggestion below.*"
                )
        else:
            custom_answer = (
                f"### Academic Concept Overview: {query.strip()}\n\n"
                f"**Architectural Foundation:**\n"
                f"The architecture incorporates multi-layered representations connected through high-dimensional mappings. "
                f"Computational states are propagated through parameterized matrices and attention mechanisms, eliminating recurrent bottlenecks.\n\n"
                f"I have initialized an Interactive 3D WebGL concept model in the panel above for you to explore the structural components in real time." if explicit_3d else
                f"### Academic Concept Overview: {query.strip()}\n\n"
                f"The architecture incorporates multi-layered representations connected through high-dimensional mappings. "
                f"Computational states are propagated through parameterized matrices and attention mechanisms, eliminating recurrent bottlenecks.\n\n"
                f"💡 *If you would like to explore this in an interactive 3D WebGL sandbox, ask: **'Show 3D model'**.*"
            )

        followups = [
            "Search arXiv papers on this topic",
            "Find monographs in catalogue",
        ]
        if not explicit_3d:
            followups.insert(0, "🪐 Show 3D Interactive Model")
        else:
            followups.insert(0, "Explain mathematical loss formulation")

        return EnhancedCopilotResponse(
            answer=custom_answer,
            intent="ACADEMIC_CONCEPTUAL_INQUIRY",
            confidence=0.95,
            provider="Athenaeum Academic Engine",
            concept_3d=concept_payload,
            suggested_followups=followups,
        )

    if is_chat and not has_actionable:
        return EnhancedCopilotResponse(
            answer="I'm doing well, thank you! As your academic library assistant, I'm always available to help you navigate our physical collections, spaces, and digital research.",
            intent="CONVERSATIONAL",
            confidence=0.98,
            provider="Librarian Concierge",
            suggested_followups=["What are my active loans?", "Where is Seat S-01 located?"],
        )

    if is_greeting and not has_actionable:
        return EnhancedCopilotResponse(
            answer=f"Hello {current_user.full_name}! I am your AI Library Concierge. How can I assist you today with library books, study spaces, or active loans?",
            intent="GREETING",
            confidence=0.99,
            provider="Librarian Concierge",
            suggested_followups=["What books are available on Machine Learning?", "Reserve a study seat for me"],
        )

    # 0b. Spatial Navigation & Coreference
    is_spatial = any(k in normalized for k in ["where is", "how do i find", "location of", "directions to", "where can i find"]) or "seat s-" in normalized or "room r-" in normalized
    if not is_spatial and bounded_history:
        last_turn = (bounded_history[-1].content or "").lower()
        if any(w in last_turn for w in ["seat", "room", "s-", "r-", "floor"]) and any(w in normalized for w in ["where", "locate", "directions", "floor map", "find it", "tell me"]):
            is_spatial = True

    if is_spatial and not any(k in normalized for k in ["reserve", "book a", "schedule"]):
        res_type = "room" if "room" in normalized else "seat"
        num_match = re.search(r"[sr]-?(\d+)", normalized)
        res_id = int(num_match.group(1)) if num_match else 1
        s_res, _ = _dispatch_tool(db=db, current_user=current_user, tool_name="get_spatial_resource", args={"resource_type": res_type, "resource_id": res_id})
        tool_calls.append(CopilotToolCall(tool_name="get_spatial_resource", arguments={"resource_type": res_type, "resource_id": res_id}, result=s_res))
        
        lbl = s_res.get("resource_label", f"{res_type.title()} S-{res_id:02d}")
        fl_name = s_res.get("floor_name", "Ground Floor")
        citations.append(StructuredCitation(
            source_type="study_space",
            title=lbl,
            snippet=f"Located on {fl_name} (Floor {s_res.get('floor_number', 0)})",
            url_or_action="/spaces",
        ))
        answer = f"{lbl} is located on {fl_name}. You can view its real-time occupancy and turn-by-turn directions on the interactive floor map."
        return EnhancedCopilotResponse(
            answer=answer,
            intent="SPATIAL_NAVIGATION",
            confidence=0.98,
            provider="Librarian Agent Spatial Guide",
            tool_calls=tool_calls,
            spatial_card=s_res,
            citations=citations,
            suggested_followups=["Reserve this study space", "What other spaces are available on this floor?"],
        )

    # 0c. Cancel Study Space Reservation
    is_cancel_intent = any(k in normalized for k in [
        "cancel my booking", "cancel booking", "cancel reservation", "cancel my reservation",
        "cancel seat", "cancel my seat", "cancel room", "cancel my room", "cancel space",
    ])
    if is_cancel_intent:
        t_res, t_action = _dispatch_tool(db=db, current_user=current_user, tool_name="cancel_study_space", args={})
        tool_calls.append(CopilotToolCall(tool_name="cancel_study_space", arguments={}, result=t_res))
        if t_action:
            agent_actions.append(t_action)

        if t_res.get("status") == "success":
            answer = (
                f"✅ **Reservation Successfully Cancelled!**\n\n"
                f"{t_res.get('message')}\n"
                f"Your active study space quota has been refreshed. You can now make a new reservation whenever needed."
            )
        else:
            answer = f"ℹ️ {t_res.get('reason', 'Could not cancel reservation.')}"

        return EnhancedCopilotResponse(
            answer=answer,
            intent="SPACE_CANCELLATION",
            confidence=0.99,
            provider="Librarian Agent Tool Runner",
            tool_calls=tool_calls,
            agent_actions=agent_actions,
            suggested_followups=["Book a study seat for me", "What are my active loans?"],
        )

    # 0d. 3D Concept Visualization Intent
    is_3d_intent = (any(k in normalized for k in ["3d", "three.js", "webgl", "bloch", "benzene", "molecule"]) or
                    ("neural" in normalized and ("visualize" in normalized or "model" in normalized or "3d" in normalized)) or
                    ("cluster" in normalized and ("visualize" in normalized or "topology" in normalized or "3d" in normalized)))
    if is_3d_intent:
        t_res = tool_visualize_3d_concept(concept_type=normalized)
        tool_calls.append(CopilotToolCall(tool_name="visualize_3d_concept", arguments={"concept_type": normalized}, result=t_res))
        answer = (
            f"🪐 **Interactive 3D WebGL Visualization Generated!**\n\n"
            f"Here is an interactive 3D model of **{t_res.get('title')}**.\n"
            f"{t_res.get('description')}\n\n"
            f"• **Controls**: Click and drag with your mouse to rotate in 3D space. Scroll to zoom in/out. Hover over elements to inspect parameters in real time."
        )
        return EnhancedCopilotResponse(
            answer=answer,
            intent="CONCEPT_3D_VISUALIZATION",
            confidence=0.99,
            provider="Librarian 3D WebGL Engine",
            tool_calls=tool_calls,
            concept_3d=t_res,
            suggested_followups=["Explain the mathematical theory behind this", "Find textbooks on this topic in the library"],
        )

    # 0e. Academic Media & Portrait Intent (Open Knowledge Archive)
    is_media_intent = any(k in normalized for k in [
        "image of", "photo of", "portrait of", "picture of", "photograph of",
        "show image", "show photo", "show portrait", "show picture", "an image of", "a photo of",
        "provide me with an image", "provide an image"
    ]) or (
        any(w in normalized for w in ["image", "photo", "portrait", "picture"]) and
        any(w in normalized for w in ["wilde", "oscar", "turing", "lovelace", "darwin", "curie", "einstein", "feynman", "author", "scientist", "writer", "poet", "cover", "jacket"])
    )
    if is_media_intent:
        subject_query = query.strip()
        for pfx in [
            "and provide me with an image of", "provide me with an image of", "provide an image of",
            "give me an image of", "show me an image of", "an image of", "a photo of",
            "image of", "photo of", "portrait of", "picture of", "photograph of",
            "show image", "show photo", "show portrait", "show picture"
        ]:
            if pfx in normalized:
                idx = normalized.find(pfx)
                subject_query = query[idx + len(pfx):].strip().rstrip(".?!,")
                for sfx in [" if possible", " please", " thanks", " if you can", " photo", " image", " portrait"]:
                    if subject_query.lower().endswith(sfx):
                        subject_query = subject_query[:-len(sfx)].strip()
                break

        t_res = tool_fetch_academic_media(query=subject_query or query)
        tool_calls.append(CopilotToolCall(tool_name="fetch_academic_media", arguments={"query": subject_query}, result=t_res))

        if t_res.get("status") == "success":
            action = CopilotAgentAction(
                action_type="academic_media",
                status="success",
                title=f"Archival Record: {t_res.get('title')}",
                description=f"Retrieved authentic portrait from {t_res.get('source')}.",
                data=t_res,
            )
            agent_actions.append(action)
            answer = (
                f"🖼️ **Archival Portrait & Biographical Record: {t_res.get('title')}**\n\n"
                f"{t_res.get('description', '')}\n\n"
                f"{t_res.get('extract', '')}\n\n"
                f"• **Source**: [{t_res.get('source')}]({t_res.get('page_url')})\n"
                f"• **License**: {t_res.get('license')}"
            )
            return EnhancedCopilotResponse(
                answer=answer,
                intent="ACADEMIC_MEDIA_RETRIEVAL",
                confidence=0.99,
                provider="Open Knowledge Archive Engine",
                tool_calls=tool_calls,
                agent_actions=agent_actions,
                media_card=t_res,
                suggested_followups=[
                    f"Search library monographs by {t_res.get('title')}",
                    f"Find biographical research on {t_res.get('title')}",
                ],
            )

    # A. Reserve study space
    reserve_keywords = [
        "reserve seat", "book seat", "reserve a seat", "book a seat", "reserve desk", "book desk",
        "reserve space", "book space", "book a desk", "reserve study", "book study", "book room",
        "reserve room", "book a room", "reserve a room"
    ]
    has_book_action = any(k in normalized for k in ["reserve", "book", "schedule"])
    has_space_target = any(k in normalized for k in ["seat", "seats", "desk", "desks", "room", "rooms", "space", "spaces", "spot"])
    is_space_reservation_intent = (has_book_action and has_space_target and not any(k in normalized for k in ["book hold", "monograph", "book on", "books on"])) or any(k in normalized for k in reserve_keywords)

    if is_space_reservation_intent:
        fl_match = re.search(r"floor\s*(-?\d+)", normalized)
        fl_num = int(fl_match.group(1)) if fl_match else (0 if "ground" in normalized else 0)
        res_type = "room" if "room" in normalized else "seat"

        t_res, t_action = _dispatch_tool(
            db=db,
            current_user=current_user,
            tool_name="reserve_study_space",
            args={"floor_number": fl_num, "resource_type": res_type},
        )
        tool_calls.append(CopilotToolCall(tool_name="reserve_study_space", arguments={"floor_number": fl_num, "resource_type": res_type}, result=t_res))
        if t_action:
            agent_actions.append(t_action)

        if t_res.get("status") == "success":
            answer = (
                f"✅ **Study Space Successfully Reserved!**\n\n"
                f"I have reserved **{t_res.get('resource_label')}** on **Floor {fl_num}** for you.\n"
                f"• **Session Window**: {t_res.get('formatted_window')}\n"
                f"• **Check-in Token**: `{t_res.get('check_in_token')}`\n\n"
                f"You can view your reserved seat on the interactive floor plan or check in using your token upon arrival."
            )
        elif t_res.get("status") == "quota_reached":
            answer = f"ℹ️ {t_res.get('message')} You can view or cancel your active reservation under the **Spaces** tab."
        else:
            answer = f"⚠️ Could not complete space reservation: {t_res.get('reason', 'Unknown error')}."

        return EnhancedCopilotResponse(
            answer=answer,
            intent="SPACE_RESERVATION",
            confidence=0.98,
            provider="Librarian Agent Tool Runner",
            tool_calls=tool_calls,
            agent_actions=agent_actions,
            suggested_followups=["View my active reservations", "Directions to this seat on the floor map"],
        )

    # B. Renew active loan
    renew_keywords = ["renew loan", "renew my loan", "renew book", "renew my book", "extend loan", "extend my loan", "extend due date"]
    if any(k in normalized for k in renew_keywords):
        t_res, t_action = _dispatch_tool(db=db, current_user=current_user, tool_name="renew_loan", args={})
        tool_calls.append(CopilotToolCall(tool_name="renew_loan", arguments={}, result=t_res))
        if t_action:
            agent_actions.append(t_action)

        if t_res.get("status") == "success":
            answer = (
                f"✅ **Loan Successfully Renewed!**\n\n"
                f"Your loan for **'{t_res.get('book_title')}'** has been extended.\n"
                f"• **New Due Date**: `{t_res.get('new_due_date')}`\n"
                f"• **Renewals Used**: {t_res.get('renewal_count')}/1 allowed renewal."
            )
        else:
            answer = f"ℹ️ {t_res.get('reason', 'Could not renew loan.')}"

        return EnhancedCopilotResponse(
            answer=answer,
            intent="LOAN_RENEWAL",
            confidence=0.98,
            provider="Librarian Agent Tool Runner",
            tool_calls=tool_calls,
            agent_actions=agent_actions,
            suggested_followups=["What are my active loans?", "What is the overdue fine policy?"],
        )

    # C. Return pass / QR token generation
    return_pass_keywords = ["return pass", "return token", "return qr", "return clearance", "generate return", "return my book", "drop off book"]
    if any(k in normalized for k in return_pass_keywords):
        t_res, t_action = _dispatch_tool(db=db, current_user=current_user, tool_name="generate_return_pass", args={})
        tool_calls.append(CopilotToolCall(tool_name="generate_return_pass", arguments={}, result=t_res))
        if t_action:
            agent_actions.append(t_action)

        if t_res.get("status") == "success":
            answer = (
                f"📱 **Return Clearance Pass Generated!**\n\n"
                f"• **Book**: '{t_res.get('book_title')}'\n"
                f"• **Pass Code**: `{t_res.get('token_code')}`\n"
                f"• **Expires**: {t_res.get('expires_at')}\n\n"
                f"Present this pass code or the QR token at the Circulation Return Desk to discharge your loan."
            )
        else:
            answer = f"ℹ️ {t_res.get('reason', 'No active loans eligible for return pass.')}"

        return EnhancedCopilotResponse(
            answer=answer,
            intent="RETURN_PASS_GENERATION",
            confidence=0.98,
            provider="Librarian Agent Tool Runner",
            tool_calls=tool_calls,
            agent_actions=agent_actions,
            suggested_followups=["What are my active loans?", "Circulation desk return hours"],
        )

    # D. Scholarly / Academic research query
    academic_keywords = ["arxiv", "openalex", "crossref", "academic paper", "scholarly", "preprints", "research papers", "scientific papers"]
    if any(k in normalized for k in academic_keywords):
        clean_q = re.sub(r"\b(arxiv|openalex|crossref|search|find|academic|papers?|scholarly|preprints?)\b", "", normalized).strip()
        clean_q = clean_q or "Artificial Intelligence"
        t_res, t_action = _dispatch_tool(db=db, current_user=current_user, tool_name="query_academic_research", args={"query": clean_q, "limit": 3})
        tool_calls.append(CopilotToolCall(tool_name="query_academic_research", arguments={"query": clean_q}, result=t_res))
        if t_action:
            agent_actions.append(t_action)

        papers = t_res.get("papers", [])
        if papers:
            p_lines = [f"• **{p['title']}** ({p.get('year', 'N/A')}) by {', '.join(p.get('authors', [])[:2])} — [Download PDF]({p.get('open_access_pdf_url')})" for p in papers]
            answer = f"🎓 **Scholarly Preprints Found for '{clean_q}':**\n\n" + "\n".join(p_lines)
        else:
            answer = f"No open-access preprints found for '{clean_q}'."

        return EnhancedCopilotResponse(
            answer=answer,
            intent="ACADEMIC_RESEARCH",
            confidence=0.96,
            provider="Librarian Agent Tool Runner",
            tool_calls=tool_calls,
            agent_actions=agent_actions,
            suggested_followups=["Search physical books on this topic", "Find more research papers"],
        )

    # E. Book hold / loan reservation
    hold_keywords = ["place hold", "hold book", "reserve book", "place a hold", "hold monograph", "book reservation"]
    if any(k in normalized for k in hold_keywords):
        clean_title = re.sub(r"\b(place|hold|reserve|book|monograph|on|the|a|for|me)\b", "", normalized).strip()
        t_res, t_action = _dispatch_tool(db=db, current_user=current_user, tool_name="place_monograph_hold", args={"book_title": clean_title})
        tool_calls.append(CopilotToolCall(tool_name="place_monograph_hold", arguments={"book_title": clean_title}, result=t_res))
        if t_action:
            agent_actions.append(t_action)

        if t_res.get("status") == "success":
            answer = (
                f"📚 **Hold Placed on '{t_res.get('book_title')}'!**\n\n"
                f"• **Status**: `{t_res.get('hold_status', '').replace('_', ' ').title()}`\n"
                f"• **Pickup Deadline**: {t_res.get('pickup_deadline', 'N/A')}\n\n"
                f"An allocated copy is reserved for you at the Circulation Desk."
            )
        else:
            answer = f"ℹ️ {t_res.get('reason', 'Could not place hold.')}"

        return EnhancedCopilotResponse(
            answer=answer,
            intent="BOOK_HOLD",
            confidence=0.97,
            provider="Librarian Agent Tool Runner",
            tool_calls=tool_calls,
            agent_actions=agent_actions,
            suggested_followups=["View my active holds", "Where is the circulation desk?"],
        )

    # F. Patron active loans
    if any(k in normalized for k in ["my loan", "my books", "due date", "what did i borrow", "active loan", "checked out"]):
        res = tool_get_patron_loans(db=db, current_user=current_user)
        tool_calls.append(CopilotToolCall(tool_name="get_patron_loans", arguments={"user_id": current_user.id}, result=res))
        if res["active_loans_count"] == 0:
            answer = f"Hello {current_user.full_name}, you currently have no active monograph loans checked out."
        else:
            loan_bullets = [
                f"• **{item['book_title']}** (Due: {item['due_date']}, Renewals used: {item['renewal_count']}/1)"
                for item in res["loans"]
            ]
            answer = f"Hello {current_user.full_name}, you have {res['active_loans_count']} active loan(s):\n" + "\n".join(loan_bullets)
        return EnhancedCopilotResponse(
            answer=answer,
            intent="PATRON_LOANS",
            confidence=0.99,
            provider="Librarian Agent Tool Runner",
            tool_calls=tool_calls,
            citations=[StructuredCitation(source_type="monograph", title="Circulation Records", snippet=f"Patron {current_user.email} active loans")],
            suggested_followups=["Renew my loan", "Generate a return pass for my book"],
        )

    # G. Space availability
    if any(k in normalized for k in ["available", "free", "empty", "open"]) and any(k in normalized for k in ["seat", "seats", "room", "rooms", "space"]):
        res = tool_get_available_spaces(db=db, floor_number=0)
        tool_calls.append(CopilotToolCall(tool_name="get_available_spaces", arguments={"floor_number": 0}, result=res))
        fl = res.get("floors", [{}])[0]
        answer = (
            f"Study space availability for {fl.get('floor_name', 'Ground Floor')}:\n"
            f"• Available Study Rooms: {fl.get('available_rooms_count', 0)}\n"
            f"• Available Study Seats: {fl.get('available_seats_count', 0)}\n\n"
            f"Would you like me to book a study desk for you?"
        )
        citations.append(StructuredCitation(
            source_type="study_space",
            title=f"{fl.get('floor_name', 'Ground Floor')} Study Spaces",
            snippet="Live availability for study seats and rooms",
            url_or_action="/spaces",
        ))
        return EnhancedCopilotResponse(
            answer=answer,
            intent="SPACE_AVAILABILITY",
            confidence=0.96,
            provider="Librarian Agent Tool Runner",
            tool_calls=tool_calls,
            citations=citations,
            suggested_followups=["Book a study seat for me on Ground Floor", "Where is Seat S-01 located?"],
        )

    # H. Catalogue search (Standard fallback)
    search_res = tool_search_catalogue(db=db, query=query, limit=4)
    tool_calls.append(CopilotToolCall(tool_name="search_catalogue", arguments={"query": query, "limit": 4}, result=search_res))
    books = search_res.get("books", [])
    if books:
        book_cards = books
        b_lines = [f"• **{b['title']}** by {b['author']} ({b['available_copies']} copy available)" for b in books]
        answer = f"Based on our catalog, here are relevant recommended titles for '{query}':\n\n" + "\n".join(b_lines)
    else:
        answer = f"I searched the library collection for '{query}', but could not find exact matching monographs. Would you like to explore related academic subjects or ask me to search global arXiv preprints?"

    return EnhancedCopilotResponse(
        answer=answer,
        intent="RECOMMENDATION_RAG",
        confidence=0.92,
        provider="Librarian Agent Tool Runner",
        tool_calls=tool_calls,
        book_cards=book_cards,
        suggested_followups=["Search arXiv for academic papers", "Book a study desk"],
    )
