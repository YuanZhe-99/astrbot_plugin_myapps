## 任务
为 Flutter 桌面应用 MyDay（YuanZhe-99/MyDay）添加一个本地 HTTP API Server，
供外部程序（如 AstrBot 插件）调用，实现 Todo、财务、体重数据的查询与管理。

## 技术要求
- 使用 `shelf` + `shelf_router` 包（在 pubspec.yaml 中添加依赖）
- 仅在 Windows/macOS/Linux 桌面端启动，端口：7790，支持设置界面修改端口
- 增加 App 后台运行能力和自启动能力，参考 MyAnime 的实现
- 默认仅绑定 localhost（InternetAddress.loopbackIPv4）
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
3. 添加 CORS 中间件（Access-Control-Allow-Origin: *）
4. finance/summary 中账户余额需要从 Transaction 记录动态计算
   （考虑 forcedBalance/forcedBalanceDate 作为基准点）
5. Todo 的 daily 任务需要考虑 startDate/deletedDate 过滤有效模板
6. 所有存储读取方式参考项目中已有的 Storage service 模式（读写 JSON 文件）