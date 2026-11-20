# HostelCare — Durable Complaint Attachment Storage with Cloudflare R2

HostelCare supports two storage backends for private student complaint photos:

| Backend | Setting | Stored `storage_path` Format | Use Case |
| :--- | :--- | :--- | :--- |
| Local filesystem | `COMPLAINT_ATTACHMENT_STORAGE_BACKEND=local` *(default)* | `YYYY/MM/<uuid>.<ext>` | Local development & automated tests |
| Cloudflare R2 | `COMPLAINT_ATTACHMENT_STORAGE_BACKEND=r2` | `r2://complaints/YYYY/MM/<uuid>.<ext>` | Production on Render (durable across deploys/restarts) |

Reading and deleting attachments dispatch automatically by the stored reference prefix (`r2://...` uses Cloudflare R2; legacy paths without `r2://` resolve from `COMPLAINT_ATTACHMENT_DIR`). Public R2 URLs and public bucket ACLs are **never** used — every download continues to flow through the authenticated, RBAC-enforced Flask route `GET /api/v1/complaints/<complaint_id>/attachments/<attachment_id>`.

---

## 1. Create a Private Cloudflare R2 Bucket

1. Sign in to the Cloudflare Dashboard and open **R2 Object Storage**.
2. Click **Create bucket** (e.g., `hostelcare-attachments-prod`).
3. Leave **Public access / Custom Domains / R2.dev subdomain disabled** (strictly private bucket).
4. Copy your **Cloudflare Account ID** from the R2 Overview page; your S3-compatible endpoint is:
   ```text
   https://<R2_ACCOUNT_ID>.r2.cloudflarestorage.com
   ```

---

## 2. Create a Scoped R2 API Token

1. In R2 Overview, click **Manage R2 API Tokens** -> **Create API Token**.
2. Set permissions to **Object Read & Write** (never Admin/All-buckets unless required).
3. Restrict **Specify bucket(s)** to **only** your private attachment bucket (`hostelcare-attachments-prod`).
4. Copy the generated **Access Key ID** and **Secret Access Key** into a private secret manager or ignored local `.env.*` file (never commit them to Git).

---

## 3. Configure Environment Variables

In Render Dashboard (or a private Git-ignored `.env.*` file locally):

```env
COMPLAINT_ATTACHMENT_STORAGE_BACKEND=r2
R2_ACCOUNT_ID=<your-cloudflare-account-id>
R2_ACCESS_KEY_ID=<your-r2-access-key-id>
R2_SECRET_ACCESS_KEY=<your-r2-secret-access-key>
R2_BUCKET_NAME=hostelcare-attachments-prod
R2_ENDPOINT_URL=https://<your-cloudflare-account-id>.r2.cloudflarestorage.com
R2_REGION=auto
R2_CONNECT_TIMEOUT_SECONDS=5
R2_READ_TIMEOUT_SECONDS=15
```

Keep `COMPLAINT_ATTACHMENT_STORAGE_BACKEND=local` in local development unless explicitly testing R2.

---

## 4. Historical Binary Migration (`backend/uploads/complaints/` -> R2)

The `migrate-attachments-r2` CLI inspects `public.complaint_attachments`, validates every local image's existence, byte size, SHA-256 digest, and magic-byte format, uploads verified binaries to `complaints/YYYY/MM/<uuid>.<ext>`, and atomically updates only `complaint_attachments.storage_path` to `r2://complaints/YYYY/MM/<uuid>.<ext>` using `MIGRATION_DATABASE_URL` (preserving primary keys, UUIDs, complaint FKs, filenames, MIME types, sizes, SHA-256 hashes, and timestamps). Local source files are **never** deleted.

### Step 1: Dry-Run (Default — Safe Inspection Only)

```powershell
# From C:\Projects\HostelCare (with Neon MIGRATION_DATABASE_URL & DATABASE_URL loaded from backend/.env.neon.local):
Push-Location backend
.\.venv\Scripts\python.exe -m flask --app wsgi migrate-attachments-r2
Pop-Location
```

Dry-run validates every local image file, reports any missing/corrupted records, prints planned `r2://complaints/...` targets, performs zero uploads, and makes zero database modifications.

### Step 2: Apply Mode (After Setting R2 Credentials & Approval)

Ensure `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_ENDPOINT_URL`, `R2_REGION=auto`, and `MIGRATION_DATABASE_URL` (`neondb_owner`) are exported into your shell, then run:

```powershell
Push-Location backend
.\.venv\Scripts\python.exe -m flask --app wsgi migrate-attachments-r2 --apply
Pop-Location
```

Notes:
* **Idempotent:** Re-running `--apply` verifies already-migrated `r2://` rows via `head_object` (without duplicate uploads) and reuses matching existing R2 objects cleanly.
* **Least-privilege DB safety:** Uses `MIGRATION_DATABASE_URL` (`neondb_owner`) because `hostelcare_app` holds `SELECT, INSERT` only on `complaint_attachments`.

---

## 5. Verifying the 4 Historical Attachments

1. **Database check (as `neondb_owner`):**
   ```sql
   SELECT id, complaint_id, original_filename, file_size_bytes, mime_type, storage_path, created_at
   FROM public.complaint_attachments
   ORDER BY id;
   ```
   Confirm all 4 `storage_path` values start with `r2://complaints/2026/11/` while all `id`, `complaint_id`, `original_filename`, `file_size_bytes`, `mime_type`, `checksum_sha256`, and `created_at` fields remain identical.
2. **Application check:** Log in as the student owner, assigned technician, or admin/warden and view complaints `4` and `6`; confirm images render through `/api/v1/complaints/<ref>/attachments/<uuid>` with `200 OK`, and verify unauthenticated `GET` requests return `401`.

---

## 6. Troubleshooting

* **Missing `R2_*` configuration at startup:** `ProductionConfig.validate()` rejects `COMPLAINT_ATTACHMENT_STORAGE_BACKEND=r2` if `R2_BUCKET_NAME`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, or `R2_ENDPOINT_URL`/`R2_ACCOUNT_ID` is empty.
* **`404 attachment_file_missing` after switching to Render:** Check whether historical rows still contain legacy local paths (`2026/11/...` instead of `r2://complaints/...`) or whether the object was deleted from the R2 bucket.
* **`502 attachment_storage_error` / signature errors:** Verify `R2_ENDPOINT_URL` matches `https://<account_id>.r2.cloudflarestorage.com` (no trailing path/bucket name), `R2_REGION=auto`, and the API token has **Object Read & Write** permissions for the exact bucket name.
