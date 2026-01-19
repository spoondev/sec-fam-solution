# SEC Filing Manager

Automated retrieval and management of SEC N-CSR/N-CSRS filings from sec-api.io.

## Project Structure

```
sec-fam-solution/
├── app/
│   ├── api/routes.py          # FastAPI endpoints
│   ├── core/
│   │   ├── sec_client.py      # SEC API client
│   │   ├── document_processor.py
│   │   ├── scheduler.py       # APScheduler integration
│   │   └── exceptions.py
│   ├── models/                # SQLAlchemy models
│   ├── services/              # Business logic
│   ├── templates/             # HTML templates
│   ├── config.py              # Configuration
│   ├── database.py            # Database setup
│   └── main.py                # FastAPI app
├── data/                      # Default document storage
├── requirements.txt
├── run.py                     # Application runner
└── .env                       # Configuration
```

## Features

### Core Functionality

- Retrieves N-CSR and N-CSRS documents from sec-api.io
- Weekly scheduled scans (configurable day/time)
- Tracks document history in SQLite database
- Only downloads new documents (deduplication by accession number)
- File naming convention: `[Fund Name]-[Ticker]-[Reporting Date]-[Form Type].html`

### Web Interface (http://localhost:8000)

- **Dashboard**: Stats overview, fund statistics, recent documents
- **Funds**: Add/remove funds by CIK code via web UI
- **Documents**: Browse all downloaded documents with pagination
- **Settings**: Change save location, schedule day/time
- **Job History**: View past scan results
- **Manual Scan**: Trigger scans via sidebar button

### Technical Features

- API key validation before each scan
- Error handling with job status tracking
- Rate limiting protection with retry logic

## Installation

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd sec-fam-solution
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Configure your SEC API key in `.env`:
   ```
   SEC_API_KEY=your_api_key_here
   ```

## Usage

### Running the Application

```bash
python run.py
```

Then open http://localhost:8000 in your browser.

### Getting Started

1. **Add funds**: Go to the Funds page and enter CIK codes for the funds you want to monitor
2. **Run a scan**: Click "Run Scan Now" in the sidebar to fetch documents
3. **Configure settings**: Adjust the save location and schedule as needed

### CIK Codes

You can add CIK codes directly through the web interface. Simply enter the CIK (with or without leading zeros) on the Funds page, and the system will automatically look up the fund name and ticker from the SEC API.

## Configuration

Configuration is managed through environment variables in `.env`:

| Variable | Description | Default |
|----------|-------------|---------|
| `SEC_API_KEY` | Your sec-api.io API key | (required) |
| `DATABASE_URL` | SQLite database path | `sqlite:///./data/sec_filings.db` |
| `DOCUMENT_SAVE_PATH` | Where to save downloaded documents | `./data/documents` |
| `SCAN_DAY_OF_WEEK` | Day for weekly scan (0=Mon, 6=Sun) | `6` |
| `SCAN_HOUR` | Hour for weekly scan (0-23) | `2` |
| `APP_PORT` | Web server port | `8000` |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Dashboard |
| `/funds` | GET/POST | Fund management |
| `/documents` | GET | Document history |
| `/settings` | GET/POST | Application settings |
| `/jobs` | GET | Job history |
| `/scan/trigger` | POST | Trigger manual scan |
| `/api/health` | GET | Health check |
| `/api/scan/status` | GET | Current scan status |

## License

MIT
