"""
Service module for PILLAR 3 (Intelligent Librarian Agent) & PILLAR 5 (RAG Recommendation Assistant).
Orchestrates structured tool calls (spatial location, availability, hybrid search, policy lookup),
assembles verified RAG context, and provides explainable recommendations with citations.
Supports bounded multi-turn conversational context and coreference resolution.
"""
from datetime import datetime
import json
import logging
import re
from typing import Any, Dict, List, Optional
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Book, BookCopy, LibraryFloor, Loan, SpatialResourceMapping, StudyRoom, StudySeat, StudyZone, User
from app.schemas import (
    ChatMessageInput,
    CopilotToolCall,
    EnhancedCopilotResponse,
    StructuredCitation,
)
from app.services import spatial as spatial_service
from app.services.copilot import get_llm_provider, get_policy_sections, search_policies
from app.services.semantic import hybrid_search_service

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Structured Tool Registry ──────────────────────────────────────────────────

def tool_search_catalogue(db: Session, query: str, limit: int = 5) -> Dict[str, Any]:
    """Tool: Searches library catalogue using hybrid lexical and semantic search."""
    res = hybrid_search_service(db=db, query=query, page_size=limit)
    items = [
        {
            "id": b.id,
            "title": b.title,
            "author": b.author,
            "isbn": b.isbn,
            "category": b.category,
            "available_copies": getattr(b, "available_copies", 0),
        }
        for b in res.items
    ]
    return {"query": query, "total_found": len(items), "books": items}


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


# ── RAG Agent Orchestrator with Multi-Turn Context & Bounded History ─────────

def execute_librarian_agent_rag(
    db: Session,
    query: str,
    current_user: User,
    conversation_history: Optional[List[ChatMessageInput]] = None,
) -> EnhancedCopilotResponse:
    """
    Genuine tool-calling librarian agent with multi-step orchestration and RAG.
    Resolves coreferences across bounded conversational history (max 6 messages / 3 turns),
    routes intents deterministically, and verifies real-time state against live database models.
    """
    normalized = query.lower().strip()
    tool_calls: List[CopilotToolCall] = []
    citations: List[StructuredCitation] = []
    book_cards: List[Dict[str, Any]] = []
    spatial_card: Optional[Dict[str, Any]] = None
    suggested_followups: List[str] = []

    # Bounded multi-turn context sanitization (max 6 messages)
    bounded_history: List[ChatMessageInput] = []
    if conversation_history:
        bounded_history = conversation_history[-6:]

    # Coreference & Follow-up Detection
    has_spatial_followup = any(p in normalized for p in [
        "there", "get there", "directions there", "how do i get there",
        "wayfinding there", "take me there", "where is that", "to there", "directions"
    ])
    has_recommendation_followup = any(p in normalized for p in [
        "more like those", "more like that", "more like this", "more like these",
        "other books like", "similar books", "tell me more about", "first recommendation",
        "first one", "second one"
    ])

    # ── 0. SOCIAL CONVERSATIONAL & CAPABILITY INTENTS ─────────────────────────
    filler_stripped = re.sub(r"^(ok(ay)?|so|well|umm*|uhh*)\b[\s,;!?-]*", "", normalized, flags=re.IGNORECASE).strip()

    greeting_match = re.search(r"^(hello|hi|hey|greetings|good\s+(morning|afternoon|evening)|howdy|sup)\b[\s,;!?-]*", filler_stripped)
    is_pure_greeting = False
    if greeting_match:
        remainder = filler_stripped[greeting_match.end():].strip()
        remainder_cleaned = re.sub(r"[^\w\s]", "", remainder).strip()
        if not remainder_cleaned or remainder_cleaned in ["there", "copilot", "assistant", "bot", "library", "ai", "hello", "hey"]:
            is_pure_greeting = True
    elif normalized in ["hey", "hi", "hello", "ok so hey hello", "hey hello", "hello there", "hi there", "greetings"]:
        is_pure_greeting = True

    if is_pure_greeting:
        provider, provider_name = get_llm_provider()
        suggested_followups = [
            "What books do I currently have checked out?",
            "What is the borrowing duration and limit?",
            "Find books on Distributed Systems",
        ]
        if provider_name != "fallback":
            try:
                system_inst = "You are the Athenaeum AI Library Copilot. Keep responses professional, warm, concise, and helpful."
                prompt = (
                    f"The user '{current_user.full_name}' greeted you with: '{query}'. "
                    "Respond warmly, naturally, and concisely in 2-3 sentences. Introduce yourself as the Athenaeum AI Library Copilot. "
                    "Invite them to search our catalog, locate study spaces, or check active loan records."
                )
                answer = provider.generate(prompt=prompt, system_instruction=system_inst, timeout=6.0)
                active_provider = f"Gemini ({provider_name})"
            except Exception as e:
                logger.warning("Gemini greeting failed, using deterministic fallback: %s", e)
                answer = (
                    f"Hello, {current_user.full_name}! I am your **Athenaeum AI Library Copilot**.\n\n"
                    "I am connected directly to our verified collection of monographs, live physical copy availability, "
                    "campus floor plans, and your personal loan records. How can I assist your research today?"
                )
                active_provider = "Librarian Agent Tool Runner"
        else:
            answer = (
                f"Hello, {current_user.full_name}! I am your **Athenaeum AI Library Copilot**.\n\n"
                "I am connected directly to our verified collection of monographs, live physical copy availability, "
                "campus floor plans, and your personal loan records. How can I assist your research today?"
            )
            active_provider = "Librarian Agent Tool Runner"

        return EnhancedCopilotResponse(
            answer=answer,
            intent="GREETING",
            confidence=0.99,
            provider=active_provider,
            tool_calls=[],
            citations=[],
            suggested_followups=suggested_followups,
        )

    # Thanks intent
    if any(k in normalized for k in ["thank you", "thanks", "thx", "appreciate it", "thank u"]):
        return EnhancedCopilotResponse(
            answer=f"You're very welcome, {current_user.full_name}! Let me know if you need any assistance with book reservations, study spaces, or borrowing policies.",
            intent="THANKS",
            confidence=0.98,
            provider="Librarian Agent Tool Runner",
            suggested_followups=["What are my active loans?", "Where are available study seats?"],
        )

    # Goodbye intent
    if any(k in normalized for k in ["goodbye", "bye", "see you", "farewell", "cya", "have a good day"]):
        return EnhancedCopilotResponse(
            answer="Goodbye! Have a productive study session, and feel free to reopen the Copilot anytime you have questions.",
            intent="GOODBYE",
            confidence=0.98,
            provider="Librarian Agent Tool Runner",
            suggested_followups=["Find books on Computer Science"],
        )

    # Help / capabilities intent
    if any(k in normalized for k in ["what can you do", "who are you", "help me", "how to use", "how does this work", "copilot features"]):
        answer = (
            "Here is how I can assist you as your **AI Library Copilot**:\n\n"
            "• **Catalogue & Hybrid Search**: Ask for monographs on any topic or author (e.g. *'Find books on Machine Learning'*).\n"
            "• **Study Space Wayfinding**: Inquire about seat or room locations (e.g. *'Where is Seat S-01?'* or *'Available rooms on floor 1'*).\n"
            "• **Circulation & Due Dates**: Check your personal active loans (e.g. *'What are my active loans?'*).\n"
            "• **Borrowing Regulations**: Clarify loan limits, durations, and return policies (e.g. *'What is the borrowing duration?'*)."
        )
        return EnhancedCopilotResponse(
            answer=answer,
            intent="HELP",
            confidence=0.98,
            provider="Librarian Agent Tool Runner",
            suggested_followups=["What are my active loans?", "Where is Seat S-01 located?", "What is the borrowing limit?"],
        )

    # ── 1. PATRON LOANS INTENT ────────────────────────────────────────────────
    # Strict patron isolation: always derived from authenticated current_user
    if any(k in normalized for k in [
        "my loan", "my books", "due date", "what did i borrow", "when is my book due",
        "active loan", "active loans", "checked out", "borrowed books", "renew my book",
        "my borrowed"
    ]):
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
            suggested_followups=["How do I renew my loans?", "What are the overdue fine policies?"],
        )

    # ── 2. SPACE AVAILABILITY INTENT (MF-AI-01 Fix) ───────────────────────────
    # Evaluated before monograph search to prevent room/seat availability queries from falling through.
    availability_keywords = ["available", "availability", "free", "empty", "open", "vacant", "vacancy", "occupancy", "unoccupied"]
    space_keywords = ["room", "rooms", "seat", "seats", "space", "spaces", "desk", "desks"]

    has_availability_word = any(k in normalized for k in availability_keywords)
    has_space_word = any(k in normalized for k in space_keywords)

    is_availability_intent = (has_availability_word and has_space_word) or any(
        phrase in normalized for phrase in [
            "study space", "free space", "empty room", "available seat", "available room",
            "any rooms", "any seats", "room availability", "seat availability",
            "which rooms", "which study rooms", "are there rooms", "are there seats"
        ]
    )

    if is_availability_intent:
        # Extract optional floor filter from query
        target_floor: Optional[int] = None
        fl_match = re.search(r"floor\s*(-?\d+)", normalized)
        if fl_match:
            target_floor = int(fl_match.group(1))
        elif "ground floor" in normalized or "ground" in normalized:
            target_floor = 0
        elif "first floor" in normalized:
            target_floor = 1
        elif "second floor" in normalized:
            target_floor = 2
        elif "third floor" in normalized:
            target_floor = 3
        elif "basement" in normalized:
            target_floor = -1

        res = tool_get_available_spaces(db=db, floor_number=target_floor)
        tool_calls.append(CopilotToolCall(
            tool_name="get_available_spaces",
            arguments={"floor_number": target_floor},
            result=res,
        ))

        floors_data = res.get("floors", [])
        asking_specifically_for_rooms = any(w in normalized for w in ["room", "rooms"])

        if not floors_data:
            floor_label = f"Floor {target_floor}" if target_floor is not None else "any floor"
            answer = f"No active floor layout or telemetry found for {floor_label}."
        elif target_floor is not None:
            fl = floors_data[0]
            fl_name = fl["floor_name"]
            rooms_count = fl["available_rooms_count"]
            seats_count = fl["available_seats_count"]
            rooms_list = fl.get("available_rooms", [])

            if asking_specifically_for_rooms and not any(w in normalized for w in ["seat", "seats"]):
                if rooms_count > 0:
                    answer = (
                        f"On {fl_name} (Floor {fl['floor_number']}), there are {rooms_count} study room(s) available right now:\n"
                        + "\n".join([f"• {r}" for r in rooms_list])
                        + f"\n\nAdditionally, {seats_count} study seat(s) are open on this floor."
                    )
                else:
                    answer = f"There are currently 0 study rooms available on {fl_name} (Floor {fl['floor_number']}). However, {seats_count} study seat(s) are available."
            else:
                sample_seats = ", ".join(fl.get("sample_available_seats", []))
                answer = (
                    f"Study space availability for {fl_name} (Floor {fl['floor_number']}):\n"
                    f"• Available Study Rooms: {rooms_count}\n"
                    f"• Available Study Seats: {seats_count}"
                )
                if sample_seats:
                    answer += f" (e.g., {sample_seats})"
                if rooms_list:
                    answer += f"\n• Open Rooms: {', '.join(rooms_list)}"
        else:
            # Multi-floor overview
            if asking_specifically_for_rooms and not any(w in normalized for w in ["seat", "seats"]):
                fl_summaries = []
                for fl in floors_data:
                    r_count = fl["available_rooms_count"]
                    r_names = fl.get("available_rooms", [])
                    r_detail = f"({', '.join(r_names)})" if r_names else ""
                    fl_summaries.append(f"{fl['floor_name']}: {r_count} room(s) available {r_detail}".strip())
                answer = "Here is the current study room availability across library floors:\n• " + "\n• ".join(fl_summaries)
            else:
                fl_summaries = [
                    f"{fl['floor_name']}: {fl['available_seats_count']} seats, {fl['available_rooms_count']} rooms available"
                    for fl in floors_data
                ]
                answer = "Here is the current study space occupancy status across library floors:\n• " + "\n• ".join(fl_summaries)

        citations.append(StructuredCitation(
            source_type="study_space",
            title="Live Study Space Telemetry",
            snippet=answer[:250],
            url_or_action="spaces_tab",
        ))
        return EnhancedCopilotResponse(
            answer=answer,
            intent="SPACE_AVAILABILITY",
            confidence=0.96,
            provider="Librarian Agent Tool Runner",
            tool_calls=tool_calls,
            citations=citations,
            suggested_followups=[
                "Book a study space on Ground Floor",
                "Where is Room 101 located?",
                "Show me silent study zones",
            ],
        )

    # ── 3. SPATIAL WAYFINDING & LOCATION INTENT ───────────────────────────────
    # Resolves physical coordinates and directional guidance for seats, rooms, and zones.
    # Supports coreference resolution ("directions there", "how do i get there") from history.
    target_seat_num: Optional[int] = None
    target_room_ident: Optional[str] = None

    seat_match = re.search(r"s[-_]?(\d+)", normalized) or re.search(r"seat\s*[-_]?\s*(\d+)", normalized)
    if seat_match:
        target_seat_num = int(seat_match.group(1))

    room_match = re.search(r"room\s*[-_]?\s*([a-zA-Z0-9]+)", normalized)
    if room_match:
        target_room_ident = room_match.group(1)

    # Coreference resolution for spatial pronouns ("there", "directions there")
    if target_seat_num is None and target_room_ident is None and has_spatial_followup:
        for prev_msg in reversed(bounded_history):
            prev_text = prev_msg.content.lower()
            prev_seat = re.search(r"s[-_]?(\d+)", prev_text) or re.search(r"seat\s*[-_]?\s*(\d+)", prev_text)
            if prev_seat:
                target_seat_num = int(prev_seat.group(1))
                break
            prev_room = re.search(r"room\s*[-_]?\s*([a-zA-Z0-9]+)", prev_text)
            if prev_room:
                target_room_ident = prev_room.group(1)
                break

    is_spatial_intent = (
        target_seat_num is not None
        or target_room_ident is not None
        or any(k in normalized for k in [
            "where is", "how do i find", "location", "floor plan", "wayfinding",
            "directions to", "directions there", "take me to", "how to get to"
        ])
    )

    if is_spatial_intent:
        if target_seat_num is not None:
            # Query study seat
            res = tool_get_spatial_resource(db=db, resource_type="seat", resource_id=target_seat_num)
            tool_calls.append(CopilotToolCall(
                tool_name="get_spatial_resource",
                arguments={"resource_type": "seat", "resource_id": target_seat_num},
                result=res,
            ))
            if "error" not in res:
                spatial_card = res
                citations.append(StructuredCitation(
                    source_type="study_space",
                    title=f"Floor Plan Directory - Seat S-{target_seat_num:02d}",
                    reference_id=f"seat_{target_seat_num}",
                    snippet=res.get("directional_guidance", ""),
                    url_or_action=f"floor_{res.get('floor_number')}",
                ))
                answer = f"Seat S-{target_seat_num:02d} is located on {res.get('floor_name')}, within {res.get('zone_name')}. {res.get('directional_guidance')}"
                suggested_followups = ["Show me the shortest wayfinding path", "Are there nearby seats with power outlets?"]
                return EnhancedCopilotResponse(
                    answer=answer,
                    intent="SPATIAL_NAVIGATION",
                    confidence=0.98,
                    provider="Librarian Agent Tool Runner",
                    tool_calls=tool_calls,
                    citations=citations,
                    spatial_card=spatial_card,
                    suggested_followups=suggested_followups,
                )

        if target_room_ident is not None:
            # Query study room from DB
            stmt = select(StudyRoom).where(
                or_(
                    StudyRoom.room_code.ilike(f"%{target_room_ident}%"),
                    StudyRoom.name.ilike(f"%{target_room_ident}%"),
                    StudyRoom.id == (int(target_room_ident) if target_room_ident.isdigit() else -1),
                )
            )
            rm_obj = db.execute(stmt).scalars().first()
            if rm_obj:
                res = tool_get_spatial_resource(db=db, resource_type="room", resource_id=rm_obj.id)
                tool_calls.append(CopilotToolCall(
                    tool_name="get_spatial_resource",
                    arguments={"resource_type": "room", "resource_id": rm_obj.id},
                    result=res,
                ))
                if "error" not in res:
                    spatial_card = res
                    citations.append(StructuredCitation(
                        source_type="study_space",
                        title=f"Floor Plan Directory - {rm_obj.name}",
                        reference_id=f"room_{rm_obj.id}",
                        snippet=res.get("directional_guidance", ""),
                        url_or_action=f"floor_{res.get('floor_number')}",
                    ))
                    answer = f"{rm_obj.name} ({rm_obj.room_code}) is located on {res.get('floor_name')}, within {res.get('zone_name')}. {res.get('directional_guidance')}"
                    return EnhancedCopilotResponse(
                        answer=answer,
                        intent="SPATIAL_NAVIGATION",
                        confidence=0.98,
                        provider="Librarian Agent Tool Runner",
                        tool_calls=tool_calls,
                        citations=citations,
                        spatial_card=spatial_card,
                        suggested_followups=["Book this study room", "Show me other rooms on this floor"],
                    )

        if any(k in normalized for k in ["where is", "how do i find", "floor plan", "wayfinding", "location"]):
            floors = spatial_service.get_all_floors_service(db=db)
            fl_names = [f"Floor {f.floor_number} ({f.name})" for f in floors]
            answer = (
                f"You can explore interactive floor plans across the library:\n• "
                + "\n• ".join(fl_names)
                + "\n\nPlease select a floor in the Wayfinding view, or ask for a specific seat (e.g. 'Where is Seat S-01?') or study room."
            )
            citations.append(StructuredCitation(
                source_type="study_space",
                title="Floor Plan Directory",
                snippet=answer[:200],
                url_or_action="floor_0",
            ))
            return EnhancedCopilotResponse(
                answer=answer,
                intent="SPATIAL_NAVIGATION",
                confidence=0.90,
                provider="Librarian Agent Tool Runner",
                citations=citations,
                suggested_followups=["Where is Seat S-01 located?", "Which study rooms are available on floor 0?"],
            )

    # ── 4. POLICY & LIBRARY RULES INTENT ──────────────────────────────────────
    matched_policies = search_policies(query, max_results=2)
    if matched_policies and any(k in normalized for k in ["policy", "rule", "limit", "how many", "duration", "hours", "return", "fine", "penalty", "visitor"]):
        pol = matched_policies[0]
        answer = f"According to library policy on **{pol['title']}**:\n\n{pol['content']}"
        citations.append(StructuredCitation(source_type="policy", title=pol["title"], snippet=pol["content"][:200]))
        return EnhancedCopilotResponse(
            answer=answer,
            intent="POLICY_INQUIRY",
            confidence=0.96,
            provider="Librarian Agent Tool Runner",
            citations=citations,
            suggested_followups=["Can teachers borrow more books than students?", "What are the library hours?"],
        )

    # ── 5. BIBLIOGRAPHIC DISCOVERY & HYBRID RAG RECOMMENDATIONS ───────────────
    # Coreference resolution for follow-up recommendation queries ("more like those")
    catalogue_query = query
    if has_recommendation_followup and bounded_history:
        for prev_msg in reversed(bounded_history):
            if prev_msg.role == "user" and prev_msg.content != query:
                catalogue_query = prev_msg.content
                break

    search_res = tool_search_catalogue(db=db, query=catalogue_query, limit=4)
    tool_calls.append(CopilotToolCall(tool_name="search_catalogue", arguments={"query": catalogue_query, "limit": 4}, result=search_res))
    books = search_res.get("books", [])
    provider, provider_name = get_llm_provider()
    active_provider = "Librarian Agent Tool Runner"

    if books:
        book_cards = books
        for b in books:
            citations.append(StructuredCitation(
                source_type="monograph",
                title=b["title"],
                reference_id=str(b["id"]),
                snippet=f"By {b['author']}. Category: {b['category']}. Available copies: {b['available_copies']}.",
                url_or_action=f"book_{b['id']}",
            ))
        book_list = [f"• **{b['title']}** by {b['author']} ({b['available_copies']} copy available)" for b in books]
        default_answer = f"Based on our catalog, here are relevant recommended titles for '{catalogue_query}':\n\n" + "\n".join(book_list) + "\n\nYou can click on any title to view details or place a reservation hold."

        if provider_name != "fallback":
            try:
                holdings_summary = "\n".join([
                    f"- '{b['title']}' by {b['author']} (Category: {b['category']}, Available copies: {b['available_copies']})"
                    for b in books
                ])
                prompt = (
                    f"<verified_catalog_holdings>\n{holdings_summary}\n</verified_catalog_holdings>\n\n"
                    f"User Inquiry: {query}\n\n"
                    "Based strictly on the verified catalog items above, write a concise, professional recommendation response. "
                    "Mention the title, author, and available copy count for each recommended book. Do not fabricate books outside this list."
                )
                system_inst = "You are the Athenaeum AI Library Copilot. Ground recommendations strictly in the verified library holdings provided."
                llm_reply = provider.generate(prompt=prompt, system_instruction=system_inst, timeout=8.0)
                answer = llm_reply
                active_provider = f"Gemini ({provider_name})"
            except Exception as e:
                logger.warning("Gemini recommendation synthesis failed: %s", e)
                answer = default_answer
        else:
            answer = default_answer

        suggested_followups = ["Tell me more about the first recommendation", "Where is this located on the floor plan?"]
    else:
        if provider_name != "fallback":
            try:
                prompt = f"The user asked: '{query}'. We searched the library catalog and found no matching physical books. Write a polite, helpful 2-sentence response explaining this and suggesting related topics or asking a librarian."
                answer = provider.generate(prompt=prompt, system_instruction="You are Athenaeum AI Library Copilot.", timeout=6.0)
                active_provider = f"Gemini ({provider_name})"
            except Exception:
                answer = f"I searched the library collection for '{catalogue_query}', but could not find exact matching monographs. Would you like to explore related academic subjects or consult a librarian?"
        else:
            answer = f"I searched the library collection for '{catalogue_query}', but could not find exact matching monographs. Would you like to explore related academic subjects or consult a librarian?"
        suggested_followups = ["Browse Computer Science subjects", "Search by author name"]

    return EnhancedCopilotResponse(
        answer=answer,
        intent="RECOMMENDATION_RAG",
        confidence=0.92,
        provider=active_provider,
        tool_calls=tool_calls,
        citations=citations,
        book_cards=book_cards,
        suggested_followups=suggested_followups,
    )
