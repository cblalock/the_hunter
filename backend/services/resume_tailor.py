import os

import anthropic

from ..config import CANDIDATE_LOCATION
from .resumes import TRACKS, classify_job, load_base_resume

_client = None


def get_client():
    global _client
    if _client is None:
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("Set ANTHROPIC_API_KEY in .env to use resume tailoring and screening answers")
        _client = anthropic.Anthropic(api_key=key)
    return _client


_LOCATION_RULE = (f"\n7. The candidate now lives in {CANDIDATE_LOCATION}; use that as the location in the header"
                  if CANDIDATE_LOCATION else "")

SYSTEM_PROMPT = f"""You are an expert resume writer tailoring a candidate's base resume to a specific job posting.

CRITICAL RULES:
1. NEVER fabricate experience, skills, tools, metrics, or credentials not present in the base resume
2. NEVER exaggerate years of experience or scope beyond what is written
3. DO reframe and rephrase existing experience to match the job's language and keywords
4. DO reorder sections and select/emphasize the bullets and projects most relevant to this role
5. DO mirror the job posting's terminology only where the candidate genuinely has that experience
6. Keep it truthful and defensible in an interview, and keep it to about one page{_LOCATION_RULE}

OUTPUT FORMAT (plain text, no markdown, no commentary before or after):
Line 1: full name
Line 2: location | phone | email
Line 3: links separated by " | "
(blank line)
Section headers in ALL CAPS on their own line (e.g. PROFESSIONAL SUMMARY, PROJECTS, TECHNICAL SKILLS, PROFESSIONAL EXPERIENCE, EDUCATION)
Entry lines like: Organization | Role | Dates
Bullets start with "- "
Write in implied first person (no "I")."""


def tailor_resume(
    job_title: str, job_company: str, job_description: str, track: str | None = None
) -> tuple[str, str]:
    """Tailor the matching base resume to a job. Returns (track, resume_text)."""
    track = track or classify_job(job_title, job_description)
    base = load_base_resume(track)

    user_message = f"""Base resume ({TRACKS[track]['label']} version):

{base}

Job to tailor for:
Company: {job_company}
Title: {job_title}

Job Description:
{job_description[:8000]}

Write the tailored resume for this job."""

    response = get_client().messages.create(
        model="claude-opus-5-5",
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    text = next((block.text for block in response.content if block.type == "text"), "")
    return track, text.strip()


def tailor_and_save(job, track: str | None = None) -> None:
    """Tailor a Job's resume and write it as a new PDF. Caller commits."""
    from .pdf_generator import generate_pdf
    from .resumes import tailored_pdf_path, to_stored_path

    track, text = tailor_resume(job.title, job.company, job.description, track)
    job.resume_track = track
    job.tailored_resume = text
    job.tailored_pdf = to_stored_path(generate_pdf(text, tailored_pdf_path(job.id, job.company, job.title)))
