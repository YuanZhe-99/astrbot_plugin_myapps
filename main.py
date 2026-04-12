"""
AstrBot Plugin: astrbot_plugin_myapps
集成 MyAnime (port 7788)、MyDevice (port 7789)、MyDay (port 7790)
支持 LLM Function Calling 自然语言交互 + 传统指令
"""
import aiohttp
from astrbot.api import star, llm_tool
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.core import logger

# ── 各 App 的本地 API 地址 ──
MYANIME_BASE  = "http://localhost:7788"
MYDEVICE_BASE = "http://localhost:7789"
MYDAY_BASE    = "http://localhost:7790"

_TIMEOUT = aiohttp.ClientTimeout(total=12)


# ════════════════════════════════════════════
#  HTTP 工具函数
# ════════════════════════════════════════════

async def _get(base: str, path: str):
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as s:
            async with s.get(f"{base}{path}") as r:
                return await r.json() if r.status == 200 else None
    except Exception as e:
        logger.error(f"[MyApps] GET {base}{path}: {e}")
        return None


async def _post(base: str, path: str, data: dict):
    try:
        async with aiohttp.ClientSession(timeout=_TIMEOUT) as s:
            async with s.post(f"{base}{path}", json=data) as r:
                return await r.json() if r.status == 200 else None
    except Exception as e:
        logger.error(f"[MyApps] POST {base}{path}: {e}")
        return None


async def _check(base: str, name: str) -> bool:
    r = await _get(base, "/ping")
    if not (r and r.get("status") == "ok"):
        logger.warning(f"[MyApps] {name} 客户端未响应 ({base})")
        return False
    return True


def _dow(day) -> str:
    return ({1:"周一",2:"周二",3:"周三",4:"周四",5:"周五",6:"周六",7:"周日"}.get(day,"")) if day else ""


# ════════════════════════════════════════════
#  插件主类
# ════════════════════════════════════════════

class Main(star.Star):
    def __init__(self, context: star.Context) -> None:
        self.context = context

    # ────────────────────────────────────────
    #  MyAnime — 番剧管理
    # ────────────────────────────────────────

    @llm_tool(name="anime_add")
    async def anime_add(self, event: AstrMessageEvent, title: str):
        """搜索并将一部番剧添加到 MyAnime 追番列表。当用户说想追/添加/记录某部动漫或番剧时调用。

        Args:
            title(string): 番剧名称，中文或日文均可
        """
        if not await _check(MYANIME_BASE, "MyAnime"):
            return "MyAnime 客户端未运行，请先启动。"
        results = await _post(MYANIME_BASE, "/anime/search", {"query": title})
        if not results:
            return f"未找到「{title}」，请检查名称是否正确。"
        best = results[0]
        t = best.get("title") or best.get("titleJa") or title
        r = await _post(MYANIME_BASE, "/anime/add", {
            "title": best.get("title"),
            "titleJa": best.get("titleJa"),
            "episodes": best.get("episodes"),
            "firstAirDate": (best.get("firstAirDate") or "")[:10] or None,
            "airDayOfWeek": best.get("airDayOfWeek"),
            "airTime": best.get("airTime"),
            "sourceUrl": best.get("sourceUrl"),
        })
        if r and r.get("success"):
            ep = best.get("episodes")
            dow = _dow(best.get("airDayOfWeek"))
            airt = best.get("airTime") or ""
            msg = f"「{t}」已添加到 MyAnime！"
            if ep: msg += f" 共{ep}集。"
            if dow: msg += f" 播出：{dow} {airt}。"
            return msg
        return f"添加「{t}」失败，请稍后再试。"

    @llm_tool(name="anime_list")
    async def anime_list(self, event: AstrMessageEvent):
        """获取 MyAnime 中所有追番列表。当用户询问在追什么番、追番列表时调用。

        Args:
        """
        if not await _check(MYANIME_BASE, "MyAnime"):
            return "MyAnime 客户端未运行。"
        data = await _get(MYANIME_BASE, "/anime/list")
        if not data:
            return "追番列表为空。"
        lines = [f"共追了 {len(data)} 部番剧："]
        for a in data:
            ep = a.get("totalEpisodes")
            nxt = a.get("nextUnwatchedEpisode")
            status = "✅已完结" if a.get("isCompleted") else (f"▶第{nxt}集待看" if nxt else "▶进行中")
            lines.append(f"· {a.get('title','?')}（{ep or '?'}集） {status}")
        return "\n".join(lines)

    @llm_tool(name="anime_unwatched")
    async def anime_unwatched(self, event: AstrMessageEvent):
        """查询 MyAnime 中还没看完/有未看集数的番剧。当用户问哪些番没看完、待看番剧时调用。

        Args:
        """
        if not await _check(MYANIME_BASE, "MyAnime"):
            return "MyAnime 客户端未运行。"
        data = await _get(MYANIME_BASE, "/anime/unwatched")
        if not data:
            return "🎉 所有番剧都看完了！"
        lines = [f"有 {len(data)} 部番剧待看："]
        for a in data:
            nxt = a.get("nextUnwatchedEpisode")
            total = a.get("totalEpisodes")
            dow = _dow(a.get("airDayOfWeek"))
            airt = a.get("airTime") or ""
            bc = f"（{dow} {airt}播）".strip("（ ）") if dow else ""
            lines.append(f"· {a.get('title','?')} — 待看第{nxt}/{total or '?'}集 {bc}")
        return "\n".join(lines)

    @llm_tool(name="anime_history")
    async def anime_history(self, event: AstrMessageEvent):
        """查询 MyAnime 的观看历史和追番进度统计。当用户问看了哪些番、追番历史时调用。

        Args:
        """
        if not await _check(MYANIME_BASE, "MyAnime"):
            return "MyAnime 客户端未运行。"
        data = await _get(MYANIME_BASE, "/anime/history")
        if not data:
            return "还没有观看历史。"
        done = [a for a in data if a.get("isCompleted")]
        ing = [a for a in data if not a.get("isCompleted") and a.get("watchedEpisodes", 0) > 0]
        parts = []
        if done:
            parts.append(f"✅ 已完结 {len(done)} 部：" + "、".join(a.get("title","?") for a in done))
        if ing:
            rows = [f"{a.get('title','?')}（{a.get('watchedEpisodes',0)}/{a.get('totalEpisodes','?')}集）" for a in ing]
            parts.append(f"▶ 进行中 {len(ing)} 部：" + "、".join(rows))
        ns = len(data) - len(done) - len(ing)
        if ns > 0:
            parts.append(f"⏸️ 未开始 {ns} 部。")
        return "\n".join(parts) if parts else "暂无记录。"

    # ────────────────────────────────────────
    #  MyDevice — 设备管理
    # ────────────────────────────────────────

    @llm_tool(name="device_list")
    async def device_list(self, event: AstrMessageEvent, category: str):
        """获取 MyDevice 中的设备列表。当用户问有哪些设备、设备清单、某类设备时调用。

        Args:
            category(string): 设备类别，可选值：all/desktop/laptop/phone/tablet/headphone/watch/router/gameConsole/vps/devBoard/other，不筛选时传 all
        """
        if not await _check(MYDEVICE_BASE, "MyDevice"):
            return "MyDevice 客户端未运行，请先启动。"
        path = "/device/list" if category in ("all", "") else f"/device/list?category={category}"
        data = await _get(MYDEVICE_BASE, path)
        if data is None:
            return "获取设备列表失败。"
        if not data:
            return f"没有找到{'任何' if category in ('all','') else category + '类别的'}设备。"
        lines = [f"共找到 {len(data)} 台设备："]
        for d in data:
            brand = d.get("brand") or ""
            model = d.get("model") or ""
            spec = f"（{brand} {model}）".strip("（ ）") if (brand or model) else ""
            os_ = d.get("os") or ""
            ram = d.get("ram") or ""
            cpu_m = (d.get("cpu") or {}).get("model") or ""
            details = " | ".join(filter(None, [cpu_m, ram, os_]))
            lines.append(f"· [{d.get('category','?')}] {d.get('name','?')}{spec}")
            if details:
                lines.append(f"   {details}")
        return "\n".join(lines)

    @llm_tool(name="device_search")
    async def device_search(self, event: AstrMessageEvent, keyword: str):
        """在 MyDevice 中搜索特定设备。当用户问某台具体设备的信息、规格、配置时调用。

        Args:
            keyword(string): 搜索关键词，例如设备名称、品牌、型号
        """
        if not await _check(MYDEVICE_BASE, "MyDevice"):
            return "MyDevice 客户端未运行。"
        data = await _get(MYDEVICE_BASE, f"/device/search?q={keyword}")
        if not data:
            return f"没有找到包含「{keyword}」的设备。"
        lines = [f"找到 {len(data)} 台匹配设备："]
        for d in data:
            cpu = d.get("cpu") or {}
            gpu = d.get("gpu") or {}
            storage_list = d.get("storage") or []
            storage_str = "、".join(s.get("capacity","?") for s in storage_list) if storage_list else ""
            lines.append(f"\n📱 {d.get('name','?')} [{d.get('category','?')}]")
            if d.get("brand"):  lines.append(f"   品牌：{d['brand']}")
            if d.get("model"):  lines.append(f"   型号：{d['model']}")
            if cpu.get("model"): lines.append(f"   CPU：{cpu['model']}")
            if gpu.get("model"): lines.append(f"   GPU：{gpu['model']}")
            if d.get("ram"):    lines.append(f"   内存：{d['ram']}")
            if storage_str:     lines.append(f"   存储：{storage_str}")
            if d.get("os"):     lines.append(f"   系统：{d['os']}")
            if d.get("purchaseDate"): lines.append(f"   购入：{d['purchaseDate'][:10]}")
        return "\n".join(lines)

    @llm_tool(name="device_add")
    async def device_add(self, event: AstrMessageEvent, name: str, category: str, brand: str, model: str, os: str, notes: str):
        """向 MyDevice 添加一台新设备。当用户说要记录/添加一台设备时调用。

        Args:
            name(string): 设备名称，例如"我的 MacBook Pro"
            category(string): 设备类别：desktop/laptop/phone/tablet/headphone/watch/router/gameConsole/vps/devBoard/other
            brand(string): 品牌，如 Apple/Samsung/Dell，不知道传空字符串
            model(string): 型号，如 MacBook Pro 14，不知道传空字符串
            os(string): 操作系统，如 macOS 15，不知道传空字符串
            notes(string): 备注，没有传空字符串
        """
        if not await _check(MYDEVICE_BASE, "MyDevice"):
            return "MyDevice 客户端未运行。"
        payload = {
            "name": name,
            "category": category,
            "brand": brand or None,
            "model": model or None,
            "os": os or None,
            "notes": notes or None,
        }
        r = await _post(MYDEVICE_BASE, "/device/add", payload)
        if r and r.get("success"):
            return f"已成功添加设备「{name}」（{category}）到 MyDevice！"
        return f"添加设备「{name}」失败，请稍后再试。"

    @llm_tool(name="device_stats")
    async def device_stats(self, event: AstrMessageEvent):
        """获取 MyDevice 的设备统计摘要。当用户问一共有多少设备、各类设备数量时调用。

        Args:
        """
        if not await _check(MYDEVICE_BASE, "MyDevice"):
            return "MyDevice 客户端未运行。"
        data = await _get(MYDEVICE_BASE, "/device/stats")
        if not data:
            return "获取设备统计失败。"
        total = data.get("total", 0)
        by_cat = data.get("byCategory", {})
        lines = [f"📊 设备统计（共 {total} 台）"]
        cat_names = {
            "desktop":"台式机","laptop":"笔记本","phone":"手机","tablet":"平板",
            "headphone":"耳机","watch":"手表","router":"路由器",
            "gameConsole":"游戏机","vps":"VPS","devBoard":"开发板","other":"其他"
        }
        for k, v in by_cat.items():
            if v > 0:
                lines.append(f"  {cat_names.get(k, k)}：{v} 台")
        recent = data.get("recentlyAdded", [])
        if recent:
            lines.append("最近添加：" + "、".join(d.get("name","?") for d in recent))
        return "\n".join(lines)

    # ────────────────────────────────────────
    #  MyDay — 日程/财务/体重
    # ────────────────────────────────────────

    @llm_tool(name="todo_today")
    async def todo_today(self, event: AstrMessageEvent, date: str):
        """获取 MyDay 中某天的待办任务列表。当用户问今天/某天有什么待办、任���、日程时调用。

        Args:
            date(string): 日期，格式 yyyy-MM-dd，查询今天时传今天的日期
        """
        if not await _check(MYDAY_BASE, "MyDay"):
            return "MyDay 客户端未运行，请先启动。"
        path = f"/todo/list?date={date}" if date else "/todo/list"
        data = await _get(MYDAY_BASE, path)
        if data is None:
            return "获取待办列表失败。"
        if not data:
            return f"{date or '今天'} 没有待办任务。"
        done = [t for t in data if t.get("isCompleted")]
        todo = [t for t in data if not t.get("isCompleted")]
        lines = [f"📋 {date or '今天'}的任务（{len(done)}/{len(data)} 已完成）"]
        if todo:
            lines.append("待完成：")
            for t in todo:
                emoji = t.get("emoji") or "○"
                due = f" 截止{t['dueDate'][:10]}" if t.get("dueDate") else ""
                lines.append(f"  {emoji} {t.get('title','?')}{due}")
        if done:
            lines.append("已完成：")
            for t in done:
                emoji = t.get("emoji") or "✓"
                lines.append(f"  {emoji} ~~{t.get('title','?')}~~")
        return "\n".join(lines)

    @llm_tool(name="todo_add")
    async def todo_add(self, event: AstrMessageEvent, title: str, task_type: str, due_date: str):
        """向 MyDay 添加一条待办任务。当用户说要添加任务、提醒、待办事项时调用。

        Args:
            title(string): 任务标题
            task_type(string): 任务类型：daily（每日循环）/ routineOnce（一次性例行）/ workOnce（一次性工作）
            due_date(string): 截止日期，格式 yyyy-MM-dd，没有则传空字符串
        """
        if not await _check(MYDAY_BASE, "MyDay"):
            return "MyDay 客户端未运行。"
        payload = {
            "title": title,
            "type": task_type or "workOnce",
            "dueDate": due_date or None,
        }
        r = await _post(MYDAY_BASE, "/todo/add", payload)
        if r and r.get("success"):
            return f"已添加待办任务「{title}」！"
        return f"添加任务「{title}」失败。"

    @llm_tool(name="todo_stats")
    async def todo_stats(self, event: AstrMessageEvent):
        """获取 MyDay 的今日任务完成统计。当用户问今天任务完成情况、完成率时调用。

        Args:
        """
        if not await _check(MYDAY_BASE, "MyDay"):
            return "MyDay 客户端未运行。"
        data = await _get(MYDAY_BASE, "/todo/stats")
        if not data:
            return "获取统计失败。"
        total = data.get("today_total", 0)
        done = data.get("today_completed", 0)
        overdue = data.get("overdue", 0)
        rate = int(done / total * 100) if total else 0
        msg = f"📊 今日任务：{done}/{total} 已完成（{rate}%）"
        if overdue:
            msg += f"，有 {overdue} 项已逾期"
        return msg

    @llm_tool(name="finance_summary")
    async def finance_summary(self, event: AstrMessageEvent, month: str):
        """获取 MyDay 的财务收支摘要。当用户问本月/某月收支、花了多少钱、余额时调用。

        Args:
            month(string): 月份，格式 yyyy-MM，查询当月时传当月，如 2026-04
        """
        if not await _check(MYDAY_BASE, "MyDay"):
            return "MyDay 客户端未运行。"
        path = f"/finance/summary?month={month}" if month else "/finance/summary"
        data = await _get(MYDAY_BASE, path)
        if not data:
            return "获取财务摘要失败。"
        income = data.get("income", 0)
        expense = data.get("expense", 0)
        balance = data.get("balance", 0)
        lines = [
            f"💰 {month or '本月'}财务摘要",
            f"  收入：{income:,.2f}",
            f"  支出：{expense:,.2f}",
            f"  结余：{balance:,.2f}",
        ]
        top = data.get("top_expense_categories", [])
        if top:
            lines.append("支出前三：" + "、".join(f"{c['name']}({c['amount']:.0f})" for c in top[:3]))
        accounts = data.get("accounts", [])
        if accounts:
            acc_str = "、".join(f"{a['name']}:{a.get('balance',0):.0f}{a.get('currency','')}" for a in accounts[:3])
            lines.append(f"账户：{acc_str}")
        return "\n".join(lines)

    @llm_tool(name="finance_add_transaction")
    async def finance_add_transaction(self, event: AstrMessageEvent, ttype: str, amount: str, note: str, account_name: str):
        """向 MyDay 记录一笔收入或支出。当用户说花了多少钱、收了多少钱、记一笔账时调用。

        Args:
            ttype(string): 交易类型：expense（支出）/ income（收入）/ transfer（转账）
            amount(string): 金额，如 "88.5"
            note(string): 备注，如"午饭"、"工资"，没有传空字符串
            account_name(string): 账户名称关键词，没有传空字符串，将使用默认账户
        """
        if not await _check(MYDAY_BASE, "MyDay"):
            return "MyDay 客户端未运行。"
        # 先获取账户列表匹配 accountId
        summary = await _get(MYDAY_BASE, "/finance/summary")
        accounts = (summary or {}).get("accounts", [])
        account_id = None
        if account_name and accounts:
            for a in accounts:
                if account_name.lower() in a.get("name","").lower():
                    account_id = a.get("id")
                    break
        if not account_id and accounts:
            account_id = accounts[0].get("id")
        if not account_id:
            return "未找到账户，请先在 MyDay 中创建账户。"
        try:
            amt = float(amount)
        except Exception:
            return f"金额格式错误：{amount}"
        r = await _post(MYDAY_BASE, "/finance/add_transaction", {
            "type": ttype,
            "amount": amt,
            "accountId": account_id,
            "note": note or "",
        })
        if r and r.get("success"):
            type_cn = {"expense":"支出","income":"收入","transfer":"转账"}.get(ttype, ttype)
            return f"已记录{type_cn}：{amt:.2f} 元，备注「{note or '无'}」。"
        return "记账失败，请稍后再试。"

    @llm_tool(name="finance_subscriptions")
    async def finance_subscriptions(self, event: AstrMessageEvent):
        """查询 MyDay 中的订阅服务列表和下次扣款时间。当用户问有哪些订阅、下次续费时间时调用。

        Args:
        """
        if not await _check(MYDAY_BASE, "MyDay"):
            return "MyDay 客户端未运行。"
        data = await _get(MYDAY_BASE, "/finance/subscriptions")
        if not data:
            return "没有活跃的订阅服务。"
        lines = [f"📦 活跃订阅（共 {len(data)} 项）"]
        for s in data:
            nxt = (s.get("nextBillingDate") or "")[:10]
            cyc = "月付" if s.get("billingCycleType") == "monthly" else "年付"
            lines.append(f"· {s.get('name','?')} — {s.get('amount',0):.2f}{s.get('currency','')} {cyc}，下次：{nxt or '未知'}")
        return "\n".join(lines)

    @llm_tool(name="weight_log")
    async def weight_log(self, event: AstrMessageEvent, weight: str):
        """向 MyDay 记录今天的体重数据。当用户说今天体重是多少、记录体重时调用。

        Args:
            weight(string): 体重数值，单位 kg，如 "65.5"
        """
        if not await _check(MYDAY_BASE, "MyDay"):
            return "MyDay 客户端未运行。"
        try:
            w = float(weight)
        except Exception:
            return f"体重格式错误：{weight}"
        r = await _post(MYDAY_BASE, "/weight/add", {"weight": w})
        if r and r.get("success"):
            return f"已记录体重 {w} kg！"
        return "记录体重失败。"

    @llm_tool(name="weight_stats")
    async def weight_stats(self, event: AstrMessageEvent):
        """查询 MyDay 的体重统计和趋势。当用户问体重变化、近期体重、体重趋势时调用。

        Args:
        """
        if not await _check(MYDAY_BASE, "MyDay"):
            return "MyDay 客户端未运行。"
        data = await _get(MYDAY_BASE, "/weight/stats")
        if not data:
            return "获取体重统计失败。"
        latest = data.get("latest")
        avg7 = data.get("avg_7d")
        avg30 = data.get("avg_30d")
        trend = {"up":"📈上升","down":"📉下降","stable":"➡️稳定","unknown":"未知"}.get(data.get("trend","unknown"),"未知")
        lines = ["⚖️ 体重统计"]
        if latest: lines.append(f"  最新：{latest:.1f} kg")
        if avg7:   lines.append(f"  7日均：{avg7:.1f} kg")
        if avg30:  lines.append(f"  30日均：{avg30:.1f} kg")
        lines.append(f"  趋势：{trend}")
        return "\n".join(lines)

    # ────────────────────────────────────────
    #  传统指令入口（无需 LLM）
    # ───────────────────���────────────────────

    @filter.command("myapps")
    async def cmd_myapps(self, event: AstrMessageEvent):
        """显示所有支持的 App 功能列表"""
        lines = [
            "🗂️  MyApps 集成插件\n",
            "📺 MyAnime（番剧）",
            "  自然语言：「帮我添加葬送的芙莉莲」「我有什么番没看」",
            "",
            "💻 MyDevice（设备）",
            "  自然语言：「我有哪些笔记本」「搜索我的 MacBook 配置」「添加一台设备」",
            "",
            "📅 MyDay（日程/财务/体重）",
            "  自然语言：「今天有什么待办」「本月花了多少钱」「记录今天体重65kg」",
            "",
            "💡 直接用自然语言跟我说就好！",
            "   （需要使用支持 Function Calling 的 LLM）",
        ]
        yield event.plain_result("\n".join(lines))