"""
Rank jobs so your limited applications go to the ones most likely to get a response:
fresh postings, few applicants, local, actually entry level.

Signals come from the search card ("Posted 8 hours ago", "Be an early applicant") and,
for the jobs worth a closer look, the job page ("City, ST · 1 day ago · 38 applicants"
plus the description).
"""
import re
from datetime import datetime, timedelta

MAX_AGE_DAYS = 14   # older postings are usually filled or buried
PER_COMPANY = 1     # per run, so one staffing agency's postings can't take over the list

_AGO = re.compile(r"(\d+)\s+(minute|hour|day|week|month)s?\s+ago", re.I)
_APPLICANTS = re.compile(r"(over\s+)?([\d,]+)\s+(?:applicants|people clicked apply)", re.I)

_ENTRY_TITLE = re.compile(
    r"\b(junior|jr|entry|associate|intern|internship|apprentice|new grad|graduate|trainee|"
    r"early career|level 1|tier 1|i)\b(?!/)", re.I)
_ENTRY_DESC = re.compile(
    r"\b(entry[- ]level|new grads?|recent (college )?grad(uate)?s?|0\s*[-–to]+\s*[12]\+?\s*years?|"
    r"no (prior |professional )?experience (required|necessary)|1\+?\s*years?)\b", re.I)
# "5+ years", "5-7 years", "minimum of 4 years" of experience
_YEARS = re.compile(r"\b(\d{1,2})\s*(?:\+|[-–to]+\s*\d{1,2})?\s*\+?\s*years?\b", re.I)


def ago_to_datetime(text: str, now: datetime | None = None) -> datetime | None:
    """UTC time for "Posted 8 hours ago" / "Reposted 2 weeks ago"; None if not found."""
    m = _AGO.search(text or "")
    if not m:
        return None
    n, unit = int(m.group(1)), m.group(2).lower()
    days = {"minute": n / 1440, "hour": n / 24, "day": n, "week": 7 * n, "month": 30 * n}[unit]
    return (now or datetime.utcnow()) - timedelta(days=days)


def parse_applicants(text: str) -> int | None:
    m = _APPLICANTS.search(text or "")
    if not m:
        return None
    n = int(m.group(2).replace(",", ""))
    return n + 1 if m.group(1) else n


def posted_at(job) -> datetime | None:
    """When the job was posted: our stored ISO stamp, jobspy's date, or failing that when we found it."""
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime((job.date_posted or "")[:16 if "%H" in fmt else 10], fmt)
        except ValueError:
            pass
    return job.date_found


# Requirement wording that isn't "of experience": "3+ years building and operating production software"
_YEARS_ASK = re.compile(
    r"\b(?:at least|minimum(?: of)?|min\.?)\s+(\d{1,2})\s+years?\b"
    r"|\b(\d{1,2})\s*\+\s*years?\b"
    r"|\b(\d{1,2})\s+or more\s+years?\b", re.I)
_RANGE_START = re.compile(r"\b(\d{1,2})\s*(?:-|–|—|to|â€“|â€”)\s*$", re.I)
# "Nice to have: 5+ years ..." isn't a requirement; "30+ years in business" is about the company
_NOT_REQUIRED = re.compile(r"prefer|nice to have|bonus|ideally|a plus", re.I)
_ABOUT_COMPANY = re.compile(r"^\W*(in business|of (service|history|excellence|experience serving)|old|ago|"
                            r"in the industry serving|of growth)", re.I)


def required_years(description: str) -> int | None:
    """Smallest "N years" experience requirement, e.g. 3 for "3-5 years of experience" or
    "3+ years building production software". Preferred/nice-to-have lines don't count."""
    desc = description or ""
    asks = []

    def line_of(pos: int) -> str:
        start = desc.rfind("\n", 0, pos) + 1
        end = desc.find("\n", pos)
        return desc[start:end if end != -1 else len(desc)]

    for m in _YEARS.finditer(desc):
        after = desc[m.end():m.end() + 40].lower()
        if ("experience" in after or "exp" in after[:6]) and not _NOT_REQUIRED.search(line_of(m.start())):
            asks.append(int(m.group(1)))
    for m in _YEARS_ASK.finditer(desc):
        n = int(next(g for g in m.groups() if g))
        low = _RANGE_START.search(desc[max(0, m.start() - 12):m.start()])
        if low:  # "2-6+ years" / "3â€“5+ years" (mangled en dash) asks for the low end
            n = min(n, int(low.group(1)))
        if n > 15 or _ABOUT_COMPANY.search(desc[m.end():m.end() + 40]) or _NOT_REQUIRED.search(line_of(m.start())):
            continue
        asks.append(n)
    return min(asks) if asks else None


SOFTWARE_MAX_YEARS = 2  # software jobs asking for more than this are filtered out (entry-level search)


def too_experienced(job) -> int | None:
    """Years required if this is a software-track job asking for more than SOFTWARE_MAX_YEARS."""
    from .resumes import classify_job

    years = required_years(job.description or "")
    if years is not None and years > SOFTWARE_MAX_YEARS and classify_job(job.title, job.description) == "software":
        return years
    return None


def score(job, now: datetime | None = None) -> tuple[int, list[str]]:
    """(score, reasons). Higher = apply sooner. Reasons are shown in the UI."""
    now = now or datetime.utcnow()
    pts, why = 0, []
    signals = set((job.signals or "").split(","))

    posted = posted_at(job)
    if posted:
        age = (now - posted).total_seconds() / 86400
        fresh = 35 if age <= 1 else 25 if age <= 3 else 12 if age <= 7 else 0
        pts += fresh
        why.append(f"posted {_age_label(age)} +{fresh}")

    n = job.applicants
    if n is not None:
        few = 25 if n < 10 else 20 if n < 25 else 12 if n < 50 else 5 if n <= 100 else -5 if n > 200 else 0
        pts += few
        why.append(f"{'over ' + str(n - 1) if n in (101, 201) else n} applicants {few:+d}")
    elif "early" in signals:
        pts += 18
        why.append("early applicant +18")

    if "reviewing" in signals:
        pts += 5
        why.append("actively reviewing +5")

    remote = (job.is_remote or "").lower() == "true" or "(remote)" in (job.location or "").lower()
    if not remote:
        pts += 15
        why.append("local +15")
    elif n is not None and n > 100:
        # Remote postings with 100+ applicants: mass "entry-level" listings, often resume harvesting
        pts -= 15
        why.append("remote, 100+ applicants -15")

    if _ENTRY_TITLE.search(job.title or ""):
        pts += 15
        why.append("entry-level title +15")
    desc = job.description or ""
    if _ENTRY_DESC.search(desc):
        pts += 10
        why.append("entry-level wording +10")
    years = required_years(desc)
    if years is not None and years >= 3:
        cost = 20 if years >= 5 else 8
        pts -= cost
        why.append(f"asks {years}+ yrs -{cost}")

    return pts, why


def is_stale(job, now: datetime | None = None) -> bool:
    posted = posted_at(job)
    return bool(posted) and (now or datetime.utcnow()) - posted > timedelta(days=MAX_AGE_DAYS)


def pick(jobs: list, n: int) -> list:
    """Top-n by score, at most PER_COMPANY per company."""
    per_co: dict[str, int] = {}
    out = []
    for job in sorted(jobs, key=lambda j: j.score or 0, reverse=True):
        co = (job.company or "").lower()
        if per_co.get(co, 0) >= PER_COMPANY:
            continue
        per_co[co] = per_co.get(co, 0) + 1
        out.append(job)
        if len(out) >= n:
            break
    return out


def _age_label(days: float) -> str:
    if days < 1:
        return f"{max(1, round(days * 24))}h ago"
    return f"{round(days)}d ago"
