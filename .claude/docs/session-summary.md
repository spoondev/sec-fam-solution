# SEC Filing Manager - Session Summary

**Date:** 2026-01-19
**Project:** sec-fam-solution
**Repository:** https://github.com/spoondev/sec-fam-solution

---

## Project Overview

Built a complete solution for retrieving SEC filings (N-CSR and N-CSRS forms) from the sec-api.io API. The application monitors specified funds by CIK code, downloads new documents on a weekly schedule, and provides a web interface for management.

---

## User Requirements

### Core Requirements
- Retrieve documents from sec-api.io API
- Check periodically (weekly) for documents of certain types (N-CSR, N-CSRS)
- Track entities by CIK codes (funds)
- Keep records of documents released and when
- Only retrieve new documents since last batch run
- Save documents to user-specified destination
- File naming convention: `[Name of fund]-[ticker]-[reporting date]`

### Stretch Goals (Requested)
- Extract fund data: Total assets, Common shares outstanding, NAV
- Local web interface to:
  - Change file save location
  - Show stats about statements
  - Manually trigger document scans
  - Add/remove funds via web UI

### Additional Features Added
- Folder browser modal for selecting save location via file system navigation

---

## Technical Decisions

### Technology Stack
- **Framework:** FastAPI (Python)
- **Database:** SQLite with SQLAlchemy ORM
- **Scheduler:** APScheduler (built-in Python scheduler)
- **Templates:** Jinja2 with Bootstrap 5
- **HTTP Client:** httpx (async)
- **Form Types:** N-CSR, N-CSRS (certified shareholder reports)

### User Preferences (from questions asked)
| Question | User Selection |
|----------|---------------|
| Form types to monitor | N-CSR / N-CSRS |
| Web stack preference | Python (FastAPI + simple HTML) |
| Scheduling approach | Built-in scheduler |
| CIK input method | Web interface input |
| GitHub repo visibility | Public |

---

## Architecture

### Project Structure
```
sec-fam-solution/
├── app/
│   ├── api/routes.py          # FastAPI endpoints
│   ├── core/
│   │   ├── sec_client.py      # SEC API client
│   │   ├── document_processor.py
│   │   ├── scheduler.py       # APScheduler integration
│   │   └── exceptions.py
│   ├── models/                # SQLAlchemy models (Fund, Document, JobRun, Setting)
│   ├── services/              # Business logic layer
│   ├── templates/             # Jinja2 HTML templates
│   ├── config.py              # Pydantic settings
│   ├── database.py            # Database setup
│   └── main.py                # FastAPI app entry point
├── data/                      # Default document storage
├── requirements.txt
├── run.py                     # Application runner
├── .env                       # Configuration (contains API key)
├── .env.example               # Template for .env
├── .gitignore
└── README.md
```

### Database Schema
- **funds:** CIK, name, ticker, is_active, timestamps
- **documents:** fund_id, accession_number, form_type, filed_at, local_path, file_size, etc.
- **job_runs:** job_type, status, funds_scanned, documents_found/downloaded, timestamps
- **settings:** key-value store for app configuration

### API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard |
| `/funds` | GET/POST | Fund management |
| `/funds/{id}/toggle` | POST | Toggle fund active status |
| `/funds/{id}/delete` | POST | Delete fund |
| `/documents` | GET | Document history |
| `/settings` | GET/POST | Application settings |
| `/jobs` | GET | Job history |
| `/scan/trigger` | POST | Manual scan trigger |
| `/api/health` | GET | Health check |
| `/api/browse` | GET | Folder browser for file picker |
| `/api/scan/status` | GET | Current scan status |
| `/api/job/{id}` | GET | Job details |

---

## SEC API Integration

### API Details
- **Provider:** sec-api.io
- **API Key:** `c49f4c26579601638c8c962c1f1fbabb4a84f8f4f57cff398a90dd54250c12bc`
- **Query API:** `https://api.sec-api.io`
- **Download API:** `https://archive.sec-api.io`

### Query Syntax
- CIK filter: `cik:320193` or `cik:(123, 456, 789)`
- Form type: `formType:"N-CSR" OR formType:"N-CSRS"`
- Date range: `filedAt:[2021-01-01 TO 2021-12-31]`
- Authentication: `Authorization: API_KEY` header

### Download URL Pattern
```
https://archive.sec-api.io/<cik>/<accession-number-no-hyphens>/<filename>
```

---

## Configuration

### Environment Variables (.env)
```
SEC_API_KEY=<api_key>
DATABASE_URL=sqlite:///./data/sec_filings.db
DOCUMENT_SAVE_PATH=./data/documents
SCAN_DAY_OF_WEEK=6  # Sunday
SCAN_HOUR=2
SCAN_MINUTE=0
APP_HOST=0.0.0.0
APP_PORT=8000
DEBUG=false
```

### Default Schedule
- Weekly scan on Sunday at 2:00 AM
- Configurable via web interface

---

## Git History

### Commits
1. **92c402d** - Initial commit: SEC Filing Manager
2. **ba6dd67** - Add folder browser to settings page

---

## Running the Application

```bash
cd /Users/georgespooner/ai-projects/sec-fam-solution
python run.py
```

Open browser to: http://localhost:8000

---

## Dependencies

```
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
python-multipart>=0.0.6
jinja2>=3.1.3
sqlalchemy>=2.0.25
httpx>=0.26.0
apscheduler>=3.10.4
pydantic>=2.5.0
pydantic-settings>=2.1.0
python-dotenv>=1.0.0
beautifulsoup4>=4.12.0
python-dateutil>=2.8.2
```

---

## Future Enhancements (Not Yet Implemented)

1. **Fund data extraction:** Parse N-CSR documents for total assets, shares outstanding, NAV
2. **N-PORT integration:** Use N-PORT filings for more structured fund data
3. **XBRL parsing:** Extract financial data from XBRL-tagged filings
4. **Email notifications:** Alert when new documents are downloaded
5. **Multiple form types:** Support for additional SEC form types

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `app/core/sec_client.py` | SEC API client with search and download |
| `app/core/scheduler.py` | APScheduler integration |
| `app/services/document_service.py` | Document scanning logic |
| `app/api/routes.py` | All FastAPI endpoints |
| `app/templates/settings.html` | Settings page with folder browser |

---

## Session Notes

- User prefers web interface for all configuration (no JSON/CSV files)
- API key is for free tier of sec-api.io
- Application tested and confirmed working
- Folder browser feature added as enhancement to settings page
