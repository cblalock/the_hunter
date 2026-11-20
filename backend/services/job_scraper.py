import pandas as pd
from jobspy import scrape_jobs
from typing import Optional
import logging
import re

logger = logging.getLogger(__name__)

# LinkedIn's logged-out search ignores the remote filter (jobspy warns and drops it;
# f_WT=2 is ignored too), so "remote" searches return on-site jobs nationwide.
# Remote searches keep only postings whose text clearly says remote.
_REMOTE = re.compile(
    r"\b(fully remote|100% remote|remote[- ](position|role|opportunity|job|work|first|based)"
    r"|work (from|at) home|wfh|work remotely|this is a remote|location:\s*remote)\b|\(remote\)",
    re.I,
)
_NOT_REMOTE = re.compile(r"\b(on-?site|in[- ]office|hybrid)\b", re.I)


def looks_remote(job: dict) -> bool:
    text = f"{job.get('title') or ''} {job.get('location') or ''} {job.get('description') or ''}"
    return bool(_REMOTE.search(text)) and not _NOT_REMOTE.search(text)


def search_jobs(
    query: str,
    location: str = "United States",
    results_wanted: int = 25,
    hours_old: int = 72,
    remote_only: bool = False,
    sites: Optional[list] = None,
    distance: int = 50,
    easy_apply: bool = False,
) -> list[dict]:
    if sites is None:
        sites = ["linkedin", "indeed", "zip_recruiter", "glassdoor"]

    try:
        jobs_df = scrape_jobs(
            site_name=sites,
            search_term=query,
            location=location,
            distance=distance,
            results_wanted=results_wanted,
            hours_old=hours_old,
            is_remote=remote_only if remote_only else None,
            country_indeed="USA",
            linkedin_fetch_description=True,
            easy_apply=easy_apply or None,
        )
    except Exception as e:
        logger.error(f"jobspy scrape failed: {e}")
        return []

    if jobs_df is None or jobs_df.empty:
        return []

    jobs = []
    for _, row in jobs_df.iterrows():
        url = _get(row, "job_url") or _get(row, "url")
        if not url:
            continue

        jobs.append({
            "title": _get(row, "title") or "Unknown",
            "company": _get(row, "company") or "Unknown",
            "location": _get(row, "location"),
            "description": _get(row, "description"),
            "url": str(url),
            "source": _get(row, "site"),
            "date_posted": str(_get(row, "date_posted") or ""),
            "is_remote": str(_get(row, "is_remote") or ""),
        })

    return jobs


def _get(row, key):
    val = row.get(key) if hasattr(row, "get") else getattr(row, key, None)
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    return val
