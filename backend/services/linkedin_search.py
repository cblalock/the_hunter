"""
LinkedIn job search through a saved, logged-in browser session (see backend/linkedin_login.py).

The logged-out search jobspy uses gets rate-limited (HTTP 429) after a handful of queries and
ignores the remote filter. Searching as the user returns what they see in the app, with
working remote / date filters, applicant counts, and an "Applied" marker on jobs already
applied to. Read-only: it opens search results and job pages, nothing else.
"""
import logging
import os
import random
from functools import lru_cache
from urllib.parse import urlencode

import requests
from playwright.sync_api import sync_playwright

from ..config import LINKEDIN_SESSION
from .ranking import ago_to_datetime, parse_applicants

logger = logging.getLogger(__name__)

_CARD = '[componentkey^="job-card-component-ref-"]'

# Card text lines look like: [aria title, title, company, "City, ST (On-site)", ...badges]
_CARDS_JS = """() => {
  const seen = new Set(), out = [];
  for (const el of document.querySelectorAll('[componentkey^="job-card-component-ref-"]')) {
    const id = el.getAttribute('componentkey').split('-').pop();
    if (!/^\\d+$/.test(id) || seen.has(id)) continue;
    seen.add(id);
    let lines = el.innerText.split('\\n').map(s => s.trim()).filter(Boolean);
    if (lines.length > 1 && lines[0].includes(lines[1])) lines = lines.slice(1);
    out.push({id, lines});
  }
  return out;
}"""

_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def has_session() -> bool:
    return LINKEDIN_SESSION.exists()


@lru_cache(maxsize=64)
def _geo_id(location: str) -> str | None:
    """LinkedIn's id for a place name. The typeahead misses "City, ST", so retry with the city alone."""
    return _typeahead_geo(location) or ("," in location and _typeahead_geo(location.split(",")[0])) or None


def _typeahead_geo(location: str) -> str | None:
    try:
        r = requests.get(
            "https://www.linkedin.com/jobs-guest/api/typeaheadHits",
            params={"origin": "jserp", "typeaheadType": "GEO",
                    "geoTypes": "POPULATED_PLACE,ADMIN_DIVISION_2,COUNTRY_REGION", "query": location},
            headers={"User-Agent": _UA},
            timeout=15,
        )
        hits = r.json() if r.ok else []
        return hits[0]["id"] if hits else None
    except Exception as e:
        logger.warning(f"geoId lookup failed for {location!r}: {e}")
        return None


class LinkedInSearch:
    """Context manager: one browser for a whole batch of searches."""

    def __enter__(self):
        if not has_session():
            raise RuntimeError("no saved LinkedIn session (run: python -m backend.linkedin_login)")
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=os.getenv("BROWSER_HEADED", "0") != "1")
        self._context = self._browser.new_context(
            user_agent=_UA, viewport={"width": 1280, "height": 900}, storage_state=str(LINKEDIN_SESSION))
        self.page = self._context.new_page()
        self.page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=15000)
        self.page.wait_for_timeout(1500)
        if "/feed" not in self.page.url:
            self.__exit__(None, None, None)
            raise RuntimeError("saved LinkedIn session expired (run: python -m backend.linkedin_login)")
        return self

    def __exit__(self, *exc):
        try:
            self._browser.close()
        finally:
            self._pw.stop()

    def search(
        self,
        query: str,
        location: str,
        results_wanted: int = 25,
        hours_old: int = 24,
        remote_only: bool = False,
        distance: int = 50,
    ) -> list[dict]:
        """Jobs for one query, skipping any already marked Applied."""
        params = {"keywords": query, "location": location, "f_TPR": f"r{hours_old * 3600}"}
        # The logged-in search page drops the location text and falls back to wherever
        # LinkedIn places the user; only a geoId sticks
        geo_id = _geo_id(location)
        if geo_id:
            params["geoId"] = geo_id
        if remote_only:
            params["f_WT"] = "2"
        else:
            params["distance"] = distance

        jobs: list[dict] = []
        for start in range(0, 100, 25):
            self.page.goto(
                f"https://www.linkedin.com/jobs/search/?{urlencode({**params, 'start': start})}",
                wait_until="domcontentloaded", timeout=30000,
            )
            try:
                self.page.wait_for_selector(_CARD, timeout=15000)
            except Exception:
                break  # no (more) results
            self.page.wait_for_timeout(random.uniform(1500, 3000))
            cards = self.page.evaluate(_CARDS_JS)
            for card in cards:
                lines = card["lines"]
                if len(lines) < 3 or "Applied" in lines:
                    continue
                where = lines[2]
                if remote_only and "(Remote)" not in where:
                    continue
                posted = ago_to_datetime(" ".join(lines))
                signals = [tag for tag, text in (("early", "Be an early applicant"),
                                                 ("reviewing", "Actively reviewing applicants"))
                           if text in lines]
                jobs.append({
                    "title": lines[0],
                    "company": lines[1],
                    "location": where,
                    "url": f"https://www.linkedin.com/jobs/view/{card['id']}",  # same form jobspy saves
                    "source": "linkedin",
                    "is_remote": str("(Remote)" in where),
                    "date_posted": posted.strftime("%Y-%m-%d %H:%M") if posted else None,
                    "signals": ",".join(signals),
                })
            if len(jobs) >= results_wanted or len(cards) < 25:
                break
            self.page.wait_for_timeout(random.uniform(3000, 6000))
        return jobs[:results_wanted]

    def details(self, url: str) -> dict:
        """Applicant count, posting age, description and whether it's closed, from the job page.
        Header line looks like "City, ST · 1 day ago · 38 applicants"."""
        self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
        try:
            self.page.wait_for_selector("text=About the job", timeout=12000)
        except Exception:
            pass
        self.page.wait_for_timeout(random.uniform(800, 1600))
        text = self.page.evaluate("document.body.innerText")
        head, _, rest = text.partition("About the job")
        header = next((l for l in head.splitlines() if "·" in l and ("ago" in l or "applicant" in l)), "")
        posted = ago_to_datetime(header)
        out = {
            "applicants": parse_applicants(header or head),
            "closed": "No longer accepting applications" in head,
        }
        if posted:
            out["date_posted"] = posted.strftime("%Y-%m-%d %H:%M")
        desc = rest.split("Set alert for similar jobs")[0].split("\n… more")[0].strip()
        if desc:
            out["description"] = desc[:15000]
        return out
