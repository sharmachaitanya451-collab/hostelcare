"""PostgreSQL sequence definitions for human-readable reference numbers."""

from sqlalchemy import Sequence

from app.extensions import db

complaint_ref_seq = Sequence("complaint_ref_seq", start=1, increment=1, metadata=db.metadata)
fine_ref_seq = Sequence("fine_ref_seq", start=1, increment=1, metadata=db.metadata)
receipt_seq = Sequence("receipt_seq", start=1, increment=1, metadata=db.metadata)
