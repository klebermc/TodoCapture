"""Claude-powered breakdown of a task into sub-tasks. The only part of the tool that needs AI."""
import datetime as dt

import anthropic
from pydantic import BaseModel

MODEL = "claude-opus-5"

SYSTEM = """You turn a short to-do note into an actionable task for a personal Notion to-do list.

Decide whether the note needs sub-tasks. Simple, single-action notes ("call the dentist")
get none. Notes implying several concrete actions (an in-person meeting that needs a room
booked, an invite sent, someone asked about something) get a short list of sub-tasks,
typically 2-5, each a concrete action starting with a verb. Don't invent busywork or
steps the note gives no reason for.

Keep the main title close to the user's wording. Resolve relative dates against today's
date given in the message. Sub-task due dates should land on or before the main due date
(e.g. book the room a day before the meeting); leave dates empty when nothing suggests one.
Pick a priority only if the note implies one, using exactly one of the allowed values."""


class Subtask(BaseModel):
    title: str
    due: dt.date | None


class Breakdown(BaseModel):
    title: str
    due: dt.date | None
    priority: str | None
    subtasks: list[Subtask]


def break_down(note: str, priorities: list[str], today: dt.date | None = None) -> Breakdown:
    today = today or dt.date.today()
    client = anthropic.Anthropic()
    response = client.beta.messages.parse(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM,
        # Server-side fallback: if the primary model declines, the API retries on
        # another model within the same call instead of returning a refusal.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{
            "role": "user",
            "content": f"Today is {today:%A %Y-%m-%d}.\n"
                       f"Allowed priorities: {', '.join(priorities) or '(none)'}\n\n"
                       f"Note: {note}",
        }],
        output_format=Breakdown,
    )
    if response.stop_reason == "refusal" or response.parsed_output is None:
        raise RuntimeError(f"Claude didn't return a breakdown (stop_reason={response.stop_reason})")
    result = response.parsed_output
    if result.priority not in priorities:
        result.priority = None
    return result
