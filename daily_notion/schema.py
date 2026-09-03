"""Single source of truth for the two Notion databases' names, properties and options.

The MCP server reads through these names; the setup script creates with them.
Changing any name here after databases exist requires updating Notion manually.
"""

# --- database names -----------------------------------------------------------
TASKS_DB_TITLE = "每日任务"
JOURNAL_DB_TITLE = "每日日志"

# --- Tasks properties ---------------------------------------------------------
T_TITLE = "任务名"
T_PLAN_DATE = "计划日期"
T_STATUS = "状态"
T_PRIORITY = "优先级"
T_DONE_AT = "完成于"
T_REVIEW_NOTE = "复盘笔记"

STATUS_OPTIONS = ["未开始", "进行中", "已完成", "已取消", "顺延"]
PRIORITY_OPTIONS = ["高", "中", "低"]

STATUS_COLORS = {
    "未开始": "gray",
    "进行中": "blue",
    "已完成": "green",
    "已取消": "brown",
    "顺延": "orange",
}
PRIORITY_COLORS = {"高": "red", "中": "yellow", "低": "gray"}

TASKS_PROPERTIES: dict = {
    T_TITLE: {"title": {}},
    T_PLAN_DATE: {"date": {}},
    T_STATUS: {
        "select": {
            "options": [
                {"name": name, "color": STATUS_COLORS[name]} for name in STATUS_OPTIONS
            ]
        }
    },
    T_PRIORITY: {
        "select": {
            "options": [
                {"name": name, "color": PRIORITY_COLORS[name]}
                for name in PRIORITY_OPTIONS
            ]
        }
    },
    T_DONE_AT: {"date": {}},
    T_REVIEW_NOTE: {"rich_text": {}},
}

# --- Journal properties -------------------------------------------------------
J_TITLE = "日期"        # title property; stores the ISO date string, e.g. 2026-06-01
J_CALENDAR = "日历"     # date property; unused by the tool, for Notion-native calendar views
J_TASKS = "今日任务"    # relation -> Tasks database
J_REVIEW = "复盘"       # rich text
J_MOOD = "心情精力"     # select

MOOD_OPTIONS = ["精力充沛", "一般", "疲惫"]

MOOD_COLORS = {"精力充沛": "green", "一般": "yellow", "疲惫": "purple"}


def journal_properties(tasks_db_id: str) -> dict:
    return {
        J_TITLE: {"title": {}},
        J_CALENDAR: {"date": {}},
        J_TASKS: {
            "relation": {
                "database_id": tasks_db_id,
                "type": "single_property",
                "single_property": {},
            }
        },
        J_REVIEW: {"rich_text": {}},
        J_MOOD: {
            "select": {
                "options": [
                    {"name": name, "color": MOOD_COLORS[name]} for name in MOOD_OPTIONS
                ]
            }
        },
    }


# --- Notion API write shapes --------------------------------------------------
def title_value(text: str) -> dict:
    return {"title": [{"text": {"content": text}}]}


def rich_text_value(text: str) -> dict:
    return {"rich_text": [{"text": {"content": text}}]}


def date_value(iso_date: str) -> dict:
    return {"date": {"start": iso_date}}


def select_value(name: str) -> dict:
    return {"select": {"name": name}}


def relation_value(page_ids: list[str]) -> dict:
    return {"relation": [{"id": pid} for pid in page_ids]}
