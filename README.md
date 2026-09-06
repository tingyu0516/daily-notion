# daily-notion

给 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 用的 Notion 日报系统：今日计划、明日计划、中途监督、晚间复盘，全部通过飞书对话完成，Notion 是记录板。

**架构**：Python stdio MCP server（薄数据层，只有 CRUD + 查询）+ Hermes SKILL.md（全部对话流程）+ 4 个带条件的 hermes cron。对话是唯一写入入口；cron 全部先查条件，条件不满足就静默。

```
你(飞书) ── Hermes Agent ──┬── daily-notion MCP server ── Notion(每日任务/每日日志)
                           └── 日报 cron ×4，条件触发（时刻自定，见下文）
```

## 首次安装

### 1. Notion 准备（约 3 分钟）

1. 打开 https://www.notion.so/profile/integrations → **New integration**，类型选 Internal，名字随意（如 `daily-notion`），创建后复制 `ntn_...` token。
2. 在 Notion 里新建（或选一个已有）页面作为两个数据库的家，复制该页面的 URL，URL 末尾那串 32 位十六进制就是 page id。
3. 在该页面点 `•••` → **Connections** → 搜索并添加你的 integration（这一步是授权，漏了脚本会报找不到页面）。

### 2. 配置并初始化

```powershell
cd E:\AIproject\AI-daily
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
copy .env.example .env
# 编辑 .env：填 NOTION_TOKEN 和 NOTION_PARENT_PAGE_ID
.\.venv\Scripts\python.exe -m daily_notion.setup            # 自动创建两个数据库并回写 id
.\.venv\Scripts\python.exe -m daily_notion.setup --check    # 随时验证连通性
```

setup 是幂等的：数据库 id 已写入 .env 就不会再建。建好后你可以把「每日任务」「每日日志」两个数据库拖到 Notion 里任意位置，id 不变。

### 3. 接入 Hermes

把 `skill\daily-notion\` 整个目录复制到 Hermes 的 skills 目录（`hermes skills list` 可确认加载），并在 Hermes 配置里加：

```yaml
mcp_servers:
  daily-notion:
    command: "<仓库路径>/.venv/Scripts/python.exe"   # Windows；Linux/macOS 用 .venv/bin/python
    args: ["-m", "daily_notion.server"]
    idle_timeout_seconds: 900   # 空闲 15 分钟回收，下次调用自动重启
```

### 4. 建四个 cron

用 `hermes cron create` 建 4 个任务，触发时刻完全由你自定（推荐：早报放在到岗后，中途提醒放在下午开工时，复盘提醒放在晚间你空闲的时段，兜底放在当天结束前）。**prompt 第一句必须点名 skill 流程**（skill 里有完整条件逻辑，时刻本身不写进 skill）：

| 流程 | prompt |
|---|---|
| 早报 | 执行 daily-notion skill 的【早报】流程，严格遵守其中的 cron 静默条件 |
| 中途提醒 | 执行 daily-notion skill 的【中途提醒】流程，严格遵守其中的 cron 静默条件 |
| 复盘提醒 | 执行 daily-notion skill 的【复盘提醒】流程，严格遵守其中的 cron 静默条件 |
| 深夜兜底 | 执行 daily-notion skill 的【深夜兜底】流程，严格遵守其中的 cron 静默条件 |

cron 触发时如果 agent 不知道当天日期，它会按 skill 指引先取系统时间，无需在 prompt 里写死。

## 日常怎么用

随时对机器人说，不用等固定时间：

- 「早报」—— 今日任务 + 顺延提醒 + 未来 3 天展望（只读）
- 「做完了 X」「X 顺延到周四」「明天要做 Y」「今天休」—— 状态随手更新
- 「复盘」—— 逐条确认未完成任务 → 生成复盘写入日志页 → 定明日计划
- 什么都不说 —— 复盘提醒时刻一句轻提醒；兜底时刻未确认任务自动顺延，次日早报点名

## 项目结构

```
daily_notion/
  config.py    .env 加载
  schema.py    两个数据库的全部字段定义（单一事实来源）
  store.py     Notion 数据访问层
  server.py    FastMCP server（9 个工具，纯数据操作）
  setup.py     初始化脚本（建库 + 回写 .env）
skill/daily-notion/SKILL.md   Hermes 技能：早报/汇报/提醒/复盘/兜底全部流程
scripts/smoke_test_mcp.py     本地冒烟测试（列出工具，无需 Notion token）
```

## 设计要点（为什么这样）

- **薄数据层 + 厚 skill**：改话术改流程 = 改 markdown，不动代码。
- **顺延不复制行**：状态改「顺延」+ 改日期，同一行，统计不重复。
- **Journal 懒创建**：没有复盘就没有空页面。
- **读不加缓存**：你在 Notion 里手动改了内容，工具照样读到。
- **cron 条件化**：周末没定任务就全静默；想周末干活，前一天晚上定计划即可。
