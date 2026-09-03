"""Load .env (package root, then cwd) into os.environ. No third-party dependency."""

import os
from pathlib import Path

_KEYS = (
    "NOTION_TOKEN",
    "NOTION_PARENT_PAGE_ID",
    "NOTION_TASKS_DB_ID",
    "NOTION_JOURNAL_DB_ID",
)


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return values
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key in _KEYS:
            values[key] = value
    return values


def load_env() -> None:
    """Populate os.environ from the nearest .env file.

    Search order: package root (.. of this file), then cwd. Existing
    os.environ values always win so real environment variables can override.
    """
    candidates = [
        Path(__file__).resolve().parent.parent / ".env",
        Path.cwd() / ".env",
    ]
    for candidate in candidates:
        for key, value in _parse_env_file(candidate).items():
            if not os.environ.get(key):
                os.environ[key] = value


def require(key: str) -> str:
    load_env()
    value = os.environ.get(key, "").strip()
    if not value:
        raise RuntimeError(
            f"Missing required env var {key}. "
            f"Copy .env.example to .env and fill it in (see README)."
        )
    return value


def optional(key: str) -> str:
    load_env()
    return os.environ.get(key, "").strip()
