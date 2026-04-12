## 任务
为 Flutter 桌面应用 MyAnime（YuanZhe-99/MyAnime）添加一个本地 HTTP API Server，
供外部程序（如 AstrBot 插件 astrbot_plugin_myapps）通过 HTTP 调用，
实现番剧的搜索、添加、列表查询、未看查询和历史统计功能。

## 项目背景
- Flutter + Riverpod 状态管理
- 番剧数据存储于本地 JSON 文件（通过 AnimeStorage 读写）
- 已有的搜索能力封装在 AnimeSearchService（调用 bangumi.tv / MAL / AniList 等）
- 数据模型核心：Anime（lib/features/anime/models/anime.dart）
- 存储服务：AnimeStorage（lib/features/anime/services/anime_storage.dart）
- 搜索服务：AnimeSearchService（lib/features/anime/services/anime_search_service.dart）

## 技术要求
- 新增 pubspec.yaml 依赖：
    shelf: ^1.4.0
    shelf_router: ^1.1.0
    launch_at_startup: ^0.5.1
    package_info_plus（如尚未添加）
- 仅在 Windows / macOS / Linux 桌面端启动（用 Platform.isWindows 等判断）
- 监听地址默认 localhost，端口 7788，均可在设置界面中修改
- 支持设置用户名和密码进行 Basic Auth 认证，默认无认证（非 localhost 访问时强制认证）
- 增加 App 后台运行能力（tray_manager + window_manager 系统托盘后台留存）
- 增加桌面自启动（launch_at_startup），在设置页添加开关
- 新建文件：lib/shared/services/local_api_server.dart
- 在 lib/main.dart 的 main() 函数中，WidgetsFlutterBinding.ensureInitialized() 之后、
  runApp() 之前添加以下调用（仅桌面端）：
    if (Platform.isWindows || Platform.isMacOS || Platform.isLinux) {
      await LocalApiServer.start();
    }
  并在 main() 最顶部 import 'dart:io'; 及新文件的路径

## 数据模型速查（已存在，直接引用，不要重新定义）

### Anime（lib/features/anime/models/anime.dart）
主要字段：
  id(String), title(String?), titleJa(String?), season(String),
  startEpisode(int), endEpisode(int?), manualType(AnimeType?),
  airDayOfWeek(int? 1=Mon..7=Sun), airTime(String? "HH:mm"),
  firstAirDate(DateTime?), episodeStatuses(Map<int, EpisodeStatus>),
  coverImage(String?), infoUrl(String?), watchUrl(String?),
  episodeWeekOffsets(Map<int,int>), notes(String?),
  createdAt(DateTime), modifiedAt(DateTime)

计算属性：
  displayTitle → title ?? titleJa ?? ''
  totalEpisodes → endEpisode != null ? endEpisode - startEpisode + 1 : null
  effectiveType → AnimeType (singleCour/halfYear/fullYear/longRunning/allAtOnce)
  nextUnwatchedEpisode → int? （第一个 unwatched 集数）
  isCompleted → bool

EpisodeStatus 枚举：unwatched, watched, skippedThisWeek

### AnimeData（顶层容器）
  animes: List<Anime>
  静态方法：AnimeData.fromJson(), toJson()

### AnimeSearchResult（lib/features/anime/services/anime_search_service.dart）
  source, sourceUrl, title, titleJa, episodes(int?),
  firstAirDate(DateTime?), airDayOfWeek(int?), airTime(String?),
  coverImageUrl(String?), summary(String?)

## 需要实现的 API 端点

### GET /ping
响应：{"status": "ok"}

---

### POST /anime/search
功能：搜索番剧（直接复用已有的 AnimeSearchService.searchAll()）
请求体：{"query": "番剧名称"}
响应：最多返回 5 条结果的 JSON 数组，每项包含：
  {
    "source": string,
    "sourceUrl": string?,
    "title": string?,
    "titleJa": string?,
    "episodes": int?,
    "firstAirDate": string?,   // ISO 8601，可 null
    "airDayOfWeek": int?,      // 1=周一..7=周日
    "airTime": string?,        // "HH:mm"
    "coverImageUrl": string?,
    "summary": string?
  }
错误：400 {"error": "query is required"}

---

### POST /anime/add
功能：将一部番剧添加到本地数据（调用 AnimeStorage.addOrUpdate()）
请求体：
  {
    "title": string?,
    "titleJa": string?,
    "episodes": int?,          // 对应 endEpisode（startEpisode 默认为 1）
    "firstAirDate": string?,   // "yyyy-MM-dd" 或 ISO 8601
    "airDayOfWeek": int?,
    "airTime": string?,
    "sourceUrl": string?,      // 作为 infoUrl
    "coverImageUrl": string?   // 暂时忽略（本地无法直接保存网络图片）
  }
实现：调用 Anime.create(...) 构造实例，再调用 AnimeStorage.addOrUpdate(anime)
响应：{"success": true, "id": "<uuid>", "title": "<displayTitle>"}
错误：400 {"error": "title or titleJa is required"}

---

### GET /anime/list
功能：返回所有番剧列表
响应：JSON 数组，每项包含：
  {
    "id": string,
    "title": string,           // displayTitle
    "titleJa": string?,
    "season": string,
    "startEpisode": int,
    "endEpisode": int?,
    "totalEpisodes": int?,
    "firstAirDate": string?,
    "airDayOfWeek": int?,
    "airTime": string?,
    "infoUrl": string?,
    "isCompleted": bool,
    "nextUnwatchedEpisode": int?,
    "type": string,            // effectiveType.name
    "createdAt": string        // ISO 8601
  }

---

### GET /anime/unwatched
功能：返回有未看集数的番剧（!isCompleted && nextUnwatchedEpisode != null）
响应：格式同 /anime/list，每项额外包含：
  "nextUnwatchedEpisode": int

---

### GET /anime/history
功能：返回所有番剧及其观看进度统计
响应：格式同 /anime/list，每项额外包含：
  "watchedEpisodes": int,   // episodeStatuses 中值为 watched 的数量
  "isCompleted": bool

---

## 实现细节要求

1. 统一 Content-Type: application/json 响应头
2. 解析请求体失败时返回 400 {"error": "invalid JSON body"}
3. 所有日期使用 ISO 8601（DateTime.toIso8601String()）
4. 添加 CORS 中间件，响应头包含：
   Access-Control-Allow-Origin: *
   Access-Control-Allow-Methods: GET, POST, OPTIONS
   Access-Control-Allow-Headers: Content-Type, Authorization
5. 捕获所有异常，返回 500 {"error": "internal error: <message>"}
6. AnimeStorage 是纯静态类，可直接调用，不需要实例化
7. 服务器实例存为静态变量 static HttpServer? _server，提供 start() 和 stop() 方法
8. 端口号从配置读取，默认 7788

## 已踩坑记录（必须遵守）

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

## 完整文件结构示例

lib/shared/services/local_api_server.dart 结构：

  import 'dart:convert';
  import 'dart:io';
  import 'package:shelf/shelf.dart';
  import 'package:shelf/shelf_io.dart' as shelf_io;
  import 'package:shelf_router/shelf_router.dart';
  import '../../features/anime/models/anime.dart';
  import '../../features/anime/services/anime_search_service.dart';
  import '../../features/anime/services/anime_storage.dart';

  class LocalApiServer {
    static HttpServer? _server;
    static int _port = 7788;
    static String _listenAddress = 'localhost';
    static bool _enabled = false;
    static String? _username;
    static String? _password;
    static String? _lastError;

    static int get port => _port;
    static String get listenAddress => _listenAddress;
    static bool get enabled => _enabled;
    static bool get isRunning => _server != null;
    static String? get lastError => _lastError;

    static Future<void> start() async { ... }
    static Future<void> stop() async { ... }
    static Future<void> restart() async { ... }
    static Future<void> loadConfig() async { ... }

    // 路由处理方法（GET /ping, POST /anime/search, POST /anime/add,
    //              GET /anime/list, GET /anime/unwatched, GET /anime/history）

    // 辅助：将 Anime 转为 Map<String, dynamic>
    static Map<String, dynamic> _animeToJson(Anime a) { ... }

    // CORS 中间件
    static Middleware _corsMiddleware() { ... }
  }

## lib/main.dart 修改

在文件顶部 import 区域添加：
  import 'dart:io';
  import 'shared/services/local_api_server.dart';

在 main() 函数体内，WidgetsFlutterBinding.ensureInitialized(); 之后添加：
  // Start local HTTP API server (desktop only)
  if (Platform.isWindows || Platform.isMacOS || Platform.isLinux) {
    await LocalApiServer.start();
  }

注意：原有的 ReminderService.init()、BackupService.runAutoBackupIfNeeded()、
AutoSyncService.instance.start()、FileOpenService.init()、
以及 runApp() 调用均保持不变，LocalApiServer.start() 插入在它们之前即可。

## pubspec.yaml 修改

在 dependencies: 下添加（与现有依赖并列）：
  shelf: ^1.4.0
  shelf_router: ^1.1.0