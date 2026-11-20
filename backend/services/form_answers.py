"""
Drafts answers to an application's screening questions from your profile
(data/applicant_profile.json) and the matching base resume.

Saved answers are reused first (no API call). Claude handles the rest and is told to leave
an answer blank rather than guess when the facts don't settle it; blank ones are queued as
"Questions for you" so you answer them once and they're reused from then on.
"""
import json
import re

from pydantic import BaseModel

from ..config import PROFILE_PATH, ensure_data_dir
from .resume_tailor import get_client
from .resumes import load_base_resume


def load_profile() -> dict:
    ensure_data_dir()
    with open(PROFILE_PATH, encoding="utf-8") as f:
        return json.load(f)


def _write_profile(profile: dict) -> None:
    PROFILE_PATH.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")


def norm(question: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", "", question.lower().replace("*", "")).strip()


def save_answer(question: str, answer: str) -> None:
    """Remember your answer so the same question is answered automatically next time."""
    profile = load_profile()
    key = norm(question)
    profile.setdefault("saved_answers", {})[key] = {"question": question, "answer": answer}
    profile.get("pending_questions", {}).pop(key, None)
    _write_profile(profile)


def record_pending(job_title: str, job_company: str, questions: list[dict]) -> None:
    """Queue questions that need your answer."""
    profile = load_profile()
    pending = profile.setdefault("pending_questions", {})
    for q in questions:
        entry = pending.setdefault(norm(q["label"]), {
            "question": q["label"], "kind": q.get("kind", "text"), "options": q.get("options", []), "seen_on": []})
        tag = f"{job_title} @ {job_company}"
        if tag not in entry["seen_on"]:
            entry["seen_on"].append(tag)
    _write_profile(profile)


class _Answer(BaseModel):
    index: int
    answer: str       # exact option text for choice fields; digits only for numeric fields; "" if unsure


class _Answers(BaseModel):
    answers: list[_Answer]


SYSTEM_PROMPT = """You draft answers to job application screening questions for a candidate, who reviews them before applying.

RULES:
1. Answer from the candidate facts and resume. Never claim a certification, license, degree, clearance or credential the candidate doesn't have.
2. Years-of-experience questions: count experience the resume shows (jobs, service, projects, coursework). If the skill/tool never appears, answer 0. Round down to a whole number.
3. "Do you have X certification/license/degree?" -> Yes only if it appears in the facts or resume; otherwise No.
4. Choice questions: answer with the EXACT text of one of the listed options.
5. Numeric questions: answer with digits only.
6. Preferences (start date, travel, schedule, shifts, contract terms) -> use the candidate's earlier answers if any apply, otherwise answer agreeably (e.g. available in 2 weeks, open to the schedule).
7. If the facts and resume don't settle a factual question, return an empty answer. Do not guess; the candidate will answer it.
8. EEO / self-identification questions: follow the candidate facts exactly; if they don't cover it, return an empty answer."""


def answer_questions(questions: list[dict], track: str, job_title: str, job_company: str) -> list[dict]:
    """questions: [{label, kind, options}] -> same list with 'answer' (str or None) added.
    Unanswered questions are queued for you."""
    profile = load_profile()
    saved = profile.get("saved_answers", {})

    pending = []
    for i, q in enumerate(questions):
        hit = saved.get(norm(q["label"]))
        q["answer"] = hit["answer"] if hit else None
        if q["answer"] is None:
            pending.append((i, q))

    if pending:
        listing = "\n".join(
            f"{i}. [{q.get('kind', 'text')}] {q['label']}"
            + (f"\n   Options: {' | '.join(q['options'])}" if q.get("options") else "")
            for i, q in pending
        )
        user_message = f"""Candidate facts:
{json.dumps(profile.get('facts', {}), indent=2, ensure_ascii=False)}

Candidate's own answers to earlier application questions (their stated preferences;
apply them to similar questions):
{json.dumps(list(saved.values()), indent=2, ensure_ascii=False) if saved else "(none yet)"}

Candidate resume:
{load_base_resume(track)}

Job: {job_title} at {job_company}

Questions (answer each by its index):
{listing}"""

        response = get_client().messages.parse(
            model="claude-sonnet-5-5",  # plenty for screening questions, cheaper than Opus
            max_tokens=4000,
            output_config={"effort": "low"},
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            output_format=_Answers,
        )
        for a in response.parsed_output.answers:
            if 0 <= a.index < len(questions) and a.answer.strip():
                q = questions[a.index]
                if q.get("options") and a.answer.strip() not in q["options"]:
                    continue  # not a real option -> leave it for the user
                q["answer"] = a.answer.strip()

    unanswered = [q for q in questions if not q.get("answer")]
    if unanswered:
        record_pending(job_title, job_company, unanswered)
    return questions
