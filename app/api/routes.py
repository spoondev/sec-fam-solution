"""FastAPI route definitions"""

from fastapi import APIRouter, Depends, Request, Form, HTTPException, BackgroundTasks, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from pathlib import Path
import logging
import csv
import io

from app.database import get_db
from app.services.fund_service import FundService
from app.services.document_service import DocumentService
from app.services.stats_service import StatsService
from app.services.settings_service import SettingsService
from app.core.scheduler import scheduler_manager
from app.core.sec_client import SECAPIClient
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


# ============ Dashboard ============

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    """Main dashboard with statistics"""
    stats_service = StatsService(db)

    context = {
        "request": request,
        "total_funds": stats_service.get_fund_count(),
        "total_documents": stats_service.get_document_count(),
        "recent_documents": stats_service.get_recent_documents(limit=10),
        "last_job": stats_service.get_last_job_run(),
        "next_scan": scheduler_manager.get_next_run_time(),
        "fund_stats": stats_service.get_fund_statistics(),
        "is_scanning": scheduler_manager.is_scan_running(),
    }
    return templates.TemplateResponse("index.html", context)


# ============ Fund Management ============

@router.get("/funds", response_class=HTMLResponse)
async def list_funds(request: Request, db: Session = Depends(get_db)):
    """Fund management page"""
    fund_service = FundService(db)
    document_service = DocumentService(db)
    funds = fund_service.get_all_funds()

    # Get latest document for each fund
    funds_with_latest = []
    for fund in funds:
        latest_doc = document_service.get_latest_document_for_fund(fund.id)
        funds_with_latest.append({
            "fund": fund,
            "latest_document": latest_doc
        })

    return templates.TemplateResponse("funds.html", {
        "request": request,
        "funds_with_latest": funds_with_latest,
        "error": request.query_params.get("error"),
        "success": request.query_params.get("success"),
    })


@router.post("/funds")
async def add_fund(
    request: Request,
    cik: str = Form(...),
    db: Session = Depends(get_db)
):
    """Add a new fund by CIK"""
    fund_service = FundService(db)

    try:
        # Remove leading zeros from CIK
        cik_clean = cik.strip().lstrip("0") or "0"
        fund = await fund_service.add_fund(cik_clean)
        return RedirectResponse(
            url=f"/funds?success=Added fund {fund.name or fund.cik}",
            status_code=303
        )
    except ValueError as e:
        return RedirectResponse(
            url=f"/funds?error={str(e)}",
            status_code=303
        )
    except Exception as e:
        logger.exception(f"Error adding fund: {e}")
        return RedirectResponse(
            url=f"/funds?error=Failed to add fund: {str(e)}",
            status_code=303
        )


@router.post("/funds/bulk", response_class=HTMLResponse)
async def bulk_add_funds(
    request: Request,
    csv_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Bulk add funds from CSV file"""
    fund_service = FundService(db)
    document_service = DocumentService(db)

    # Result tracking
    result = {
        "added": 0,
        "skipped_duplicates": [],
        "invalid_ciks": [],
        "errors": []
    }

    try:
        # Read and decode CSV content
        content = await csv_file.read()
        try:
            text_content = content.decode('utf-8')
        except UnicodeDecodeError:
            text_content = content.decode('latin-1')

        # Parse CSV
        csv_reader = csv.DictReader(io.StringIO(text_content))

        # Check for CIK column
        if not csv_reader.fieldnames or 'CIK' not in [f.upper() for f in csv_reader.fieldnames]:
            # Re-render the page with error
            funds = fund_service.get_all_funds()
            funds_with_latest = []
            for fund in funds:
                latest_doc = document_service.get_latest_document_for_fund(fund.id)
                funds_with_latest.append({"fund": fund, "latest_document": latest_doc})

            return templates.TemplateResponse("funds.html", {
                "request": request,
                "funds_with_latest": funds_with_latest,
                "error": "CSV file must have a 'CIK' column header",
            })

        # Find the actual CIK column name (case-insensitive)
        cik_column = next(f for f in csv_reader.fieldnames if f.upper() == 'CIK')

        # Get existing CIKs for duplicate checking
        existing_ciks = {fund.cik for fund in fund_service.get_all_funds()}

        # Process each row
        ciks_to_add = []
        for row in csv_reader:
            cik_raw = row.get(cik_column, '').strip()

            if not cik_raw:
                continue

            # Validate: CIK must be numeric only
            if not cik_raw.replace('0', '').isdigit() and cik_raw != '0':
                # Check if it's actually numeric (could be all zeros or have leading zeros)
                if not cik_raw.isdigit():
                    result["invalid_ciks"].append(cik_raw)
                    continue

            # Format: strip leading zeros
            cik_clean = cik_raw.lstrip("0") or "0"

            # Check for duplicates against existing funds
            if cik_clean in existing_ciks:
                result["skipped_duplicates"].append(cik_clean)
                continue

            # Check for duplicates within the CSV itself
            if cik_clean in [c for c, _ in ciks_to_add]:
                continue

            ciks_to_add.append((cik_clean, cik_raw))

        # Add valid CIKs
        for cik_clean, cik_raw in ciks_to_add:
            try:
                await fund_service.add_fund(cik_clean)
                result["added"] += 1
            except ValueError as e:
                # Already exists (race condition) or other validation error
                if "already exists" in str(e).lower():
                    result["skipped_duplicates"].append(cik_clean)
                else:
                    result["errors"].append({"cik": cik_clean, "message": str(e)})
            except Exception as e:
                result["errors"].append({"cik": cik_clean, "message": str(e)})

    except Exception as e:
        logger.exception(f"Error processing CSV: {e}")
        funds = fund_service.get_all_funds()
        funds_with_latest = []
        for fund in funds:
            latest_doc = document_service.get_latest_document_for_fund(fund.id)
            funds_with_latest.append({"fund": fund, "latest_document": latest_doc})

        return templates.TemplateResponse("funds.html", {
            "request": request,
            "funds_with_latest": funds_with_latest,
            "error": f"Error processing CSV file: {str(e)}",
        })

    # Re-fetch funds to show updated list
    funds = fund_service.get_all_funds()
    funds_with_latest = []
    for fund in funds:
        latest_doc = document_service.get_latest_document_for_fund(fund.id)
        funds_with_latest.append({"fund": fund, "latest_document": latest_doc})

    return templates.TemplateResponse("funds.html", {
        "request": request,
        "funds_with_latest": funds_with_latest,
        "bulk_result": result,
    })


@router.post("/funds/{fund_id}/toggle")
async def toggle_fund(fund_id: int, db: Session = Depends(get_db)):
    """Toggle fund active status"""
    fund_service = FundService(db)
    fund = fund_service.toggle_fund_status(fund_id)
    if not fund:
        return RedirectResponse(url="/funds?error=Fund not found", status_code=303)
    return RedirectResponse(url="/funds", status_code=303)


@router.post("/funds/{fund_id}/delete")
async def delete_fund(fund_id: int, db: Session = Depends(get_db)):
    """Delete a fund"""
    fund_service = FundService(db)
    if fund_service.delete_fund(fund_id):
        return RedirectResponse(url="/funds?success=Fund deleted", status_code=303)
    return RedirectResponse(url="/funds?error=Fund not found", status_code=303)


# ============ Documents ============

@router.get("/documents", response_class=HTMLResponse)
async def list_documents(
    request: Request,
    fund_id: int = None,
    page: int = 1,
    db: Session = Depends(get_db)
):
    """Document history page with optional fund filter"""
    document_service = DocumentService(db)
    fund_service = FundService(db)

    page_size = 25
    documents, total = document_service.get_documents(
        fund_id=fund_id,
        offset=(page - 1) * page_size,
        limit=page_size
    )

    total_pages = max(1, (total + page_size - 1) // page_size)

    return templates.TemplateResponse("documents.html", {
        "request": request,
        "documents": documents,
        "funds": fund_service.get_all_funds(),
        "selected_fund_id": fund_id,
        "page": page,
        "total_pages": total_pages,
        "total_documents": total
    })


# ============ Settings ============

@router.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request, db: Session = Depends(get_db)):
    """Settings page"""
    settings_service = SettingsService(db)

    days_of_week = [
        (0, "Monday"), (1, "Tuesday"), (2, "Wednesday"),
        (3, "Thursday"), (4, "Friday"), (5, "Saturday"), (6, "Sunday")
    ]

    return templates.TemplateResponse("settings.html", {
        "request": request,
        "save_location": settings_service.get_document_save_path(),
        "schedule_day": int(settings_service.get("scan_day_of_week", "6")),
        "schedule_hour": int(settings_service.get("scan_hour", "2")),
        "next_scan": scheduler_manager.get_next_run_time(),
        "days_of_week": days_of_week,
        "saved": request.query_params.get("saved"),
        "error": request.query_params.get("error"),
    })


@router.post("/settings")
async def update_settings(
    request: Request,
    save_location: str = Form(...),
    schedule_day: int = Form(...),
    schedule_hour: int = Form(...),
    db: Session = Depends(get_db)
):
    """Update application settings"""
    settings_service = SettingsService(db)

    # Validate save location exists and is writable
    path = Path(save_location)
    try:
        path.mkdir(parents=True, exist_ok=True)
        # Test write access
        test_file = path / ".write_test"
        test_file.touch()
        test_file.unlink()
    except Exception as e:
        return RedirectResponse(
            url=f"/settings?error=Cannot create or write to directory: {e}",
            status_code=303
        )

    # Save settings
    settings_service.set("document_save_path", save_location)
    settings_service.set("scan_day_of_week", str(schedule_day))
    settings_service.set("scan_hour", str(schedule_hour))

    # Update scheduler
    scheduler_manager.reschedule(schedule_day, schedule_hour, 0)

    return RedirectResponse(url="/settings?saved=true", status_code=303)


# ============ Actions ============

@router.post("/scan/trigger")
async def trigger_scan(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Manually trigger a document scan"""
    if scheduler_manager.is_scan_running():
        return RedirectResponse(
            url="/?error=A scan is already running",
            status_code=303
        )

    # Run scan in background
    background_tasks.add_task(scheduler_manager.trigger_manual_scan)

    return RedirectResponse(
        url="/?scan_started=true",
        status_code=303
    )


@router.get("/api/scan/status")
async def get_scan_status():
    """Get current scan status (for AJAX polling)"""
    return {
        "is_running": scheduler_manager.is_scan_running(),
        "job_id": scheduler_manager.get_running_job_id(),
    }


@router.get("/api/job/{job_id}")
async def get_job_status(job_id: int, db: Session = Depends(get_db)):
    """Get job status by ID"""
    stats_service = StatsService(db)
    job = stats_service.get_job_by_id(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "id": job.id,
        "status": job.status,
        "job_type": job.job_type,
        "funds_scanned": job.funds_scanned,
        "documents_found": job.documents_found,
        "documents_downloaded": job.documents_downloaded,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "error_message": job.error_message,
    }


# ============ Job History ============

@router.get("/jobs", response_class=HTMLResponse)
async def job_history(request: Request, db: Session = Depends(get_db)):
    """Job history page"""
    stats_service = StatsService(db)
    jobs = stats_service.get_job_history(limit=50)

    return templates.TemplateResponse("jobs.html", {
        "request": request,
        "jobs": jobs,
    })


# ============ File Browser ============

@router.get("/api/browse")
async def browse_directory(path: str = None):
    """Browse directories for folder picker"""
    import os

    # Default to user's home directory if no path provided
    if not path:
        path = str(Path.home())

    path = Path(path)

    # Validate path exists and is a directory
    if not path.exists():
        raise HTTPException(status_code=404, detail="Path does not exist")
    if not path.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")

    # Get parent directory
    parent = str(path.parent) if path.parent != path else None

    # List directories only (not files)
    directories = []
    try:
        for item in sorted(path.iterdir()):
            if item.is_dir() and not item.name.startswith('.'):
                directories.append({
                    "name": item.name,
                    "path": str(item)
                })
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")

    return {
        "current_path": str(path),
        "parent": parent,
        "directories": directories
    }


# ============ Health Check ============

@router.get("/api/health")
async def health_check():
    """Application health check"""
    api_ok = False
    try:
        async with SECAPIClient(settings.SEC_API_KEY) as client:
            api_ok = await client.test_connection()
    except Exception as e:
        logger.warning(f"Health check API test failed: {e}")

    return {
        "status": "healthy" if api_ok else "degraded",
        "api_connection": api_ok,
        "scheduler_running": scheduler_manager.scheduler.running,
        "next_scan": scheduler_manager.get_next_run_time().isoformat()
            if scheduler_manager.get_next_run_time() else None,
    }
