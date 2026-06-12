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
  note, isCompleted, reminderTime, subtasks(List<SubTask>), createdDate,
  completedDate, scheduledDate, deletedDate, startDate, dueDate, recurrence, modifiedAt
- SubTask 字段：id, title, isCompleted, modifiedAt
- DailyCompletionLog：追踪每日任务完成状态
- DailyScoreLog：追踪每日 -5..5 日评分，显式 0 也要保留

### Finance（lib/features/finance/models/finance.dart）
- Account 字段：id, type(AccountType: fund/credit/recharge/financial),
  bankOrApp, name, currency, cardNumber, expiryDate, securityCode, emoji,
  imagePath, feeWaiverMinimumBalance, feeWaiverMonthlyDeposit, modifiedAt
- Transaction 字段：id, type(TransactionType: expense/income/transfer),
  amount, currency, rateSnapshotId, accountId, toAccountId, toAmount,
  toCurrency, categoryId, subscriptionId, note, date, modifiedAt
- Category 字段：id, name, type(expense/income/transfer), emoji, icon, modifiedAt
- Subscription 字段：id, name, emoji, startDate, trialDays,
  billingCycleType(monthly/yearly), billingInterval, amount, currency,
  accountId, isActive, nextBillingDate, modifiedAt

### Weight（lib/features/weight/models/weight_record.dart）
- WeightRecord 字段：id, weight(double), bodyFat, bustCm, waistCm, hipCm,
  datetime, notes, modifiedAt
- WeightData 字段：height, records, reminder settings, reminderGraceMinutes,
  settingsModifiedAt

## 需要实现的 API 端点

### GET /ping
- 返回：{"status": "ok"}

### Todo 接口

#### GET /todo/list
- 查询参数：date=yyyy-MM-dd（可选，不传则返回今日），type=daily|routineOnce|workOnce（可选）
- 返回该日期的任务列表（包含当天有效的 daily 模板 + 当天的 workOnce/routineOnce）
- 每个任务包含：id, title, emoji, type, isCompleted(考虑DailyCompletionLog), 
  note, reminderTime, subtasks(含modifiedAt), created/completed/scheduled/start/due/deleted日期,
  recurrence, modifiedAt

#### GET /todo/day
- 查询参数：date=yyyy-MM-dd（可选，不传则返回今日）
- 返回：{"date": "yyyy-MM-dd", "score": int, "total": int, "completed": int, "tasks": [...]}

#### POST /todo/add
- 请求体：{"title": string, "type": string, "emoji": string?, "note": string?,
  "dueDate": string?, "scheduledDate": string?, "reminderTime": string?,
  "subtasks": [{"title": string, "isCompleted": bool?}]?,
  "recurrence": {"type": "everyNDays"|"monthlyOnDay"|"yearlyOnMonthDay",
  "intervalDays": int?, "monthOfYear": int?, "dayOfMonth": int?}?}
- 返回：{"success": true, "id": string}

#### POST /todo/complete
- 请求体：{"id": string, "date": string?(yyyy-MM-dd，daily任务需要),
  "completed": bool, "subtaskId": string?, "createNextRecurrence": bool?}
- 返回：{"success": true}

#### POST /todo/score
- 请求体：{"date": string?(yyyy-MM-dd), "score": int}
- 返回：{"success": true, "date": string, "score": int}

#### GET /todo/stats
- 返回：{"today_total": int, "today_completed": int, "overdue": int}

### Finance 接口

#### GET /finance/summary
- 查询参数：month=yyyy-MM（可选，默认当月）
- 返回：{
    "month": "yyyy-MM",
    "defaultCurrency": string,
    "income": double,
    "expense": double, 
    "balance": double,
    "total_assets": double,
    "accounts": [ {id, name, type, bankOrApp, currency, balance, convertedBalance, defaultCurrency, fee waiver fields, modifiedAt} ],
    "category_totals": [ {categoryId, name, type, amount, count, currency} ],
    "top_expense_categories": [ {name, amount, count} ]
  }
  收入、支出、结余、分类和总资产使用 FinanceData.defaultCurrency 与历史 rateSnapshotId 折算。

#### GET /finance/accounts
- 查询参数：type=fund|credit|recharge|financial（可选）
- 返回账户列表，必须省略 securityCode、cardNumber、expiryDate 等敏感字段。

#### GET /finance/categories
- 查询参数：type=expense|income|transfer（可选）
- 返回分类列表，包含 icon JSON。

#### GET /finance/transactions
- 查询参数：limit=20（默认）, offset=0, type=expense|income|transfer（可选）,
  month=yyyy-MM（可选）, start/startDate, end/endDate, accountId, categoryId
- 返回最近的交易记录列表，包含 account/category display names、transfer fields、
  rateSnapshotId、subscriptionId、modifiedAt

#### POST /finance/add_transaction
- 请求体：{
    "type": "expense"|"income"|"transfer",
    "amount": number,
    "currency": string?,（默认源账户币种）
    "accountId": string,
    "toAccountId": string?,（转账用）
    "toAmount": number?,（跨币种转账用）
    "toCurrency": string?,（默认目标账户币种）
    "categoryId": string?,
    "note": string?,
    "date": string?（ISO8601，默认now）
  }
- 校验 account/category id，category type 必须与交易类型一致；保存当前 rateSnapshotId。
- 返回：{"success": true, "id": string, "transaction": {...}}

#### GET /finance/subscriptions
- 查询参数：includeInactive=true（可选）
- 返回订阅、账户/分类名称、周期、试用、取消信息、备注、modifiedAt 和下次扣款日期

### Weight 接口

#### GET /weight/list
- 查询参数：limit=30（默认）
- 返回最近体重记录：[ {id, weight, bodyFat, bustCm, waistCm, hipCm,
  effectiveMeasurements, date, datetime, notes, modifiedAt} ]

#### POST /weight/add
- 请求体：{"weight": number, "bodyFat": number?, "bustCm": number?,
  "waistCm": number?, "hipCm": number?, "notes": string?,
  "date": string?（ISO8601，默认now）}
- 返回：{"success": true, "id": string, "record": {...}}

#### GET /weight/stats
- 返回：{"latest": double?, "avg_7d": double?, "avg_30d": double?,
  "trend": "up"|"down"|"stable"|"unknown", "height": double?, "bmi": double?,
  "waistHipRatio": double?, "bodyFat": double?, "latestRecord": {...}?,
  "effectiveMeasurements": {...}?}

## 实现要点
1. 统一返回 Content-Type: application/json
2. 错误时返回 {"error": "描述"} + 合适的 HTTP 状态码
3. 添加 CORS 中间件（Access-Control-Allow-Origin: *，Allow-Headers 包含 Authorization）
4. finance/summary 中账户余额需要从 Transaction 记录动态计算；forcedBalance 字段是迁移兼容哨兵，不再作为实时余额基准
5. Todo 的 daily 任务需要考虑 startDate/deletedDate 过滤有效模板
6. 所有存储读取方式参考项目中已有的 Storage service 模式（读写 JSON 文件）
7. 当配置了 username + password，所有非 OPTIONS 请求（包括 localhost）都必须校验 Basic Auth

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
