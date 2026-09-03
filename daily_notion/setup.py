"""One-shot initializer: creates the two Notion databases and wires .env.

Usage:
    python -m daily_notion.setup            # create databases (idempotent-ish)
    python -m daily_notion.setup --check    # verify token + database access only

Prerequisites (see README):
1. Create an internal integration at https://www.notion.so/profile/integrations
   and copy the token into .env as NOTION_TOKEN.
2. In Notion, open the page that will host the databases, share it with the
   integration (page menu -> Connections), and put its page id into
   .env as NOTION_PARENT_PAGE_ID.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import schema as S
from .config import load_env, optional, require


def _env_path() -> Path:
    candidates = [Path(__file__).resolve().parent.parent / ".env", Path.cwd() / ".env"]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def _save_env_value(key: str, value: str) -> None:
    path = _env_path()
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    replaced = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            lines[i] = f"{key}={value}"
            replaced = True
            break
    if not replaced:
        lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  wrote {key} -> {path}")


def _friendly(err: Exception) -> str:
    text = str(err)
    if "Could not find database" in text or "Could not find page" in text:
        return (
            "Notion says the target was not found. Two usual causes:\n"
            "  1) The parent page is not shared with the integration — open the page in\n"
            "     Notion, use ... menu -> Connections -> add your integration.\n"
            "  2) An id in .env is wrong or stale — fix/remove it and re-run."
        )
    if "unauthorized" in text.lower() or "API token is invalid" in text:
        return (
            "Token rejected. Check NOTION_TOKEN in .env, and that the integration\n"
            "is an INTERNAL integration with content capabilities enabled."
        )
    return text


def check(client) -> bool:
    ok = True
    token_info = client.users.me()
    print(f"token OK (bot: {token_info.get('name', '?')})")
    for key, label in [
        ("NOTION_PARENT_PAGE_ID", "parent page"),
        ("NOTION_TASKS_DB_ID", f"'{S.TASKS_DB_TITLE}' database"),
        ("NOTION_JOURNAL_DB_ID", f"'{S.JOURNAL_DB_TITLE}' database"),
    ]:
        value = optional(key)
        if not value:
            print(f"{label}: not configured ({key} empty)")
            continue
        try:
            if key == "NOTION_PARENT_PAGE_ID":
                client.pages.retrieve(value)
            else:
                client.databases.retrieve(value)
            print(f"{label}: OK ({value})")
        except Exception as err:  # noqa: BLE001 - report and continue
            ok = False
            print(f"{label}: FAILED\n{_friendly(err)}")
    return ok


def setup(client) -> int:
    parent = require("NOTION_PARENT_PAGE_ID")

    tasks_id = optional("NOTION_TASKS_DB_ID")
    if tasks_id:
        print(f"'{S.TASKS_DB_TITLE}' database id already configured: {tasks_id}")
    else:
        db = client.databases.create(
            parent={"type": "page_id", "page_id": parent},
            title=[{"type": "text", "text": {"content": S.TASKS_DB_TITLE}}],
            properties=S.TASKS_PROPERTIES,
        )
        tasks_id = db["id"]
        _save_env_value("NOTION_TASKS_DB_ID", tasks_id)
        print(f"created '{S.TASKS_DB_TITLE}' database: {db.get('url', tasks_id)}")

    journal_id = optional("NOTION_JOURNAL_DB_ID")
    if journal_id:
        print(f"'{S.JOURNAL_DB_TITLE}' database id already configured: {journal_id}")
    else:
        db = client.databases.create(
            parent={"type": "page_id", "page_id": parent},
            title=[{"type": "text", "text": {"content": S.JOURNAL_DB_TITLE}}],
            properties=S.journal_properties(tasks_id),
        )
        journal_id = db["id"]
        _save_env_value("NOTION_JOURNAL_DB_ID", journal_id)
        print(f"created '{S.JOURNAL_DB_TITLE}' database: {db.get('url', journal_id)}")

    print("\nDone. You can move the two databases anywhere in Notion — the ids do not change.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialize Notion databases for daily-notion")
    parser.add_argument("--check", action="store_true", help="verify access only, create nothing")
    args = parser.parse_args()

    load_env()
    try:
        from notion_client import Client

        client = Client(auth=require("NOTION_TOKEN"))
    except Exception as err:  # noqa: BLE001
        print(_friendly(err), file=sys.stderr)
        return 1

    try:
        if args.check:
            return 0 if check(client) else 1
        return setup(client)
    except Exception as err:  # noqa: BLE001
        print(f"\nFAILED\n{_friendly(err)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
