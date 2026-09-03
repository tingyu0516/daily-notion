"""FastMCP server exposing the thin Notion data layer.

Design rules (agreed in the planning session):
- Tools are atomic CRUD + queries only. All conversational logic (how to word
  the morning briefing, how to run the review dialog) lives in the Hermes skill.
- Every tool that needs a date takes it as an explicit parameter; the agent is
  responsible for knowing today.
- All writes go through conversation: the user never edits statuses by hand
  (though manual Notion edits are still honored because reads are uncached).
"""

from __future__ import annotations

import json
import sys

from mcp.server.fastmcp import FastMCP

from . import schema as S
from . import store

mcp = FastMCP("daily-notion")


def _dump(value) -> str:
    return json.dumps(value, ensure_ascii=False, indent=1)


VALID_STATUSES = ", ".join(S.STATUS_OPTIONS)
VALID_PRIORITIES = ", ".join(S.PRIORITY_OPTIONS)
VALID_MOODS = ", ".join(S.MOOD_OPTIONS)


@mcp.tool()
def create_task(title: str, plan_date: str, priority: str = "中") -> str:
    """Create one task row. plan_date is 'YYYY-MM-DD' (may be a future date).
    priority must be one of: 高 / 中 / 低 (default 中).
    Idempotent: creating a task with the same title on the same date returns
    the existing row instead of duplicating it."""
    if priority not in S.PRIORITY_OPTIONS:
        return f"错误：priority 必须是 {VALID_PRIORITIES} 之一，收到：{priority}"
    return _dump(store.create_task(title, plan_date, priority))


@mcp.tool()
def update_task(
    task_id: str,
    status: str = "",
    plan_date: str = "",
    priority: str = "",
    review_note: str = "",
) -> str:
    """Update a task by its Notion page id. Empty string = leave unchanged.
    status: 未开始 / 进行中 / 已完成 / 已取消 / 顺延.
    Postponement (顺延) = set status='顺延' AND plan_date to the new date, on the
    SAME row — never copy the task to a new row."""
    kwargs = {}
    if status:
        if status not in S.STATUS_OPTIONS:
            return f"错误：status 必须是 {VALID_STATUSES} 之一，收到：{status}"
        kwargs["status"] = status
    if plan_date:
        kwargs["plan_date"] = plan_date
    if priority:
        if priority not in S.PRIORITY_OPTIONS:
            return f"错误：priority 必须是 {VALID_PRIORITIES} 之一，收到：{priority}"
        kwargs["priority"] = priority
    if review_note:
        kwargs["review_note"] = review_note
    if not kwargs:
        return "错误：所有字段都为空，没有可更新的内容"
    return _dump(store.update_task(task_id, **kwargs))


@mcp.tool()
def complete_task(task_id: str, done_date: str) -> str:
    """Mark a task 已完成 and stamp its 完成于 date ('YYYY-MM-DD', normally today)."""
    return _dump(store.complete_task(task_id, done_date))


@mcp.tool()
def get_tasks_by_date(date: str, status: str = "") -> str:
    """All tasks planned on `date` ('YYYY-MM-DD'), optionally filtered to one status.
    Returns a list of {id, title, plan_date, status, priority, done_at, review_note, url}."""
    return _dump(store.get_tasks_by_date(date, status or None))


@mcp.tool()
def get_upcoming(from_date: str, days: int = 3) -> str:
    """Tasks planned in the `days` calendar days after (and including) `from_date`.
    Used by the morning briefing for the 'future outlook' section."""
    return _dump(store.get_upcoming(from_date, days))


@mcp.tool()
def get_or_create_journal(date: str) -> str:
    """Get today's journal page, lazily creating it if absent (one page per day).
    Check the 'created' flag for idempotency. Returns {id, date, review, mood, task_ids, url}."""
    return _dump(store.get_or_create_journal(date))


@mcp.tool()
def get_journal(date: str) -> str:
    """Read today's journal page WITHOUT creating it. Returns null if absent —
    use this to check whether the review already happened (idempotency guard)."""
    return _dump(store.get_journal(date))


@mcp.tool()
def link_tasks_to_journal(date: str, task_ids: list[str]) -> str:
    """Attach tasks (by page id) to the day's journal relation. Merges; never unlinks.
    Creates the journal page if it does not exist yet."""
    return _dump(store.link_tasks_to_journal(date, task_ids))


@mcp.tool()
def write_review(date: str, review_text: str, mood: str = "") -> str:
    """Write (overwrite) the day's review summary onto the journal page.
    mood is optional, one of: 精力充沛 / 一般 / 疲惫."""
    if mood and mood not in S.MOOD_OPTIONS:
        return f"错误：mood 必须是 {VALID_MOODS} 之一，收到：{mood}"
    return _dump(store.write_review(date, review_text, mood or None))


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
