## 任务
为 Flutter 桌面应用 MyDevice（YuanZhe-99/MyDevice）添加一个本地 HTTP API Server，
供外部程序（如 AstrBot 插件）调用，以实现自然语言查询和管理设备数据。

## 技术要求
- 使用 `shelf` + `shelf_router` 包（在 pubspec.yaml 中添加依赖）
- 仅在 Windows/macOS/Linux 桌面端启动，端口：7789，支持设置界面修改端口
- 增加 App 后台运行能力和自启动能力，参考 MyAnime 的实现
- 默认仅绑定 localhost（InternetAddress.loopbackIPv4），不对外暴露
- 在 lib/main.dart 的 main() 中，await LocalApiServer.start() 调用（仅桌面）
- 新建文件：lib/shared/services/local_api_server.dart

## 数据模型（已存在，直接引用）
- `lib/features/devices/models/device.dart` 中的 Device、DeviceData、DeviceCategory
  - Device 字段：id, name, category(enum), emoji, brand, model, serialNumber,
    cpu(CpuInfo: model/architecture/frequency/performanceCores/efficiencyCores/threads/cache),
    gpu(GpuInfo: model/architecture), ram, ramType(enum), storage(List<StorageInfo>),
    screenSize, screenResolutionW, screenResolutionH, battery, os,
    locationName, latitude, longitude, purchaseDate, releaseDate, notes, modifiedAt
- `lib/features/devices/services/` 中的存储 Service（参考 AnimeStorage 的模式，
  读写 device_data.json，方法：load() → DeviceData, addOrUpdate(Device), deleteDevice(String id)）

## 需要实现的 API 端点

### GET /ping
- 返回：{"status": "ok"}

### GET /device/list
- 返回所有设备的 JSON 数组
- 每个设备包含：id, name, category, emoji, brand, model, serialNumber,
  cpu{model,cores,threads,frequency}, gpu{model}, ram, ramType, 
  storage[{capacity,type,interface}], screenSize, battery, os,
  locationName, purchaseDate, releaseDate, notes, modifiedAt

### GET /device/list?category=<category>
- category 可选值（对应 DeviceCategory.name）：
  desktop, laptop, phone, tablet, headphone, watch, router, gameConsole, vps, devBoard, other
- 返回过滤后的设备列表

### GET /device/search?q=<keyword>
- 在 name、brand、model、notes 字段中进行大小写不敏感的模糊搜索
- 返回匹配的设备列表

### POST /device/add
- 请求体 JSON：
  {
    "name": string (required),
    "category": string (required, DeviceCategory.name),
    "brand": string?,
    "model": string?,
    "serialNumber": string?,
    "cpu": { "model": string?, "architecture": string?, "frequency": string?,
             "performanceCores": int?, "efficiencyCores": int?, "threads": int?, "cache": string? }?,
    "gpu": { "model": string?, "architecture": string? }?,
    "ram": string?,
    "ramType": string?,
    "storage": [{ "capacity": string?, "type": string?, "interface": string? }]?,
    "screenSize": string?,
    "battery": string?,
    "os": string?,
    "locationName": string?,
    "purchaseDate": string? (ISO8601),
    "releaseDate": string? (ISO8601),
    "notes": string?
  }
- 返回：{"success": true, "id": "<uuid>", "name": "<name>"}

### GET /device/stats
- 返回统计摘要：
  {
    "total": int,
    "byCategory": { "desktop": int, "laptop": int, ... },
    "recentlyAdded": [ 最近5台设备的简要信息 ]
  }

## 实现要点
1. 统一返回 Content-Type: application/json
2. 错误时返回 {"error": "描述"} 并使用合适的 HTTP 状态码
3. 添加 CORS 中间件（Access-Control-Allow-Origin: *）
4. 所有日期字段使用 ISO 8601 格式
5. 参考项目中 lib/shared/services/backup_service.dart 或类似文件了解存储路径约定