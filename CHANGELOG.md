# 更新日志

## v0.4.1

### 新增

1. **MyAnime评分排行**：新增 `anime_ranking` 工具，支持按全部/季度/年份/季度范围、番剧类型、评分项、升降序和数量限制查询评分榜。

### 改动

1. `anime_list` 和 `anime_history` 优先使用 MyAnime API 返回的统一 `status`、进度计数和评分摘要，状态分类与 MyAnime 统计页保持一致。
2. MyAnime API 文档更新到 `/anime/ranking` 和扩展后的列表字段。

## v0.4.0

### 新增

1. **服务查询**：新增 `device_service_search` 工具，支持按关键词搜索 MyDevice 中手动记录的服务、端口和端点。
2. **服务路由**：新增 `device_service_routes` 工具，查询公网访问路径、反代、隧道、FRP、域名路由等信息。
3. **服务统计**：新增 `device_service_stats` 工具，获取服务数量、端点数量、路由数量等统计概览。
4. **网络查询**：新增 `device_network_search` 工具，查询网络信息和设备 IP 分配（支持 Tailscale/WireGuard/局域网等）。
5. **数据集查询**：新增 `device_dataset_search` 工具，查询数据集及其链接的设备存储信息。

### 改动

1. `device_list` 新增生命周期状态和位置信息显示。
2. `device_search` 新增位置、生命周期状态、购入/售出价格、周期费用等详情。
3. `device_stats` 新增生命周期统计、服务/网络/数据集概览和财务摘要。
4. `device_search` 关键词现在正确进行 URL 编码。

## v0.3.1

### 修复

1. 修复 `anime_history` 中已弃番被归入"进行中"的问题，现在正确归为"🚫已弃番"分类。
2. `anime_list` 和 `anime_history` 现在显示完整的统计摘要（完结/进行中/未开始/弃番数量），当数据为随机抽样时标注"以下随机展示N部"。

### 改动

1. API `/anime/list` 和 `/anime/history` 响应格式从数组变为 `{"total", "counts", "data"}` 对象，包含总数和各状态计数。

## v0.3.0

### 新增

1. **隐私保护**：新增 `allowed_sender_ids` 配置项（列表类型），可指定允许使用本插件的用户 ID，留空则不限制。所有 LLM 工具和指令均受此限制。
2. **MyDay 模块开关**：新增 `myday_todo_enabled`、`myday_finance_enabled`、`myday_weight_enabled` 配置项，可单独开关 MyDay 的待办、财务、体重模块。

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
