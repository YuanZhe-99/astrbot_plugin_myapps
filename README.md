# astrbot_plugin_myapps

集成 **MyAnime**、**MyDevice**、**MyDay** 三个 Flutter 个人管理 App 的 AstrBot 插件，支持自然语言（LLM Function Calling）和传统指令双模式。

## 功能概览

| App | 功能 | 示例自然语言 |
|-----|------|-------------|
| 📺 **MyAnime** | 添加番剧、查看追番列表、未看番剧、观看历史、评分排行 | 「帮我追葬送的芙莉莲」「我有什么番没看完」「我的番剧评分排行」 |
| 💻 **MyDevice** | 查询设备列表、搜索设备规格、添加设备、统计 | 「我有哪些笔记本」「我的 MacBook 配置是什么」 |
| 📅 **MyDay** | 查看/添加/完成待办、日评分、收支摘要、账户/分类、记账/转账、订阅、体重/体脂/三围 | 「今天有什么待办」「今天评分3分」「本月花了多少」「记录今天体重65.5kg体脂21%」 |

---

## 架构说明

```
用户 IM 消息
    ↓
AstrBot (Python 插件)
    ↓  HTTP (localhost)
┌───────────┬────────────┬──────────┐
│ MyAnime   │ MyDevice   │ MyDay    │
│ :7788     │ :7789      │ :7790    │
└───────────┴────────────┴──────────┘
    ↓              ↓           ↓
  anime_data   device_data  task/finance/weight
  .json        .json        .json (各自存储)
```

各 App 客户端需在**桌面端运行时**内嵌一个本地 HTTP Server（仅 localhost，不对外暴露）。

---

## 安装

### 1. 安装插件

将 `astrbot_plugin_myapps` 目录放到 AstrBot 的 `data/plugins/` 目录下，重启 AstrBot。

### 2. 各 App 添加本地 HTTP Server

> **这是接入的关键步骤。** 每个 Flutter App 需要按照对应的开发 Prompt 添加 `LocalApiServer`。

| App | 端口 | 参考 Prompt |
|-----|------|-------------|
| MyAnime | 7788 | 见 `MyAnime_API_Server_Prompt.md` |
| MyDevice | 7789 | 见 `MyDevice_API_Server_Prompt.md` |
| MyDay | 7790 | 见 `MyDay_API_Server_Prompt.md` |

**Flutter 侧改动摘要（每个 App 一致）：**

```yaml
# pubspec.yaml 新增
dependencies:
  shelf: ^1.4.0
  shelf_router: ^1.1.0
```

```dart
// lib/main.dart 新增（仅桌面端）
import 'dart:io';
import 'package:my_app/shared/services/local_api_server.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  if (Platform.isWindows || Platform.isMacOS || Platform.isLinux) {
    await LocalApiServer.start();
  }
  runApp(const MyApp());
}
```

### 3. 确保 LLM 支持 Function Calling

在 AstrBot 管理面板确认使用的模型支持 Function Calling：

| 模型 | 支持 |
|------|------|
| GPT-4o / GPT-4 Turbo | ✅ |
| Claude 3.5+ | ✅ |
| Gemini 1.5+ | ✅ |
| DeepSeek-V3 | ✅ |
| Qwen3 系列 | ✅ |
| DeepSeek-R1（思考模型） | ❌ |

---

## 使用方法

### 自然语言（推荐）

直接对 Bot 说自然语言，LLM 会自动选择调用哪个工具：

```
用户: 帮我把"蜡笔小新"加进追番
Bot:  ✅「蜡笔小新」已添加到 MyAnime！共 1000+ 集。

用户: 我最近有哪些番没看完？
Bot:  有 3 部番剧待看：
      · 葬送的芙莉莲 — 待看第8/28集（周五 23:00播）
      · ...

用户: 我的番剧评分排行？
Bot:  🏆 MyAnime评分排行（全部，全部类型，综合高到低，共12部）
      1. 葬送的芙莉莲 — 9.5分（✅已看完 | 28/28集 | 评分9.5）

用户: 我的电脑设备有哪些？
Bot:  找到 2 台 laptop 设备：
      · MacBook Pro 14（Apple M3 Pro）
      · ThinkPad X1 Carbon（Intel Core i7）

用户: 本月财务怎么样？
Bot:  💰 2026-04 财务摘要
      收入：8,000.00
      支出：3,240.50
      结余：4,759.50
      支出前三：餐饮(890)、购物(720)、交通(380)

用户: 今天体重65.2公斤
Bot:  已记录体重 65.2 kg！

用户: 今天评分4分
Bot:  已设置 2026-04-01 的日评分：4。

用户: 从现金转100到招商银行
Bot:  已记录转账：100.00CNY -> 招商银行，备注「无」。
```

### 传统指令

```
/myapps   — 显示所有功能说明
```

---

## API 端口汇总

| App | 端口 | 主要端点 |
|-----|------|---------|
| MyAnime | 7788 | `/ping` `/anime/search` `/anime/add` `/anime/list` `/anime/unwatched` `/anime/history` `/anime/ranking` |
| MyDevice | 7789 | `/ping` `/device/list` `/device/search` `/device/add` `/device/stats` |
| MyDay | 7790 | `/ping` `/todo/list` `/todo/day` `/todo/add` `/todo/complete` `/todo/score` `/todo/stats` `/finance/summary` `/finance/accounts` `/finance/categories` `/finance/transactions` `/finance/add_transaction` `/finance/subscriptions` `/weight/list` `/weight/add` `/weight/stats` |

---

## 注意事项

1. **App 必须运行**：插件通过 HTTP 调用本地 App，对应客户端必须处于运行状态
2. **隐私安全**：默认 API 绑定 localhost；如 App 侧配置了用户名密码，插件会通过 Basic Auth 访问
3. **端口冲突**：如果端口已被占用，可修改 `main.py` 顶部的 `*_BASE` 常量，并同步修改 Flutter 端的端口号
4. **货币计算**：MyDay `0.8.0+` 的 `finance/summary` 会返回默认币种折算后的收支、分类和总资产，账户仍保留原币种余额

---

## 依赖

- Python `aiohttp`（AstrBot 已内置）
- AstrBot >= 4.0
- 各 Flutter App 添加 `shelf` + `shelf_router` 依赖后重新构建

---

## License

GPL-3.0
