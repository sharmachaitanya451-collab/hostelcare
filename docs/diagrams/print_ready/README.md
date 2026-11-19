# HostelCare — Print-Ready Technical Diagrams (`docs/diagrams/print_ready/`)

This directory contains professionally redesigned, print-ready **SVG** (editable vector) and **300 DPI PNG** assets for the B.Tech Seminar II (`CSD0502`) report:

**"HostelCare: A Database-Driven Hostel Management System Using SQL and PostgreSQL"**

All diagrams are designed cleanly on white backgrounds with dark, high-contrast typography, solid vs. dashed line encoding (grayscale-safe for black-and-white A4 printing), and explicit entity/workflow fidelity verified directly against the HostelCare source code, SQLAlchemy 2 models, and Alembic PostgreSQL migrations (`0001_initial_schema` and `0002_complaint_attachments`).

---

## 1. File Inventory & Report Replacement Mapping

| Asset Files (`.svg` + `.png`) | Replaces / Maps To | Pixel Dimensions (300 DPI PNG) | Recommended Word Insertion Width (A4) |
|---|---|---|---|
| `figure_3_1_system_architecture` | **Figure 3.1** (Three-layer modular monolith architecture) | `1872 × 1476` | `6.0 – 6.2 in` (`15.2 – 15.7 cm`) |
| `figure_3_2_user_roles` | **Figure 3.2** (User roles, permissions & access boundaries) | `1881 × 1056` | `6.0 – 6.2 in` (`15.2 – 15.7 cm`) |
| `figure_3_3_complaint_lifecycle` | **Figure 3.3** (Complaint maintenance lifecycle flowchart) | `1888 × 1536` | `6.0 – 6.2 in` (`15.2 – 15.7 cm`) |
| `figure_3_4a_identity_auth` | **Figure 3.4a** (Module A ER sub-diagram: 4 tables) | `1856 × 1344` | `5.9 – 6.2 in` (`15.0 – 15.7 cm`) |
| `figure_3_4b_rooms_allocations` | **Figure 3.4b** (Module B ER sub-diagram: 3 tables) | `1882 × 1277` | `5.9 – 6.2 in` (`15.0 – 15.7 cm`) |
| `figure_3_4c_complaints` | **Figure 3.4c** (Module C ER sub-diagram: 6 tables + `complaint_ref_seq`) | `1867 × 1653` | `5.9 – 6.2 in` (`15.0 – 15.7 cm`) |
| `figure_3_4d_fines_payments` | **Figure 3.4d** (Modules D & E ER sub-diagram: 6 tables + 2 sequences) | `1871 × 1653` | `5.9 – 6.2 in` (`15.0 – 15.7 cm`) |
| `figure_3_4e_notifications_audit` | **Figure 3.4e** (Modules F & G ER sub-diagram: 2 tables) | `1872 × 1116` | `5.9 – 6.2 in` (`15.0 – 15.7 cm`) |

> **Tip for Word Insertion:** Insert the `.png` exports cleanly with `Insert -> Pictures -> This Device` and set width to `6.1 inches` (`15.5 cm`) with **Lock Aspect Ratio** enabled, or insert the `.svg` vector files directly in Microsoft 365 / Word 2019+.

---

## 2. Coordinated ER Sub-Diagram Grouping (All 21 Tables + 3 Sequences)

Instead of crowding 21 PostgreSQL tables into a single unreadable figure, **Figure 3.4** is divided into five cohesive sub-diagrams in **Crow's Foot ER notation**:

1. **Figure 3.4a — Identity, Role Profiles & Password Recovery (4 tables):**
   `users`, `student_profiles`, `staff_profiles`, `password_reset_tokens`
2. **Figure 3.4b — Hostel Infrastructure & Room Allocations (3 tables):**
   `blocks`, `rooms`, `room_allocations`
3. **Figure 3.4c — Complaints, Assignments, Notes, History & Attachments (6 tables + 1 sequence):**
   `complaints`, `complaint_assignments`, `complaint_updates`, `complaint_internal_notes`, `complaint_history`, `complaint_attachments`, plus `<<PostgreSQL Sequence>> complaint_ref_seq` (`CMP-YYYY-NNNNN`)
4. **Figure 3.4d — Fines, Disputes, History, Attempts, Payments & Events (6 tables + 2 sequences):**
   `fines`, `fine_disputes`, `fine_history`, `payment_attempts`, `payments`, `payment_events`, plus `fine_ref_seq` (`FIN-YYYY-NNNNN`) and `receipt_seq` (`RCP-YYYY-NNNNN`)
5. **Figure 3.4e — Notifications & Security Audit Trail (2 tables):**
   `notifications`, `audit_logs`

**Total Verified Schema Coverage:** `4 + 3 + 6 + 6 + 2 = 21 PostgreSQL tables` and `3 PostgreSQL sequences`.

---

## 3. Cross-Module Relationships Reference

Because modular ER diagrams must preserve cross-module foreign keys explicitly without drawing tangled global wires, each sub-diagram shows dashed continuation annotations for external FKs:

- `student_profiles.requested_room_id` (**3.4a**) `->` `rooms.id` (**3.4b**)
- `room_allocations.student_user_id` (**3.4b**) `->` `student_profiles.user_id` (**3.4a**); `allocated_by`, `ended_by` `->` `users.id` (**3.4a**)
- `complaints.student_user_id` (**3.4c**) `->` `student_profiles.user_id` (**3.4a**); `room_id`, `block_id` `->` `rooms.id`, `blocks.id` (**3.4b**)
- `complaint_assignments.staff_user_id` (**3.4c**) `->` `staff_profiles.user_id` (**3.4a**); `assigned_by`, `ended_by`, `author_user_id`, `actor_user_id` `->` `users.id` (**3.4a**)
- `fines.student_user_id` (**3.4d**) `->` `student_profiles.user_id` (**3.4a**); `room_id` `->` `rooms.id` (**3.4b**); `issued_by`, `resolved_by`, `decided_by`, `actor_user_id`, `initiated_by`, `recorded_by` `->` `users.id` (**3.4a**)
- `notifications.recipient_user_id` & `audit_logs.actor_user_id` (**3.4e**) `->` `users.id` (**3.4a**)
