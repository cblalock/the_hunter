import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import SessionLocal, get_db
from ..models import Job
from ..schemas import JobOut, JobUpdate, SearchRequest, SearchResult
from ..services.job_scraper import search_jobs

router = APIRouter(prefix="/jobs", tags=["jobs"])

# In-memory status of manual searches
_search_status: dict = {}


def _run_search(search_id: str, request: SearchRequest):
    # Own session: the request's session is closed by the time a background task runs
    db = SessionLocal()
    try:
        _search_status[search_id] = {"status": "running", "jobs_found": 0}
        jobs = search_jobs(
            query=request.query,
            location=request.location,
            results_wanted=request.results_wanted,
            hours_old=request.hours_old,
            remote_only=request.remote_only,
            sites=request.sites,
        )

        added = 0
        for job_data in jobs:
            # Skip if URL already exists
            if not job_data.get("url"):
                continue
            existing = db.query(Job).filter(Job.url == job_data["url"]).first()
            if existing:
                continue
            job = Job(**job_data)
            db.add(job)
            added += 1

        db.commit()
        _search_status[search_id] = {"status": "complete", "jobs_found": added}
    except Exception as e:
        db.rollback()
        _search_status[search_id] = {"status": "error", "jobs_found": 0, "message": str(e)}
    finally:
        db.close()


@router.post("/search", response_model=SearchResult)
def start_search(request: SearchRequest, background_tasks: BackgroundTasks):
    search_id = str(uuid.uuid4())
    _search_status[search_id] = {"status": "queued", "jobs_found": 0}
    background_tasks.add_task(_run_search, search_id, request)
    return SearchResult(search_id=search_id, status="queued", message="Search started")


@router.get("/search/{search_id}", response_model=SearchResult)
def get_search_status(search_id: str):
    if search_id not in _search_status:
        raise HTTPException(status_code=404, detail="Search not found")
    info = _search_status[search_id]
    return SearchResult(
        search_id=search_id,
        status=info["status"],
        jobs_found=info.get("jobs_found", 0),
        message=info.get("message", ""),
    )


@router.get("", response_model=list[JobOut])
def list_jobs(
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    query = db.query(Job)
    if status:
        query = query.filter(Job.status == status)
    return query.order_by(Job.date_found.desc()).offset(offset).limit(limit).all()


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.patch("/{job_id}", response_model=JobOut)
def update_job(job_id: int, update: JobUpdate, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if update.status is not None:
        if update.status == "applied" and job.status != "applied":
            job.applied_at = datetime.utcnow()
        job.status = update.status
    if update.notes is not None:
        job.notes = update.notes
    if update.tailored_resume is not None:
        job.tailored_resume = update.tailored_resume
    db.commit()
    db.refresh(job)
    return job


@router.delete("/{job_id}")
def delete_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    db.delete(job)
    db.commit()
    return {"ok": True}
