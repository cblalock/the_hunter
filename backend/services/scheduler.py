"""
The daily pipeline: search -> filter -> rank -> pick a resume (and tailor it).

It never applies to anything. The result is a ranked "Up next" list; you open the posting,
apply yourself, and mark the job Applied.
"""
import logging
import random
import re
import threading
from contextlib import ExitStack
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import func

from .location_filter import excluded_location_reason
from .scam_filter import CloneIndex, scam_reason
from .staffing_filter import body_shop_reason

logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler()
_run_lock = threading.Lock()
_stop = threading.Event()   # set by the UI's Stop button; checked between searches/jobs
_progress = {"text": ""}    # what the current run is doing, shown in the UI header


def is_running() -> bool:
    return _run_lock.locked()


def run_progress() -> str:
    return _progress["text"] if is_running() else ""


def request_stop():
    if is_running():
        _stop.set()
        _progress["text"] = "Stopping after the current step..."


def run_daily_pipeline():
    """Runs on schedule or on demand; one run at a time."""
    if not _run_lock.acquire(blocking=False):
        logger.info("Pipeline already running, skipped")
        return
    _stop.clear()
    _progress["text"] = "Starting..."
    try:
        _pipeline()
    finally:
        _progress["text"] = ""
        _run_lock.release()


def _pipeline():
    from ..database import SessionLocal
    from ..models import Job, Settings
    from .job_scraper import looks_remote, search_jobs
    from .linkedin_search import LinkedInSearch
    from .resume_tailor import tailor_and_save
    from .resumes import classify_job

    db = SessionLocal()
    try:
        settings = db.query(Settings).filter(Settings.id == 1).first()
        if not settings or not settings.search_configs:
            if settings:
                _save(db, settings, "No searches set up yet: add some in Settings")
            return
        configs = settings.search_configs

        errors: list[str] = []
        # Two budgets per run: LinkedIn jobs (ranked using applicant counts from the job page)
        # and everything else. What's left of each is split across the remaining searches,
        # so a search that comes up short passes its share on.
        li_budget = settings.linkedin_limit * 3   # gather extra, rank, keep the best
        li_added = other_added = 0
        new_jobs: list[Job] = []

        # Search as the logged-in user if a session was saved; otherwise jobspy's public search.
        with ExitStack() as stack:
            li = None
            if any("linkedin" in c.get("sites", ["linkedin"]) for c in configs):
                try:
                    li = stack.enter_context(LinkedInSearch())
                except Exception as e:
                    errors.append(f"Logged-in LinkedIn search unavailable, using public search: {e}")

            for n, config in enumerate(configs):
                if n:
                    # Back-to-back public searches get rate-limited
                    _stop.wait(random.uniform(8, 15) if li else random.uniform(20, 40))
                if _stop.is_set():
                    break
                _progress["text"] = f"Searching {n + 1}/{len(configs)}: {config.get('query', '')} ({len(new_jobs)} new so far)"
                searches_left = len(configs) - n
                li_room = -(-(li_budget - li_added) // searches_left)
                other_room = -(-(settings.daily_limit - other_added) // searches_left)

                search_args = dict(
                    query=config.get("query", "software engineer"),
                    location=config.get("location", "United States"),
                    hours_old=config.get("hours_old", 24),
                    remote_only=config.get("remote_only", False),
                    distance=config.get("distance", 50),
                )
                sites = config.get("sites", ["linkedin", "indeed"])
                other_sites = [s for s in sites if s != "linkedin"]
                try:
                    if "linkedin" in sites and li_room > 0:
                        if li:
                            raw = li.search(results_wanted=li_room * 2, **search_args)
                        else:
                            raw = search_jobs(sites=["linkedin"], results_wanted=min(li_room * 2, 50), **search_args)
                            if search_args["remote_only"]:
                                raw = [jd for jd in raw if looks_remote(jd)]
                        added = _add_new(db, raw, li_room)
                        new_jobs += added
                        li_added += len(added)
                    if other_sites and other_room > 0:
                        raw = search_jobs(sites=other_sites, results_wanted=min(other_room * 2, 25), **search_args)
                        added = _add_new(db, raw, other_room)
                        new_jobs += added
                        other_added += len(added)
                except Exception as e:
                    errors.append(f"Search '{config.get('query')}': {e}")

            # Rank the new jobs plus anything still waiting from earlier runs
            ranked = 0
            if not _stop.is_set():
                pool = new_jobs + [j for j in db.query(Job).filter(Job.status == "new").all() if j not in new_jobs]
                ranked = len(_rank(db, pool, settings, li, errors))

        # Pick each job's base resume, and tailor where that's switched on
        tailored = 0
        for job in new_jobs:
            if _stop.is_set():
                break
            if job.status != "new":
                continue  # filtered out while ranking
            is_linkedin = "linkedin.com" in (job.url or "")
            if not settings.auto_tailor or not job.description or (is_linkedin and not settings.tailor_linkedin):
                job.resume_track = classify_job(job.title, job.description)
                continue
            _progress["text"] = f"Tailoring resume: {job.title} at {job.company}"
            try:
                tailor_and_save(job)
                tailored += 1
            except Exception as e:
                errors.append(f"Tailor job {job.id}: {e}")
                job.resume_track = classify_job(job.title, job.description)
        db.commit()

        summary = f"Found {len(new_jobs)}, ranked {ranked}, tailored {tailored}"
        if _stop.is_set():
            summary += " (stopped early)"
        if errors:
            summary += f" | {len(errors)} error(s): {'; '.join(errors[:3])}"
        _save(db, settings, summary)
        logger.info(f"Pipeline complete: {summary}")

    except Exception as e:
        logger.error(f"Pipeline crashed: {e}")
        db.rollback()
    finally:
        db.close()


def _filter_reason(job, settings, clones) -> str | None:
    """Why this job should be skipped, as a note for the UI, or None."""
    from . import ranking

    where = excluded_location_reason(job.location, settings.excluded_locations)
    if where:
        return f"location matches your excluded list ({where})"
    scam = scam_reason(job, clones)
    if scam:
        return f"looks like a fake/scam posting ({scam})"
    shop = body_shop_reason(job, settings.blocked_companies)
    if shop:
        return f"staffing vendor ({shop})"
    years = ranking.too_experienced(job)
    if years:
        return f"software job requires {years}+ years experience"
    return None


def _skip(job, why: str):
    job.status = "rejected"
    job.notes = (job.notes or "") + f"\n[Filter]: {why}, skipped"


def _rank(db, pool: list, settings, li, errors: list[str]) -> list:
    """Filter and score the pool. With a logged-in session, the promising LinkedIn jobs get
    their page read first for applicant count, age and full description."""
    from . import ranking
    from ..models import Job

    clones = CloneIndex(db.query(Job).filter(Job.description.isnot(None)).all())
    for job in pool:
        why = _filter_reason(job, settings, clones)
        if why:
            _skip(job, why)
    pool = [j for j in pool if j.status == "new" and not ranking.is_stale(j)]
    for job in pool:
        job.score, _ = ranking.score(job)

    if li:
        # Card data is enough to see which jobs are worth a page visit
        todo = [j for j in sorted(pool, key=lambda j: j.score, reverse=True)
                if "linkedin.com" in (j.url or "") and "seen" not in (j.signals or "")][:settings.linkedin_limit]
        for i, job in enumerate(todo, 1):
            if _stop.is_set():
                break
            _progress["text"] = f"Checking {i}/{len(todo)}: {job.title} at {job.company}"
            try:
                info = li.details(job.url)
            except Exception as e:
                errors.append(f"Details job {job.id}: {e}")
                continue
            job.signals = ",".join(filter(None, [job.signals, "seen"]))
            job.applicants = info.get("applicants")
            job.date_posted = info.get("date_posted") or job.date_posted
            job.description = info.get("description") or job.description
            clones.add(job)  # full description now, so later clones of it are caught too
            why = _filter_reason(job, settings, clones)
            if why:
                _skip(job, why)
            elif info.get("closed"):
                _skip(job, "no longer accepting applications")
            li.page.wait_for_timeout(random.uniform(1500, 3500))
        pool = [j for j in pool if j.status == "new" and not ranking.is_stale(j)]

    for job in pool:
        job.score, why = ranking.score(job)
        job.score_why = "; ".join(why)
    db.commit()
    return pool


def _add_new(db, raw: list[dict], limit: int) -> list:
    """Save up to `limit` scraped jobs that pass the title checks and aren't already in the DB."""
    from ..models import Job
    from .resumes import title_is_relevant

    added = []
    for jd in raw:
        if len(added) >= limit:
            break
        title = jd.get("title", "")
        if not jd.get("url") or _too_senior(title) or not title_is_relevant(title):
            continue
        if db.query(Job).filter(Job.url == jd["url"]).first():
            continue
        # Same posting cross-listed on another site (in this batch or already saved)
        key = (title.lower(), (jd.get("company") or "").lower())
        if key in {(j.title.lower(), j.company.lower()) for j in added} or db.query(Job).filter(
            func.lower(Job.title) == title.lower(),
            func.lower(Job.company) == (jd.get("company") or "").lower(),
        ).first():
            continue
        job = Job(**jd)
        db.add(job)
        added.append(job)
    db.commit()
    for job in added:
        db.refresh(job)
    return added


_SENIOR_WORDS = re.compile(
    r"\b(senior|sr|lead|principal|staff|manager|director|architect|head of|vp|vice president|iii|iv)\b", re.I
)


def _too_senior(title: str) -> bool:
    """Skip roles well above entry level."""
    return bool(_SENIOR_WORDS.search(title))


def _save(db, settings, summary: str):
    settings.last_run = datetime.utcnow()
    settings.last_run_summary = summary
    db.commit()


def start_scheduler(hour: int = 8, minute: int = 0, enabled: bool = False):
    _scheduler.add_job(
        run_daily_pipeline,
        CronTrigger(hour=hour, minute=minute),
        id="daily_pipeline",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    if not _scheduler.running:
        _scheduler.start()
    if not enabled:
        _scheduler.pause_job("daily_pipeline")
    logger.info(f"Scheduler ready: daily run at {hour:02d}:{minute:02d} {'ON' if enabled else 'OFF (Run now only)'}")


def reschedule(hour: int, minute: int, enabled: bool):
    if _scheduler.running:
        _scheduler.reschedule_job("daily_pipeline", trigger=CronTrigger(hour=hour, minute=minute))
        if enabled:
            _scheduler.resume_job("daily_pipeline")
        else:
            _scheduler.pause_job("daily_pipeline")
        logger.info(f"Daily run {hour:02d}:{minute:02d} {'ON' if enabled else 'OFF'}")


def stop_scheduler():
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
