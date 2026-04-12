## 任务
为 Flutter 桌面应用 MyDay（YuanZhe-99/MyDay）添加一个本地 HTTP API Server，
供外部程序（如 AstrBot 插件）调用，实现 Todo、财务、体重数据的查询与管理。

## 技术要求
- 使用 `shelf` + `shelf_router` 包（在 pubspec.yaml 中添加依赖）
- 新增 pubspec.yaml 依赖：
    shelf: ^1.4.0
    shelf_router: ^1.1.0
    launch_at_startup: ^0.5.1
    package_info_plus（如尚未添加）
- 仅在 Windows/macOS/Linux 桌面端启动，端口：7790，支持设置界面修改端口
- 增加 App 后台运行能力（tray_manager + window_manager 系统托盘后台留存）和自启动能力（launch_at_startup），参考 MyAnime 的实现
- 监听地址默认 localhost，支持设置界面修改
- 支持设置用户名和密码进行 Basic Auth 认证，默认无认证（非 localhost 访问时强制认证）
- 在 lib/main.dart 的 main() 中，await LocalApiServer.start() 调用（仅桌面）
- 新建文件：lib/shared/services/local_api_server.dart

## 数据模型（已存在，直接引用）

### Todo（lib/features/todo/models/task.dart）
- Task 字段：id, title, emoji, type(TaskType: daily/routineOnce/workOnce),
  isCompleted, reminderTime, subtasks(List<SubTask>), createdDate,
  completedDate, scheduledDate, deletedDate, startDate, dueDate, modifiedAt
- SubTask 字段：id, title, isCompleted, modifiedAt
- DailyCompletionLog：追踪每日任务完成状态

### Finance（lib/features/finance/models/finance.dart）
- Account 字段：id, type(AccountType: fund/credit/recharge/financial),
  bankOrApp, name, currency, cardNumber, expiryDate, emoji, modifiedAt
- Transaction 字段：id, type(TransactionType: expense/income/transfer),
  amount, currency, accountId, toAccountId, toAmount, categoryId, note, date, modifiedAt
- Category 字段：id, name, type(expense/income), emoji, modifiedAt
- Subscription 字段：id, name, emoji, startDate, trialDays,
  billingCycleType(monthly/yearly), billingInterval, amount, currency,
  accountId, isActive, nextBillingDate, modifiedAt

### Weight（lib/features/weight/models/ 中，参考同目录文件）
- WeightEntry 字段推断：id, weight(double), date(DateTime), modifiedAt

## 需要实现的 API 端点

### GET /ping
- 返回：{"status": "ok"}

### Todo 接口

#### GET /todo/list
- 查询参数：date=yyyy-MM-dd（可选，不传则返回今日），type=daily|routineOnce|workOnce（可选）
- 返回该日期的任务列表（包含当天有效的 daily 模板 + 当天的 workOnce/routineOnce）
- 每个任务包含：id, title, emoji, type, isCompleted(考虑DailyCompletionLog), 
  subtasks, dueDate, scheduledDate

#### POST /todo/add
- 请求体：{"title": string, "type": string, "emoji": string?, "dueDate": string?, "scheduledDate": string?}
- 返回：{"success": true, "id": string}

#### POST /todo/complete
- 请求体：{"id": string, "date": string?(yyyy-MM-dd，daily任务需要), "completed": bool}
- 返回：{"success": true}

#### GET /todo/stats
- 返回：{"today_total": int, "today_completed": int, "overdue": int}

### Finance 接口

#### GET /finance/summary
- 查询参数：month=yyyy-MM（可选，默认当月）
- 返回：{
    "income": double,
    "expense": double, 
    "balance": double,
    "accounts": [ {id, name, type, currency, balance(计算值)} ],
    "top_expense_categories": [ {name, amount, count} ]
  }

#### GET /finance/transactions
- 查询参数：limit=20（默认）, offset=0, type=expense|income|transfer（可选）
- 返回最近的交易记录列表

#### POST /finance/add_transaction
- 请求体：{
    "type": "expense"|"income"|"transfer",
    "amount": number,
    "currency": string?,（默认CNY）
    "accountId": string,
    "toAccountId": string?,（转账用）
    "categoryId": string?,
    "note": string?,
    "date": string?（ISO8601，默认now）
  }
- 返回：{"success": true, "id": string}

#### GET /finance/subscriptions
- 返回所有活跃订阅及下次扣款日期
- 返回：[ {id, name, emoji, amount, currency, nextBillingDate, billingCycleType} ]

### Weight 接口

#### GET /weight/list
- 查询参数：limit=30（默认）
- 返回最近体重记录：[ {id, weight, date} ]

#### POST /weight/add
- 请求体：{"weight": number, "date": string?（ISO8601，默认now）}
- 返回：{"success": true, "id": string}

#### GET /weight/stats
- 返回：{"latest": double?, "avg_7d": double?, "avg_30d": double?, "trend": "up"|"down"|"stable"|"unknown"}

## 实现要点
1. 统一返回 Content-Type: application/json
2. 错误时返回 {"error": "描述"} + 合适的 HTTP 状态码
3. 添加 CORS 中间件（Access-Control-Allow-Origin: *，Allow-Headers 包含 Authorization）
4. finance/summary 中账户余额需要从 Transaction 记录动态计算
   （考虑 forcedBalance/forcedBalanceDate 作为基准点）
5. Todo 的 daily 任务需要考虑 startDate/deletedDate 过滤有效模板
6. 所有存储读取方式参考项目中已有的 Storage service 模式（读写 JSON 文件）

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
  - 在 `AppDelegate.swift` 的 `applicationDidFinishLaunching` 中注册 MethodChannel（如 `com.yuanzhe.my_day/dock`）
  - 处理 `setDockIconVisible` 方法：`NSApp.setActivationPolicy(.accessory)` 隐藏、`.regular` 显示
  - Flutter 端 `tray_service.dart` 在窗口隐藏/显示时调用该 channel