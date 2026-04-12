# 更新日志

## v0.2.3

### 修复

1. 修复 `anime_list` 中"等待更新"判断时区不一致的问题：App 返回的 `nextEpisodeAirDate` 现已转为 UTC（带 `Z` 后缀），插件使用 `datetime.now(timezone.utc)` 进行比较，避免因服务器与 App 时区不同导致误判。

## v0.2.2

### 修复

1. 修复 `anime_list` 中弃番显示为"进行中"的问题，现在正确显示"🚫已弃番"。
2. 修复 `anime_list` 中未播出集数显示为"待看"的问题，现在显示"▶第N集等待更新"。
3. API 新增 `nextEpisodeAirDate` 字段，供插件区分"已播未看"和"尚未播出"。

## v0.2.1

### 修复

1. 更新三个 API Server Prompt 文件，补充 macOS close-to-tray 和 Dock 图标隐藏/显示的踩坑记录。

## v0.2.0

### 新增

1. 每个 App 支持独立的**启用/禁用开关**（`myanime_enabled`、`mydevice_enabled`、`myday_enabled`）。
2. 每个 App 支持**只读模式**（`myanime_readonly`、`mydevice_readonly`、`myday_readonly`），开启后仅查询工具可用，写入工具返回只读提示。
3. `anime_list` 和 `anime_history` 新增 `season` 参数，支持按季度筛选（`current`/`2026Q2`/`unassigned`/`all`）。
4. `anime_unwatched` 仅返回已播出但未观看的集数。

## v0.1.0

### 新增

1. 初始版本：集成 MyAnime、MyDevice、MyDay 三个 App 的 LLM Function Calling 工具。
2. 支持 AstrBot WebUI 配置界面管理所有连接参数和认证信息。
