"""Resolves --due / --priority / --tag values.

Dates come only from --due, never from the task text, because dateparser's
search mode happily reads ordinary words ("may", "second") as dates.
"""
import datetime as dt
import os

import dateparser

WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


def parse_date(text: str, today: dt.date | None = None) -> dt.date:
    """Parse a --due value: weekday names, today/tomorrow, 10/21, 2026-10-21, "in 3 days", next-week."""
    today = today or dt.date.today()
    s = text.lower().strip()
    if any(c.isalpha() for c in s):
        s = s.replace("-", " ")

    if s in ("today", "tod"):
        return today
    # dateparser resolves bare weekday names inconsistently (on a Thursday, "fri"
    # came back as the Friday a week later), so weekdays are handled here:
    # always the next occurrence strictly after today.
    for i, name in enumerate(WEEKDAYS):
        if len(s) >= 3 and name.startswith(s):
            delta = (i - today.weekday()) % 7 or 7
            return today + dt.timedelta(days=delta)

    parsed = dateparser.parse(
        s,
        settings={
            "PREFER_DATES_FROM": "future",
            "DATE_ORDER": os.environ.get("TODO_DATE_ORDER", "MDY"),
            "RELATIVE_BASE": dt.datetime.combine(today, dt.time()),
        },
    )
    if parsed is None:
        raise ValueError(f"can't understand --due '{text}'")
    return parsed.date()


def match_option(value: str, options: list[str], kind: str) -> str:
    """Resolve a shorthand against a Notion select's options: exact, then prefix, then substring."""
    v = value.lower()
    for test in (lambda o: o == v, lambda o: o.startswith(v), lambda o: v in o):
        hits = [o for o in options if test(_plain(o))]
        if len(hits) == 1:
            return hits[0]
        # "ess" should mean "Essential", not be ambiguous with "Essential - Soon":
        # when one hit is contained in all the others, take it.
        base = [h for h in hits if all(_plain(h) in _plain(o) for o in hits)]
        if len(base) == 1:
            return base[0]
        if len(hits) > 1:
            raise ValueError(f"{kind} '{value}' is ambiguous: {', '.join(hits)}")
    raise ValueError(f"unknown {kind} '{value}'; options: {', '.join(options)}")


def _plain(option: str) -> str:
    # Notion option names often carry emoji ("🐞 Bug"); match on the words only.
    return "".join(c for c in option if c.isalnum() or c in " -").strip().lower()

