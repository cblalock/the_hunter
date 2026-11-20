"""
Fill the app with fake demo data (fake candidate, fake companies) so you can click around
without an API key or a job search.

    python -m backend.demo          # only if the database has no jobs yet
    python -m backend.demo --reset  # wipe data/the_hunter.db first

Scores and filter notes come from the real ranking and filter code.
"""
import json
import sys
from datetime import datetime, timedelta

from .config import DB_PATH, PROFILE_PATH, ensure_data_dir

NOW = datetime.utcnow()


def _ago(hours: float) -> str:
    return (NOW - timedelta(hours=hours)).strftime("%Y-%m-%d %H:%M")


def _desc(*parts: str) -> str:
    return "\n".join(parts)


ABOUT = "We're a mid-sized team that values curiosity, clear writing and owning your work from start to finish."
BENEFITS = "Benefits include health, dental and vision coverage, a 401(k) match and paid time off from day one."

JOBS = [
    # Up next: scored by ranking.score()
    dict(title="Junior Data Analyst", company="Northwind Analytics", location="Columbus, OH", is_remote="False",
         date_posted=_ago(6), applicants=12, signals="early,seen", source="linkedin",
         description=_desc("This is an entry-level role for a recent graduate who likes turning messy data into clear answers.",
                           "You will write SQL against our warehouse and build Tableau dashboards for the operations team.",
                           "0-2 years of experience with SQL and a BI tool; Python is a plus.", ABOUT, BENEFITS)),
    dict(title="IT Support Specialist I", company="Harbor Health Systems", location="Dublin, OH", is_remote="False",
         date_posted=_ago(26), applicants=23, signals="reviewing,seen", source="linkedin",
         description=_desc("Provide tier 1 support to clinic staff in person and over the phone, including device setup and account access.",
                           "1+ years of help desk experience or a CompTIA A+ certification.", ABOUT, BENEFITS)),
    dict(title="Help Desk Technician", company="Bluegrass Credit Union", location="Columbus, OH", is_remote="False",
         date_posted=_ago(50), applicants=None, signals="early", source="indeed",
         description=_desc("Support branch employees with Windows, Microsoft 365 and printers. Entry-level candidates welcome.",
                           "You'll log every request in our ticketing system and escalate network issues to the infrastructure team.", BENEFITS)),
    dict(title="Associate Software Engineer", company="Lumen Lane Software", location="United States (Remote)", is_remote="True",
         date_posted=_ago(70), applicants=101, signals="seen", source="linkedin",
         description=_desc("New grads welcome. Build features across our React front end and Python services.",
                           "You'll pair with a senior engineer for your first quarter and ship to production in week one.", ABOUT)),
    dict(title="Business Intelligence Analyst", company="Cardinal Freight", location="Westerville, OH", is_remote="False",
         date_posted=_ago(120), applicants=61, signals="seen", source="linkedin",
         description=_desc("Own the weekly lane-profitability reporting and partner with finance on forecasts.",
                           "3+ years of experience with SQL and Power BI or Tableau.", BENEFITS)),
    dict(title="Junior Python Developer", company="Tiny Robot Labs", location="United States (Remote)", is_remote="True",
         date_posted=_ago(30), applicants=41, signals="seen", source="linkedin",
         description=_desc("Write and test the Python services behind our warehouse robots' scheduling system.",
                           "1+ years of Python, comfortable with Git and writing tests.", ABOUT)),
    dict(title="Desktop Support Technician", company="Riverbend Schools", location="Columbus, OH", is_remote="False",
         date_posted=_ago(190), applicants=None, signals="", source="indeed",
         description=_desc("Image, repair and deploy staff and student laptops across six campuses.",
                           "A valid driver's license is required for travel between buildings.", BENEFITS)),
    # Caught by the filters (real filter code writes the notes)
    dict(title="Data Entry Analyst", company="Quick Remote Tasks", location="United States (Remote)", is_remote="True",
         date_posted=_ago(10), applicants=None, signals="", source="linkedin",
         description=_desc("No previous experience required! Flexible hours, paid weekly.",
                           "Reply Yes and we will contact you on WhatsApp to schedule your interview.")),
    dict(title="Python Developer", company="Example Vendor Solutions", location="Columbus, OH", is_remote="False",
         date_posted=_ago(20), applicants=None, signals="", source="indeed",
         description=_desc("Our implementation partner needs a Python developer for a 12 month contract.",
                           "C2C only. GC-EAD, USC/GC and H1B transfer candidates welcome.")),
    dict(title="Software Engineer", company="Big Platform Inc", location="Columbus, OH", is_remote="False",
         date_posted=_ago(15), applicants=88, signals="seen", source="linkedin",
         description=_desc("Design and operate distributed services at scale.",
                           "5+ years of experience building production software in Java or Go.")),
]

APPLIED = [
    dict(title="Data Analyst", company="Buckeye Mutual Insurance", location="Columbus, OH", is_remote="False",
         date_posted=_ago(80), applicants=19, signals="seen", source="linkedin", status="applied", applied_hours=46,
         resume_track="data",
         description=_desc("Entry-level analyst on the claims analytics team. SQL, Excel and a BI tool required.",
                           "Recent graduates are encouraged to apply.", BENEFITS),
         screening=[
             {"question": "How many years of SQL experience do you have?", "answer": "2", "options": []},
             {"question": "Are you legally authorized to work in the United States?", "answer": "Yes", "options": ["Yes", "No"]},
             {"question": "Will you now or in the future require sponsorship?", "answer": "No", "options": ["Yes", "No"]},
             {"question": "How many years of Tableau experience do you have?", "answer": "0", "options": [], "fixed": "1"},
         ],
         tailored=True),
    dict(title="IT Technician", company="Scioto Medical Group", location="Columbus, OH", is_remote="False",
         date_posted=_ago(150), applicants=34, signals="seen", source="linkedin", status="interview", applied_hours=100,
         resume_track="it",
         description=_desc("Support two clinics' workstations, printers and badge readers. CompTIA A+ preferred.", BENEFITS),
         screening=[
             {"question": "Do you have a CompTIA A+ certification?", "answer": "Yes", "options": ["Yes", "No"]},
             {"question": "Are you comfortable lifting 25 lbs?", "answer": "Yes", "options": ["Yes", "No"]},
         ]),
]

PENDING = {
    "do you have experience with servicenow": {
        "question": "Do you have experience with ServiceNow?", "kind": "choice", "options": ["Yes", "No"],
        "seen_on": ["IT Support Specialist I @ Harbor Health Systems"]},
    "what are your salary expectations": {
        "question": "What are your salary expectations?", "kind": "text", "options": [],
        "seen_on": ["Junior Data Analyst @ Northwind Analytics"]},
}

TAILORED_SAMPLE = """Alex Rivera
Columbus, OH | (555) 010-0142 | alex.rivera@example.com
github.com/example | linkedin.com/in/example

PROFESSIONAL SUMMARY
Information Systems graduate with hands-on SQL, Excel and Tableau reporting experience, looking to grow as a claims data analyst.

PROFESSIONAL EXPERIENCE
Midwest Grocers Co-op | Data Analyst Intern | Summer 2024
- Built a weekly SQL and Tableau report on store shrink used by 12 managers
- Cleaned 3 years of sales exports in Python (pandas) for a pricing study
- Automated a monthly Excel reconciliation that used to take a full day

TECHNICAL SKILLS
Data: SQL, Excel, Tableau, Python (pandas)

EDUCATION
The Ohio State University | B.S. Information Systems | 2025"""


def main():
    reset = "--reset" in sys.argv
    ensure_data_dir()
    if reset and DB_PATH.exists():
        DB_PATH.unlink()

    from .database import SessionLocal, engine
    from .models import Base, Job, Settings
    from .services import ranking
    from .services.pdf_generator import generate_pdf
    from .services.resumes import classify_job, tailored_pdf_path, to_stored_path
    from .services.scam_filter import CloneIndex
    from .services.scheduler import _filter_reason, _skip

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Job).count():
            print("The database already has jobs. Run with --reset to replace them with demo data.")
            return

        settings = Settings(
            id=1,
            search_configs=[
                {"query": "junior data analyst", "location": "Columbus, OH", "hours_old": 72, "remote_only": False,
                 "distance": 40, "sites": ["linkedin", "indeed"]},
                {"query": "help desk", "location": "Columbus, OH", "hours_old": 72, "remote_only": False,
                 "distance": 40, "sites": ["linkedin", "indeed"]},
                {"query": "junior python developer", "location": "United States", "hours_old": 72, "remote_only": True,
                 "distance": 40, "sites": ["linkedin"]},
            ],
            excluded_locations=[], blocked_companies=[],
            last_run=NOW - timedelta(hours=2),
            last_run_summary="Found 10, ranked 7, tailored 1",
        )
        db.add(settings)

        for n, jd in enumerate(JOBS + APPLIED, 1):
            extra = {k: jd.pop(k) for k in ("status", "applied_hours", "screening", "tailored") if k in jd}
            job = Job(**jd, url=f"https://example.com/jobs/{n}", date_found=NOW - timedelta(hours=3))
            job.resume_track = jd.get("resume_track") or classify_job(job.title, job.description)
            if "status" in extra:
                job.status = extra["status"]
                job.applied_at = NOW - timedelta(hours=extra["applied_hours"])
                job.screening_answers = extra.get("screening")
            db.add(job)
        db.commit()

        clones = CloneIndex([])
        for job in db.query(Job).filter(Job.status == "new").all():
            why = _filter_reason(job, settings, clones)
            if why:
                _skip(job, why)
                continue
            job.score, reasons = ranking.score(job)
            job.score_why = "; ".join(reasons)

        sample = db.query(Job).filter(Job.company == "Buckeye Mutual Insurance").one()
        sample.tailored_resume = TAILORED_SAMPLE
        sample.tailored_pdf = to_stored_path(generate_pdf(TAILORED_SAMPLE, tailored_pdf_path(sample.id, sample.company, sample.title)))
        db.commit()

        profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
        if profile.get("facts", {}).get("name") == "Alex Rivera":  # never touch a real profile
            profile["pending_questions"] = PENDING
            profile["saved_answers"] = {
                "how many years of tableau experience do you have": {
                    "question": "How many years of Tableau experience do you have?", "answer": "1"}}
            PROFILE_PATH.write_text(json.dumps(profile, indent=2), encoding="utf-8")

        print(f"Demo data loaded: {db.query(Job).count()} jobs. Start the app and open http://localhost:8000")
    finally:
        db.close()


if __name__ == "__main__":
    main()
