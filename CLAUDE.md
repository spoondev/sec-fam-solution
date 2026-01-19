# SEC Filing Manager - Project Context

## Overview

A FastAPI web application that automatically retrieves and manages SEC N-CSR/N-CSRS filings from sec-api.io. Monitors specified funds by CIK code, downloads new documents on a weekly schedule, and provides a web interface for management.

## Quick Start

```bash
# Activate virtual environment
source .venv/bin/activate

# Run the application
python run.py

# Open browser to http://localhost:8000
```

## Project Structure

```
sec-fam-solution/
├── app/
│   ├── api/routes.py          # All FastAPI endpoints
│   ├── core/
│   │   ├── sec_client.py      # SEC API client (search & download)
│   │   ├── document_processor.py
│   │   ├── scheduler.py       # APScheduler integration
│   │   └── exceptions.py
│   ├── models/                # SQLAlchemy models
│   │   ├── fund.py            # Fund model (CIK, name, ticker)
│   │   ├── document.py        # Document model (filings)
│   │   ├── job.py             # JobRun model (scan history)
│   │   └── setting.py         # Settings key-value store
│   ├── services/              # Business logic
│   │   ├── fund_service.py    # Fund CRUD operations
│   │   ├── document_service.py # Document scanning logic
│   │   ├── stats_service.py   # Dashboard statistics
│   │   └── settings_service.py
│   ├── templates/             # Jinja2 HTML templates (Bootstrap 5)
│   ├── config.py              # Pydantic settings
│   ├── database.py            # SQLite/SQLAlchemy setup
│   └── main.py                # FastAPI app entry point
├── data/                      # Default document storage & SQLite DB
├── requirements.txt
├── run.py                     # Application runner
└── .env                       # Configuration (SEC_API_KEY required)
```

## Tech Stack

- **Framework:** FastAPI (Python)
- **Database:** SQLite with SQLAlchemy ORM
- **Scheduler:** APScheduler
- **Templates:** Jinja2 + Bootstrap 5
- **HTTP Client:** httpx (async)

## Key Features

- Weekly scheduled scans for N-CSR/N-CSRS filings
- Web UI for fund management, document browsing, settings
- Dynamic search/filter on all tables (client-side JavaScript)
- Folder browser for selecting save location
- Deduplication by accession number

## Configuration

Environment variables in `.env`:
- `SEC_API_KEY` - Required: sec-api.io API key
- `DATABASE_URL` - SQLite path (default: `sqlite:///./data/sec_filings.db`)
- `DOCUMENT_SAVE_PATH` - Where to save documents (default: `./data/documents`)
- `SCAN_DAY_OF_WEEK` - 0=Mon, 6=Sun (default: 6)
- `SCAN_HOUR` - Hour for weekly scan (default: 2)

## Web Routes

| Route | Description |
|-------|-------------|
| `/` | Dashboard with stats |
| `/funds` | Fund management (add/remove/toggle) |
| `/documents` | Document history with pagination |
| `/settings` | Save location & schedule config |
| `/jobs` | Scan job history |
| `/scan/trigger` | POST to trigger manual scan |

## Development Notes

- Templates use Bootstrap 5 classes
- All tables have client-side search filtering via JavaScript
- Fund statistics include latest document info
- Server runs on port 8000 by default
