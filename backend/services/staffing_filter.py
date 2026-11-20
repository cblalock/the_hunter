"""
Skip contract-vendor ("C2C") staffing postings.

Some staffing vendors post real contract jobs, but every applicant gets mass-messaged and the
resume is forwarded on to other vendors; they rarely place entry-level people. Two signals:

1. The company is on your blocklist (Settings -> Filters -> Blocked companies). It ships
   empty: add names as you run into them.
2. The posting talks like a C2C vendor: C2C / corp-to-corp, implementation partner, prime
   vendor, visa-status lists (GC-EAD, USC/GC, H1B transfer...). "No C2C" doesn't count, and
   neither does a normal employer's "we can't sponsor H-1B".
Mainstream staffing agencies are exempt from signal 2.
"""
import re

# Mainstream agencies: still allowed even if a posting mentions C2C/visas
_MAINSTREAM = re.compile(
    r"^(randstad|kforce|robert half|insight global|teksystems|hays|vaco|kelly|"
    r"motion recruitment|jobot|cybercoders|yoh|apex systems|beacon hill|aquent|adecco|manpower|"
    r"experis|aerotek|actalent|modis|akkodis)\b"
)

_VENDOR_TALK = re.compile(
    r"\b(c2c|corp[\s-]?to[\s-]?corp|"
    r"prime vendor|tier[\s-]?1 vendor|h[\s-]?1[\s-]?b\s?(holders|candidates|transfer)|gc[\s/-]?ead|h4[\s-]?ead|usc\s?/\s?gc|"
    r"gc\s?/\s?usc|visa independent|opt\s?/\s?cpt|cpt\s?/\s?opt)\b",
    re.I,
)

_NEG_BEFORE = re.compile(r"\b(no|not|nor|without|unable|cannot|can't|won't|does not|do not)\b", re.I)
_NEG_AFTER = re.compile(r"\b(not|no longer|unable|will not|cannot)\b", re.I)


def _norm(company: str | None) -> str:
    s = re.sub(r"[^a-z0-9 ]", "", (company or "").lower().replace("&", " ").replace("-", " "))
    return re.sub(r" +", " ", s).strip()


def body_shop_reason(job, blocked: list[str] | None = None) -> str | None:
    """Why this job looks like a C2C vendor posting, or None."""
    co = _norm(job.company)
    for name in blocked or []:
        n = _norm(name)
        if n and re.match(rf"{re.escape(n)}\b", co):
            return f'"{job.company}" is on your blocked companies list'
    if _MAINSTREAM.match(co):
        return None
    desc = job.description or ""
    for m in _VENDOR_TALK.finditer(desc):
        # "No C2C", "NOT open to C2C", "C2C ... arrangements are not accepted" = a normal employer
        before = desc[max(0, m.start() - 50):m.start()]
        after = desc[m.end():m.end() + 70]
        if _NEG_BEFORE.search(before) or _NEG_AFTER.search(after):
            continue
        return f'posting uses vendor wording "{m.group(0)}"'
    return None
