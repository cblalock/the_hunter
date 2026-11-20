from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String, Text
from sqlalchemy.sql import func
from .database import Base
import enum


class JobStatus(str, enum.Enum):
    new = "new"
    saved = "saved"
    applied = "applied"
    rejected = "rejected"
    interview = "interview"


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    company = Column(String, nullable=False)
    location = Column(String)
    description = Column(Text)
    url = Column(String, unique=True)
    source = Column(String)
    date_posted = Column(String)
    is_remote = Column(String)
    status = Column(String, default=JobStatus.new)
    date_found = Column(DateTime, server_default=func.now())
    applied_at = Column(DateTime, nullable=True)  # set when you mark the job applied
    tailored_resume = Column(Text)
    resume_track = Column(String)    # data | it | software: which base resume fits
    tailored_pdf = Column(String)    # tailored PDF path, relative to the project folder
    notes = Column(Text)
    applicants = Column(Integer)     # from the LinkedIn job page; "Over 100" is stored as 101
    signals = Column(String)         # card badges: "early", "reviewing" (comma-separated)
    score = Column(Integer)          # priority, see services/ranking.py
    score_why = Column(String)       # the reasons behind it, shown in the UI
    screening_answers = Column(JSON) # drafted answers: [{question, answer, options, fixed?}]


class Settings(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, default=1)
    daily_limit = Column(Integer, default=15)          # new jobs per run from non-LinkedIn sites
    linkedin_limit = Column(Integer, default=30)       # LinkedIn jobs ranked per run
    schedule_hour = Column(Integer, default=8)
    schedule_minute = Column(Integer, default=0)
    schedule_enabled = Column(Boolean, default=False)  # off = only runs when "Run now" is clicked
    auto_tailor = Column(Boolean, default=True)
    tailor_linkedin = Column(Boolean, default=False)   # off = LinkedIn jobs just get the matching base resume
    search_configs = Column(JSON, default=list)        # [{query, location, sites, remote_only, hours_old}]
    excluded_locations = Column(JSON, default=list)    # job locations to skip, e.g. ["Austin, TX"]
    blocked_companies = Column(JSON, default=list)     # companies to skip (see staffing_filter.py)
    last_run = Column(DateTime, nullable=True)
    last_run_summary = Column(String, nullable=True)
