from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class JobBase(BaseModel):
    title: str
    company: str
    location: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    source: Optional[str] = None
    date_posted: Optional[str] = None
    is_remote: Optional[str] = None


class JobUpdate(BaseModel):
    status: Optional[str] = None
    notes: Optional[str] = None
    tailored_resume: Optional[str] = None


class JobOut(JobBase):
    id: int
    status: str
    date_found: Optional[datetime] = None
    applied_at: Optional[datetime] = None
    tailored_resume: Optional[str] = None
    resume_track: Optional[str] = None
    tailored_pdf: Optional[str] = None
    notes: Optional[str] = None
    applicants: Optional[int] = None
    score: Optional[int] = None
    score_why: Optional[str] = None
    screening_answers: Optional[list] = None

    class Config:
        from_attributes = True


class SearchRequest(BaseModel):
    query: str
    location: str = "United States"
    remote_only: bool = False
    results_wanted: int = 25
    hours_old: int = 72
    sites: list[str] = ["linkedin", "indeed", "zip_recruiter", "glassdoor"]


class SearchResult(BaseModel):
    search_id: str
    status: str
    jobs_found: int = 0
    message: str = ""


class TailorRequest(BaseModel):
    job_id: int
    track: Optional[str] = None   # force a base resume: data | it | software


class TailorResponse(BaseModel):
    job_id: int
    tailored_resume: str
    resume_track: Optional[str] = None
    pdf_available: bool = False


class SettingsIn(BaseModel):
    daily_limit: Optional[int] = None
    linkedin_limit: Optional[int] = None
    schedule_hour: Optional[int] = None
    schedule_minute: Optional[int] = None
    schedule_enabled: Optional[bool] = None
    auto_tailor: Optional[bool] = None
    tailor_linkedin: Optional[bool] = None
    search_configs: Optional[list] = None
    excluded_locations: Optional[list[str]] = None
    blocked_companies: Optional[list[str]] = None


class SettingsOut(BaseModel):
    daily_limit: int
    linkedin_limit: int
    schedule_hour: int
    schedule_minute: int
    schedule_enabled: bool
    running: bool = False
    run_progress: str = ""
    auto_tailor: bool
    tailor_linkedin: bool
    search_configs: list
    excluded_locations: list[str]
    blocked_companies: list[str]
    linkedin_session: bool = False   # a saved logged-in LinkedIn session exists
    last_run: Optional[str] = None
    last_run_summary: Optional[str] = None
