from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Job
from ..schemas import TailorRequest, TailorResponse
from ..services.resume_tailor import tailor_and_save
from ..services.resumes import TRACKS, base_pdf_path, resolve_pdf

router = APIRouter(prefix="/resume", tags=["resume"])


@router.get("/tracks")
def list_tracks():
    return {key: t["label"] for key, t in TRACKS.items()}


@router.post("/tailor", response_model=TailorResponse)
def tailor_job_resume(request: TailorRequest, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == request.job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job.description:
        raise HTTPException(
            status_code=400,
            detail="Job has no description to tailor against",
        )
    if request.track and request.track not in TRACKS:
        raise HTTPException(status_code=400, detail=f"Unknown track '{request.track}'")

    try:
        tailor_and_save(job, request.track)
    except (RuntimeError, FileNotFoundError) as e:  # no API key / base resume missing
        raise HTTPException(status_code=400, detail=str(e))
    db.commit()

    return TailorResponse(
        job_id=job.id,
        tailored_resume=job.tailored_resume,
        resume_track=job.resume_track,
        pdf_available=bool(job.tailored_pdf),
    )


@router.get("/{job_id}/download")
def download_resume(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    pdf = resolve_pdf(job.tailored_pdf) or (base_pdf_path(job.resume_track) if job.resume_track else None)
    if not pdf:
        raise HTTPException(status_code=404, detail="No resume PDF for this job yet")

    return FileResponse(str(pdf), media_type="application/pdf", filename=pdf.name)
