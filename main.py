"""
AstrBot Plugin: astrbot_plugin_myapps
集成 MyAnime、MyDevice、MyDay 三个 Flutter 个人管理 App
支持 LLM Function Calling 自然语言交互 + 传统指令
所有设定通过 AstrBot WebUI 配置界面管理
"""
import base64
from datetime import datetime, timezone
from urllib.parse import quote
import aiohttp
from astrbot.api import star, llm_tool, AstrBotConfig
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.core import logger


def _make_auth_header(username: str, password: str) -> dict:
    if username and password:
        cred = base64.b64encode(f"{username}:{password}".encode()).decode()
        return {"Authorization": f"Basic {cred}"}
    return {}


async def _get(base: str, path: str, *, auth: dict | None = None):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{base}{path}", headers=auth or {}) as r:
                return await r.json() if r.status == 200 else None
    except Exception as e:
        logger.error(f"[MyApps] GET {base}{path}: {e}")
        return None


async def _post(base: str, path: str, data: dict, *, auth: dict | None = None):
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(f"{base}{path}", json=data, headers=auth or {}) as r:
                return await r.json() if r.status == 200 else None
    except Exception as e:
        logger.error(f"[MyApps] POST {base}{path}: {e}")
        return None


async def _check(base: str, name: str, *, auth: dict | None = None) -> bool:
    r = await _get(base, "/ping", auth=auth)
    if not (r and r.get("status") == "ok"):
        logger.warning(f"[MyApps] {name} 客户端未响应 ({base})")
        return False
    return True


def _dow(day) -> str:
    return ({1:"周一",2:"周二",3:"周三",4:"周四",5:"周五",6:"周六",7:"周日"}.get(day,"")) if day else ""


def _short_text(text, limit: int = 90) -> str:
    if not text:
        return ""
    value = str(text).replace("\n", " ").strip()
    return value if len(value) <= limit else value[:limit - 1] + "…"


def _format_money(value) -> str:
    if not isinstance(value, dict):
        return ""
    amount = value.get("amount")
    currency = value.get("currency") or ""
    converted = value.get("convertedAmount")
    default_currency = value.get("defaultCurrency") or ""
    try:
        amount_text = f"{float(amount):,.2f}{currency}" if amount is not None else ""
        if converted is not None and default_currency and default_currency != currency:
            return f"{amount_text}（{float(converted):,.2f}{default_currency}）"
        return amount_text
    except Exception:
        return str(amount) if amount is not None else ""


def _format_endpoint(endpoint: dict) -> str:
    label = endpoint.get("label") or ""
    protocol = endpoint.get("protocol") or ""
    port = endpoint.get("portText") or endpoint.get("port") or ""
    scope = endpoint.get("scope") or ""
    path = endpoint.get("path") or ""
    prefix = f"{label} " if label else ""
    target = f"{protocol}:{port}" if port else protocol
    suffix = " ".join(x for x in [scope, path] if x)
    return f"{prefix}{target} {suffix}".strip()


# ════════════════════════════════════════════
#  插件主类
# ════════════════════════════════════════════

class Main(star.Star):
    def __init__(self, context: star.Context, config: AstrBotConfig) -> None:
        self.context = context
        self.config = config

    def _check_sender(self, event: AstrMessageEvent) -> str | None:
        allowed = self.config.get("allowed_sender_ids", [])
        if not allowed:
            return None
        sender_id = event.get_sender_id()
        if sender_id not in allowed:
            return "⛔ 你没有权限使用此功能。"
        return None

    @property
    def _anime_base(self) -> str:
        return (self.config.get("myanime_base") or "http://localhost:7788").rstrip("/")

    @property
    def _anime_auth(self) -> dict:
        return _make_auth_header(self.config.get("myanime_username", ""), self.config.get("myanime_password", ""))

    @property
    def _anime_enabled(self) -> bool:
        return self.config.get("myanime_enabled", True)

    @property
    def _anime_readonly(self) -> bool:
        return self.config.get("myanime_readonly", False)

    @property
    def _device_base(self) -> str:
        return (self.config.get("mydevice_base") or "http://localhost:7789").rstrip("/")

    @property
    def _device_auth(self) -> dict:
        return _make_auth_header(self.config.get("mydevice_username", ""), self.config.get("mydevice_password", ""))

    @property
    def _device_enabled(self) -> bool:
        return self.config.get("mydevice_enabled", True)

    @property
    def _device_readonly(self) -> bool:
        return self.config.get("mydevice_readonly", False)

    @property
    def _day_base(self) -> str:
        return (self.config.get("myday_base") or "http://localhost:7790").rstrip("/")

    @property
    def _day_auth(self) -> dict:
        return _make_auth_header(self.config.get("myday_username", ""), self.config.get("myday_password", ""))

    @property
    def _day_enabled(self) -> bool:
        return self.config.get("myday_enabled", True)

    @property
    def _day_readonly(self) -> bool:
        return self.config.get("myday_readonly", False)

    @property
    def _day_todo_enabled(self) -> bool:
        return self._day_enabled and self.config.get("myday_todo_enabled", True)

    @property
    def _day_finance_enabled(self) -> bool:
        return self._day_enabled and self.config.get("myday_finance_enabled", True)

    @property
    def _day_weight_enabled(self) -> bool:
        return self._day_enabled and self.config.get("myday_weight_enabled", True)

    # ────────────────────────────────────────
    #  MyAnime — 番剧管理
    # ────────────────────────────────────────

    @llm_tool(name="anime_add")
    async def anime_add(self, event: AstrMessageEvent, title: str):
        """搜索并将一部番剧添加到 MyAnime 追番列表。当用户说想追/添加/记录某部动漫或番剧时调用。

        Args:
            title(string): 番剧名称，中文或日文均可
        """
        if (deny := self._check_sender(event)): return deny
        if not self._anime_enabled:
            return "MyAnime 功能已关闭。"
        if self._anime_readonly:
            return "MyAnime 处于只读模式，无法添加番剧。"
        if not await _check(self._anime_base, "MyAnime", auth=self._anime_auth):
            return "MyAnime 客户端未运行，请先启动。"
        results = await _post(self._anime_base, "/anime/search", {"query": title}, auth=self._anime_auth)
        if not results:
            return f"未找到「{title}」，请检查名称是否正确。"
        best = results[0]
        t = best.get("title") or best.get("titleJa") or title
        r = await _post(self._anime_base, "/anime/add", {
            "title": best.get("title"),
            "titleJa": best.get("titleJa"),
            "episodes": best.get("episodes"),
            "firstAirDate": (best.get("firstAirDate") or "")[:10] or None,
            "airDayOfWeek": best.get("airDayOfWeek"),
            "airTime": best.get("airTime"),
            "sourceUrl": best.get("sourceUrl"),
        }, auth=self._anime_auth)
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
    async def anime_list(self, event: AstrMessageEvent, season: str):
        """获取 MyAnime 中的追番列表。当用户询问在追什么番、追番列表时调用。

        Args:
            season(string): 季度筛选，可选值：current（当前季度，默认）/ 2026Q2这样的格式指定季度 / unassigned（未分配季度）/ all（全部，随机返40个）
        """
        if (deny := self._check_sender(event)): return deny
        if not self._anime_enabled:
            return "MyAnime 功能已关闭。"
        if not await _check(self._anime_base, "MyAnime", auth=self._anime_auth):
            return "MyAnime 客户端未运行。"
        s = (season or "current").strip()
        resp = await _get(self._anime_base, f"/anime/list?season={s}", auth=self._anime_auth)
        if not resp:
            return "追番列表为空。"
        total = resp.get("total", 0)
        counts = resp.get("counts", {})
        data = resp.get("data", [])
        if not data:
            return "追番列表为空。"
        lines = []
        # Summary line with counts
        parts = []
        if counts.get("completed"): parts.append(f"完结{counts['completed']}")
        if counts.get("inProgress"): parts.append(f"进行中{counts['inProgress']}")
        if counts.get("notStarted"): parts.append(f"未开始{counts['notStarted']}")
        if counts.get("abandoned"): parts.append(f"弃番{counts['abandoned']}")
        summary = f"共{total}部（{'、'.join(parts)}）"
        if len(data) < total:
            summary += f"，以下随机展示{len(data)}部"
        lines.append(summary + "：")
        for a in data:
            ep = a.get("totalEpisodes")
            nxt = a.get("nextUnwatchedEpisode")
            if a.get("isCompleted"):
                status = "✅已完结"
            elif nxt:
                air = a.get("nextEpisodeAirDate")
                if air and air > datetime.now(timezone.utc).isoformat():
                    status = f"▶第{nxt}集等待更新"
                else:
                    status = f"▶第{nxt}集待看"
            else:
                status = "🚫已弃番"
            lines.append(f"· {a.get('title','?')}（{ep or '?'}集） {status}")
        return "\n".join(lines)

    @llm_tool(name="anime_unwatched")
    async def anime_unwatched(self, event: AstrMessageEvent):
        """查询 MyAnime 中已更新但未观看的番剧集数。当用户问哪些番没看完、待看、最近有什么番没看时调用。只返回已经播出但未观看的剧集。

        Args:
        """
        if (deny := self._check_sender(event)): return deny
        if not self._anime_enabled:
            return "MyAnime 功能已关闭。"
        if not await _check(self._anime_base, "MyAnime", auth=self._anime_auth):
            return "MyAnime 客户端未运行。"
        data = await _get(self._anime_base, "/anime/unwatched", auth=self._anime_auth)
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
    async def anime_history(self, event: AstrMessageEvent, season: str):
        """查询 MyAnime 的观看历史和追番进度统计。当用户问看了哪些番、追番历史时调用。

        Args:
            season(string): 季度筛选，可选值：current（当前季度，默认）/ 2026Q2这样的格式指定季度 / unassigned（未分配季度）/ all（全部，随机返40个）
        """
        if (deny := self._check_sender(event)): return deny
        if not self._anime_enabled:
            return "MyAnime 功能已关闭。"
        if not await _check(self._anime_base, "MyAnime", auth=self._anime_auth):
            return "MyAnime 客户端未运行。"
        s = (season or "current").strip()
        resp = await _get(self._anime_base, f"/anime/history?season={s}", auth=self._anime_auth)
        if not resp:
            return "还没有观看历史。"
        total = resp.get("total", 0)
        counts = resp.get("counts", {})
        data = resp.get("data", [])
        if not data:
            return "还没有观看历史。"
        done = [a for a in data if a.get("isCompleted")]
        abandoned = [a for a in data if not a.get("isCompleted") and a.get("nextUnwatchedEpisode") is None]
        ing = [a for a in data if not a.get("isCompleted") and a.get("nextUnwatchedEpisode") is not None and a.get("watchedEpisodes", 0) > 0]
        ns = [a for a in data if not a.get("isCompleted") and a.get("nextUnwatchedEpisode") is not None and a.get("watchedEpisodes", 0) == 0]
        parts = []
        # Summary with full counts
        count_parts = []
        if counts.get("completed"): count_parts.append(f"完结{counts['completed']}")
        if counts.get("inProgress"): count_parts.append(f"进行中{counts['inProgress']}")
        if counts.get("notStarted"): count_parts.append(f"未开始{counts['notStarted']}")
        if counts.get("abandoned"): count_parts.append(f"弃番{counts['abandoned']}")
        header = f"共{total}部（{'、'.join(count_parts)}）"
        if len(data) < total:
            header += f"，以下随机展示{len(data)}部"
        parts.append(header)
        if done:
            parts.append(f"✅ 已完结 {len(done)} 部：" + "、".join(a.get("title","?") for a in done))
        if ing:
            rows = [f"{a.get('title','?')}（{a.get('watchedEpisodes',0)}/{a.get('totalEpisodes','?')}集）" for a in ing]
            parts.append(f"▶ 进行中 {len(ing)} 部：" + "、".join(rows))
        if ns:
            parts.append(f"⏸️ 未开始 {len(ns)} 部：" + "、".join(a.get("title","?") for a in ns))
        if abandoned:
            rows = [f"{a.get('title','?')}（{a.get('watchedEpisodes',0)}/{a.get('totalEpisodes','?')}集）" for a in abandoned]
            parts.append(f"🚫 已弃番 {len(abandoned)} 部：" + "、".join(rows))
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
        if (deny := self._check_sender(event)): return deny
        if not self._device_enabled:
            return "MyDevice 功能已关闭。"
        if not await _check(self._device_base, "MyDevice", auth=self._device_auth):
            return "MyDevice 客户端未运行，请先启动。"
        path = "/device/list" if category in ("all", "") else f"/device/list?category={category}"
        data = await _get(self._device_base, path, auth=self._device_auth)
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
            lifecycle = d.get("lifecycleStatus")
            lifecycle_text = "" if lifecycle in (None, "inService") else f" | {lifecycle}"
            location = d.get("locationName") or ""
            details = " | ".join(x for x in [cpu_m, ram, os_, location] if x)
            lines.append(f"· [{d.get('category','?')}] {d.get('name','?')}{spec}")
            if details:
                lines.append(f"   {details}{lifecycle_text}")
        return "\n".join(lines)

    @llm_tool(name="device_search")
    async def device_search(self, event: AstrMessageEvent, keyword: str):
        """在 MyDevice 中搜索特定设备。当用户问某台具体设备的信息、规格、配置时调用。

        Args:
            keyword(string): 搜索关键词，例如设备名称、品牌、型号
        """
        if (deny := self._check_sender(event)): return deny
        if not self._device_enabled:
            return "MyDevice 功能已关闭。"
        if not await _check(self._device_base, "MyDevice", auth=self._device_auth):
            return "MyDevice 客户端未运行。"
        data = await _get(self._device_base, f"/device/search?q={quote(keyword or '')}", auth=self._device_auth)
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
            if d.get("locationName"): lines.append(f"   位置：{d['locationName']}")
            lifecycle = d.get("lifecycleStatus")
            if lifecycle and lifecycle != "inService":
                lines.append(f"   状态：{lifecycle}")
            purchase_price = _format_money(d.get("purchasePrice"))
            sold_price = _format_money(d.get("soldPrice"))
            if purchase_price: lines.append(f"   购入价格：{purchase_price}")
            if sold_price:     lines.append(f"   售出价格：{sold_price}")
            recurring = d.get("recurringCosts") or []
            if recurring:
                lines.append(f"   周期费用：{len(recurring)} 项")
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
        if (deny := self._check_sender(event)): return deny
        if not self._device_enabled:
            return "MyDevice 功能已关闭。"
        if self._device_readonly:
            return "MyDevice 处于只读模式，无法添加设备。"
        if not await _check(self._device_base, "MyDevice", auth=self._device_auth):
            return "MyDevice 客户端未运行。"
        payload = {
            "name": name,
            "category": category,
            "brand": brand or None,
            "model": model or None,
            "os": os or None,
            "notes": notes or None,
        }
        r = await _post(self._device_base, "/device/add", payload, auth=self._device_auth)
        if r and r.get("success"):
            return f"已成功添加设备「{name}」（{category}）到 MyDevice！"
        return f"添加设备「{name}」失败，请稍后再试。"

    @llm_tool(name="device_stats")
    async def device_stats(self, event: AstrMessageEvent):
        """获取 MyDevice 的设备统计摘要。当用户问一共有多少设备、各类设备数量时调用。

        Args:
        """
        if (deny := self._check_sender(event)): return deny
        if not self._device_enabled:
            return "MyDevice 功能已关闭。"
        if not await _check(self._device_base, "MyDevice", auth=self._device_auth):
            return "MyDevice 客户端未运行。"
        data = await _get(self._device_base, "/device/stats", auth=self._device_auth)
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
        lifecycle = data.get("byLifecycle", {})
        lifecycle_parts = []
        if lifecycle.get("retired"): lifecycle_parts.append(f"退役{lifecycle['retired']}")
        if lifecycle.get("sold"): lifecycle_parts.append(f"售出{lifecycle['sold']}")
        if lifecycle_parts:
            lines.append("生命周期：" + "、".join(lifecycle_parts))
        services = data.get("services") or {}
        if services:
            lines.append(f"服务：{services.get('total',0)} 个，路由 {services.get('routes',0)} 条，端点 {services.get('endpoints',0)} 个")
        networks = data.get("networks") or {}
        if networks:
            lines.append(f"网络：{networks.get('total',0)} 个，分配 {networks.get('assignments',0)} 条")
        datasets = data.get("datasets") or {}
        if datasets:
            lines.append(f"数据集：{datasets.get('total',0)} 个，存储链接 {datasets.get('storageLinks',0)} 条")
        finance = data.get("finance") or {}
        if finance.get("devices"):
            total_cost = finance.get("totalCost")
            cost_text = f"，总成本 {float(total_cost):,.2f}" if isinstance(total_cost, (int, float)) else ""
            lines.append(f"财务记录：{finance.get('devices')} 台{cost_text}")
        return "\n".join(lines)

    @llm_tool(name="device_service_search")
    async def device_service_search(self, event: AstrMessageEvent, keyword: str):
        """查询 MyDevice 中手动记录的服务、端口和端点。当用户问某个服务在哪、端口是什么、有哪些服务时调用。

        Args:
            keyword(string): 服务名、端口、设备名、标签、网络名等关键词；查询全部服务时传空字符串
        """
        if (deny := self._check_sender(event)): return deny
        if not self._device_enabled:
            return "MyDevice 功能已关闭。"
        if not await _check(self._device_base, "MyDevice", auth=self._device_auth):
            return "MyDevice 客户端未运行。"
        path = f"/service/search?q={quote(keyword)}" if keyword else "/service/list"
        data = await _get(self._device_base, path, auth=self._device_auth)
        if data is None:
            return "获取服务列表失败。"
        if not data:
            return f"没有找到{'包含「' + keyword + '」的' if keyword else '任何'}服务。"
        lines = [f"找到 {len(data)} 个服务："]
        for s in data[:12]:
            icon = s.get("icon") or "🔧"
            device = s.get("deviceName") or s.get("deviceId") or "未知设备"
            kind = s.get("kind") or "custom"
            state = s.get("state") or "unknown"
            lines.append(f"· {icon} {s.get('name','?')}（{device}，{kind}/{state}）")
            endpoints = [_format_endpoint(e) for e in (s.get("endpoints") or [])]
            endpoints = [e for e in endpoints if e]
            if endpoints:
                lines.append("   端点：" + "、".join(endpoints[:4]))
            tags = s.get("tags") or []
            if tags:
                lines.append("   标签：" + "、".join(tags[:6]))
            if s.get("notes") and keyword and keyword.lower() in str(s.get("notes")).lower():
                lines.append(f"   备注：{_short_text(s.get('notes'))}")
        if len(data) > 12:
            lines.append(f"还有 {len(data) - 12} 个结果未显示。")
        return "\n".join(lines)

    @llm_tool(name="device_service_routes")
    async def device_service_routes(self, event: AstrMessageEvent):
        """查询 MyDevice 中手动记录的服务访问路径。当用户问公网访问、反代、隧道、FRP、域名路由时调用。

        Args:
        """
        if (deny := self._check_sender(event)): return deny
        if not self._device_enabled:
            return "MyDevice 功能已关闭。"
        if not await _check(self._device_base, "MyDevice", auth=self._device_auth):
            return "MyDevice 客户端未运行。"
        data = await _get(self._device_base, "/service/routes", auth=self._device_auth)
        if data is None:
            return "获取服务路由失败。"
        if not data:
            return "还没有记录服务访问路径。"
        lines = [f"服务访问路径（共 {len(data)} 条）："]
        for r in data[:12]:
            source = r.get("sourceServiceName") or r.get("sourceServiceId") or "未知服务"
            targets = r.get("publicTargets") or []
            target = r.get("finalUrl") or (targets[0] if targets else "")
            access = r.get("accessLevel") or "lan"
            hop_count = len(r.get("hops") or [])
            line = f"· {source} -> {target or '未填写目标'}（{access}"
            line += f"，{hop_count} hops" if hop_count else ""
            line += "）"
            lines.append(line)
            if len(targets) > 1:
                lines.append("   其他目标：" + "、".join(targets[1:5]))
            if r.get("notes"):
                lines.append(f"   备注：{_short_text(r.get('notes'))}")
        if len(data) > 12:
            lines.append(f"还有 {len(data) - 12} 条路径未显示。")
        return "\n".join(lines)

    @llm_tool(name="device_service_stats")
    async def device_service_stats(self, event: AstrMessageEvent):
        """获取 MyDevice 服务模块统计。当用户问服务数量、端点数量、路由数量时调用。

        Args:
        """
        if (deny := self._check_sender(event)): return deny
        if not self._device_enabled:
            return "MyDevice 功能已关闭。"
        if not await _check(self._device_base, "MyDevice", auth=self._device_auth):
            return "MyDevice 客户端未运行。"
        data = await _get(self._device_base, "/service/stats", auth=self._device_auth)
        if not data:
            return "获取服务统计失败。"
        lines = [
            f"🔧 服务统计：{data.get('total',0)} 个服务，{data.get('endpoints',0)} 个端点，{data.get('routes',0)} 条访问路径",
            f"涉及设备：{data.get('devices',0)} 台，公网/分组目标：{data.get('publicTargets',0)} 个",
        ]
        by_kind = data.get("byKind") or {}
        if by_kind:
            lines.append("类型：" + "、".join(f"{k}:{v}" for k, v in by_kind.items() if v))
        by_state = data.get("byState") or {}
        if by_state:
            lines.append("状态：" + "、".join(f"{k}:{v}" for k, v in by_state.items() if v))
        return "\n".join(lines)

    @llm_tool(name="device_network_search")
    async def device_network_search(self, event: AstrMessageEvent, keyword: str):
        """查询 MyDevice 中记录的网络和设备 IP 分配。当用户问网络、IP、子网、Tailscale/WireGuard/局域网时调用。

        Args:
            keyword(string): 网络名、设备名、主机名、IP、子网等关键词；查询全部网络时传空字符串
        """
        if (deny := self._check_sender(event)): return deny
        if not self._device_enabled:
            return "MyDevice 功能已关闭。"
        if not await _check(self._device_base, "MyDevice", auth=self._device_auth):
            return "MyDevice 客户端未运行。"
        path = f"/network/search?q={quote(keyword)}" if keyword else "/network/list"
        data = await _get(self._device_base, path, auth=self._device_auth)
        if data is None:
            return "获取网络列表失败。"
        if not data:
            return f"没有找到{'包含「' + keyword + '」的' if keyword else '任何'}网络。"
        lines = [f"找到 {len(data)} 个网络："]
        for n in data[:10]:
            bits = [n.get("type"), n.get("subnet"), n.get("gateway")]
            lines.append(f"· {n.get('name','?')}（{' | '.join(x for x in bits if x)}）")
            assignments = n.get("assignments") or []
            shown = []
            for a in assignments[:4]:
                host = a.get("hostname") or a.get("deviceName") or a.get("deviceId") or "未知设备"
                addr = a.get("ipAddress") or a.get("addressMode") or ""
                shown.append(f"{host}:{addr}" if addr else host)
            if shown:
                lines.append("   分配：" + "、".join(shown))
        if len(data) > 10:
            lines.append(f"还有 {len(data) - 10} 个网络未显示。")
        return "\n".join(lines)

    @llm_tool(name="device_dataset_search")
    async def device_dataset_search(self, event: AstrMessageEvent, keyword: str):
        """查询 MyDevice 中记录的数据集和它们链接的设备存储。当用户问数据集、资料、备份、存在哪块盘时调用。

        Args:
            keyword(string): 数据集名、设备名、硬盘品牌/容量等关键词；查询全部数据集时传空字符串
        """
        if (deny := self._check_sender(event)): return deny
        if not self._device_enabled:
            return "MyDevice 功能已关闭。"
        if not await _check(self._device_base, "MyDevice", auth=self._device_auth):
            return "MyDevice 客户端未运行。"
        path = f"/dataset/search?q={quote(keyword)}" if keyword else "/dataset/list"
        data = await _get(self._device_base, path, auth=self._device_auth)
        if data is None:
            return "获取数据集列表失败。"
        if not data:
            return f"没有找到{'包含「' + keyword + '」的' if keyword else '任何'}数据集。"
        lines = [f"找到 {len(data)} 个数据集："]
        for ds in data[:12]:
            lines.append(f"· {ds.get('emoji','📁')} {ds.get('name','?')}")
            links = ds.get("storageLinks") or []
            parts = []
            for link in links[:4]:
                device = link.get("deviceName") or link.get("deviceId") or "未知设备"
                storage = link.get("storage") or []
                caps = [s.get("capacity") for s in storage if s.get("capacity")]
                parts.append(f"{device}({ '、'.join(caps) if caps else 'slot ' + ','.join(map(str, link.get('storageIndices') or [])) })")
            if parts:
                lines.append("   存储：" + "、".join(parts))
        if len(data) > 12:
            lines.append(f"还有 {len(data) - 12} 个数据集未显示。")
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
        if (deny := self._check_sender(event)): return deny
        if not self._day_todo_enabled:
            return "MyDay 待办功能已关闭。"
        if not await _check(self._day_base, "MyDay", auth=self._day_auth):
            return "MyDay 客户端未运行，请先启动。"
        path = f"/todo/list?date={date}" if date else "/todo/list"
        data = await _get(self._day_base, path, auth=self._day_auth)
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
        if (deny := self._check_sender(event)): return deny
        if not self._day_todo_enabled:
            return "MyDay 待办功能已关闭。"
        if self._day_readonly:
            return "MyDay 处于只读模式，无法添加任务。"
        if not await _check(self._day_base, "MyDay", auth=self._day_auth):
            return "MyDay 客户端未运行。"
        payload = {
            "title": title,
            "type": task_type or "workOnce",
            "dueDate": due_date or None,
        }
        r = await _post(self._day_base, "/todo/add", payload, auth=self._day_auth)
        if r and r.get("success"):
            return f"已添加待办任务「{title}」！"
        return f"添加任务「{title}」失败。"

    @llm_tool(name="todo_stats")
    async def todo_stats(self, event: AstrMessageEvent):
        """获取 MyDay 的今日任务完成统计。当用户问今天任务完成情况、完成率时调用。

        Args:
        """
        if (deny := self._check_sender(event)): return deny
        if not self._day_todo_enabled:
            return "MyDay 待办功能已关闭。"
        if not await _check(self._day_base, "MyDay", auth=self._day_auth):
            return "MyDay 客户端未运行。"
        data = await _get(self._day_base, "/todo/stats", auth=self._day_auth)
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
        if (deny := self._check_sender(event)): return deny
        if not self._day_finance_enabled:
            return "MyDay 财务功能已关闭。"
        if not await _check(self._day_base, "MyDay", auth=self._day_auth):
            return "MyDay 客户端未运行。"
        path = f"/finance/summary?month={month}" if month else "/finance/summary"
        data = await _get(self._day_base, path, auth=self._day_auth)
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
        if (deny := self._check_sender(event)): return deny
        if not self._day_finance_enabled:
            return "MyDay 财务功能已关闭。"
        if self._day_readonly:
            return "MyDay 处于只读模式，无法记账。"
        if not await _check(self._day_base, "MyDay", auth=self._day_auth):
            return "MyDay 客户端未运行。"
        # 先获取账户列表匹配 accountId
        summary = await _get(self._day_base, "/finance/summary", auth=self._day_auth)
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
        r = await _post(self._day_base, "/finance/add_transaction", {
            "type": ttype,
            "amount": amt,
            "accountId": account_id,
            "note": note or "",
        }, auth=self._day_auth)
        if r and r.get("success"):
            type_cn = {"expense":"支出","income":"收入","transfer":"转账"}.get(ttype, ttype)
            return f"已记录{type_cn}：{amt:.2f} 元，备注「{note or '无'}」。"
        return "记账失败，请稍后再试。"

    @llm_tool(name="finance_subscriptions")
    async def finance_subscriptions(self, event: AstrMessageEvent):
        """查询 MyDay 中的订阅服务列表和下次扣款时间。当用户问有哪些订阅、下次续费时间时调用。

        Args:
        """
        if (deny := self._check_sender(event)): return deny
        if not self._day_finance_enabled:
            return "MyDay 财务功能已关闭。"
        if not await _check(self._day_base, "MyDay", auth=self._day_auth):
            return "MyDay 客户端未运行。"
        data = await _get(self._day_base, "/finance/subscriptions", auth=self._day_auth)
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
        if (deny := self._check_sender(event)): return deny
        if not self._day_weight_enabled:
            return "MyDay 体重功能已关闭。"
        if self._day_readonly:
            return "MyDay 处于只读模式，无法记录体重。"
        if not await _check(self._day_base, "MyDay", auth=self._day_auth):
            return "MyDay 客户端未运行。"
        try:
            w = float(weight)
        except Exception:
            return f"体重格式错误：{weight}"
        r = await _post(self._day_base, "/weight/add", {"weight": w}, auth=self._day_auth)
        if r and r.get("success"):
            return f"已记录体重 {w} kg！"
        return "记录体重失败。"

    @llm_tool(name="weight_stats")
    async def weight_stats(self, event: AstrMessageEvent):
        """查询 MyDay 的体重统计和趋势。当用户问体重变化、近期体重、体重趋势时调用。

        Args:
        """
        if (deny := self._check_sender(event)): return deny
        if not self._day_weight_enabled:
            return "MyDay 体重功能已关闭。"
        if not await _check(self._day_base, "MyDay", auth=self._day_auth):
            return "MyDay 客户端未运行。"
        data = await _get(self._day_base, "/weight/stats", auth=self._day_auth)
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
        if (deny := self._check_sender(event)):
            yield event.plain_result(deny)
            return
        lines = [
            "🗂️  MyApps 集成插件\n",
            "📺 MyAnime（番剧）",
            "  自然语言：「帮我添加葬送的芙莉莲」「我有什么番没看」",
            "",
            "💻 MyDevice（设备）",
            "  自然语言：「我有哪些笔记本」「搜索我的 MacBook 配置」「查一下 Gitea 服务端口」「我的 Tailscale 网络有哪些设备」",
            "",
            "📅 MyDay（日程/财务/体重）",
            "  自然语言：「今天有什么待办」「本月花了多少钱」「记录今天体重65kg」",
            "",
            "💡 直接用自然语言跟我说就好！",
            "   （需要使用支持 Function Calling 的 LLM）",
        ]
        yield event.plain_result("\n".join(lines))