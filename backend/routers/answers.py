from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..database import SessionLocal
from ..models import Job
from ..services.form_answers import answer_questions, load_profile, save_answer
from ..services.resumes import classify_job

router = APIRouter(tags=["answers"])


class AnswerIn(BaseModel):
    key: str
    answer: str


class FixIn(BaseModel):
    answer: str


class QuestionIn(BaseModel):
    label: str
    options: list[str] = []


class ScreeningIn(BaseModel):
    questions: list[QuestionIn]


@router.get("/answers/pending")
def pending_questions():
    pending = load_profile().get("pending_questions", {})
    return [{"key": k, **v} for k, v in pending.items()]


@router.post("/answers")
def answer_question(body: AnswerIn):
    pending = load_profile().get("pending_questions", {})
    if body.key not in pending:
        raise HTTPException(status_code=404, detail="No such pending question")
    save_answer(pending[body.key]["question"], body.answer.strip())
    return {"ok": True}


def _kind(q: QuestionIn) -> str:
    if q.options:
        return "choice"
    return "number" if any(w in q.label.lower() for w in ("how many", "years", "number")) else "text"


@router.post("/jobs/{job_id}/screening")
def draft_screening_answers(job_id: int, body: ScreeningIn):
    """Draft answers to a job's screening questions (pasted from the application form).
    Saved answers are reused; Claude drafts the rest; anything it can't settle from your
    profile and resume is left blank and queued under "Questions for you"."""
    if not body.questions:
        raise HTTPException(status_code=400, detail="No questions given")
    db = SessionLocal()
    try:
        job = db.query(Job).get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        track = job.resume_track or classify_job(job.title, job.description)
        qs = [{"label": q.label.strip(), "kind": _kind(q), "options": [o.strip() for o in q.options if o.strip()]}
              for q in body.questions if q.label.strip()]
        try:
            filled = answer_questions(qs, track, job.title, job.company)
        except RuntimeError as e:
            raise HTTPException(status_code=400, detail=str(e))
        job.resume_track = track
        job.screening_answers = [{"question": q["label"], "answer": q.get("answer") or "", "options": q["options"]}
                                 for q in filled]
        db.commit()
        return job.screening_answers
    finally:
        db.close()


@router.post("/jobs/{job_id}/answers/{index}")
def fix_answer(job_id: int, index: int, body: FixIn):
    """Correct a drafted answer. The correction is saved to your profile, so the same
    question gets this answer on every later job."""
    db = SessionLocal()
    try:
        job = db.query(Job).get(job_id)
        answers = list(job.screening_answers or []) if job else []
        if not 0 <= index < len(answers):
            raise HTTPException(status_code=404, detail="No such answer")
        answers[index] = {**answers[index], "fixed": body.answer.strip()}
        job.screening_answers = answers
        db.commit()
        save_answer(answers[index]["question"], body.answer.strip())
        return {"ok": True}
    finally:
        db.close()
