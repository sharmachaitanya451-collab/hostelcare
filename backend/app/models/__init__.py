"""SQLAlchemy 2 model registry for all 20 HostelCare tables and 3 sequences.

Note: `ComplaintInternalNote` is imported here solely to register its table in
`db.metadata` for Alembic migrations. Student and staff service modules must
never import `ComplaintInternalNote` or `app.models.complaint_internal_notes`.
"""

from app.models.audit import AuditLog
from app.models.complaint_internal_notes import ComplaintInternalNote
from app.models.complaints import (
    Complaint,
    ComplaintAssignment,
    ComplaintAttachment,
    ComplaintHistory,
    ComplaintUpdate,
)
from app.models.fines import Fine, FineDispute, FineHistory
from app.models.identity import PasswordResetToken, StaffProfile, StudentProfile, User
from app.models.notifications import Notification
from app.models.payments import Payment, PaymentAttempt, PaymentEvent
from app.models.rooms import Block, Room, RoomAllocation
from app.models.sequences import complaint_ref_seq, fine_ref_seq, receipt_seq

__all__ = [
    "AuditLog",
    "Block",
    "Complaint",
    "ComplaintAssignment",
    "ComplaintAttachment",
    "ComplaintHistory",
    "ComplaintInternalNote",
    "ComplaintUpdate",
    "Fine",
    "FineDispute",
    "FineHistory",
    "Notification",
    "PasswordResetToken",
    "Payment",
    "PaymentAttempt",
    "PaymentEvent",
    "Room",
    "RoomAllocation",
    "StaffProfile",
    "StudentProfile",
    "User",
    "complaint_ref_seq",
    "fine_ref_seq",
    "receipt_seq",
]
