"""Reusable breakdowns stored as YAML — the path to needing Claude less over time.

Templates live outside the repo (default ~/.config/todo-capture/templates.yaml)
because they tend to name real people and places.
"""
import datetime as dt
import os
from pathlib import Path

import yaml

from .breakdown import Breakdown, Subtask


def path() -> Path:
    default = Path.home() / ".config" / "todo-capture" / "templates.yaml"
    return Path(os.environ.get("TODO_TEMPLATES", default)).expanduser()


def load() -> dict:
    p = path()
    return (yaml.safe_load(p.read_text()) or {}) if p.exists() else {}


def apply(name: str, title: str, due: dt.date | None, priority: str | None) -> Breakdown:
    templates = load()
    if name not in templates:
        raise ValueError(f"no template '{name}' in {path()} (have: {', '.join(templates) or 'none'})")
    t = templates[name]
    subtasks = []
    for sub in t.get("subtasks", []):
        # Offsets are days relative to the main due date; without one there's nothing to anchor to.
        offset = sub.get("offset")
        sub_due = due + dt.timedelta(days=offset) if due and offset is not None else None
        # A short-notice task can push early steps into the past; those are due now.
        if sub_due and sub_due < dt.date.today():
            sub_due = dt.date.today()
        subtasks.append(Subtask(title=sub["title"].replace("{}", title), due=sub_due))
    return Breakdown(
        title=t.get("title", "{}").replace("{}", title),
        due=due,
        priority=priority or t.get("priority"),
        subtasks=subtasks,
    )


def save(name: str, b: Breakdown) -> Path:
    templates = load()
    templates[name] = {
        # The saved title is a bare placeholder: next time, whatever you type becomes the title.
        "title": "{}",
        "subtasks": [
            {"title": s.title, "offset": (s.due - b.due).days if s.due and b.due else None}
            for s in b.subtasks
        ],
    }
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(yaml.safe_dump(templates, sort_keys=False, allow_unicode=True))
    return p
