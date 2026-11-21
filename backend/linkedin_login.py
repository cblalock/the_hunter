"""
Save a logged-in LinkedIn browser session for search.

    python -m backend.linkedin_login

Opens a normal browser window: log in by hand (including any security check), then come back
and press Enter. The session cookies are saved to data/linkedin_session.json, which stays on
your machine (git-ignored). the_hunter never sees or stores your password.
"""
from playwright.sync_api import sync_playwright

from .config import LINKEDIN_SESSION, ensure_data_dir


def main():
    ensure_data_dir()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        page.goto("https://www.linkedin.com/login")
        input("Log in to LinkedIn in the browser window, then press Enter here... ")
        if "/feed" not in page.url and "/jobs" not in page.url:
            print(f"Doesn't look logged in yet (at {page.url}). Saving anyway; search will tell you if it fails.")
        context.storage_state(path=str(LINKEDIN_SESSION))
        browser.close()
    print(f"Saved session to {LINKEDIN_SESSION}")


if __name__ == "__main__":
    main()
