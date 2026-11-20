"""Paths and environment settings. Everything personal lives in data/ (git-ignored)."""
import os
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = Path(os.getenv("HUNTER_DATA_DIR", PROJECT_ROOT / "data"))
EXAMPLES_DIR = PROJECT_ROOT / "examples"

DB_PATH = DATA_DIR / "the_hunter.db"
PROFILE_PATH = DATA_DIR / "applicant_profile.json"   # facts + saved screening answers
LINKEDIN_SESSION = DATA_DIR / "linkedin_session.json"  # created by `python -m backend.linkedin_login`
TAILORED_DIR = DATA_DIR / "tailored_resumes"
BASE_PDF_DIR = DATA_DIR / "base_resumes"

# Your base resumes (.docx, optionally a matching .pdf). Defaults to the fake sample candidate.
RESUME_DIR = Path(os.getenv("RESUME_DIR", EXAMPLES_DIR / "resumes"))

# Optional: overrides the city in tailored resume headers (e.g. after a move)
CANDIDATE_LOCATION = os.getenv("CANDIDATE_LOCATION", "").strip()


def ensure_data_dir() -> None:
    """Create data/ and seed the profile from the example on first run."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not PROFILE_PATH.exists():
        shutil.copy(EXAMPLES_DIR / "applicant_profile.example.json", PROFILE_PATH)
