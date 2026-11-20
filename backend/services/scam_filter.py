"""
Skip fake / scam job postings: the "no experience needed, reply on WhatsApp" task scams.

Two signals:
1. Wording real tech employers don't use: "no previous experience required", contact over
   WhatsApp/Telegram, personal email addresses, bank-account or buy-your-own-equipment talk.
2. Clone postings: the same description posted under 4+ unrelated "companies". Staffing
   agencies reposting one client's job also produce clones, hence the 4-company bar, and
   clones that read like a contract posting are let through.
"""
import re

_PHRASES = re.compile(
    r"no (previous |prior )?(work |professional |relevant )?experience (is )?(required|needed|necessary)"
    r"|(contact|reach|message|text) (us|me|you) (on|via|through) (whatsapp|telegram|signal)"
    r"|\bwhatsapp\b.{0,60}\b(interview|contact|apply|message)|\btelegram\b"
    r"|[\w.+-]+@(gmail|yahoo|outlook|hotmail|aol|proton)\.(com|me)"
    r"|valid (u\.?s\.? )?bank account|bank account (details|information)"
    r"|purchase (your |the )?(equipment|laptop|software) .{0,40}(reimburs|check)",
    re.I,
)

# Staffing-agency reposts of a real client job read like contract postings
_STAFFING = re.compile(
    r"\bw-?2\b|\bc2c\b|corp.to.corp|\bcontract\b|\bduration\b|our client|end client|pay rate|"
    r"\$\s?\d+(\.\d+)?\s?(/|per )\s?(hr|hour)",
    re.I,
)

CLONE_MIN_COMPANIES = 4  # this many different companies posting the same text = fake


def _lines(desc: str | None) -> set[str]:
    """Normalized sentences/bullets long enough to be distinctive."""
    out = set()
    for part in re.split(r"[\n•]|(?<=[.;])\s+", desc or ""):
        n = re.sub(r" +", " ", re.sub(r"[^a-z0-9 ]", "", part.lower())).strip()
        if len(n) >= 60:
            out.add(n)
    return out


def _co(name: str | None) -> str:
    return (name or "").lower().strip()


class CloneIndex:
    """Which companies have posted each description line, across every job in the DB."""

    def __init__(self, jobs):
        self.by_line: dict[str, set[str]] = {}
        for j in jobs:
            self.add(j)

    def add(self, job):
        for line in _lines(job.description):
            self.by_line.setdefault(line, set()).add(_co(job.company))

    def other_companies(self, job) -> set[str]:
        """Other companies whose posting shares most (>= 60%) of this job's text."""
        lines = _lines(job.description)
        if len(lines) < 3:
            return set()
        me = _co(job.company)
        shared = [l for l in lines if self.by_line.get(l, set()) - {me}]
        if len(shared) / len(lines) < 0.6:
            return set()
        others: dict[str, int] = {}
        for l in shared:
            for co in self.by_line[l] - {me}:
                others[co] = others.get(co, 0) + 1
        # Only companies that share a good chunk, not one boilerplate sentence
        return {co for co, n in others.items() if n >= max(2, len(lines) // 3)}


def scam_reason(job, clones: CloneIndex | None = None) -> str | None:
    """Why this posting looks fake, or None."""
    m = _PHRASES.search(job.description or "")
    if m:
        return f'says "{m.group(0)[:60]}"'
    if clones:
        others = clones.other_companies(job)
        if len(others) + 1 >= CLONE_MIN_COMPANIES and not _STAFFING.search(job.description or ""):
            return f"same description posted by {len(others)} other companies"
    return None
