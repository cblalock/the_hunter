"""
Skip jobs in locations you've ruled out (Settings -> Filters -> Excluded locations).

Only the job's own location field is checked. Entries match as whole words, case-insensitive,
so "Austin" skips "Austin, TX" but not "Austintown, OH".
"""
import re


def excluded_location_reason(location: str | None, excluded: list[str] | None) -> str | None:
    """The excluded entry this location matches, or None."""
    if not location or not excluded:
        return None
    for entry in excluded:
        entry = (entry or "").strip()
        if entry and re.search(rf"(?<!\w){re.escape(entry)}(?!\w)", location, re.I):
            return entry
    return None
