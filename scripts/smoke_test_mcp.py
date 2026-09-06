"""Smoke test: launch the MCP server over stdio and list its tools. No Notion token needed."""

import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED = {
    "create_task",
    "update_task",
    "complete_task",
    "get_tasks_by_date",
    "get_upcoming",
    "get_or_create_journal",
    "get_journal",
    "link_tasks_to_journal",
    "write_review",
}

REPO_ROOT = Path(__file__).resolve().parent.parent


async def main() -> int:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "daily_notion.server"],
        cwd=str(REPO_ROOT),
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            names = {t.name for t in result.tools}
            print(f"{len(names)} tools registered:")
            for t in sorted(names):
                print(f"  - {t}")
            missing = EXPECTED - names
            extra = names - EXPECTED
            if missing:
                print(f"MISSING: {sorted(missing)}")
                return 1
            if extra:
                print(f"unexpected extras: {sorted(extra)}")
            print("smoke test OK")
            return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
