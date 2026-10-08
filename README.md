# TodoCapture

> **Note:** The code and documentation in this repository were written by an AI coding agent (Claude). Kleber Cabral specified the tool, directed the work and tested it.

A small command-line tool for getting to-dos into a Notion database quickly. Most items go in as-is with inline shorthand for date, priority and tag. Bigger items (an in-person meeting that needs a room booked, an invite sent, someone asked about something) can be expanded from a saved template or, optionally, broken into sub-tasks by Claude.

Everything works without AI. Only `--breakdown` needs Claude, and it requires a paid Anthropic API key. Without a key, `--breakdown` explains what to use instead.

Viewing, completing and replanning stay in Notion.

## What it does

![Three dry runs in the terminal: a plain task, a task with priority and tag, and a meeting expanded from a template](figures/demo.gif)

*Real output of the tool in `--dry-run` mode, with the Notion connection replaced by a stand-in database, so nothing was written.*

```bash
todo call dentist --due fri                                       # plain add, no AI
todo email the specs to the supplier --priority imp --tag feat    # with priority and tag
todo budget review --template meeting --due tue                   # expand a saved template, no AI
todo in-person budget meeting --breakdown --due tue               # optional: Claude proposes sub-tasks (paid API key)
todo ... --dry-run                                                # show it, write nothing
todo --schema                                                     # which Notion properties get used
todo --templates                                                  # list saved templates
todo                                                              # no arguments: cheat sheet (same as --help)
```

**Options.** The task title is whatever text isn't an option; quotes are only needed for characters like apostrophes. Options can go before or after the title and can be abbreviated (`--pri`, `--temp`).
- `--due`: `fri`, `tues`, `today`, `tomorrow`, `2026-10-05`, `10/21`, `"in 3 days"`, `next-week`. A weekday always means its next occurrence after today.
- `--priority`: matched against the database's Priority options. A prefix or any substring works (`ess` → Essential, `soon` → Essential - Soon). If one option is contained in every match, that one wins.
- `--tag`: matched the same way against the first multi-select property, and can be repeated. Emoji in option names are ignored.

**Review prompt** (for `--template` and `--breakdown`): `[a]ccept`, `[e]dit` (opens the proposal as YAML in `$EDITOR`), `[c]ancel`, and, only for `--breakdown`, `[t]` to accept and save the breakdown as a template.

**Relying on AI less over time:** each `--breakdown` you like can be saved with `[t]`. The next similar item then uses `--template` with no API call. Template sub-task dates are stored as day offsets from the main due date.

**Sub-tasks in Notion**
- If the database has Notion's *Sub-items* feature on (a self-relation named "Parent item"), each sub-task becomes its own row linked to the parent.
- Otherwise the sub-tasks become a checklist inside the parent task's page.

## Structure

```
src/todo_capture/
  cli.py         argument parsing, review/edit loop, entry point (`todo`)
  parse.py       --due date parsing and --priority/--tag option matching
  notion.py      Notion writes; auto-detects title/date/select/multi-select/sub-item properties
  breakdown.py   Claude call that returns a structured task + sub-tasks
  templates.py   YAML templates: apply and save
.env.example             credential template
templates.example.yaml   example template file
figures/                 demo GIF used in this README
```

## Install

```bash
python3 -m venv .venv
.venv/bin/pip install -e .
ln -s "$PWD/.venv/bin/todo" ~/.local/bin/todo    # optional: `todo` on PATH
```

## Configure

Credentials and templates live **outside the repo** in `~/.config/todo-capture/`:

```bash
mkdir -p ~/.config/todo-capture
cp .env.example ~/.config/todo-capture/.env && chmod 600 ~/.config/todo-capture/.env
cp templates.example.yaml ~/.config/todo-capture/templates.yaml
```

Fill in `.env`:
- `NOTION_TOKEN`: an internal integration secret from https://www.notion.so/my-integrations. The integration must be added to the database under `···` → **Connections**. An integration you already use for the same database works here.
- `NOTION_DATABASE_ID`: the 32-character ID from the database URL.
- `ANTHROPIC_API_KEY`: optional; only needed for `--breakdown`. This is a pay-per-use key from https://console.anthropic.com, separate from a Claude.ai subscription. Leave it out and everything else still works.

A `./.env` in the working directory also works and fills in anything the config-dir file leaves unset. `TODO_TEMPLATES` overrides the template file path. `TODO_DATE_ORDER` (`MDY` by default, or `DMY`/`YMD`) sets how dates like `3/10` are read.

## Key dependencies

- `notion-client` (Notion API, pinned to API version `2022-06-28`)
- `anthropic` (Claude API, `claude-opus-5`, structured output via Pydantic, server-side refusal fallback)
- `dateparser`, `pyyaml`, `python-dotenv`, `pydantic`

## Status

v0.1 (2026-09-24). Capture only: plain add, Claude breakdown, and templates. For a step-by-step walkthrough, see [GETTING_STARTED.md](GETTING_STARTED.md).

- Tested end-to-end against a real database: plain add, and template add with checklist sub-tasks.
- `--breakdown` is implemented but has not been run against the live API yet (no API key configured). Treat it as untested.
- Not planned for now: reminders, listing, completing or deleting tasks (those are done in Notion).
