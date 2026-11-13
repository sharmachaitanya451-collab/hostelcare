# HostelCare

Single-hostel maintenance and complaint management. Modular monolith: Flask API + React SPA + PostgreSQL.

## Status
Phase 0 (foundation) only. No authentication or complaint features yet. See [docs/TODO.md](docs/TODO.md) and [docs/DEVLOG.md](docs/DEVLOG.md).

## Layout
```
backend/   Flask app factory, SQLAlchemy, Flask-Migrate, pytest
frontend/  React + Vite + Tailwind, Vitest
docs/      ARCHITECTURE.md, adr/, DEVLOG.md, TODO.md
```

## Local development (Windows, PowerShell)
Prerequisites: Python 3.12, Node.js >= 22, PostgreSQL 18 (native), Git.
Use `npm.cmd` if PowerShell blocks `npm.ps1`.

Backend:
```powershell
cd backend
py -3.12 -m venv .venv            # once
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
copy .env.example .env            # then edit values
.\.venv\Scripts\python.exe -m flask --app wsgi run --port 5000
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m ruff check . ; .\.venv\Scripts\python.exe -m ruff format --check .
```

Frontend:
```powershell
cd frontend
npm.cmd install
npm.cmd run dev        # http://localhost:5173, proxies /api to Flask on :5000
npm.cmd test ; npm.cmd run lint ; npm.cmd run build
```

The app database and role are not yet created. `/readyz` reports `not_configured` until `DATABASE_URL` is set.
