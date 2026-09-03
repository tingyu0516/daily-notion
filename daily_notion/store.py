"""Notion data-access layer. All MCP tools delegate here.

Conventions:
- All dates are ISO strings "YYYY-MM-DD" (date-only, Notion date property).
- Callers pass dates explicitly; the server never guesses "today" so the
  agent (which knows the current date) stays the single source of truth.
- Reads are unfiltered and uncached: manual edits in Notion are always seen.
"""

from __future__ import annotations

from typing import Any

from notion_client import Client

from . import schema as S
from .config import require

_DATABASE_IDS: dict[str, str] = {}


def _client() -> Client:
    return Client(auth=require("NOTION_TOKEN"))


def _tasks_db_id() -> str:
    if "tasks" not in _DATABASE_IDS:
        _DATABASE_IDS["tasks"] = require("NOTION_TASKS_DB_ID")
    return _DATABASE_IDS["tasks"]


def _journal_db_id() -> str:
    if "journal" not in _DATABASE_IDS:
        _DATABASE_IDS["journal"] = require("NOTION_JOURNAL_DB_ID")
    return _DATABASE_IDS["journal"]


# --- internal helpers ---------------------------------------------------------


def _query(db_id: str, filter_: dict, page_size: int = 100) -> list[dict]:
    client = _client()
    results: list[dict] = []
    cursor: str | None = None
    while True:
        kwargs: dict[str, Any] = {"database_id": db_id, "filter": filter_, "page_size": page_size}
        if cursor:
            kwargs["start_cursor"] = cursor
        resp = client.databases.query(**kwargs)
        results.extend(resp.get("results", []))
        if not resp.get("has_more"):
            return results
        cursor = resp.get("next_cursor")


def _prop(page: dict, name: str) -> Any:
    return page.get("properties", {}).get(name, {})


def _title_of(page: dict, prop: str) -> str:
    parts = _prop(page, prop).get("title", [])
    return "".join(p.get("plain_text", "") for p in parts)


def _text_of(page: dict, prop: str) -> str:
    parts = _prop(page, prop).get("rich_text", [])
    return "".join(p.get("plain_text", "") for p in parts)


def _select_of(page: dict, prop: str) -> str | None:
    sel = _prop(page, prop).get("select")
    return sel.get("name") if sel else None


def _date_of(page: dict, prop: str) -> str | None:
    d = _prop(page, prop).get("date")
    return d.get("start") if d else None


def _date_filter(prop: str, condition: dict) -> dict:
    return {"property": prop, "date": condition}


def _compact_task(page: dict) -> dict:
    return {
        "id": page["id"],
        "title": _title_of(page, S.T_TITLE),
        "plan_date": _date_of(page, S.T_PLAN_DATE),
        "status": _select_of(page, S.T_STATUS),
        "priority": _select_of(page, S.T_PRIORITY),
        "done_at": _date_of(page, S.T_DONE_AT),
        "review_note": _text_of(page, S.T_REVIEW_NOTE),
        "url": page.get("url"),
    }


def _compact_journal(page: dict) -> dict:
    relations = _prop(page, S.J_TASKS).get("relation", [])
    return {
        "id": page["id"],
        "date": _title_of(page, S.J_TITLE),
        "review": _text_of(page, S.J_REVIEW),
        "mood": _select_of(page, S.J_MOOD),
        "task_ids": [r["id"] for r in relations],
        "url": page.get("url"),
    }


def _find_journal(date: str) -> dict | None:
    results = _query(
        _journal_db_id(),
        {"property": S.J_TITLE, "title": {"equals": date}},
        page_size=1,
    )
    return results[0] if results else None


def _find_task_by_title(date: str, title: str) -> dict | None:
    """Exact-title match within one day's tasks; used for dedupe and fuzzy-free lookup."""
    results = _query(
        _tasks_db_id(),
        {
            "and": [
                _date_filter(S.T_PLAN_DATE, {"equals": date}),
                {"property": S.T_TITLE, "title": {"equals": title}},
            ]
        },
        page_size=1,
    )
    return results[0] if results else None


# --- public operations (called by MCP tools) ----------------------------------


def create_task(title: str, plan_date: str, priority: str = "中") -> dict:
    """Create one task. Idempotent: returns the existing row on same (date, title)."""
    existing = _find_task_by_title(plan_date, title)
    if existing:
        return {"created": False, "task": _compact_task(existing)}

    page = _client().pages.create(
        parent={"type": "database_id", "database_id": _tasks_db_id()},
        properties={
            S.T_TITLE: S.title_value(title),
            S.T_PLAN_DATE: S.date_value(plan_date),
            S.T_STATUS: S.select_value("未开始"),
            S.T_PRIORITY: S.select_value(priority),
        },
    )
    return {"created": True, "task": _compact_task(page)}


def update_task(
    task_id: str,
    status: str | None = None,
    plan_date: str | None = None,
    priority: str | None = None,
    review_note: str | None = None,
) -> dict:
    """Update a task. Postponement = status='顺延' + new plan_date (same row, no copies)."""
    props: dict[str, Any] = {}
    if status is not None:
        props[S.T_STATUS] = S.select_value(status)
    if plan_date is not None:
        props[S.T_PLAN_DATE] = S.date_value(plan_date)
    if priority is not None:
        props[S.T_PRIORITY] = S.select_value(priority)
    if review_note is not None:
        props[S.T_REVIEW_NOTE] = S.rich_text_value(review_note)
    if not props:
        raise ValueError("update_task: nothing to update")
    page = _client().pages.update(page_id=task_id, properties=props)
    return {"updated": True, "task": _compact_task(page)}


def complete_task(task_id: str, done_date: str) -> dict:
    """Mark done and stamp completion date."""
    page = _client().pages.update(
        page_id=task_id,
        properties={
            S.T_STATUS: S.select_value("已完成"),
            S.T_DONE_AT: S.date_value(done_date),
        },
    )
    return {"updated": True, "task": _compact_task(page)}


def get_tasks_by_date(date: str, status: str | None = None) -> list[dict]:
    """All tasks planned on `date`, optionally narrowed to one status."""
    conditions: list[dict] = [_date_filter(S.T_PLAN_DATE, {"equals": date})]
    if status:
        conditions.append({"property": S.T_STATUS, "select": {"equals": status}})
    filter_ = conditions[0] if len(conditions) == 1 else {"and": conditions}
    pages = _query(_tasks_db_id(), filter_)
    return [_compact_task(p) for p in pages]


def get_upcoming(from_date: str, days: int = 3) -> list[dict]:
    """Tasks planned strictly after `from_date`, within `days` calendar days."""
    from datetime import date as _date, timedelta

    end = (_date.fromisoformat(from_date) + timedelta(days=days)).isoformat()
    pages = _query(
        _tasks_db_id(),
        {
            "and": [
                _date_filter(S.T_PLAN_DATE, {"on_or_after": from_date}),
                _date_filter(S.T_PLAN_DATE, {"on_or_before": end}),
            ]
        },
    )
    return [_compact_task(p) for p in pages]


def get_or_create_journal(date: str) -> dict:
    """One journal page per day (keyed by ISO date in the title). Lazy creation."""
    existing = _find_journal(date)
    if existing:
        return {"created": False, "journal": _compact_journal(existing)}
    page = _client().pages.create(
        parent={"type": "database_id", "database_id": _journal_db_id()},
        properties={
            S.J_TITLE: S.title_value(date),
            S.J_CALENDAR: S.date_value(date),
        },
    )
    return {"created": True, "journal": _compact_journal(page)}


def get_journal(date: str) -> dict | None:
    existing = _find_journal(date)
    return _compact_journal(existing) if existing else None


def link_tasks_to_journal(date: str, task_ids: list[str]) -> dict:
    """Merge the given tasks into the journal's relation (never drops existing links)."""
    journal = get_or_create_journal(date)["journal"]
    merged = list(dict.fromkeys(journal["task_ids"] + task_ids))
    page = _client().pages.update(
        page_id=journal["id"], properties={S.J_TASKS: S.relation_value(merged)}
    )
    return {"updated": True, "journal": _compact_journal(page)}


def write_review(date: str, review_text: str, mood: str | None = None) -> dict:
    """Write (overwrite) the day's review text and optional mood onto the journal."""
    journal = get_or_create_journal(date)["journal"]
    props: dict[str, Any] = {S.J_REVIEW: S.rich_text_value(review_text)}
    if mood is not None:
        props[S.J_MOOD] = S.select_value(mood)
    page = _client().pages.update(page_id=journal["id"], properties=props)
    return {"updated": True, "journal": _compact_journal(page)}
