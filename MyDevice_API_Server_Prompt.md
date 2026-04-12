## 任务
为 Flutter 桌面应用 MyDevice（YuanZhe-99/MyDevice）添加一个本地 HTTP API Server，
供外部程序（如 AstrBot 插件）调用，以实现自然语言查询和管理设备数据。

## 技术要求
- 使用 `shelf` + `shelf_router` 包（在 pubspec.yaml 中添加依赖）
- 新增 pubspec.yaml 依赖：
    shelf: ^1.4.0
    shelf_router: ^1.1.0
    launch_at_startup: ^0.5.1
    package_info_plus（如尚未添加）
- 仅在 Windows/macOS/Linux 桌面端启动，端口：7789，支持设置界面修改端口
- 增加 App 后台运行能力（tray_manager + window_manager 系统托盘后台留存）和自启动能力（launch_at_startup），参考 MyAnime 的实现
- 监听地址默认 localhost，支持设置界面修改
- 支持设置用户名和密码进行 Basic Auth 认证，默认无认证（非 localhost 访问时强制认证）
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
3. 添加 CORS 中间件（Access-Control-Allow-Origin: *，Allow-Headers 包含 Authorization）
4. 所有日期字段使用 ISO 8601 格式
5. 参考项目中 lib/shared/services/backup_service.dart 或类似文件了解存储路径约定

## 已踩坑记录（必须遵守，参考 MyAnime 实现）

### InternetAddress 地址绑定
- **绝对不能**使用 `InternetAddress('localhost', type: InternetAddressType.any)`
  — 'localhost' 是主机名不是数字地址，`InternetAddress` 构造函数会抛异常
- 正确做法：
  ```dart
  final InternetAddress bindAddress;
  if (addr == '0.0.0.0') {
    bindAddress = InternetAddress.anyIPv4;
  } else if (addr == 'localhost' || addr == '127.0.0.1') {
    bindAddress = InternetAddress.loopbackIPv4;
  } else {
    bindAddress = InternetAddress(addr, type: InternetAddressType.any);
  }
  ```

### 非 localhost 监听必须设置凭据
- 当 listenAddress 为 0.0.0.0 或非 localhost/127.0.0.1 时，
  如果未设置 username + password，服务器应**拒绝启动**
- 设置 `_lastError = 'credentials_required'` 并 return，不启动服务器
- UI 设置页应检查 `LocalApiServer.lastError`，红色字体显示错误原因

### 错误状态暴露给 UI
- LocalApiServer 需要 `static String? _lastError` 和 `static String? get lastError`
- start() 开始时 `_lastError = null`
- start() 失败时 catch 中设置 `_lastError = e.toString()`
- 设置页 subtitle 根据 isRunning / lastError 显示不同状态文字

### macOS 平台特殊要求
- **Release.entitlements 必须包含** `com.apple.security.network.server` 权限
  （DebugProfile.entitlements 通常已有，Release.entitlements 容易遗漏）
  如缺失，macOS Release 构建的 sandbox 会阻止 socket bind，导致服务器静默失败
- **launch_at_startup 需要 macOS 平台配置：**
  1. 在 `macos/Runner/MainFlutterWindow.swift` 中添加：
     - `import LaunchAtLogin`
     - FlutterMethodChannel(name: "launch_at_startup") 处理
       `launchAtStartupIsEnabled` 和 `launchAtStartupSetEnabled` 方法
  2. 在 `macos/Runner.xcodeproj/project.pbxproj` 中添加 Swift Package 依赖：
     - XCRemoteSwiftPackageReference: `https://github.com/sindresorhus/LaunchAtLogin-Modern`
     - minimumVersion: 1.1.0, kind: upToNextMajorVersion
     - Runner target 添加 packageProductDependencies
  3. MACOSX_DEPLOYMENT_TARGET 须 >= 13.0（LaunchAtLogin-Modern 要求 macOS 13+）
     pbxproj 中所有 3 处 MACOSX_DEPLOYMENT_TARGET（Debug/Release/Profile）都要改
- **关闭到托盘（close-to-tray）：**
  - `AppDelegate.swift` 的 `applicationShouldTerminateAfterLastWindowClosed` 必须返回 `false`
    （默认返回 `true`，会导致关闭窗口时整个应用退出而非隐藏到托盘）
- **Dock 图标隐藏/显示：**
  - 最小化/关闭到托盘时隐藏 Dock 图标，从托盘恢复时重新显示
  - 在 `AppDelegate.swift` 的 `applicationDidFinishLaunching` 中注册 MethodChannel（如 `com.yuanzhe.my_device/dock`）
  - 处理 `setDockIconVisible` 方法：`NSApp.setActivationPolicy(.accessory)` 隐藏、`.regular` 显示
  - Flutter 端 `tray_service.dart` 在窗口隐藏/显示时调用该 channel