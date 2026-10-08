# Getting started

A 10-minute walkthrough from install to your first broken-down task. For the full reference, see [README.md](README.md).

## 1. Install (once)

```bash
cd TodoCapture
python3 -m venv .venv
.venv/bin/pip install -e .
mkdir -p ~/.local/bin && ln -s "$PWD/.venv/bin/todo" ~/.local/bin/todo
todo --help        # if "command not found", add ~/.local/bin to your PATH
```

## 2. Connect Notion (once)

1. At https://www.notion.so/my-integrations, create an internal integration and copy its secret. If you already have one for the same database, reuse it.
2. In Notion, open your to-do database → `···` → **Connections** → add that integration.
3. Create your local config. It lives outside the repo, so it never gets committed:

   ```bash
   mkdir -p ~/.config/todo-capture
   cp .env.example ~/.config/todo-capture/.env
   chmod 600 ~/.config/todo-capture/.env
   nano ~/.config/todo-capture/.env     # fill in NOTION_TOKEN and NOTION_DATABASE_ID
   ```

4. Check that it can see your database:

   ```bash
   todo --schema
   ```

   This lists which properties it will use for title, due date, priority and tags, and whether sub-items are enabled.

## 3. Add your first to-dos (no AI)

Start with `--dry-run` so nothing gets written:

```bash
todo call the dentist --due fri --dry-run
```

When it looks right, drop `--dry-run`:

```bash
todo call the dentist --due fri
todo renew passport --due "in 2 weeks" --priority imp
todo fix login bug --due tomorrow --priority ess --tag bug
```

| Option | Meaning | Examples |
|---|---|---|
| `--due` | due date | `fri` `tomorrow` `10/21` `2026-10-05` `"in 3 days"` `next-week` |
| `--priority` | priority | the first letters of any Priority option: `ess` `imp` `extra` `soon` |
| `--tag` | tag (repeatable) | the first letters of any tag option: `bug` `feat` `pol` |

Everything that isn't an option becomes the title. Options can go anywhere and can be abbreviated (`--pri imp`). If a value doesn't match, it tells you the valid options. Quote the title only when it has shell-special characters, e.g. an apostrophe: `todo "landlord's form" --due mon`.

## 4. Break a bigger task down with Claude (optional, paid; skip if you have no API key)

> This step needs an Anthropic API key, which is billed per use and separate from a Claude.ai subscription. Without one, skip to step 5: templates give you the same breakdowns without AI. Running `todo --breakdown` without a key just prints these alternatives.

Add `ANTHROPIC_API_KEY=...` to `~/.config/todo-capture/.env` (get a key at https://console.anthropic.com). Then:

```bash
todo in-person meeting with the team about the budget --breakdown --due tue
```

You'll see a proposal like:

```
  In-person meeting with the team about the budget    Tue Sep 29
    1. Book a meeting room                  Mon Sep 28
    2. Send the team a calendar invite      Mon Sep 28
    3. Pull the latest budget numbers       Mon Sep 28

[a]ccept  [e]dit  [c]ancel  [t] accept + save as template >
```

- `a` adds it to Notion.
- `e` opens it in your editor as YAML (set `$EDITOR`; the default is nano). Change titles or dates, delete lines, save and close, and it shows the proposal again.
- `c` discards it.
- `t` adds it **and** saves it as a template, so next time you won't need Claude (see step 5).

Simple notes come back with no sub-tasks. That's intended.

## 5. Templates: the same breakdown, without AI

When a breakdown is one you'll repeat (meetings, trips, onboarding someone), save it with `t`. Or write one yourself:

```bash
cp templates.example.yaml ~/.config/todo-capture/templates.yaml
nano ~/.config/todo-capture/templates.yaml
```

```yaml
meeting:
  title: "Meeting: {}"          # {} = the text you type after the template name
  subtasks:
    - title: Book a room
      offset: -1                # days relative to the due date (-1 = the day before)
    - title: Send invite + agenda
      offset: -1
```

Use it:

```bash
todo --templates               # list what you have
todo budget review --template meeting --due tue   # → "Meeting: budget review" due Tue, sub-tasks before/after
```

## 6. Where the sub-tasks end up

- **Sub-items enabled** in the Notion database (database `···` → *Sub-items*): each sub-task becomes its own row, linked to the parent.
- **Not enabled:** the sub-tasks become a checklist inside the parent task's page.

`todo --schema` tells you which one applies.

## Everyday flow

- Something small comes up → `todo <it> --due <when>`
- Something with moving parts → `todo <it> --template <name> --due <when>`, or, if you have an API key, `todo <it> --breakdown --due <when>`
- A recurring kind of thing → save it as a template once, then `--template <name>`
- Viewing, completing and replanning happen in Notion.
