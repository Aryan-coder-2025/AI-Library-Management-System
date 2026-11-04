"""
Deterministic demonstration spatial layout seeder.
Seeds:
- 4 Library Floors (Ground, 1st, 2nd, 3rd)
- Published floor plans with structural architectural SVG elements
- 100% complete spatial mapping for all 8 Study Zones, 150 Seats, and 10 Rooms
- Wayfinding nodes and navigation edges

DISCLOSURE:
ILLUSTRATIVE DEMONSTRATION LAYOUT — NOT A SURVEYED BUILDING PLAN.
Used for digital wayfinding and space discovery demonstration.
"""
from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    FloorPlan,
    FloorPlanElement,
    LibraryFloor,
    SpatialResourceMapping,
    StudyRoom,
    StudySeat,
    StudyZone,
    WayfindingEdge,
    WayfindingNode,
)
from app.utils.date import get_utc_now


FLOOR_DEFINITIONS = [
    {
        "floor_number": 0,
        "name": "Ground Floor",
        "description": "Main entrance, welcome reception, café, circulation desk, and Ground Floor Deep Focus Room.",
        "display_order": 0,
        "width": 1000.0,
        "height": 700.0,
    },
    {
        "floor_number": 1,
        "name": "1st Floor",
        "description": "Collaborative commons, north reading terrace, group seminar suites (Ada, Turing, Hopper).",
        "display_order": 1,
        "width": 1000.0,
        "height": 700.0,
    },
    {
        "floor_number": 2,
        "name": "2nd Floor",
        "description": "Digital innovation lab, graduate research carrels, study studios (Shannon, Knuth, Dijkstra, Liskov).",
        "display_order": 2,
        "width": 1000.0,
        "height": 700.0,
    },
    {
        "floor_number": 3,
        "name": "3rd Floor",
        "description": "Silent study tower wing, multimedia suites, math alcove, research chambers (von Neumann, Lamport, Goldwasser).",
        "display_order": 3,
        "width": 1000.0,
        "height": 700.0,
    },
]


def seed_spatial_data(db: Session) -> Dict[str, int]:
    """
    Populates floor plans, elements, resource mappings, and wayfinding graphs.
    Idempotent: skips if floors already exist.
    """
    existing_floors = db.execute(select(LibraryFloor)).scalars().all()
    if existing_floors:
        return {"floors": len(existing_floors), "status": "already_seeded"}

    now = get_utc_now()
    floors_by_num: Dict[int, LibraryFloor] = {}

    # 1. Create Floors
    for f_def in FLOOR_DEFINITIONS:
        fl = LibraryFloor(
            floor_number=f_def["floor_number"],
            name=f_def["name"],
            description=f_def["description"],
            display_order=f_def["display_order"],
            width=f_def["width"],
            height=f_def["height"],
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        db.add(fl)
        db.flush()
        floors_by_num[f_def["floor_number"]] = fl

    # Prefetch existing resources
    zones_by_code = {z.zone_code: z for z in db.execute(select(StudyZone)).scalars().all()}
    rooms_by_code = {r.room_code: r for r in db.execute(select(StudyRoom)).scalars().all()}
    seats_by_zone_id: Dict[int, List[StudySeat]] = {}
    for seat in db.execute(select(StudySeat).order_by(StudySeat.id.asc())).scalars().all():
        seats_by_zone_id.setdefault(seat.zone_id, []).append(seat)

    total_elements = 0
    total_mappings = 0
    total_nodes = 0
    total_edges = 0

    # 2. Populate Layouts, Elements, Mappings, and Wayfinding per floor
    for fl_num, fl in floors_by_num.items():
        # Create FloorPlan
        plan = FloorPlan(
            floor_id=fl.id,
            version=1,
            status="published",
            title=f"{fl.name} Authoritative Layout",
            description=f"Primary published demonstration spatial layout for {fl.name}.",
            svg_viewbox="0 0 1000 700",
            published_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(plan)
        db.flush()
        fl.published_layout_id = plan.id

        # Common Architectural Elements (Outer Boundary, Core Stairs, Restrooms)
        common_elements = [
            # Outer walls
            FloorPlanElement(
                floor_id=fl.id,
                layout_id=plan.id,
                element_type="wall",
                label="Perimeter Wall",
                geometry_type="rect",
                geometry_data={"x": 0.05, "y": 0.07, "width": 0.90, "height": 0.86},
                style_properties={"fill": "#f8fafc", "stroke": "#475569", "strokeWidth": 3},
                display_order=1,
            ),
            # Stairs & Elevators
            FloorPlanElement(
                floor_id=fl.id,
                layout_id=plan.id,
                element_type="stairs",
                label="Stairs & Elevator Core",
                geometry_type="rect",
                geometry_data={"x": 0.82, "y": 0.38, "width": 0.10, "height": 0.16},
                style_properties={"fill": "#e2e8f0", "stroke": "#64748b", "strokeWidth": 2},
                display_order=5,
            ),
            # Restrooms
            FloorPlanElement(
                floor_id=fl.id,
                layout_id=plan.id,
                element_type="restroom",
                label="Restrooms",
                geometry_type="rect",
                geometry_data={"x": 0.08, "y": 0.76, "width": 0.10, "height": 0.12},
                style_properties={"fill": "#f1f5f9", "stroke": "#94a3b8", "strokeWidth": 1.5},
                display_order=5,
            ),
        ]

        if fl_num == 0:
            # Main Entrance
            common_elements.append(
                FloorPlanElement(
                    floor_id=fl.id,
                    layout_id=plan.id,
                    element_type="entrance",
                    label="Main Campus Entrance",
                    geometry_type="rect",
                    geometry_data={"x": 0.44, "y": 0.90, "width": 0.12, "height": 0.03},
                    style_properties={"fill": "#22c55e", "stroke": "#15803d", "strokeWidth": 2},
                    display_order=10,
                )
            )
            # Service Desk
            common_elements.append(
                FloorPlanElement(
                    floor_id=fl.id,
                    layout_id=plan.id,
                    element_type="service_desk",
                    label="Welcome & Circulation Desk",
                    geometry_type="rect",
                    geometry_data={"x": 0.40, "y": 0.70, "width": 0.20, "height": 0.08},
                    style_properties={"fill": "#e0e7ff", "stroke": "#4f46e5", "strokeWidth": 2},
                    display_order=8,
                )
            )
            # Cafe
            common_elements.append(
                FloorPlanElement(
                    floor_id=fl.id,
                    layout_id=plan.id,
                    element_type="facility",
                    label="Athenaeum Café & Lounge",
                    geometry_type="rect",
                    geometry_data={"x": 0.08, "y": 0.12, "width": 0.18, "height": 0.20},
                    style_properties={"fill": "#fef3c7", "stroke": "#d97706", "strokeWidth": 1.5},
                    display_order=4,
                )
            )

        for el in common_elements:
            db.add(el)
            total_elements += 1

        # Zone & Resource Mappings for this floor
        if fl_num == 0:
            # Zone 0: Ground Floor Deep Focus Room (25 seats)
            z = zones_by_code.get("ZONE-G-SILENT")
            if z:
                # Zone boundary element
                db.add(
                    FloorPlanElement(
                        floor_id=fl.id,
                        layout_id=plan.id,
                        element_type="zone_boundary",
                        label=z.name,
                        geometry_type="rect",
                        geometry_data={"x": 0.30, "y": 0.12, "width": 0.48, "height": 0.48},
                        style_properties={"fill": "#f0fdf4", "stroke": "#22c55e", "strokeWidth": 2, "strokeDasharray": "6 4"},
                        display_order=2,
                    )
                )
                total_elements += 1

                # Map Zone
                db.add(
                    SpatialResourceMapping(
                        floor_id=fl.id,
                        resource_type="zone",
                        resource_id=z.id,
                        label=z.name,
                        x=0.54,
                        y=0.15,
                        width=0.48,
                        height=0.48,
                    )
                )
                total_mappings += 1

                # Map 25 seats in 5x5 grid
                z_seats = seats_by_zone_id.get(z.id, [])
                for idx, s in enumerate(z_seats):
                    row = idx // 5
                    col = idx % 5
                    sx = 0.34 + col * 0.08
                    sy = 0.20 + row * 0.075
                    db.add(
                        SpatialResourceMapping(
                            floor_id=fl.id,
                            resource_type="seat",
                            resource_id=s.id,
                            label=s.seat_code,
                            x=round(sx, 3),
                            y=round(sy, 3),
                            width=0.04,
                            height=0.04,
                        )
                    )
                    total_mappings += 1

        elif fl_num == 1:
            # 1st Floor Commons (35 seats) + North Reading Terrace (20 seats)
            # Rooms: ROOM-101 (Ada), ROOM-102 (Turing), ROOM-103 (Hopper)
            z1 = zones_by_code.get("ZONE-1-COLLAB")
            if z1:
                db.add(
                    FloorPlanElement(
                        floor_id=fl.id,
                        layout_id=plan.id,
                        element_type="zone_boundary",
                        label=z1.name,
                        geometry_type="rect",
                        geometry_data={"x": 0.08, "y": 0.12, "width": 0.42, "height": 0.52},
                        style_properties={"fill": "#eff6ff", "stroke": "#3b82f6", "strokeWidth": 2, "strokeDasharray": "6 4"},
                        display_order=2,
                    )
                )
                total_elements += 1
                db.add(
                    SpatialResourceMapping(
                        floor_id=fl.id,
                        resource_type="zone",
                        resource_id=z1.id,
                        label=z1.name,
                        x=0.29,
                        y=0.15,
                        width=0.42,
                        height=0.52,
                    )
                )
                total_mappings += 1
                for idx, s in enumerate(seats_by_zone_id.get(z1.id, [])):
                    row = idx // 7
                    col = idx % 7
                    db.add(
                        SpatialResourceMapping(
                            floor_id=fl.id,
                            resource_type="seat",
                            resource_id=s.id,
                            label=s.seat_code,
                            x=round(0.11 + col * 0.055, 3),
                            y=round(0.20 + row * 0.085, 3),
                            width=0.035,
                            height=0.035,
                        )
                    )
                    total_mappings += 1

            z2 = zones_by_code.get("ZONE-1-QUIET")
            if z2:
                db.add(
                    FloorPlanElement(
                        floor_id=fl.id,
                        layout_id=plan.id,
                        element_type="zone_boundary",
                        label=z2.name,
                        geometry_type="rect",
                        geometry_data={"x": 0.54, "y": 0.12, "width": 0.26, "height": 0.52},
                        style_properties={"fill": "#f0fdf4", "stroke": "#10b981", "strokeWidth": 2, "strokeDasharray": "6 4"},
                        display_order=2,
                    )
                )
                total_elements += 1
                db.add(
                    SpatialResourceMapping(
                        floor_id=fl.id,
                        resource_type="zone",
                        resource_id=z2.id,
                        label=z2.name,
                        x=0.67,
                        y=0.15,
                        width=0.26,
                        height=0.52,
                    )
                )
                total_mappings += 1
                for idx, s in enumerate(seats_by_zone_id.get(z2.id, [])):
                    row = idx // 4
                    col = idx % 4
                    db.add(
                        SpatialResourceMapping(
                            floor_id=fl.id,
                            resource_type="seat",
                            resource_id=s.id,
                            label=s.seat_code,
                            x=round(0.57 + col * 0.06, 3),
                            y=round(0.20 + row * 0.085, 3),
                            width=0.035,
                            height=0.035,
                        )
                    )
                    total_mappings += 1

            # Rooms on Floor 1
            r101 = rooms_by_code.get("ROOM-101")
            r102 = rooms_by_code.get("ROOM-102")
            r103 = rooms_by_code.get("ROOM-103")
            room_defs = [
                (r101, 0.22, 0.74, 0.15, 0.15),
                (r102, 0.40, 0.74, 0.12, 0.15),
                (r103, 0.55, 0.74, 0.18, 0.15),
            ]
            for rm, rx, ry, rw, rh in room_defs:
                if rm:
                    db.add(
                        FloorPlanElement(
                            floor_id=fl.id,
                            layout_id=plan.id,
                            element_type="room",
                            label=f"{rm.room_code} - {rm.name}",
                            geometry_type="rect",
                            geometry_data={"x": rx, "y": ry, "width": rw, "height": rh},
                            style_properties={"fill": "#fdf4ff", "stroke": "#c026d3", "strokeWidth": 2},
                            display_order=4,
                        )
                    )
                    total_elements += 1
                    db.add(
                        SpatialResourceMapping(
                            floor_id=fl.id,
                            resource_type="room",
                            resource_id=rm.id,
                            label=rm.name,
                            x=round(rx + rw / 2, 3),
                            y=round(ry + rh / 2, 3),
                            width=rw,
                            height=rh,
                        )
                    )
                    total_mappings += 1

        elif fl_num == 2:
            # 2nd Floor Digital Lab (25 seats) + Graduate Carrels (15 seats)
            # Rooms: ROOM-201, ROOM-202, ROOM-203, ROOM-204
            zt = zones_by_code.get("ZONE-2-TECH")
            if zt:
                db.add(
                    FloorPlanElement(
                        floor_id=fl.id,
                        layout_id=plan.id,
                        element_type="zone_boundary",
                        label=zt.name,
                        geometry_type="rect",
                        geometry_data={"x": 0.08, "y": 0.12, "width": 0.42, "height": 0.52},
                        style_properties={"fill": "#f0f9ff", "stroke": "#0284c7", "strokeWidth": 2, "strokeDasharray": "6 4"},
                        display_order=2,
                    )
                )
                total_elements += 1
                db.add(
                    SpatialResourceMapping(
                        floor_id=fl.id,
                        resource_type="zone",
                        resource_id=zt.id,
                        label=zt.name,
                        x=0.29,
                        y=0.15,
                        width=0.42,
                        height=0.52,
                    )
                )
                total_mappings += 1
                for idx, s in enumerate(seats_by_zone_id.get(zt.id, [])):
                    row = idx // 5
                    col = idx % 5
                    db.add(
                        SpatialResourceMapping(
                            floor_id=fl.id,
                            resource_type="seat",
                            resource_id=s.id,
                            label=s.seat_code,
                            x=round(0.12 + col * 0.075, 3),
                            y=round(0.20 + row * 0.085, 3),
                            width=0.035,
                            height=0.035,
                        )
                    )
                    total_mappings += 1

            zg = zones_by_code.get("ZONE-2-GRAD")
            if zg:
                db.add(
                    FloorPlanElement(
                        floor_id=fl.id,
                        layout_id=plan.id,
                        element_type="zone_boundary",
                        label=zg.name,
                        geometry_type="rect",
                        geometry_data={"x": 0.54, "y": 0.12, "width": 0.26, "height": 0.52},
                        style_properties={"fill": "#fafaf9", "stroke": "#78716c", "strokeWidth": 2, "strokeDasharray": "6 4"},
                        display_order=2,
                    )
                )
                total_elements += 1
                db.add(
                    SpatialResourceMapping(
                        floor_id=fl.id,
                        resource_type="zone",
                        resource_id=zg.id,
                        label=zg.name,
                        x=0.67,
                        y=0.15,
                        width=0.26,
                        height=0.52,
                    )
                )
                total_mappings += 1
                for idx, s in enumerate(seats_by_zone_id.get(zg.id, [])):
                    row = idx // 3
                    col = idx % 3
                    db.add(
                        SpatialResourceMapping(
                            floor_id=fl.id,
                            resource_type="seat",
                            resource_id=s.id,
                            label=s.seat_code,
                            x=round(0.58 + col * 0.08, 3),
                            y=round(0.20 + row * 0.085, 3),
                            width=0.035,
                            height=0.035,
                        )
                    )
                    total_mappings += 1

            # Rooms on Floor 2
            r201 = rooms_by_code.get("ROOM-201")
            r202 = rooms_by_code.get("ROOM-202")
            r203 = rooms_by_code.get("ROOM-203")
            r204 = rooms_by_code.get("ROOM-204")
            room_defs = [
                (r201, 0.20, 0.74, 0.12, 0.15),
                (r202, 0.35, 0.74, 0.14, 0.15),
                (r203, 0.52, 0.74, 0.13, 0.15),
                (r204, 0.68, 0.74, 0.14, 0.15),
            ]
            for rm, rx, ry, rw, rh in room_defs:
                if rm:
                    db.add(
                        FloorPlanElement(
                            floor_id=fl.id,
                            layout_id=plan.id,
                            element_type="room",
                            label=f"{rm.room_code} - {rm.name}",
                            geometry_type="rect",
                            geometry_data={"x": rx, "y": ry, "width": rw, "height": rh},
                            style_properties={"fill": "#fdf4ff", "stroke": "#c026d3", "strokeWidth": 2},
                            display_order=4,
                        )
                    )
                    total_elements += 1
                    db.add(
                        SpatialResourceMapping(
                            floor_id=fl.id,
                            resource_type="room",
                            resource_id=rm.id,
                            label=rm.name,
                            x=round(rx + rw / 2, 3),
                            y=round(ry + rh / 2, 3),
                            width=rw,
                            height=rh,
                        )
                    )
                    total_mappings += 1

        elif fl_num == 3:
            # 3rd Floor Tower Silent Study (15) + Media (10) + Math Alcove (5)
            # Rooms: ROOM-301, ROOM-302, ROOM-303
            zs = zones_by_code.get("ZONE-3-SILENT")
            zm = zones_by_code.get("ZONE-3-MEDIA")
            za = zones_by_code.get("ZONE-3-MATH")

            if zs:
                db.add(
                    FloorPlanElement(
                        floor_id=fl.id,
                        layout_id=plan.id,
                        element_type="zone_boundary",
                        label=zs.name,
                        geometry_type="rect",
                        geometry_data={"x": 0.08, "y": 0.12, "width": 0.26, "height": 0.52},
                        style_properties={"fill": "#f0fdf4", "stroke": "#16a34a", "strokeWidth": 2, "strokeDasharray": "6 4"},
                        display_order=2,
                    )
                )
                total_elements += 1
                db.add(
                    SpatialResourceMapping(
                        floor_id=fl.id,
                        resource_type="zone",
                        resource_id=zs.id,
                        label=zs.name,
                        x=0.21,
                        y=0.15,
                        width=0.26,
                        height=0.52,
                    )
                )
                total_mappings += 1
                for idx, s in enumerate(seats_by_zone_id.get(zs.id, [])):
                    row = idx // 3
                    col = idx % 3
                    db.add(
                        SpatialResourceMapping(
                            floor_id=fl.id,
                            resource_type="seat",
                            resource_id=s.id,
                            label=s.seat_code,
                            x=round(0.12 + col * 0.08, 3),
                            y=round(0.20 + row * 0.085, 3),
                            width=0.035,
                            height=0.035,
                        )
                    )
                    total_mappings += 1

            if zm:
                db.add(
                    FloorPlanElement(
                        floor_id=fl.id,
                        layout_id=plan.id,
                        element_type="zone_boundary",
                        label=zm.name,
                        geometry_type="rect",
                        geometry_data={"x": 0.38, "y": 0.12, "width": 0.22, "height": 0.52},
                        style_properties={"fill": "#fefce8", "stroke": "#ca8a04", "strokeWidth": 2, "strokeDasharray": "6 4"},
                        display_order=2,
                    )
                )
                total_elements += 1
                db.add(
                    SpatialResourceMapping(
                        floor_id=fl.id,
                        resource_type="zone",
                        resource_id=zm.id,
                        label=zm.name,
                        x=0.49,
                        y=0.15,
                        width=0.22,
                        height=0.52,
                    )
                )
                total_mappings += 1
                for idx, s in enumerate(seats_by_zone_id.get(zm.id, [])):
                    row = idx // 2
                    col = idx % 2
                    db.add(
                        SpatialResourceMapping(
                            floor_id=fl.id,
                            resource_type="seat",
                            resource_id=s.id,
                            label=s.seat_code,
                            x=round(0.42 + col * 0.09, 3),
                            y=round(0.20 + row * 0.085, 3),
                            width=0.035,
                            height=0.035,
                        )
                    )
                    total_mappings += 1

            if za:
                db.add(
                    FloorPlanElement(
                        floor_id=fl.id,
                        layout_id=plan.id,
                        element_type="zone_boundary",
                        label=za.name,
                        geometry_type="rect",
                        geometry_data={"x": 0.64, "y": 0.12, "width": 0.16, "height": 0.52},
                        style_properties={"fill": "#fdf2f8", "stroke": "#db2777", "strokeWidth": 2, "strokeDasharray": "6 4"},
                        display_order=2,
                    )
                )
                total_elements += 1
                db.add(
                    SpatialResourceMapping(
                        floor_id=fl.id,
                        resource_type="zone",
                        resource_id=za.id,
                        label=za.name,
                        x=0.72,
                        y=0.15,
                        width=0.16,
                        height=0.52,
                    )
                )
                total_mappings += 1
                for idx, s in enumerate(seats_by_zone_id.get(za.id, [])):
                    db.add(
                        SpatialResourceMapping(
                            floor_id=fl.id,
                            resource_type="seat",
                            resource_id=s.id,
                            label=s.seat_code,
                            x=round(0.70, 3),
                            y=round(0.20 + idx * 0.09, 3),
                            width=0.035,
                            height=0.035,
                        )
                    )
                    total_mappings += 1

            # Rooms on Floor 3
            r301 = rooms_by_code.get("ROOM-301")
            r302 = rooms_by_code.get("ROOM-302")
            r303 = rooms_by_code.get("ROOM-303")
            room_defs = [
                (r301, 0.20, 0.74, 0.18, 0.15),
                (r302, 0.41, 0.74, 0.12, 0.15),
                (r303, 0.56, 0.74, 0.20, 0.15),
            ]
            for rm, rx, ry, rw, rh in room_defs:
                if rm:
                    db.add(
                        FloorPlanElement(
                            floor_id=fl.id,
                            layout_id=plan.id,
                            element_type="room",
                            label=f"{rm.room_code} - {rm.name}",
                            geometry_type="rect",
                            geometry_data={"x": rx, "y": ry, "width": rw, "height": rh},
                            style_properties={"fill": "#fdf4ff", "stroke": "#c026d3", "strokeWidth": 2},
                            display_order=4,
                        )
                    )
                    total_elements += 1
                    db.add(
                        SpatialResourceMapping(
                            floor_id=fl.id,
                            resource_type="room",
                            resource_id=rm.id,
                            label=rm.name,
                            x=round(rx + rw / 2, 3),
                            y=round(ry + rh / 2, 3),
                            width=rw,
                            height=rh,
                        )
                    )
                    total_mappings += 1

        # Wayfinding Nodes & Edges per Floor
        n_entrance = WayfindingNode(
            floor_id=fl.id,
            node_type="entrance" if fl_num == 0 else "stairs",
            label="Floor Entrance" if fl_num == 0 else "Stairs / Elevator Exit",
            x=0.50 if fl_num == 0 else 0.82,
            y=0.88 if fl_num == 0 else 0.46,
        )
        n_central = WayfindingNode(
            floor_id=fl.id,
            node_type="hallway",
            label="Central Concourse",
            x=0.50,
            y=0.68,
        )
        n_west = WayfindingNode(
            floor_id=fl.id,
            node_type="hallway",
            label="West Corridor",
            x=0.25,
            y=0.68,
        )
        n_east = WayfindingNode(
            floor_id=fl.id,
            node_type="hallway",
            label="East Corridor",
            x=0.75,
            y=0.68,
        )
        n_stairs = WayfindingNode(
            floor_id=fl.id,
            node_type="stairs",
            label="Central Stairs",
            x=0.82,
            y=0.46,
        )
        n_restroom = WayfindingNode(
            floor_id=fl.id,
            node_type="door",
            label="Restrooms Access",
            x=0.12,
            y=0.76,
        )

        db.add_all([n_entrance, n_central, n_west, n_east, n_stairs, n_restroom])
        db.flush()
        total_nodes += 6

        # Connect corridor edges
        edges = [
            WayfindingEdge(from_node_id=n_entrance.id, to_node_id=n_central.id, distance=20.0, is_accessible=True),
            WayfindingEdge(from_node_id=n_central.id, to_node_id=n_west.id, distance=25.0, is_accessible=True),
            WayfindingEdge(from_node_id=n_central.id, to_node_id=n_east.id, distance=25.0, is_accessible=True),
            WayfindingEdge(from_node_id=n_east.id, to_node_id=n_stairs.id, distance=15.0, is_accessible=True),
            WayfindingEdge(from_node_id=n_west.id, to_node_id=n_restroom.id, distance=18.0, is_accessible=True),
        ]
        db.add_all(edges)
        total_edges += len(edges)

    db.flush()
    return {
        "floors": len(floors_by_num),
        "elements": total_elements,
        "mappings": total_mappings,
        "nodes": total_nodes,
        "edges": total_edges,
        "status": "seeded_successfully",
    }

