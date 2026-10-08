"""todo — quick capture into a Notion to-do database. See DESCRIPTION for usage."""
import argparse
import datetime as dt
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml
from dotenv import load_dotenv

from . import templates
from .breakdown import Breakdown, Subtask
from .notion import Notion
from .parse import match_option, parse_date

CONFIG_DIR = Path.home() / ".config" / "todo-capture"

DESCRIPTION = """todo — quick capture into a Notion to-do database.

EXAMPLES
  todo call dentist --due fri                          one task, due Friday
  todo fix login bug --due tomorrow --priority ess --tag bug
  todo robotics workshop --template visit --due 10/21  task + sub-tasks from a template
  todo ... --dry-run                                   show it, write nothing
"""

CHEATSHEET = """
VALUES
  --due       fri, tues, today, tomorrow, 10/21, 2026-10-21, "in 3 days", next-week
  --priority  first letters of a Priority option (ess, imp, extra, soon)
  --tag       first letters of a tag option (bug, feat, pol); repeatable
  Options can go before or after the text, and can be shortened (--pri, --temp).

REVIEW PROMPT  (after --template / --breakdown)
  a  accept and add to Notion      e  edit in $EDITOR (YAML), then review again
  c  cancel                        t  accept + save as template (--breakdown only)

TEMPLATES  ({path})
  {names}
  Offsets are days relative to --due; past dates become today.
  Add your own: copy the blank pattern at the top of that file.

MORE
  todo --templates   template names + their sub-tasks
  todo --schema      Notion properties in use, valid priorities/tags
  Guide: GETTING_STARTED.md in the TodoCapture repo
"""


def _cheatsheet() -> str:
    try:
        names = ", ".join(templates.load()) or "(none yet)"
    except Exception:  # a broken YAML file shouldn't break --help
        names = "(couldn't read the templates file)"
    return CHEATSHEET.format(path=templates.path(), names=names)


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"error: {name} is not set (put it in {CONFIG_DIR / '.env'}, see .env.example)")
    return value


def _fmt_date(d: dt.date | None) -> str:
    if not d:
        return ""
    return f"{d:%a %b %d}" + (f" {d.year}" if d.year != dt.date.today().year else "")


def _show(b: Breakdown, tags: list[str]) -> None:
    meta = "  ".join(x for x in (_fmt_date(b.due), b.priority or "", " ".join(tags)) if x)
    print(f"\n  {b.title}    {meta}")
    width = max((len(s.title) for s in b.subtasks), default=0) + 2
    for i, s in enumerate(b.subtasks, 1):
        print(f"    {i}. {s.title:<{width}}{_fmt_date(s.due)}")
    print()


def _edit(b: Breakdown) -> Breakdown:
    data = {
        "title": b.title,
        "due": b.due.isoformat() if b.due else None,
        "priority": b.priority,
        "subtasks": [{"title": s.title, "due": s.due.isoformat() if s.due else None} for s in b.subtasks],
    }
    with tempfile.NamedTemporaryFile("w+", suffix=".yaml", delete=False) as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
    subprocess.call([os.environ.get("EDITOR", "nano"), f.name])
    edited = yaml.safe_load(Path(f.name).read_text())
    os.unlink(f.name)
    return Breakdown(
        title=edited["title"],
        due=edited.get("due"),
        priority=edited.get("priority"),
        subtasks=[Subtask(**s) for s in edited.get("subtasks") or []],
    )


def _review(b: Breakdown, tags: list[str], allow_save: bool) -> Breakdown | None:
    """Show a proposed breakdown and loop until accepted or cancelled."""
    choices = "[a]ccept  [e]dit  [c]ancel" + ("  [t] accept + save as template" if allow_save else "")
    while True:
        _show(b, tags)
        answer = input(choices + " > ").strip().lower()[:1]
        if answer == "a":
            return b
        if answer == "e":
            b = _edit(b)
        elif answer == "c":
            return None
        elif answer == "t" and allow_save:
            name = input("template name > ").strip()
            if name:
                print(f"saved '{name}' to {templates.save(name, b)}")
            return b


def main() -> None:
    load_dotenv(CONFIG_DIR / ".env")
    load_dotenv()  # a local ./.env, if present, fills anything still unset

    ap = argparse.ArgumentParser(prog="todo", description=DESCRIPTION, epilog=_cheatsheet(),
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("text", nargs="*", help="the to-do title (quotes optional)")
    ap.add_argument("--due", metavar="DATE", help="due date, e.g. fri, tomorrow, 10/21")
    ap.add_argument("--priority", metavar="P", help="priority, e.g. ess, imp")
    ap.add_argument("--tag", metavar="T", action="append", default=[], help="tag, e.g. bug; repeatable")
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--template", metavar="NAME", help="expand a saved template into task + sub-tasks (no AI)")
    mode.add_argument("--breakdown", action="store_true", help="Claude proposes sub-tasks (optional; needs a paid ANTHROPIC_API_KEY)")
    ap.add_argument("--dry-run", action="store_true", help="show what would be added, write nothing")
    ap.add_argument("--templates", action="store_true", help="list saved templates")
    ap.add_argument("--schema", action="store_true", help="show which Notion properties are used")
    # Intermixed so options work anywhere: `todo call --due fri dentist` as well as at the end.
    args = ap.parse_intermixed_args()

    if args.templates:
        saved = templates.load()
        print(f"{templates.path()}:")
        for name, t in saved.items():
            print(f"  {name}: {', '.join(s['title'] for s in t.get('subtasks', []))}")
        return

    notion = Notion(_env("NOTION_TOKEN"), _env("NOTION_DATABASE_ID"))
    schema = notion.schema

    if args.schema:
        print(f"title: {schema.title}\ndue: {schema.due}\npriority: {schema.priority} {schema.priority_options}\n"
              f"tags: {schema.tags} {schema.tag_options}\n"
              f"sub-items: {schema.parent_relation or '(not enabled — sub-tasks become a checklist in the page)'}")
        return

    if not args.text:
        ap.print_help()
        return

    try:
        title = " ".join(args.text).strip()
        due = parse_date(args.due) if args.due else None
        priority = match_option(args.priority, schema.priority_options, "priority") if args.priority else None
        tags = [match_option(t, schema.tag_options, "tag") for t in args.tag]
        if args.breakdown:
            if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
                sys.exit(
                    "--breakdown (Claude) is optional and needs a paid Anthropic API key; none is configured.\n"
                    "Without it:\n"
                    "  todo <task>                      add it as a single task\n"
                    "  todo <task> --template <name>    expand a saved template (list: todo --templates)\n"
                    f"To enable --breakdown later: add ANTHROPIC_API_KEY to {CONFIG_DIR / '.env'}"
                )
            import anthropic
            from .breakdown import break_down  # keeps plain adds from importing the SDK
            print("asking Claude…", file=sys.stderr)
            try:
                b = break_down(title, schema.priority_options)
            except anthropic.AuthenticationError:
                sys.exit("error: Anthropic rejected the API key; check ANTHROPIC_API_KEY")
            except (anthropic.APIConnectionError, anthropic.APIStatusError, RuntimeError) as e:
                sys.exit(f"error: breakdown failed: {e}")
            # Explicit options beat Claude's guesses.
            b.due = due or b.due
            b.priority = priority or b.priority
        elif args.template:
            b = templates.apply(args.template, title, due, priority)
        else:
            b = Breakdown(title=title, due=due, priority=priority, subtasks=[])
    except ValueError as e:
        sys.exit(f"error: {e}")

    if args.breakdown or args.template:
        b = _review(b, tags, allow_save=args.breakdown)
        if b is None:
            print("cancelled")
            return
    elif args.dry_run:
        _show(b, tags)

    if args.dry_run:
        print("(dry run — nothing written)")
        return

    url = notion.add(b.title, b.due, b.priority, tags, [(s.title, s.due) for s in b.subtasks])
    extra = f" + {len(b.subtasks)} sub-tasks" if b.subtasks else ""
    print(f"added: {b.title}{extra}  {_fmt_date(b.due)}\n{url}")


if __name__ == "__main__":
    main()
