"""
Base resumes, one per job track. The originals in RESUME_DIR are only ever read;
tailored copies are written to data/tailored_resumes/.
"""
import re
from pathlib import Path

import docx

from ..config import BASE_PDF_DIR, PROJECT_ROOT, RESUME_DIR, TAILORED_DIR

TRACKS = {
    # "file" is the .docx the tailor reads. "pdf" is your own PDF of it, used as-is if present
    # (otherwise one is rendered from the .docx).
    "data": {"label": "Data Analyst", "file": "resume_data.docx", "pdf": "resume_data.pdf"},
    "it": {"label": "IT / Help Desk", "file": "resume_it.docx", "pdf": "resume_it.pdf"},
    "software": {"label": "Software", "file": "resume_software.docx", "pdf": "resume_software.pdf"},
}

# Checked in order; first track with a matching title keyword wins
_TRACK_KEYWORDS = [
    ("data", [
        "data analyst", "data analytics", "analytics", "business intelligence", "bi analyst",
        "bi developer", "reporting analyst", "data scientist", "data science", "data engineer",
        "business analyst", "insights analyst", "operations analyst", "sql analyst", "tableau",
        "power bi",
    ]),
    ("it", [
        "help desk", "helpdesk", "service desk", "desktop support", "it support", "technical support",
        "tech support", "support technician", "support specialist", "support analyst", "it technician",
        "it specialist", "computer technician", "field technician", "field service", "network",
        "noc ", "system administrator", "systems administrator", "sysadmin", "tier 1", "tier 2",
        "tier i", "tier ii", "it analyst", "it associate", "end user", "deskside", "service technician",
        "infrastructure technician", "av technician", "telecommunications",
    ]),
    ("software", [
        "software", "developer", "programmer", "engineer", "web ", "full stack", "full-stack",
        "frontend", "front-end", "backend", "back-end", "devops", "python", "java", "automation",
    ]),
]


# Trades that share words like "service technician" / "field engineer" with IT titles
_NOT_TECH = re.compile(
    r"\b(hvac|mechanic|electrician|plumb\w*|welder|diesel|automotive|heavy equipment|refrigeration"
    r"|boiler|roofer|carpenter|cdl|truck|forklift|nurse|nursing|pharmacy|dental|veterinary|medical assistant"
    r"|electrical engineer|mechanical engineer|civil engineer|structural engineer|chemical engineer)\b",
    re.I,
)


def title_is_relevant(title: str) -> bool:
    """True if the job title matches one of our tracks (filters out loose search hits)."""
    t = f" {title.lower()} "
    if _NOT_TECH.search(t):
        return False
    return "analyst" in t or any(w in t for _, words in _TRACK_KEYWORDS for w in words)


def title_track(title: str) -> str | None:
    """Track whose keywords appear in the title, or None if the title doesn't cleanly fit one."""
    t = f" {title.lower()} "
    for track, words in _TRACK_KEYWORDS:
        if any(w in t for w in words):
            return track
    return None


def classify_job(title: str, description: str = "") -> str:
    """Pick the base-resume track for a job. Title decides; description is a tiebreaker."""
    track = title_track(title)
    if track:
        return track
    if "analyst" in f" {title.lower()} ":
        return "data"
    d = (description or "").lower()[:3000]
    scores = {track: sum(d.count(w) for w in words) for track, words in _TRACK_KEYWORDS}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "software"


def load_base_resume(track: str) -> str:
    """Return the base resume for a track as plain text (read-only)."""
    path = RESUME_DIR / TRACKS[track]["file"]
    if not path.exists():
        raise FileNotFoundError(f"Base resume not found: {path} (set RESUME_DIR in .env)")
    d = docx.Document(str(path))
    lines = [p.text.strip() for p in d.paragraphs if p.text.strip()]
    for table in d.tables:
        for row in table.rows:
            lines.append(" | ".join(c.text.strip() for c in row.cells))
    return "\n".join(lines)


def _structured_text(track: str) -> str:
    """Base .docx as text in the same layout the tailor emits, so generate_pdf formats it alike."""
    d = docx.Document(str(RESUME_DIR / TRACKS[track]["file"]))
    lines, seen_header = [], False
    for i, p in enumerate(x for x in d.paragraphs if x.text.strip()):
        text = p.text.strip()
        if i == 0:
            lines.append(text)
            continue
        ppr = p._p.pPr
        is_bullet = (ppr is not None and ppr.numPr is not None) or p.style.name.startswith("List")
        is_bold = all(r.bold for r in p.runs if r.text.strip())
        if is_bold and not is_bullet and "|" not in text and len(text.split()) <= 4:
            lines += ["", text.upper()]
            seen_header = True
        elif not seen_header:
            lines.append(re.sub(r"\s{2,}", " ", text))   # contact / links lines
        else:
            lines.append(f"- {text}" if is_bullet else text)
    return "\n".join(lines)


def base_pdf_path(track: str) -> Path:
    """Untailored PDF for a track: your own PDF from RESUME_DIR if there is one, else one
    rendered from the .docx (re-rendered whenever the .docx is newer)."""
    from .pdf_generator import generate_pdf

    own = RESUME_DIR / TRACKS[track]["pdf"]
    if own.exists():
        return own
    src = RESUME_DIR / TRACKS[track]["file"]
    out = BASE_PDF_DIR / TRACKS[track]["pdf"]
    if not out.exists() or (src.exists() and src.stat().st_mtime > out.stat().st_mtime):
        out.parent.mkdir(parents=True, exist_ok=True)
        generate_pdf(_structured_text(track), out)
    return out


def to_stored_path(path: str | Path) -> str:
    """Store PDF paths relative to the project so moving the folder doesn't break them."""
    path = Path(path)
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def resolve_pdf(stored: str | None) -> Path | None:
    """Stored PDF path -> existing absolute path, or None if the file is gone."""
    if not stored:
        return None
    path = Path(stored)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path if path.exists() else None


def tailored_pdf_path(job_id: int, company: str, title: str) -> Path:
    """data/tailored_resumes/<id>_<company>_<title>/Resume.pdf: employers see a clean filename."""
    slug = re.sub(r"[^A-Za-z0-9]+", "_", f"{company}_{title}").strip("_")[:80]
    folder = TAILORED_DIR / f"{job_id}_{slug}"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "Resume.pdf"
