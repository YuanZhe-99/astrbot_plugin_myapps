# AGENTS.md

This file is the operating guide for agents working on **astrbot_plugin_myapps**. Read it before editing anything, then read the relevant source files and the user's request carefully. The user's message is the change request: plan the work, execute it in this workspace, verify it, and keep this document current when the project changes.

## Project Snapshot

- **Name:** `astrbot_plugin_myapps`.
- **Description:** AstrBot plugin integrating MyAnime, MyDevice, and MyDay with LLM Function Calling natural-language interaction plus a traditional `/myapps` command.
- **Author:** `YuanZhe-99`.
- **License:** GPL-3.0.
- **Current version:** `0.4.2` in `metadata.yaml`.
- **Framework:** AstrBot Star plugin written in async Python.
- **Runtime dependency:** `aiohttp`, normally bundled with AstrBot.
- **Repository:** Use the current runtime workspace root / repository path instead of hard-coding a machine-specific absolute path.
- **Remotes:**
  - `origin` -> `<local_gitea_address>`
  - `github` -> `git@github.com:YuanZhe-99/astrbot_plugin_myapps.git`

Do not include secrets, credentials, API Basic Auth usernames/passwords, private local app data, real local-only machine addresses, or personal sender IDs in commits or in this file. Keep the `origin` URL masked as `<local_gitea_address>` in public documentation.

## Required Agent Workflow

1. Treat the user's message as the modification request.
2. Before making any modification, check whether the relevant remote has new commits by fetching and comparing the current branch with its upstream. If the branch is behind or has diverged, stop and resolve that situation before editing.
3. Read this `AGENTS.md`, inspect the relevant source files, and understand the current behavior before editing.
4. Make a concise plan when the work is non-trivial, then implement the requested changes directly in the workspace.
5. Keep changes scoped. Do not revert unrelated user work in the tree.
6. Update `AGENTS.md` in the same change set whenever architecture, behavior, API contracts, config keys, commands, release process, remotes, caveats, feature descriptions, or project history change. This document replaces the older external summary role and must stay current and complete.
7. Verify with the narrowest meaningful checks for the change. For Python changes, at minimum consider `python -m py_compile main.py`; also run any available AstrBot/plugin-specific checks if they exist.
8. When the work is complete, report briefly in both English and Chinese:
   - what changed,
   - what was verified,
   - the current/pre-change version,
   - the configured remotes,
   - whether anything could not be done.
9. For normal code changes, ask whether the user wants to push to all remotes. The user must provide or confirm the release version before a release push.

## Release, Version, Commit, Tag, and Push Flow

For ordinary feature/fix work, do not bump versions or tag until the user confirms the release version and confirms pushing.

When the user confirms the version and wants to push:

1. Update every version location:
   - `metadata.yaml`: `version: "X.Y.Z"`.
   - `CHANGELOG.md`: add a new `## vX.Y.Z` section with concise user-visible changes.
   - `README.md`: update only if setup, behavior, commands, endpoints, or compatibility changed.
   - `AGENTS.md`: update the current version and any changed architecture/process notes.
2. Re-run appropriate verification.
3. Commit all intended changes.
4. Create an annotated tag named `vX.Y.Z`.
5. Push the commit to both `origin` and `github` when the user has requested pushing.
6. Push the tag to both `origin` and `github` when the user has requested pushing.

For documentation-only maintenance that the user explicitly says does not require a release, commit and push the documentation change only when requested, without changing versions or creating a tag.

## Repository Structure

```text
main.py                         # Plugin entry: Main(Star), llm_tool handlers, /myapps command
metadata.yaml                   # AstrBot plugin metadata and version
_conf_schema.json               # AstrBot WebUI config schema
README.md                       # User-facing documentation
CHANGELOG.md                    # Release history
MyAnime_API_Server_Prompt.md    # MyAnime local API implementation prompt/reference
MyDevice_API_Server_Prompt.md   # MyDevice local API implementation prompt/reference
MyDay_API_Server_Prompt.md      # MyDay local API implementation prompt/reference
AGENTS.md                       # Agent operating guide for this repository
```

There is currently no dedicated test suite in this repository. Keep verification focused and avoid adding broad infrastructure unless the user requests it or a change clearly needs it.

## Core Architecture

```text
User IM message
    -> AstrBot
    -> astrbot_plugin_myapps Python plugin
    -> HTTP JSON calls through aiohttp
    -> desktop local API servers in MyAnime / MyDevice / MyDay
```

Default local API targets:

| App | Default base URL | Purpose |
| --- | --- | --- |
| MyAnime | `http://localhost:7788` | Anime tracking/search/history/ranking |
| MyDevice | `http://localhost:7789` | Device inventory/search/stats |
| MyDay | `http://localhost:7790` | Todo, finance, and weight |

Each Flutter app must be running its desktop local API server for the corresponding plugin tools to work. The plugin is only an AstrBot integration layer; it does not read or write the Flutter apps' JSON data files directly.

## Configuration

All settings are managed through AstrBot WebUI using `_conf_schema.json`.

Global config:

| Key | Type | Default | Notes |
| --- | --- | --- | --- |
| `allowed_sender_ids` | list | `[]` | Platform sender IDs allowed to use the plugin. Empty means unrestricted. |
| `http_timeout` | int | `12` | Request timeout applied to all aiohttp GET/POST calls through `ClientTimeout(total=...)`. |

Per-app config keys follow this pattern:

| App | Enabled | Read-only | Base URL | Basic Auth |
| --- | --- | --- | --- | --- |
| MyAnime | `myanime_enabled` | `myanime_readonly` | `myanime_base` | `myanime_username`, `myanime_password` |
| MyDevice | `mydevice_enabled` | `mydevice_readonly` | `mydevice_base` | `mydevice_username`, `mydevice_password` |
| MyDay | `myday_enabled` | `myday_readonly` | `myday_base` | `myday_username`, `myday_password` |

MyDay also has module-level gates:

| Key | Default | Notes |
| --- | --- | --- |
| `myday_todo_enabled` | `true` | Enables Todo tools when `myday_enabled` is also true. |
| `myday_finance_enabled` | `true` | Enables Finance tools when `myday_enabled` is also true. |
| `myday_weight_enabled` | `true` | Enables Weight tools when `myday_enabled` is also true. |

Do not commit real Basic Auth credentials or private allow-list sender IDs.

## Code Conventions

- Keep helper functions at module level unless a change clearly benefits from moving them: `_make_auth_header()`, `_get()`, `_post()`, `_check()`, `_dow()`.
- Keep `Main(star.Star)` as the single plugin class unless a feature becomes genuinely reusable or too large.
- Use config property accessors for app-specific base URL, auth, enabled state, read-only state, and MyDay module gates.
- Every handler should follow the same guard order: `_check_sender()` -> app/module enabled check -> read-only check for write operations -> local API connectivity check -> business logic.
- `llm_tool` handlers return plain strings.
- Traditional command handlers yield `event.plain_result(...)`.
- HTTP helpers should catch exceptions, log through `astrbot.core.logger`, and return `None` on failure.
- Keep user-facing strings concise and understandable in Chinese, matching the existing style.
- Do not add backward-compatibility shims unless persisted data, shipped behavior, external API consumers, or the user explicitly requires them.

## LLM Tools

### MyAnime

| Tool | Args | Behavior |
| --- | --- | --- |
| `anime_add` | `title` | Search MyAnime sources and add the best match to the tracking list. Write operation; blocked in read-only mode. |
| `anime_list` | `season` | List tracked anime for `current`, `YYYYQn`, `unassigned`, or `all`. |
| `anime_unwatched` | none | List aired but unwatched episodes. |
| `anime_history` | `season` | Show viewing progress/history for a season filter. |
| `anime_ranking` | `time`, `season`, `year`, `start`, `end`, `anime_type`, `field`, `order`, `limit` | Show rating rankings by all/quarter/year/range, type, rating field, order, and limit. |

MyAnime list/history API responses are expected to be objects with `total`, `counts`, and `data`. `counts` may include `completed`, `watching`, `inProgress`, `notStarted`, `dropped`, and `abandoned`. Item `status` values are `completed`, `watching`, `dropped`, and `notStarted`. `nextEpisodeAirDate` is expected to be UTC-compatible so `datetime.now(timezone.utc)` comparisons are meaningful. Ranking responses are expected to include `total`, `filters`, `sort`, `limit`, and ranked `data` rows with `rank`, `score`, and rating summary fields.

### MyDevice

| Tool | Args | Behavior |
| --- | --- | --- |
| `device_list` | `category` | List devices, optionally filtered by category. |
| `device_search` | `keyword` | Search saved devices by name/brand/model and show specs. |
| `device_add` | `name`, `category`, `brand`, `model`, `os`, `notes` | Add a new device. Write operation; blocked in read-only mode. |
| `device_stats` | none | Show count summary by category and recently added devices. |

Device categories currently include `all`, `desktop`, `laptop`, `phone`, `tablet`, `headphone`, `watch`, `router`, `gameConsole`, `vps`, `devBoard`, and `other`.

### MyDay Todo

| Tool | Args | Behavior |
| --- | --- | --- |
| `todo_today` | `date` | List tasks for a date. |
| `todo_add` | `title`, `task_type`, `due_date`, `note`, `scheduled_date`, `reminder_time`, `subtasks`, recurrence fields | Add a task with notes, schedule/start date, reminder, subtasks, and optional one-time recurrence. Write operation; blocked in read-only mode. |
| `todo_complete` | `title`, `date`, `completed`, `subtask_title`, `create_next_recurrence` | Complete or reopen a task/subtask by title keyword. Write operation; blocked in read-only mode. |
| `todo_score` | `date`, `score` | Set the todo day score from -5 to 5. Write operation; blocked in read-only mode. |
| `todo_stats` | none | Show today's completion stats. |

`task_type` values are `daily`, `routineOnce`, and `workOnce`.

### MyDay Finance

| Tool | Args | Behavior |
| --- | --- | --- |
| `finance_summary` | `month` | Show monthly income, expense, balance, top expense categories, and sample accounts. |
| `finance_accounts` | `account_type` | List accounts and balances, optionally filtered by account type. |
| `finance_categories` | `ttype` | List expense/income/transfer categories. |
| `finance_add_transaction` | `ttype`, `amount`, `note`, `account_name`, `category_name`, `date`, `currency`, `to_account_name`, `to_amount`, `to_currency` | Record income, expense, or transfer using matched account/category names. Write operation; blocked in read-only mode. |
| `finance_subscriptions` | none | List active subscriptions and next billing dates. |

`ttype` values are `expense`, `income`, and `transfer`. MyDay `0.8.0+` performs default-currency conversion in `/finance/summary`; the plugin formats values from the API response.

### MyDay Weight

| Tool | Args | Behavior |
| --- | --- | --- |
| `weight_log` | `weight`, `body_fat`, `bust_cm`, `waist_cm`, `hip_cm`, `notes`, `date` | Record weight, optional body fat, measurements, notes, and date. Write operation; blocked in read-only mode. |
| `weight_stats` | none | Show latest, averages, BMI, waist-hip ratio, effective measurements, trend, and recent records. |
| `weight_recent` | `limit` | List recent weight records with body composition and effective measurements. |

## Traditional Commands

| Command | Behavior |
| --- | --- |
| `/myapps` | Show a concise feature overview and example natural-language prompts. |

The sender allow-list applies to both LLM tools and `/myapps`.

## Local API Contract Reference

The plugin calls these endpoints:

| App | Endpoints |
| --- | --- |
| MyAnime | `GET /ping`, `POST /anime/search`, `POST /anime/add`, `GET /anime/list`, `GET /anime/unwatched`, `GET /anime/history`, `GET /anime/ranking` |
| MyDevice | `GET /ping`, `GET /device/list`, `GET /device/search`, `POST /device/add`, `GET /device/stats` |
| MyDay | `GET /ping`, `GET /todo/list`, `GET /todo/day`, `POST /todo/add`, `POST /todo/complete`, `POST /todo/score`, `GET /todo/stats`, `GET /finance/summary`, `GET /finance/accounts`, `GET /finance/categories`, `GET /finance/transactions`, `POST /finance/add_transaction`, `GET /finance/subscriptions`, `GET /weight/list`, `POST /weight/add`, `GET /weight/stats` |

The README lists a broader set of local API endpoints implemented by the apps. `main.py` is the source of truth for endpoints currently used by this plugin.

If the Flutter-side API contract changes, update the relevant `*_API_Server_Prompt.md`, `README.md`, `main.py`, and this guide together.

## Security and Privacy Rules

- `allowed_sender_ids` is the primary plugin-side privacy gate. It uses `event.get_sender_id()` from AstrBot.
- Empty `allowed_sender_ids` means no sender restriction.
- Per-app read-only modes must block all write operations before any write endpoint is called.
- Basic Auth headers are constructed only when both username and password are configured.
- Do not log credentials, tokens, sender IDs, or private personal data.
- Prefer localhost/local-only API usage. If users configure LAN addresses, credentials are their responsibility on the Flutter app side.

## Prompt Files

The three `*_API_Server_Prompt.md` files document how the Flutter apps' local Shelf API servers should be implemented. They are references for cross-repository API changes, not executable code in this plugin.

When updating these prompt files:

- Keep port numbers and endpoint names aligned with `main.py` and `README.md`.
- Preserve important platform caveats, especially desktop tray, close-to-tray, and macOS network server behavior.
- Do not copy secrets or local machine-specific values from app repositories.

## Useful Commands

```powershell
python -m py_compile main.py
git status --short --branch
git diff -- main.py metadata.yaml _conf_schema.json README.md CHANGELOG.md AGENTS.md
```

Use the narrowest relevant verification. Documentation-only changes usually need a read/diff check rather than Python execution. Python code changes should at least compile `main.py`; behavior changes should also be checked in an AstrBot runtime when feasible.

## Version History Reference

- `v0.1.0`: Initial integration of MyAnime, MyDevice, and MyDay LLM Function Calling tools plus AstrBot WebUI configuration.
- `v0.2.0`: Per-app enabled/disabled switches, per-app read-only modes, MyAnime `season` filters for list/history, and aired-only `anime_unwatched` behavior.
- `v0.2.1`: Updated API server prompt files with macOS close-to-tray and Dock behavior notes.
- `v0.2.2`: Fixed abandoned anime display and not-yet-aired episode display; added `nextEpisodeAirDate` handling.
- `v0.2.3`: Fixed timezone comparison for MyAnime `nextEpisodeAirDate` by comparing against UTC.
- `v0.3.0`: Added `allowed_sender_ids` privacy protection and independent MyDay Todo/Finance/Weight module toggles.
- `v0.3.1`: MyAnime list/history consume `total`, `counts`, and `data`, show full summary counts, and classify abandoned anime correctly.
- `v0.4.0`: Added MyDevice service, network, and dataset query tools plus richer device detail formatting.
- `v0.4.1`: Added MyAnime rating ranking tool and consumed the refreshed MyAnime status/progress/rating API fields.
- `v0.4.2`: Refreshed MyDay integration for MyDay `0.8.0`, adding todo completion/day scores, finance account/category lookup, richer transaction creation, body-composition weight logging/recent records, and configured HTTP timeouts.
