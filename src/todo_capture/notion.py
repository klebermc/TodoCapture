"""Notion writes. Property names are auto-detected by type so the tool isn't tied to one database layout."""
import datetime as dt
from dataclasses import dataclass

from notion_client import Client

# Pinned on purpose: newer versions split databases into
# "data sources" and change the page-parent shape.
NOTION_VERSION = "2022-06-28"


@dataclass
class Schema:
    title: str
    due: str | None
    priority: str | None
    priority_options: list[str]
    tags: str | None
    tag_options: list[str]
    parent_relation: str | None  # set when Notion's "Sub-items" feature is enabled


def _first(props: dict, type_: str, prefer: str | None = None) -> str | None:
    names = [n for n, p in props.items() if p["type"] == type_]
    if prefer and prefer in names:
        return prefer
    return names[0] if names else None


class Notion:
    def __init__(self, token: str, database_id: str):
        self.client = Client(auth=token, notion_version=NOTION_VERSION)
        self.database_id = database_id
        self._schema: Schema | None = None

    @property
    def schema(self) -> Schema:
        if self._schema is None:
            db = self.client.databases.retrieve(database_id=self.database_id)
            props = db["properties"]
            priority = _first(props, "select", prefer="Priority")
            tags = _first(props, "multi_select")
            # Notion's built-in sub-items feature is a self-relation named "Parent item".
            parent = next(
                (n for n, p in props.items()
                 if p["type"] == "relation"
                 and p["relation"]["database_id"].replace("-", "") == self.database_id.replace("-", "")
                 and "parent" in n.lower()),
                None,
            )
            self._schema = Schema(
                title=_first(props, "title"),
                due=_first(props, "date"),
                priority=priority,
                priority_options=[o["name"] for o in props[priority]["select"]["options"]] if priority else [],
                tags=tags,
                tag_options=[o["name"] for o in props[tags]["multi_select"]["options"]] if tags else [],
                parent_relation=parent,
            )
        return self._schema

    def _properties(self, title, due=None, priority=None, tags=None, parent_id=None) -> dict:
        s = self.schema
        props = {s.title: {"title": [{"text": {"content": title}}]}}
        if due and s.due:
            props[s.due] = {"date": {"start": due.isoformat()}}
        if priority and s.priority:
            props[s.priority] = {"select": {"name": priority}}
        if tags and s.tags:
            props[s.tags] = {"multi_select": [{"name": t} for t in tags]}
        if parent_id and s.parent_relation:
            props[s.parent_relation] = {"relation": [{"id": parent_id}]}
        return props

    def add(self, title: str, due: dt.date | None = None, priority: str | None = None,
            tags: list[str] | None = None, subtasks: list[tuple[str, dt.date | None]] | None = None) -> str:
        """Create a task (and its sub-tasks); returns the parent page URL."""
        page = self.client.pages.create(
            parent={"database_id": self.database_id},
            properties=self._properties(title, due, priority, tags),
        )
        for sub_title, sub_due in subtasks or []:
            if self.schema.parent_relation:
                self.client.pages.create(
                    parent={"database_id": self.database_id},
                    properties=self._properties(sub_title, sub_due, priority, tags, parent_id=page["id"]),
                )
        if subtasks and not self.schema.parent_relation:
            # Without Sub-items enabled there's nowhere to link child rows, so they
            # become a checklist inside the parent page instead.
            self.client.blocks.children.append(block_id=page["id"], children=[
                {"object": "block", "type": "to_do", "to_do": {
                    "rich_text": [{"text": {"content": t + (f" (by {d:%a %b %d})" if d else "")}}],
                    "checked": False,
                }} for t, d in subtasks
            ])
        return page["url"]
