"""Room, block, and allocation lifecycle services."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from app.audit.service import record_audit_event
from app.auth.service import AuthServiceError
from app.extensions import db
from app.models.identity import StudentProfile, User
from app.models.notifications import Notification
from app.models.rooms import Block, Room, RoomAllocation
from app.rooms.serializers import serialize_allocation, serialize_block, serialize_room

_BLOCK_CODE_RE = re.compile(r"^[A-Z0-9]{1,10}$")
_ROOM_NUMBER_RE = re.compile(r"^[A-Za-z0-9-]{1,10}$")


class RoomServiceError(AuthServiceError):
    """Domain exception for room/block/allocation operations."""

    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(code, message, status)


_IST = timezone(timedelta(hours=5, minutes=30))


def _today() -> date:
    return datetime.now(_IST).date()


def _parse_date(raw: Any) -> date:
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if isinstance(raw, datetime):
        return raw.date()
    val = str(raw or "").strip()
    if not val:
        return _today()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(val, fmt).date()
        except ValueError:
            pass
    raise RoomServiceError(
        "invalid_date_format",
        f"Invalid date format for '{val}'. Expected YYYY-MM-DD or DD/MM/YYYY.",
        400,
    )


# ---------------------------------------------------------------------------
# Block Management
# ---------------------------------------------------------------------------


def _resolve_block(block_identifier: Any, *, for_update: bool = False) -> Block:
    raw = str(block_identifier or "").strip()
    if not raw:
        raise RoomServiceError("not_found", "Block identifier is required.", 404)

    stmt = select(Block)
    if for_update:
        stmt = stmt.with_for_update()

    if raw.isdigit():
        b = db.session.execute(stmt.where(Block.id == int(raw))).scalar_one_or_none()
        if b is not None:
            return b

    b = db.session.execute(stmt.where(Block.code == raw.upper())).scalar_one_or_none()
    if b is not None:
        return b

    b = db.session.execute(stmt.where(func.lower(Block.name) == raw.lower())).scalar_one_or_none()
    if b is not None:
        return b

    raise RoomServiceError("not_found", f"Block '{raw}' not found.", 404)


def list_blocks() -> list[dict[str, Any]]:
    """Return all blocks ordered by display_order, code with aggregated occupancy stats."""
    blocks = list(
        db.session.execute(
            select(Block).order_by(Block.display_order.asc(), Block.code.asc(), Block.name.asc())
        )
        .scalars()
        .all()
    )
    if not blocks:
        return []

    today = _today()
    rooms_stmt = select(
        Room.block_id,
        func.count(Room.id).label("rooms_count"),
        func.count().filter(Room.is_active.is_(True)).label("active_rooms_count"),
        func.coalesce(func.sum(Room.capacity), 0).label("total_capacity"),
    ).group_by(Room.block_id)
    room_stats = {
        row.block_id: {
            "rooms_count": int(row.rooms_count or 0),
            "active_rooms_count": int(row.active_rooms_count or 0),
            "total_capacity": int(row.total_capacity or 0),
        }
        for row in db.session.execute(rooms_stmt)
    }

    alloc_stmt = (
        select(Room.block_id, func.count(RoomAllocation.id).label("occupied_beds"))
        .join(RoomAllocation, RoomAllocation.room_id == Room.id)
        .where(
            RoomAllocation.start_date <= today,
            (RoomAllocation.end_date.is_(None)) | (RoomAllocation.end_date > today),
        )
        .group_by(Room.block_id)
    )
    occupied_stats = {
        row.block_id: int(row.occupied_beds or 0) for row in db.session.execute(alloc_stmt)
    }

    results = []
    for b in blocks:
        st = room_stats.get(b.id, {})
        st["occupied_beds"] = occupied_stats.get(b.id, 0)
        results.append(serialize_block(b, st))
    return results


def create_block(data: dict[str, Any], admin_user: User) -> dict[str, Any]:
    """Create a new hostel block."""
    name = str(data.get("name") or data.get("block_name") or data.get("blockName") or "").strip()
    if not name:
        raise RoomServiceError("validation_error", "Block name is required.", 400)
    if len(name) > 80:
        raise RoomServiceError("validation_error", "Block name must not exceed 80 characters.", 400)

    # Validate name uniqueness
    dup_name = db.session.execute(
        select(Block.id).where(func.lower(Block.name) == name.lower())
    ).scalar_one_or_none()
    if dup_name is not None:
        raise RoomServiceError("conflict", f"A block with name '{name}' already exists.", 409)

    raw_code = (
        str(data.get("code") or data.get("block_code") or data.get("blockCode") or "")
        .strip()
        .upper()
    )
    if not raw_code:
        # Generate code from name (e.g. "Block A (Nalanda)" -> "BLKA")
        clean_chars = re.sub(r"[^A-Z0-9]", "", name.upper())
        raw_code = clean_chars[:10] if clean_chars else "BLK01"
        # Ensure generated code is unique
        count = int(db.session.execute(select(func.count()).select_from(Block)).scalar_one() or 0)
        if db.session.execute(select(Block.id).where(Block.code == raw_code)).scalar_one_or_none():
            raw_code = f"BLK{count + 1:02d}"[:10]

    if not _BLOCK_CODE_RE.match(raw_code):
        raise RoomServiceError(
            "validation_error",
            "Block code must be 1 to 10 alphanumeric uppercase characters (e.g. 'BLKA', 'NORTH').",
            400,
        )

    dup_code = db.session.execute(
        select(Block.id).where(Block.code == raw_code)
    ).scalar_one_or_none()
    if dup_code is not None:
        raise RoomServiceError("conflict", f"Block code '{raw_code}' already exists.", 409)

    try:
        raw_order = (
            data.get("display_order") if "display_order" in data else data.get("displayOrder", 0)
        )
        display_order = int(raw_order) if raw_order is not None else 0
    except (ValueError, TypeError):
        display_order = 0

    is_active = bool(data.get("is_active", data.get("isActive", True)))

    block = Block(
        name=name,
        code=raw_code,
        display_order=display_order,
        is_active=is_active,
    )
    db.session.add(block)
    db.session.flush()

    record_audit_event(
        action="block.created",
        actor=admin_user,
        target_type="block",
        target_id=str(block.id),
        metadata={"code": block.code, "name": block.name},
    )
    db.session.commit()
    return serialize_block(block)


def update_block(block_identifier: Any, data: dict[str, Any], admin_user: User) -> dict[str, Any]:
    """Update block mutable attributes (name, code, display_order, is_active)."""
    block = _resolve_block(block_identifier, for_update=True)
    today = _today()

    name_val = data.get("name") if "name" in data else data.get("block_name", data.get("blockName"))
    if name_val is not None:
        new_name = str(name_val).strip()
        if not new_name:
            raise RoomServiceError("validation_error", "Block name cannot be empty.", 400)
        if len(new_name) > 80:
            raise RoomServiceError(
                "validation_error", "Block name must not exceed 80 characters.", 400
            )
        if new_name.lower() != block.name.lower():
            dup = db.session.execute(
                select(Block.id).where(
                    func.lower(Block.name) == new_name.lower(), Block.id != block.id
                )
            ).scalar_one_or_none()
            if dup is not None:
                raise RoomServiceError(
                    "conflict", f"A block named '{new_name}' already exists.", 409
                )
            block.name = new_name

    code_val = data.get("code") if "code" in data else data.get("block_code", data.get("blockCode"))
    if code_val is not None:
        new_code = str(code_val).strip().upper()
        if not _BLOCK_CODE_RE.match(new_code):
            raise RoomServiceError(
                "validation_error",
                "Block code must be 1 to 10 alphanumeric uppercase characters.",
                400,
            )
        if new_code != block.code:
            dup = db.session.execute(
                select(Block.id).where(Block.code == new_code, Block.id != block.id)
            ).scalar_one_or_none()
            if dup is not None:
                raise RoomServiceError("conflict", f"Block code '{new_code}' already exists.", 409)
            block.code = new_code

    if "display_order" in data or "displayOrder" in data:
        val = data.get("display_order") if "display_order" in data else data.get("displayOrder")
        block.display_order = int(val or 0)

    if "is_active" in data or "isActive" in data:
        new_active = bool(data.get("is_active") if "is_active" in data else data.get("isActive"))
        if not new_active and block.is_active:
            # Check for active resident allocations in this block
            alloc_count = int(
                db.session.execute(
                    select(func.count(RoomAllocation.id))
                    .join(Room, RoomAllocation.room_id == Room.id)
                    .where(
                        Room.block_id == block.id,
                        RoomAllocation.start_date <= today,
                        (RoomAllocation.end_date.is_(None)) | (RoomAllocation.end_date > today),
                    )
                ).scalar_one()
                or 0
            )
            if alloc_count > 0:
                raise RoomServiceError(
                    "active_allocations_exist",
                    f"Cannot deactivate block '{block.name}'. "
                    f"It contains {alloc_count} active resident allocations.",
                    409,
                )
        block.is_active = new_active

    block.updated_at = datetime.now(UTC)
    record_audit_event(
        action="block.updated",
        actor=admin_user,
        target_type="block",
        target_id=str(block.id),
        metadata={"code": block.code, "name": block.name, "is_active": block.is_active},
    )
    db.session.commit()
    return serialize_block(block)


# ---------------------------------------------------------------------------
# Room Management
# ---------------------------------------------------------------------------


def _resolve_room(room_identifier: Any, *, for_update: bool = False) -> Room:
    raw = str(room_identifier or "").strip()
    if not raw:
        raise RoomServiceError("not_found", "Room identifier is required.", 404)

    stmt = select(Room)
    stmt = stmt.with_for_update() if for_update else stmt.options(joinedload(Room.block))

    if raw.isdigit():
        rm = db.session.execute(stmt.where(Room.id == int(raw))).scalar_one_or_none()
        if rm is not None:
            return rm

    rm = db.session.execute(
        stmt.where(func.lower(Room.room_number) == raw.lower())
    ).scalar_one_or_none()
    if rm is not None:
        return rm

    raise RoomServiceError("not_found", f"Room '{raw}' not found.", 404)


def list_rooms(
    filters: dict[str, Any] | None = None,
    *,
    block_id: Any | None = None,
    floor: int | None = None,
    is_active: bool | None = None,
) -> list[dict[str, Any]]:
    """Return rooms and active-today occupancy stats with filters (avoiding N+1 queries)."""
    filters = dict(filters or {})
    if block_id is not None:
        filters["block_id"] = block_id
    if floor is not None:
        filters["floor"] = floor
    if is_active is not None:
        filters["is_active"] = is_active
    today = _today()

    stmt = (
        select(Room)
        .join(Block, Room.block_id == Block.id)
        .options(joinedload(Room.block))
        .order_by(
            Block.display_order.asc(),
            Block.code.asc(),
            Room.floor.asc(),
            Room.room_number.asc(),
        )
    )

    block_id = filters.get("block_id") or filters.get("blockId")
    if block_id:
        if str(block_id).isdigit():
            stmt = stmt.where(Room.block_id == int(block_id))
        else:
            stmt = stmt.where(func.lower(Block.code) == str(block_id).strip().lower())

    floor = filters.get("floor")
    if floor is not None and str(floor).strip() != "":
        stmt = stmt.where(Room.floor == int(floor))

    is_active = filters.get("is_active") or filters.get("isActive")
    if is_active is not None and str(is_active).strip().lower() in ("true", "false"):
        stmt = stmt.where(Room.is_active.is_(str(is_active).strip().lower() == "true"))

    rooms = list(db.session.execute(stmt).scalars().all())
    if not rooms:
        return []

    room_ids = [rm.id for rm in rooms]
    alloc_stmt = (
        select(RoomAllocation)
        .options(joinedload(RoomAllocation.student).joinedload(StudentProfile.user))
        .where(
            RoomAllocation.room_id.in_(room_ids),
            RoomAllocation.start_date <= today,
            (RoomAllocation.end_date.is_(None)) | (RoomAllocation.end_date > today),
        )
        .order_by(
            RoomAllocation.room_id.asc(),
            RoomAllocation.bed_number.asc(),
            RoomAllocation.id.asc(),
        )
    )
    active_allocs = list(db.session.execute(alloc_stmt).scalars().all())

    allocs_by_room: dict[int, list[RoomAllocation]] = {}
    for alloc in active_allocs:
        allocs_by_room.setdefault(alloc.room_id, []).append(alloc)

    q = str(filters.get("q") or "").strip().lower()
    serialized = []
    for rm in rooms:
        s = serialize_room(rm, allocs_by_room.get(rm.id, []))
        if q:
            matches_room = q in s["room_number"].lower() or q in s["block"].lower()
            matches_resident = any(q in name.lower() for name in s["residents"])
            if not matches_room and not matches_resident:
                continue
        serialized.append(s)

    return serialized


def get_room(room_identifier: Any) -> dict[str, Any]:
    """Return a single room with its bed allocations."""
    rm = _resolve_room(room_identifier)
    today = _today()
    allocs = list(
        db.session.execute(
            select(RoomAllocation)
            .options(joinedload(RoomAllocation.student).joinedload(StudentProfile.user))
            .where(
                RoomAllocation.room_id == rm.id,
                RoomAllocation.start_date <= today,
                (RoomAllocation.end_date.is_(None)) | (RoomAllocation.end_date > today),
            )
            .order_by(RoomAllocation.bed_number.asc())
        )
        .scalars()
        .all()
    )
    return serialize_room(rm, allocs)


def create_room(data: dict[str, Any], admin_user: User) -> dict[str, Any]:
    """Create a new room in an active block."""
    block_raw = (
        data.get("block_id")
        or data.get("blockId")
        or data.get("block_code")
        or data.get("blockCode")
    )
    if not block_raw:
        raise RoomServiceError("validation_error", "Block is required for room creation.", 400)

    block = _resolve_block(block_raw)
    if not block.is_active:
        raise RoomServiceError(
            "block_inactive",
            f"Cannot create room in inactive block '{block.name}'. Activate the block first.",
            400,
        )

    room_number = str(data.get("room_number") or data.get("roomNumber") or "").strip()
    if not room_number:
        raise RoomServiceError("validation_error", "Room number is required.", 400)
    if not _ROOM_NUMBER_RE.match(room_number):
        raise RoomServiceError(
            "validation_error",
            "Room number must be 1 to 10 alphanumeric characters or hyphens (e.g. 'A-101', '102').",
            400,
        )

    # Check uniqueness in block
    dup_room = db.session.execute(
        select(Room.id).where(
            Room.block_id == block.id, func.lower(Room.room_number) == room_number.lower()
        )
    ).scalar_one_or_none()
    if dup_room is not None:
        raise RoomServiceError(
            "conflict",
            f"Room '{room_number}' already exists in {block.name}.",
            409,
        )

    raw_floor = data.get("floor")
    if raw_floor is None or str(raw_floor).strip() == "":
        raise RoomServiceError("validation_error", "Floor number is required.", 400)
    try:
        floor = int(raw_floor)
        if floor < 0 or floor > 50:
            raise ValueError()
    except (ValueError, TypeError):
        raise RoomServiceError(
            "validation_error", "Floor must be an integer between 0 and 50.", 400
        ) from None

    raw_capacity = data.get("capacity")
    if raw_capacity is None or str(raw_capacity).strip() == "":
        raise RoomServiceError("validation_error", "Bed capacity is required.", 400)
    try:
        capacity = int(raw_capacity)
        if capacity < 1 or capacity > 8:
            raise ValueError()
    except (ValueError, TypeError):
        raise RoomServiceError(
            "validation_error", "Bed capacity must be an integer between 1 and 8.", 400
        ) from None

    room_type = str(data.get("room_type") or data.get("roomType") or "").strip() or None
    is_active = bool(data.get("is_active", data.get("isActive", True)))

    room = Room(
        block_id=block.id,
        room_number=room_number,
        floor=floor,
        capacity=capacity,
        room_type=room_type,
        is_active=is_active,
    )
    db.session.add(room)
    db.session.flush()

    record_audit_event(
        action="room.created",
        actor=admin_user,
        target_type="room",
        target_id=str(room.id),
        metadata={
            "room_number": room.room_number,
            "block_code": block.code,
            "capacity": room.capacity,
            "floor": room.floor,
        },
    )
    db.session.commit()
    return serialize_room(room, [])


def update_room(room_identifier: Any, data: dict[str, Any], admin_user: User) -> dict[str, Any]:
    """Update room attributes with capacity reduction protection and active allocation checks."""
    room = _resolve_room(room_identifier, for_update=True)
    today = _today()

    if "room_number" in data or "roomNumber" in data:
        val = str(data.get("room_number") or data.get("roomNumber") or "").strip()
        if not val or not _ROOM_NUMBER_RE.match(val):
            raise RoomServiceError("validation_error", "Invalid room number format.", 400)
        if val.lower() != room.room_number.lower():
            dup = db.session.execute(
                select(Room.id).where(
                    Room.block_id == room.block_id,
                    func.lower(Room.room_number) == val.lower(),
                    Room.id != room.id,
                )
            ).scalar_one_or_none()
            if dup is not None:
                raise RoomServiceError(
                    "conflict", f"Room '{val}' already exists in this block.", 409
                )
            room.room_number = val

    if "floor" in data:
        try:
            fl = int(data["floor"])
            if fl < 0 or fl > 50:
                raise ValueError()
            room.floor = fl
        except (ValueError, TypeError):
            raise RoomServiceError(
                "validation_error", "Floor must be between 0 and 50.", 400
            ) from None

    if "room_type" in data or "roomType" in data:
        val = data.get("room_type") if "room_type" in data else data.get("roomType")
        room.room_type = str(val).strip() if val else None

    if "capacity" in data and data["capacity"] is not None:
        try:
            new_capacity = int(data["capacity"])
            if new_capacity < 1 or new_capacity > 8:
                raise ValueError()
        except (ValueError, TypeError):
            raise RoomServiceError(
                "validation_error", "Capacity must be between 1 and 8.", 400
            ) from None

        if new_capacity < room.capacity:
            # Check maximum active or future allocated bed number
            alloc_query = db.session.execute(
                select(
                    func.count(RoomAllocation.id).label("count"),
                    func.max(RoomAllocation.bed_number).label("max_bed"),
                ).where(
                    RoomAllocation.room_id == room.id,
                    (RoomAllocation.end_date.is_(None)) | (RoomAllocation.end_date > today),
                )
            ).one()

            active_count = int(alloc_query.count or 0)
            max_allocated_bed = int(alloc_query.max_bed or 0)

            if new_capacity < active_count:
                raise RoomServiceError(
                    "capacity_reduction_denied",
                    f"Cannot reduce capacity to {new_capacity}. Room {room.room_number} "
                    f"currently has {active_count} active bed allocations.",
                    409,
                )
            if new_capacity < max_allocated_bed:
                raise RoomServiceError(
                    "capacity_reduction_denied",
                    f"Cannot reduce capacity to {new_capacity}. "
                    f"Bed {max_allocated_bed} is currently allocated.",
                    409,
                )

        room.capacity = new_capacity

    if "is_active" in data or "isActive" in data:
        val = bool(data.get("is_active") if "is_active" in data else data.get("isActive"))
        if not val and room.is_active:
            # Check for active resident allocations
            active_count = int(
                db.session.execute(
                    select(func.count(RoomAllocation.id)).where(
                        RoomAllocation.room_id == room.id,
                        RoomAllocation.start_date <= today,
                        (RoomAllocation.end_date.is_(None)) | (RoomAllocation.end_date > today),
                    )
                ).scalar_one()
                or 0
            )
            if active_count > 0:
                raise RoomServiceError(
                    "active_allocations_exist",
                    f"Cannot deactivate room '{room.room_number}' with "
                    f"{active_count} active resident allocations.",
                    409,
                )
        room.is_active = val

    room.updated_at = datetime.now(UTC)
    record_audit_event(
        action="room.updated",
        actor=admin_user,
        target_type="room",
        target_id=str(room.id),
        metadata={
            "room_number": room.room_number,
            "capacity": room.capacity,
            "is_active": room.is_active,
        },
    )
    db.session.commit()
    return get_room(room.id)


# ---------------------------------------------------------------------------
# Student Room Allocation Management
# ---------------------------------------------------------------------------


def list_room_allocations(
    filters: dict[str, Any] | None = None,
    *,
    room_id: int | None = None,
    student_id: Any | None = None,
    active_only: bool | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """List student room allocations with status filters."""
    filters = dict(filters or {})
    if room_id is not None:
        filters["room_id"] = room_id
    if student_id is not None:
        filters["student_id"] = student_id
    if active_only is not None:
        filters["status"] = "active" if active_only else "all"
    if status is not None:
        filters["status"] = status
    today = _today()

    stmt = (
        select(RoomAllocation)
        .options(
            joinedload(RoomAllocation.room).joinedload(Room.block),
            joinedload(RoomAllocation.student).joinedload(StudentProfile.user),
            joinedload(RoomAllocation.allocator),
            joinedload(RoomAllocation.ender),
        )
        .order_by(RoomAllocation.start_date.desc(), RoomAllocation.id.desc())
    )

    status_filter = str(filters.get("status") or "all").strip().lower()
    if status_filter == "active":
        stmt = stmt.where(
            RoomAllocation.start_date <= today,
            (RoomAllocation.end_date.is_(None)) | (RoomAllocation.end_date > today),
        )
    elif status_filter == "ended":
        stmt = stmt.where(
            RoomAllocation.end_date.is_not(None),
            RoomAllocation.end_date <= today,
        )

    room_id = filters.get("room_id") or filters.get("roomId")
    if room_id and str(room_id).isdigit():
        stmt = stmt.where(RoomAllocation.room_id == int(room_id))

    student_id = filters.get("student_id") or filters.get("studentId")
    if student_id:
        if str(student_id).isdigit():
            stmt = stmt.where(RoomAllocation.student_user_id == int(student_id))
        else:
            try:
                stu_uuid = uuid.UUID(str(student_id))
                stmt = (
                    stmt.join(
                        StudentProfile, RoomAllocation.student_user_id == StudentProfile.user_id
                    )
                    .join(User, StudentProfile.user_id == User.id)
                    .where(User.public_id == stu_uuid)
                )
            except (ValueError, TypeError):
                stmt = stmt.join(
                    StudentProfile, RoomAllocation.student_user_id == StudentProfile.user_id
                ).where(StudentProfile.roll_number == str(student_id).strip().upper())

    allocs = list(db.session.execute(stmt).scalars().all())
    return [serialize_allocation(a) for a in allocs]


def create_room_allocation(data: dict[str, Any], admin_user: User) -> dict[str, Any]:
    """Allocate an active student to an available room bed with concurrency protection."""
    stu_raw = (
        data.get("student_id")
        or data.get("studentId")
        or data.get("rollNumber")
        or data.get("roll_number")
    )
    if not stu_raw:
        raise RoomServiceError("validation_error", "Student is required for room allocation.", 400)

    # Lock student user for concurrency safety
    student_query = select(User)
    student = None
    if str(stu_raw).isdigit():
        student = db.session.execute(
            student_query.where(User.id == int(stu_raw)).with_for_update()
        ).scalar_one_or_none()
    if student is None:
        try:
            stu_uuid = uuid.UUID(str(stu_raw))
            student = db.session.execute(
                student_query.where(User.public_id == stu_uuid).with_for_update()
            ).scalar_one_or_none()
        except (ValueError, TypeError):
            pass
    if student is None:
        sp = db.session.execute(
            select(StudentProfile.user_id).where(
                StudentProfile.roll_number == str(stu_raw).strip().upper()
            )
        ).scalar_one_or_none()
        if sp is not None:
            student = db.session.execute(
                student_query.where(User.id == sp).with_for_update()
            ).scalar_one_or_none()

    if student is None or student.student_profile is None:
        raise RoomServiceError("not_found", f"Student '{stu_raw}' not found.", 404)

    if student.role != "student":
        raise RoomServiceError(
            "invalid_role", "Only student accounts can be allocated hostel rooms.", 400
        )

    if student.status != "active":
        raise RoomServiceError(
            "student_not_active",
            f"Cannot allocate room to student with status '{student.status}'. "
            "Student must be active and approved.",
            400,
        )

    room_raw = (
        data.get("room_id")
        or data.get("roomId")
        or data.get("roomNumber")
        or data.get("room_number")
    )
    if not room_raw:
        raise RoomServiceError("validation_error", "Room is required for allocation.", 400)

    room = _resolve_room(room_raw, for_update=True)
    if not room.is_active:
        raise RoomServiceError(
            "room_inactive",
            f"Cannot allocate bed in inactive room '{room.room_number}'.",
            400,
        )
    if not room.block.is_active:
        raise RoomServiceError(
            "block_inactive",
            f"Cannot allocate room in inactive block '{room.block.name}'.",
            400,
        )

    raw_bed = data.get("bed_number") or data.get("bedNumber")
    if raw_bed is None or str(raw_bed).strip() == "":
        raise RoomServiceError("validation_error", "Bed number is required.", 400)
    try:
        bed_number = int(raw_bed)
        if bed_number < 1 or bed_number > room.capacity:
            raise ValueError()
    except (ValueError, TypeError):
        raise RoomServiceError(
            "invalid_bed_number",
            f"Bed number must be between 1 and room capacity ({room.capacity}) "
            f"for room {room.room_number}.",
            400,
        ) from None

    start_date = _parse_date(data.get("start_date") or data.get("startDate"))

    # 1. Check if student already has an active or overlapping allocation
    existing_stu_alloc = db.session.execute(
        select(RoomAllocation)
        .options(joinedload(RoomAllocation.room))
        .where(
            RoomAllocation.student_user_id == student.id,
            RoomAllocation.start_date <= start_date,
            (RoomAllocation.end_date.is_(None)) | (RoomAllocation.end_date > start_date),
        )
    ).scalar_one_or_none()
    if existing_stu_alloc is not None:
        raise RoomServiceError(
            "student_already_allocated",
            f"Student {student.full_name} ({student.student_profile.roll_number}) "
            f"already has an active allocation in Room {existing_stu_alloc.room.room_number}. "
            "Transfer or end the allocation first.",
            409,
        )

    # 2. Check if the specified bed is already occupied on start_date
    existing_bed_alloc = db.session.execute(
        select(RoomAllocation).where(
            RoomAllocation.room_id == room.id,
            RoomAllocation.bed_number == bed_number,
            RoomAllocation.start_date <= start_date,
            (RoomAllocation.end_date.is_(None)) | (RoomAllocation.end_date > start_date),
        )
    ).scalar_one_or_none()
    if existing_bed_alloc is not None:
        raise RoomServiceError(
            "bed_already_occupied",
            f"Bed {bed_number} in Room {room.room_number} is already occupied.",
            409,
        )

    alloc = RoomAllocation(
        room_id=room.id,
        student_user_id=student.id,
        bed_number=bed_number,
        start_date=start_date,
        end_date=None,
        allocated_by=admin_user.id,
    )
    db.session.add(alloc)
    db.session.flush()

    # Create in-app notification for the student
    notif = Notification(
        recipient_user_id=student.id,
        category="system",
        event_type="room_allocated",
        title="Hostel Room Allocated",
        message=(
            f"You have been allocated Bed {bed_number} in Room {room.room_number} "
            f"({room.block.name})."
        ),
    )
    db.session.add(notif)

    record_audit_event(
        action="room.allocated",
        actor=admin_user,
        target_type="room_allocation",
        target_id=str(alloc.id),
        metadata={
            "student_roll": student.student_profile.roll_number,
            "student_name": student.full_name,
            "room_number": room.room_number,
            "bed_number": bed_number,
            "start_date": start_date.isoformat(),
        },
    )
    db.session.commit()

    db.session.refresh(alloc)
    return serialize_allocation(alloc)


def end_room_allocation(
    allocation_id: Any, data: dict[str, Any], admin_user: User
) -> dict[str, Any]:
    """End an active room allocation with mandatory reason."""
    raw_id = str(allocation_id or "").strip()
    if not raw_id.isdigit():
        raise RoomServiceError("not_found", "Allocation ID must be an integer.", 404)

    alloc = db.session.execute(
        select(RoomAllocation).where(RoomAllocation.id == int(raw_id)).with_for_update()
    ).scalar_one_or_none()

    if alloc is None:
        raise RoomServiceError("not_found", f"Room allocation #{raw_id} not found.", 404)

    if alloc.end_date is not None:
        raise RoomServiceError(
            "allocation_already_ended",
            f"Room allocation #{raw_id} was already ended on {alloc.end_date.isoformat()}.",
            409,
        )

    reason = str(
        data.get("reason") or data.get("end_reason") or data.get("endReason") or ""
    ).strip()
    if not reason or len(reason) < 3:
        raise RoomServiceError(
            "validation_error",
            "A mandatory explanation reason (at least 3 characters) "
            "is required to end a room allocation.",
            400,
        )

    end_date_val = _parse_date(data.get("end_date") or data.get("endDate") or _today())
    if end_date_val < alloc.start_date:
        raise RoomServiceError(
            "invalid_date_order",
            f"End date ({end_date_val}) cannot precede allocation start date ({alloc.start_date}).",
            400,
        )

    alloc.end_date = end_date_val
    alloc.ended_by = admin_user.id
    alloc.end_reason = reason

    student_user = alloc.student.user if alloc.student else None
    if student_user is not None:
        notif = Notification(
            recipient_user_id=student_user.id,
            category="system",
            event_type="room_allocation_ended",
            title="Room Allocation Ended",
            message=(
                f"Your allocation for Room {alloc.room.room_number} Bed {alloc.bed_number} "
                f"has been ended. Reason: {reason}"
            ),
        )
        db.session.add(notif)

    record_audit_event(
        action="room.vacated",
        actor=admin_user,
        target_type="room_allocation",
        target_id=str(alloc.id),
        metadata={
            "room_number": alloc.room.room_number,
            "bed_number": alloc.bed_number,
            "end_date": end_date_val.isoformat(),
            "reason": reason,
        },
    )
    db.session.commit()
    db.session.refresh(alloc)
    return serialize_allocation(alloc)


def transfer_room_allocation(
    allocation_id: Any, data: dict[str, Any], admin_user: User
) -> dict[str, Any]:
    """Transfer student from current room/bed to an available target room/bed."""
    raw_id = str(allocation_id or "").strip()
    if not raw_id.isdigit():
        raise RoomServiceError("not_found", "Allocation ID must be an integer.", 404)

    curr_alloc = db.session.execute(
        select(RoomAllocation).where(RoomAllocation.id == int(raw_id)).with_for_update()
    ).scalar_one_or_none()

    if curr_alloc is None:
        raise RoomServiceError("not_found", f"Room allocation #{raw_id} not found.", 404)

    today = _today()
    if curr_alloc.end_date is not None and curr_alloc.end_date <= today:
        raise RoomServiceError(
            "allocation_not_active",
            "Only currently active room allocations can be transferred.",
            409,
        )

    target_room_raw = (
        data.get("target_room_id")
        or data.get("targetRoomId")
        or data.get("room_id")
        or data.get("roomId")
    )
    if not target_room_raw:
        raise RoomServiceError("validation_error", "Target room is required for transfer.", 400)

    target_room = _resolve_room(target_room_raw, for_update=True)
    if not target_room.is_active:
        raise RoomServiceError(
            "room_inactive", f"Target room '{target_room.room_number}' is inactive.", 400
        )
    if not target_room.block.is_active:
        raise RoomServiceError(
            "block_inactive", f"Target block '{target_room.block.name}' is inactive.", 400
        )

    raw_bed = (
        data.get("target_bed_number")
        or data.get("targetBedNumber")
        or data.get("bed_number")
        or data.get("bedNumber")
    )
    if raw_bed is None or str(raw_bed).strip() == "":
        raise RoomServiceError("validation_error", "Target bed number is required.", 400)
    try:
        target_bed = int(raw_bed)
        if target_bed < 1 or target_bed > target_room.capacity:
            raise ValueError()
    except (ValueError, TypeError):
        raise RoomServiceError(
            "invalid_bed_number",
            f"Target bed number must be between 1 and {target_room.capacity} "
            f"for room {target_room.room_number}.",
            400,
        ) from None

    if curr_alloc.room_id == target_room.id and curr_alloc.bed_number == target_bed:
        raise RoomServiceError(
            "same_bed_transfer",
            f"Student is already in Room {target_room.room_number} Bed {target_bed}. "
            "Cannot transfer to identical bed.",
            400,
        )

    effective_date = _parse_date(data.get("effective_date") or data.get("effectiveDate") or today)
    if effective_date < curr_alloc.start_date:
        raise RoomServiceError(
            "invalid_date_order",
            f"Transfer date ({effective_date}) cannot precede "
            f"allocation start date ({curr_alloc.start_date}).",
            400,
        )

    reason = str(
        data.get("reason") or data.get("transfer_reason") or "Administrative Room Transfer"
    ).strip()

    # Verify target bed is not occupied on effective_date
    occupied_target = db.session.execute(
        select(RoomAllocation).where(
            RoomAllocation.room_id == target_room.id,
            RoomAllocation.bed_number == target_bed,
            RoomAllocation.start_date <= effective_date,
            (RoomAllocation.end_date.is_(None)) | (RoomAllocation.end_date > effective_date),
            RoomAllocation.id != curr_alloc.id,
        )
    ).scalar_one_or_none()

    if occupied_target is not None:
        raise RoomServiceError(
            "target_bed_occupied",
            f"Bed {target_bed} in Room {target_room.room_number} is already occupied.",
            409,
        )

    # 1. Terminate current allocation as of effective_date
    old_room_number = curr_alloc.room.room_number
    old_bed = curr_alloc.bed_number
    curr_alloc.end_date = effective_date
    curr_alloc.ended_by = admin_user.id
    curr_alloc.end_reason = (
        f"Transferred to Room {target_room.room_number} Bed {target_bed}: {reason}"
    )

    # Flush current allocation so Postgres exclusion range doesn't collide
    db.session.flush()

    # 2. Insert new allocation
    new_alloc = RoomAllocation(
        room_id=target_room.id,
        student_user_id=curr_alloc.student_user_id,
        bed_number=target_bed,
        start_date=effective_date,
        end_date=None,
        allocated_by=admin_user.id,
    )
    db.session.add(new_alloc)
    db.session.flush()

    student_user = curr_alloc.student.user if curr_alloc.student else None
    if student_user is not None:
        notif = Notification(
            recipient_user_id=student_user.id,
            category="system",
            event_type="room_transferred",
            title="Hostel Room Transfer",
            message=(
                f"You have been transferred from Room {old_room_number} Bed {old_bed} "
                f"to Room {target_room.room_number} Bed {target_bed} ({target_room.block.name})."
            ),
        )
        db.session.add(notif)

    record_audit_event(
        action="room.transferred",
        actor=admin_user,
        target_type="room_allocation",
        target_id=str(new_alloc.id),
        metadata={
            "from_room": old_room_number,
            "from_bed": old_bed,
            "to_room": target_room.room_number,
            "to_bed": target_bed,
            "effective_date": effective_date.isoformat(),
            "reason": reason,
        },
    )
    db.session.commit()

    db.session.refresh(curr_alloc)
    db.session.refresh(new_alloc)
    return {
        "allocation": serialize_allocation(new_alloc),
        "previous_allocation": serialize_allocation(curr_alloc),
    }
