"""Serializers for blocks, rooms, and bed-level allocations."""

from __future__ import annotations

from datetime import date
from typing import Any

from app.models.rooms import Block, Room, RoomAllocation


def format_floor_label(floor: int) -> str:
    """Format an integer floor into a human-readable display string."""
    if floor == 0:
        return "Ground Floor"
    if floor == 1:
        return "1st Floor"
    if floor == 2:
        return "2nd Floor"
    if floor == 3:
        return "3rd Floor"
    return f"{floor}th Floor"


def serialize_block(block: Block, stats: dict[str, int] | None = None) -> dict[str, Any]:
    """Serialize a `Block` record with aggregated room/occupancy stats."""
    stats = stats or {}
    return {
        "id": block.id,
        "code": block.code,
        "name": block.name,
        "display_order": block.display_order,
        "displayOrder": block.display_order,
        "is_active": block.is_active,
        "isActive": block.is_active,
        "rooms_count": stats.get("rooms_count", 0),
        "totalRooms": stats.get("rooms_count", 0),
        "active_rooms_count": stats.get("active_rooms_count", 0),
        "activeRooms": stats.get("active_rooms_count", 0),
        "total_capacity": stats.get("total_capacity", 0),
        "totalCapacity": stats.get("total_capacity", 0),
        "occupied_beds": stats.get("occupied_beds", 0),
        "occupiedBeds": stats.get("occupied_beds", 0),
        "vacant_beds": max(0, stats.get("total_capacity", 0) - stats.get("occupied_beds", 0)),
        "vacantBeds": max(0, stats.get("total_capacity", 0) - stats.get("occupied_beds", 0)),
        "created_at": block.created_at.isoformat() if block.created_at else None,
        "updated_at": block.updated_at.isoformat() if block.updated_at else None,
    }


def serialize_room(
    room: Room, active_allocations: list[RoomAllocation] | None = None
) -> dict[str, Any]:
    """Serialize a `Room` with bed slots, active residents, and occupancy stats."""
    capacity = int(room.capacity)
    allocs = [
        alloc
        for alloc in (active_allocations or [])
        if alloc.student is not None and alloc.student.user is not None
    ]
    occupied = len(allocs)
    vacant_beds = max(0, capacity - occupied)

    by_bed: dict[int, RoomAllocation] = {int(alloc.bed_number): alloc for alloc in allocs}
    resident_names: list[str] = []
    resident_details: list[dict[str, Any]] = []

    for alloc in allocs:
        stu_profile = alloc.student
        stu_user = stu_profile.user
        resident_names.append(stu_user.full_name)
        resident_details.append(
            {
                "allocation_id": alloc.id,
                "id": str(stu_user.public_id),
                "user_id": stu_user.id,
                "full_name": stu_user.full_name,
                "fullName": stu_user.full_name,
                "roll_number": stu_profile.roll_number,
                "rollNumber": stu_profile.roll_number,
                "email": stu_user.email,
                "phone": stu_user.phone,
                "bed_number": int(alloc.bed_number),
                "bedNumber": int(alloc.bed_number),
                "start_date": alloc.start_date.isoformat(),
                "startDate": alloc.start_date.strftime("%d/%m/%Y"),
            }
        )

    beds: list[dict[str, Any]] = []
    students_slots: list[str] = []

    for bed_no in range(1, capacity + 1):
        alloc = by_bed.get(bed_no)
        if alloc is not None and alloc.student is not None and alloc.student.user is not None:
            stu_profile = alloc.student
            stu_user = stu_profile.user
            beds.append(
                {
                    "bed_number": bed_no,
                    "occupied": True,
                    "student_id": str(stu_user.public_id),
                    "student_name": stu_user.full_name,
                    "roll_number": stu_profile.roll_number,
                    "allocation_id": alloc.id,
                }
            )
            students_slots.append(stu_user.full_name)
        else:
            beds.append(
                {
                    "bed_number": bed_no,
                    "occupied": False,
                    "student_id": None,
                    "student_name": None,
                    "roll_number": None,
                    "allocation_id": None,
                }
            )
            students_slots.append("(Vacant Bed)")

    block = room.block
    return {
        "id": room.id,
        "room_id": room.id,
        "roomId": room.id,
        "room_number": room.room_number,
        "roomNumber": room.room_number,
        "block": block.name if block is not None else "Hostel",
        "block_id": room.block_id,
        "blockId": room.block_id,
        "block_code": block.code if block is not None else None,
        "blockCode": block.code if block is not None else None,
        "floor": format_floor_label(int(room.floor)),
        "floor_number": int(room.floor),
        "floorNumber": int(room.floor),
        "room_type": room.room_type or "standard",
        "roomType": room.room_type or "standard",
        "capacity": capacity,
        "occupied": occupied,
        "occupied_beds": occupied,
        "occupiedBeds": occupied,
        "vacant": vacant_beds,
        "vacant_beds": vacant_beds,
        "vacantBeds": vacant_beds,
        "is_active": room.is_active,
        "isActive": room.is_active,
        "residents": resident_names,
        "resident_details": resident_details,
        "residentDetails": resident_details,
        "beds": beds,
        "students": students_slots,
        "created_at": room.created_at.isoformat() if room.created_at else None,
        "updated_at": room.updated_at.isoformat() if room.updated_at else None,
    }


def serialize_allocation(alloc: RoomAllocation) -> dict[str, Any]:
    """Serialize a `RoomAllocation` record."""
    room = alloc.room
    block = room.block if room is not None else None
    stu_profile = alloc.student
    stu_user = stu_profile.user if stu_profile is not None else None
    allocator = alloc.allocator
    ender = alloc.ender

    today = date.today()
    is_active = alloc.end_date is None or alloc.end_date > today
    return {
        "id": alloc.id,
        "room_id": alloc.room_id,
        "roomId": alloc.room_id,
        "room_number": room.room_number if room is not None else None,
        "roomNumber": room.room_number if room is not None else None,
        "block_id": block.id if block is not None else None,
        "block_name": block.name if block is not None else "Hostel",
        "blockName": block.name if block is not None else "Hostel",
        "block_code": block.code if block is not None else None,
        "floor": format_floor_label(int(room.floor)) if room is not None else None,
        "bed_number": int(alloc.bed_number),
        "bedNumber": int(alloc.bed_number),
        "start_date": alloc.start_date.isoformat(),
        "startDate": alloc.start_date.strftime("%d/%m/%Y"),
        "end_date": alloc.end_date.isoformat() if alloc.end_date else None,
        "endDate": alloc.end_date.strftime("%d/%m/%Y") if alloc.end_date else None,
        "is_active": is_active,
        "isActive": is_active,
        "status": "active" if is_active else "ended",
        "end_reason": alloc.end_reason,
        "endReason": alloc.end_reason,
        "student": {
            "id": str(stu_user.public_id) if stu_user else None,
            "user_id": stu_user.id if stu_user else None,
            "fullName": stu_user.full_name if stu_user else "Resident Student",
            "full_name": stu_user.full_name if stu_user else "Resident Student",
            "rollNumber": stu_profile.roll_number if stu_profile else None,
            "roll_number": stu_profile.roll_number if stu_profile else None,
            "email": stu_user.email if stu_user else None,
            "phone": stu_user.phone if stu_user else None,
        },
        "allocated_by": allocator.full_name if allocator else "Warden Desk",
        "ended_by": ender.full_name if ender else None,
        "created_at": alloc.created_at.isoformat() if alloc.created_at else None,
    }
