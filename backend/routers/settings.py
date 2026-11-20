import threading

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Settings
from ..schemas import SettingsIn, SettingsOut
from ..services.linkedin_search import has_session
from ..services.scheduler import is_running, request_stop, reschedule, run_daily_pipeline, run_progress

router = APIRouter(prefix="/settings", tags=["settings"])


def _get_or_create(db: Session) -> Settings:
    s = db.query(Settings).filter(Settings.id == 1).first()
    if not s:
        s = Settings(id=1, search_configs=[], excluded_locations=[], blocked_companies=[])
        db.add(s)
        db.commit()
        db.refresh(s)
    return s


def _to_out(s: Settings) -> SettingsOut:
    return SettingsOut(
        daily_limit=s.daily_limit,
        linkedin_limit=s.linkedin_limit,
        schedule_hour=s.schedule_hour,
        schedule_minute=s.schedule_minute,
        schedule_enabled=bool(s.schedule_enabled),
        running=is_running(),
        run_progress=run_progress(),
        auto_tailor=s.auto_tailor,
        tailor_linkedin=bool(s.tailor_linkedin),
        search_configs=s.search_configs or [],
        excluded_locations=s.excluded_locations or [],
        blocked_companies=s.blocked_companies or [],
        linkedin_session=has_session(),
        last_run=s.last_run.isoformat() if s.last_run else None,
        last_run_summary=s.last_run_summary,
    )


@router.get("", response_model=SettingsOut)
def get_settings(db: Session = Depends(get_db)):
    return _to_out(_get_or_create(db))


@router.put("", response_model=SettingsOut)
def update_settings(data: SettingsIn, db: Session = Depends(get_db)):
    s = _get_or_create(db)
    for field, value in data.model_dump(exclude_none=True).items():
        if field in ("excluded_locations", "blocked_companies"):
            value = [v.strip() for v in value if v.strip()]
        setattr(s, field, value)
    db.commit()
    db.refresh(s)
    reschedule(s.schedule_hour, s.schedule_minute, bool(s.schedule_enabled))
    return _to_out(s)


@router.post("/run-now")
def run_now():
    """Start the pipeline in a background thread."""
    if is_running():
        return {"message": "A run is already in progress"}
    threading.Thread(target=run_daily_pipeline, daemon=True).start()
    return {"message": "Run started"}


@router.post("/stop")
def stop_run():
    """Ask the current run to stop after the step it's on."""
    if not is_running():
        return {"message": "Nothing is running"}
    request_stop()
    return {"message": "Stopping after the current step..."}
