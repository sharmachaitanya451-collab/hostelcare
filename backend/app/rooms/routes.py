"""HTTP routes for admin block, room, and allocation lifecycle management."""

from __future__ import annotations

import json
from typing import Any

from flask import Blueprint, g, jsonify, request

from app.auth.security import require_role
from app.rooms.service import (
    create_block,
    create_room,
    create_room_allocation,
    end_room_allocation,
    get_room,
    list_blocks,
    list_room_allocations,
    list_rooms,
    transfer_room_allocation,
    update_block,
    update_room,
)

bp = Blueprint("rooms", __name__)


def _json_body() -> dict[str, Any]:
    data = request.get_json(silent=True)
    if isinstance(data, str):
        try:
            parsed = json.loads(data)
            if isinstance(parsed, dict):
                return parsed
        except (ValueError, TypeError):
            return {}
    return data if isinstance(data, dict) else {}


# ---------------------------------------------------------------------------
# Block Management Routes (Admin only)
# ---------------------------------------------------------------------------


@bp.get("/api/v1/admin/blocks")
@require_role("admin")
def admin_list_blocks():
    """List all hostel blocks with room and occupancy counts."""
    blocks = list_blocks()
    return jsonify({"blocks": blocks}), 200


@bp.post("/api/v1/admin/blocks")
@require_role("admin")
def admin_create_block():
    """Create a new hostel block."""
    data = _json_body()
    created = create_block(data, g.current_user)
    return jsonify({"block": created}), 201


@bp.patch("/api/v1/admin/blocks/<int:block_id>")
@require_role("admin")
def admin_update_block(block_id: int):
    """Update block name, code, display order, or active status."""
    data = _json_body()
    updated = update_block(block_id, data, g.current_user)
    return jsonify({"block": updated}), 200


# ---------------------------------------------------------------------------
# Room Management Routes (Admin only)
# ---------------------------------------------------------------------------


@bp.get("/api/v1/admin/rooms")
@require_role("admin")
def admin_list_rooms():
    """List rooms with bed occupancy stats, optional block_id/floor/is_active filter."""
    block_id_arg = request.args.get("block_id") or request.args.get("blockId")
    block_id = int(block_id_arg) if block_id_arg and block_id_arg.isdigit() else None

    floor_arg = request.args.get("floor")
    floor = int(floor_arg) if floor_arg and floor_arg.isdigit() else None

    active_arg = request.args.get("is_active") or request.args.get("isActive")
    is_active: bool | None = None
    if active_arg in ("true", "1", "True"):
        is_active = True
    elif active_arg in ("false", "0", "False"):
        is_active = False

    rooms = list_rooms(block_id=block_id, floor=floor, is_active=is_active)
    return jsonify({"rooms": rooms}), 200


@bp.post("/api/v1/admin/rooms")
@require_role("admin")
def admin_create_room():
    """Create a new room in a block."""
    data = _json_body()
    created = create_room(data, g.current_user)
    return jsonify({"room": created}), 201


@bp.get("/api/v1/admin/rooms/<room_identifier>")
@require_role("admin")
def admin_get_room(room_identifier: str):
    """Get full details of a specific room, including bed allocations and residents."""
    room = get_room(room_identifier)
    return jsonify({"room": room}), 200


@bp.patch("/api/v1/admin/rooms/<room_identifier>")
@require_role("admin")
def admin_update_room(room_identifier: str):
    """Update room capacity or active status with safety checks."""
    data = _json_body()
    updated = update_room(room_identifier, data, g.current_user)
    return jsonify({"room": updated}), 200


# ---------------------------------------------------------------------------
# Room Allocation Management Routes (Admin only)
# ---------------------------------------------------------------------------


@bp.get("/api/v1/admin/room-allocations")
@require_role("admin")
def admin_list_allocations():
    """List room allocations with optional room, student, or active-only filters."""
    room_id_arg = request.args.get("room_id") or request.args.get("roomId")
    room_id = int(room_id_arg) if room_id_arg and room_id_arg.isdigit() else None

    student_id = request.args.get("student_id") or request.args.get("studentId")

    active_only_arg = request.args.get("active_only") or request.args.get("activeOnly")
    active_only: bool | None = None
    if active_only_arg in ("true", "1", "True"):
        active_only = True
    elif active_only_arg in ("false", "0", "False"):
        active_only = False

    allocations = list_room_allocations(
        room_id=room_id, student_id=student_id, active_only=active_only
    )
    return jsonify({"allocations": allocations}), 200


@bp.post("/api/v1/admin/room-allocations")
@require_role("admin")
def admin_create_allocation():
    """Allocate an active student to an available bed in a room."""
    data = _json_body()
    created = create_room_allocation(data, g.current_user)
    return jsonify({"allocation": created}), 201


@bp.post("/api/v1/admin/room-allocations/<int:allocation_id>/end")
@require_role("admin")
def admin_end_allocation(allocation_id: int):
    """End an active room allocation with mandatory reason and end date."""
    data = _json_body()
    ended = end_room_allocation(allocation_id, data, g.current_user)
    return jsonify({"allocation": ended}), 200


@bp.post("/api/v1/admin/room-allocations/<int:allocation_id>/transfer")
@require_role("admin")
def admin_transfer_allocation(allocation_id: int):
    """Transfer an active resident to a new room and bed."""
    data = _json_body()
    result = transfer_room_allocation(allocation_id, data, g.current_user)
    return jsonify(result), 200
