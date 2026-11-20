from datetime import datetime, timedelta
from types import SimpleNamespace

from backend.services import ranking
from backend.services.location_filter import excluded_location_reason
from backend.services.resumes import classify_job, title_is_relevant
from backend.services.scam_filter import CloneIndex, scam_reason
from backend.services.staffing_filter import body_shop_reason


def job(**kw):
    base = dict(title="Junior Data Analyst", company="Acme", location="Columbus, OH", description="",
                is_remote="False", applicants=None, signals="", date_posted=None, date_found=datetime.utcnow())
    return SimpleNamespace(**{**base, **kw})


def test_required_years():
    assert ranking.required_years("3-5 years of experience with SQL") == 3
    assert ranking.required_years("Minimum of 4 years building production software") == 4
    assert ranking.required_years("Nice to have: 5+ years of experience") is None
    assert ranking.required_years("Serving customers for 30+ years in business") is None


def test_score_prefers_fresh_local_entry_level():
    fresh = job(date_posted=(datetime.utcnow() - timedelta(hours=5)).strftime("%Y-%m-%d %H:%M"), applicants=8,
                description="Entry-level role for recent graduates")
    stale = job(title="Data Analyst", date_posted=(datetime.utcnow() - timedelta(days=10)).strftime("%Y-%m-%d %H:%M"),
                applicants=150, is_remote="True", description="5+ years of experience required")
    assert ranking.score(fresh)[0] > ranking.score(stale)[0]


def test_parse_applicants():
    assert ranking.parse_applicants("City, ST · 1 day ago · 38 applicants") == 38
    assert ranking.parse_applicants("Over 100 applicants") == 101


def test_excluded_locations_match_whole_words():
    assert excluded_location_reason("Austin, TX", ["austin"]) == "austin"
    assert excluded_location_reason("Austintown, OH", ["Austin"]) is None
    assert excluded_location_reason("Columbus, OH", []) is None


def test_staffing_filter():
    assert body_shop_reason(job(description="C2C only. H1B transfer welcome."))
    assert body_shop_reason(job(description="No C2C. W2 only.")) is None
    assert body_shop_reason(job(company="Example Staffing Inc"), ["example staffing"])
    assert body_shop_reason(job(company="Randstad", description="C2C ok")) is None


def test_scam_filter():
    assert scam_reason(job(description="No previous experience required! Contact us on WhatsApp."))
    text = "\n".join(f"Line {i}: we are hiring motivated people for a great remote opportunity with growth." for i in range(4))
    others = [job(company=f"Co {i}", description=text) for i in range(4)]
    assert scam_reason(job(company="Co X", description=text), CloneIndex(others))


def test_tracks():
    assert classify_job("Help Desk Technician") == "it"
    assert classify_job("Junior Data Analyst") == "data"
    assert classify_job("Associate Software Engineer") == "software"
    assert not title_is_relevant("HVAC Service Technician")
