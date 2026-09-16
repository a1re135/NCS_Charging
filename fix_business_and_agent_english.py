from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP = ROOT / "static" / "app.js"
EN = ROOT / "static" / "i18n" / "en.json"
AGENT = ROOT / "ncs" / "agent.py"
LLM = ROOT / "ncs" / "llm_agent.py"

required = (APP, EN, AGENT, LLM)
missing = [str(p.relative_to(ROOT)) for p in required if not p.exists()]
if missing:
    raise SystemExit(
        "Run this script from the NCS_Charging repository root. Missing: "
        + ", ".join(missing)
    )

for path in required:
    backup = path.with_suffix(path.suffix + ".before-business-agent-english")
    if not backup.exists():
        shutil.copy2(path, backup)


def replace_once_or_done(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        print(f"[already] {label}")
        return text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[{label}] expected 1 match, found {count}")
    print(f"[patch] {label}")
    return text.replace(old, new, 1)


def replace_all_if_present(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        print(f"[already] {label}")
        return text
    count = text.count(old)
    if count:
        print(f"[patch] {label}: {count}")
        return text.replace(old, new)
    print(f"[skip] {label}: no remaining matches")
    return text


# ============================================================================
# 1. Frontend: translate displayed business/demo data without changing DB data
# ============================================================================
app = APP.read_text(encoding="utf-8")

if "const dataText =" not in app:
    role_marker = '''const roleNames = {
  user: "普通用户",
  operator: "运营人员",
  technician: "运维人员",
  admin: "系统管理员",
};'''
    if role_marker not in app:
        raise SystemExit("[dataText helper] roleNames block not found")
    app = app.replace(
        role_marker,
        role_marker
        + '''

/*
 * Translate known business/demo values only for display.
 * tr() falls back to the original value, so unknown user-entered data is kept.
 */
const dataText = (value) =>
  tr(String(value ?? ""));''',
        1,
    )
    print("[patch] dataText helper")
else:
    print("[already] dataText helper")

app = replace_once_or_done(
    app,
    '''      ${esc(t)}
   </option>`;''',
    '''      ${esc(dataText(t))}
   </option>`;''',
    "translated option labels",
)

app = replace_once_or_done(
    app,
    '''    <b>${esc(v)}</b>
  </div>`;''',
    '''    <b>${esc(dataText(v))}</b>
  </div>`;''',
    "translated detail-line values",
)

app = replace_all_if_present(
    app,
    '''                      x[labelKey],
                    )}''',
    '''                      dataText(x[labelKey]),
                    )}''',
    "realtime business labels",
)

# Common display-only escaped business fields.
direct_fields = [
    ("S.user.nickname", "current user nickname"),
    ("u.nickname", "user nickname"),
    ("s.name", "station name"),
    ("s.address", "station address"),
    ("s.city", "station city"),
    ("s.parking_info", "station parking info"),
    ("c.station_name", "charger station name"),
    ("c.address", "charger station address"),
    ("c.city", "charger station city"),
    ("c.parking_info", "charger parking info"),
    ("o.station_name", "order station name"),
    ("o.nickname", "order user nickname"),
    ("x.station_name", "recent-order station name"),
    ("d.active[0].station_name", "active-order station name"),
    ("f.station_name", "fault station name"),
    ("f.fault_type", "fault type"),
    ("f.description", "fault description"),
]
for expr, label in direct_fields:
    pattern = re.compile(
        r"esc\(\s*(?!dataText\(|tr\()" + re.escape(expr) + r"\s*,?\s*\)"
    )
    app, count = pattern.subn(f"esc(dataText({expr}))", app)
    if count:
        print(f"[patch] {label}: {count}")

app, count = re.subn(
    r'esc\(\s*(?!dataText\(|tr\()f\.resolution\s*\|\|\s*"—"\s*,?\s*\)',
    'esc(dataText(f.resolution || "—"))',
    app,
)
if count:
    print(f"[patch] fault resolution: {count}")

app = replace_all_if_present(
    app,
    '${esc(u.nickname.slice(0, 1))}',
    '${esc(dataText(u.nickname).slice(0, 1))}',
    "avatar initial",
)

app = replace_all_if_present(
    app,
    '''S.user.nickname.slice(
                    0,
                    1,
                  )''',
    '''dataText(S.user.nickname).slice(
                    0,
                    1,
                  )''',
    "agent user avatar initial",
)

app = replace_all_if_present(
    app,
    'esc(x.name)',
    'esc(dataText(x.name))',
    "revenue station title",
)

app = replace_all_if_present(
    app,
    'esc(x.name.length > 6 ? x.name.slice(0, 6) + "…" : x.name)',
    'esc(dataText(x.name).length > 12 ? dataText(x.name).slice(0, 12) + "…" : dataText(x.name))',
    "revenue station short label",
)

app = replace_all_if_present(
    app,
    '''tr("前往 ") +
      s.name,''',
    '''tr("前往 ") +
      dataText(s.name),''',
    "map modal station title",
)

station_search_old = '''      (
        s.name +
        s.address +
        s.city
      )
        .toLowerCase()
        .includes(q),'''
station_search_new = '''      (
        s.name +
        s.address +
        s.city +
        dataText(s.name) +
        dataText(s.address) +
        dataText(s.city)
      )
        .toLowerCase()
        .includes(q),'''
if station_search_new not in app and station_search_old in app:
    app = app.replace(station_search_old, station_search_new, 1)
    print("[patch] bilingual station search")

order_search_old = '''            `${
              o.id
            } ${
              o.station_name
            } ${
              o.nickname
            }`
              .toLowerCase()'''
order_search_new = '''            `${
              o.id
            } ${
              o.station_name
            } ${
              o.nickname
            } ${
              dataText(o.station_name)
            } ${
              dataText(o.nickname)
            }`
              .toLowerCase()'''
if order_search_new not in app and order_search_old in app:
    app = app.replace(order_search_old, order_search_new, 1)
    print("[patch] bilingual order search")

charger_search_old = '''          `${
            c.number
          } ${
            c.station_name
          }`
            .toLowerCase()'''
charger_search_new = '''          `${
            c.number
          } ${
            c.station_name
          } ${
            dataText(c.station_name)
          }`
            .toLowerCase()'''
if charger_search_new not in app and charger_search_old in app:
    app = app.replace(charger_search_old, charger_search_new, 1)
    print("[patch] bilingual charger search")

APP.write_text(app, encoding="utf-8", newline="\n")


# ============================================================================
# 2. Translation dictionary: current demo/business data
# ============================================================================
with EN.open("r", encoding="utf-8") as f:
    en = json.load(f)

business_translations = {
    "小林": "Xiaolin",
    "小明": "Xiaoming",
    "管理员": "Administrator",
    "运营演示": "Operator Demo",
    "运维演示": "Technician Demo",

    "海淀 · 智慧充电站": "Haidian · Smart Charging Station",
    "北京市海淀区中关村大街": "Zhongguancun Avenue, Haidian District, Beijing",
    "北京市海淀区": "Haidian District, Beijing",
    "停车前 30 分钟免费，之后按停车场标准收费":
        "The first 30 minutes are free; standard parking rates apply afterward.",

    "城市中心 · 绿能站": "City Center · Green Energy Station",
    "北京市东城区中心区域": "Central Dongcheng District, Beijing",
    "北京市东城区": "Dongcheng District, Beijing",
    "充电车辆前 2 小时免停车费":
        "Charging vehicles receive 2 hours of free parking.",

    "朝阳 · 阳光充电站": "Chaoyang · Sunshine Charging Station",
    "北京市朝阳区朝阳公园南路": "Chaoyang Park South Road, Chaoyang District, Beijing",
    "北京市朝阳区": "Chaoyang District, Beijing",
    "地下停车场 B2 层，按场内标准收费":
        "B2 underground parking; standard on-site parking fees apply.",

    "丰台 · 花园充电站": "Fengtai · Garden Charging Station",
    "北京市丰台区丰台北路": "Fengtai North Road, Fengtai District, Beijing",
    "北京市丰台区": "Fengtai District, Beijing",
    "充电期间停车优惠以现场公告为准":
        "Parking discounts during charging are subject to on-site notices.",

    "石景山 · 星光充电站": "Shijingshan · Starlight Charging Station",
    "北京市石景山区石景山路": "Shijingshan Road, Shijingshan District, Beijing",
    "北京市石景山区": "Shijingshan District, Beijing",
    "地面停车位，充电车辆优先":
        "Ground-level parking; priority is given to charging vehicles.",

    "房山 · 良乡充电站": "Fangshan · Liangxiang Charging Station",
    "北京市房山区良乡区域": "Liangxiang Area, Fangshan District, Beijing",
    "北京市房山区": "Fangshan District, Beijing",

    "大兴 · 黄村充电站": "Daxing · Huangcun Charging Station",
    "北京市大兴区黄村区域": "Huangcun Area, Daxing District, Beijing",
    "北京市大兴区": "Daxing District, Beijing",

    "通州 · 运河充电站": "Tongzhou · Canal Charging Station",
    "北京市通州区运河区域": "Canal Area, Tongzhou District, Beijing",
    "北京市通州区": "Tongzhou District, Beijing",

    "昌平 · 未来充电站": "Changping · Future Charging Station",
    "北京市昌平区城区区域": "Changping Urban Area, Beijing",
    "北京市昌平区": "Changping District, Beijing",

    "顺义 · 空港充电站": "Shunyi · Airport Charging Station",
    "北京市顺义区城区区域": "Shunyi Urban Area, Beijing",
    "北京市顺义区": "Shunyi District, Beijing",

    "演示站点，停车规则以现场公告为准":
        "Demo station; parking rules are subject to on-site notices.",

    "通信故障": "Communication fault",
    "设备异常": "Device fault",
    "由设备管理页面手动标记": "Manually marked from Charger Management",
    "软件重启恢复": "Recovered after software restart",
    "管理员手动恢复": "Restored manually by administrator",
}
en.update(business_translations)
EN.write_text(
    json.dumps(en, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
    newline="\n",
)


# ============================================================================
# 3. Local AI Agent: bilingual understanding + English responses in English UI
# ============================================================================
agent = AGENT.read_text(encoding="utf-8")

if "from .i18n import current_language, translate" not in agent:
    import_marker = "from .services import distance, pricing_for_station\n"
    if import_marker not in agent:
        raise SystemExit("[agent i18n import] import marker not found")
    agent = agent.replace(
        import_marker,
        import_marker + "from .i18n import current_language, translate\n",
        1,
    )
    print("[patch] agent i18n import")

helper_code = r'''
def _english_mode():
    return current_language() == "en"


def _display_text(value):
    if value is None:
        return ""
    return translate(str(value))


def localize_result(intent, result):
    # Rebuild verified local-tool answers in the current interface language.
    if not _english_mode():
        return result

    result = dict(result or {})
    data = result.get("data")

    aliases = {
        "recommend_station": "station_recommendation",
        "wallet_info": "wallet",
    }
    intent = aliases.get(intent, intent)

    if intent == "station_recommendation":
        if not data:
            answer = "There are currently no nearby available chargers matching your request."
        else:
            station = data[0]
            station_name = _display_text(station.get("station_name", ""))
            free_fast = int(station.get("free_fast") or 0)
            free = int(station.get("free") or 0)
            available = (
                f"{free_fast} available fast charger(s)"
                if free_fast
                else f"{free} available charger(s)"
            )
            answer = (
                f'I recommend "{station_name}". '
                f'It is about {station.get("distance", 0)} km away, '
                f'with {available}. '
                f'The current rate is approximately '
                f'¥{(station.get("price_cents") or 0) / 100:.2f}/kWh.'
            )

    elif intent == "current_order":
        if not data:
            answer = "You do not currently have an unfinished charging order."
        else:
            status = {
                "reserved": "reserved",
                "charging": "charging",
            }.get(data.get("status"), data.get("status", "active"))
            answer = (
                f'You currently have a {status} order at '
                f'"{_display_text(data.get("station_name", ""))}". '
                f'Charger: {data.get("charger_number", "—")}.'
            )

    elif intent == "latest_order":
        if not data:
            answer = "You do not have any completed charging orders yet."
        else:
            answer = (
                f'Your most recent charging session was at '
                f'"{_display_text(data.get("station_name", ""))}". '
                f'Energy: {float(data.get("energy") or 0):.2f} kWh. '
                f'Order amount: ¥{(data.get("amount_cents") or 0) / 100:.2f}. '
                f'Paid: ¥{(data.get("paid_cents") or 0) / 100:.2f}.'
            )

    elif intent == "wallet":
        data = data or {}
        answer = (
            f'Your current balance is ¥{(data.get("balance_cents") or 0) / 100:.2f}. '
            f'Outstanding payment: ¥{(data.get("debt_cents") or 0) / 100:.2f}.'
        )

    elif intent == "charging_fault_help":
        if not data:
            answer = (
                "You do not currently have an active reservation or charging order. "
                "If charging cannot start after scanning, check that the charger is "
                "available and that your account is not frozen and has no unpaid balance."
            )
        else:
            status = data.get("charger_status")
            if status == "fault":
                advice = (
                    "This charger is currently faulty and cannot start charging. "
                    "Please choose another available charger and contact staff."
                )
            elif status == "offline":
                advice = (
                    "This charger is offline, so the platform cannot communicate with it. "
                    "Please use another charger."
                )
            elif status == "maintenance":
                advice = (
                    "This charger is under maintenance and cannot be used. "
                    "Please choose another available charger."
                )
            elif data.get("operating_status") != "operating":
                advice = (
                    "This charging station is paused or under maintenance, "
                    "so charging cannot start right now."
                )
            else:
                advice = (
                    "The charger currently appears normal. If charging still cannot start, "
                    "check your reservation status, wallet balance and unpaid orders."
                )
            answer = f'Charger {data.get("number", "—")}: {advice}'

    elif intent == "today_top_station":
        if not data:
            answer = "There are no charging orders yet today."
        else:
            answer = (
                f'The station with the most orders today is '
                f'"{_display_text(data.get("name", ""))}", '
                f'with {data.get("orders", 0)} order(s).'
            )

    elif intent == "revenue_summary":
        data = data or {}
        answer = (
            f'Recent period summary: {data.get("orders", 0)} settled order(s), '
            f'¥{(data.get("revenue") or 0) / 100:.2f} collected revenue, '
            f'and {float(data.get("energy") or 0):.2f} kWh delivered.'
        )

    elif intent == "device_summary":
        data = data or {}
        abnormal = (
            int(data.get("fault") or 0)
            + int(data.get("offline") or 0)
            + int(data.get("maintenance") or 0)
        )
        answer = (
            "Current device status: "
            f'{data.get("idle", 0)} available, '
            f'{data.get("charging", 0)} charging, '
            f'{data.get("reserved", 0)} reserved, '
            f'{data.get("fault", 0)} faulty, '
            f'{data.get("maintenance", 0)} under maintenance, '
            f'{data.get("offline", 0)} offline. '
            f'Total abnormal devices: {abnormal}.'
        )

    elif intent == "fault_ranking":
        if not data:
            answer = "There are currently no device fault records."
        else:
            top = data[0]
            answer = (
                f'Charger {top.get("number", "—")} has the most recorded faults. '
                f'It is located at "{_display_text(top.get("station_name", ""))}" '
                f'with {top.get("faults", 0)} fault record(s).'
            )

    elif intent == "operations_report":
        data = data or {}
        answer = (
            "Operations report:\n"
            f'1. Settled orders: {data.get("orders", 0)}.\n'
            f'2. Collected revenue: ¥{(data.get("revenue_cents") or 0) / 100:.2f}.\n'
            f'3. Total charging energy: {float(data.get("energy") or 0):.2f} kWh.\n'
            f'4. Registered users: {data.get("users", 0)}.\n'
            f'5. Total devices: {data.get("devices", 0)}.\n'
            f'6. Open faults: {data.get("open_faults", 0)}.'
        )

    else:
        return result

    result["answer"] = answer
    return result


'''
if "def localize_result(" not in agent:
    marker = "\ndef chat(\n"
    if marker not in agent:
        raise SystemExit("[agent helper insertion] chat() marker not found")
    agent = agent.replace(marker, "\n" + helper_code + "def chat(\n", 1)
    print("[patch] agent English response helper")

new_chat = r'''def chat(
    user,
    message,
    lat=39.9593,
    lng=116.2981,
):
    text = normalize(message)
    english = _english_mode()

    if not text:
        return {
            "answer": (
                "Please enter a question."
                if english
                else "请输入你想咨询的问题。"
            ),
            "intent": "empty",
        }

    role = user["role"]

    def finish(result, intent):
        result["intent"] = intent
        return localize_result(intent, result)

    nearby = (
        "附近" in text
        or "nearby" in text
        or "nearest" in text
        or "closest" in text
    )
    charger_topic = (
        "快充" in text
        or "充电站" in text
        or "充电桩" in text
        or "charger" in text
        or "charging station" in text
        or "fast charge" in text
        or "fast charger" in text
    )
    if nearby and charger_topic:
        return finish(
            station_recommendation(
                user,
                lat,
                lng,
                fast_only=("快充" in text or "fast" in text),
            ),
            "station_recommendation",
        )

    latest_words = (
        "最近一次" in text
        or "上一次" in text
        or "most recent" in text
        or "latest" in text
        or "last charging" in text
    )
    latest_topic = (
        "充电" in text
        or "花了多少钱" in text
        or "charging" in text
        or "cost" in text
        or "spent" in text
    )
    if latest_words and latest_topic:
        return finish(latest_order(user["id"]), "latest_order")

    if (
        "余额" in text
        or "欠费" in text
        or "balance" in text
        or "outstanding" in text
        or "unpaid" in text
        or "debt" in text
    ):
        return finish(wallet_info(user["id"]), "wallet")

    fault_question = (
        (
            "为什么" in text
            and ("无法" in text or "不能" in text or "启动" in text)
        )
        or (
            ("why" in text or "can't" in text or "cannot" in text or "unable" in text)
            and ("start" in text or "charger" in text or "charging" in text)
        )
    )
    if fault_question:
        return finish(fault_help(user["id"]), "charging_fault_help")

    if (
        "当前订单" in text
        or "现在有订单" in text
        or "正在充电" in text
        or "current order" in text
        or "active order" in text
        or "charging order" in text
        or ("do i have" in text and "order" in text)
    ):
        return finish(current_order(user["id"]), "current_order")

    if role in ("operator", "admin"):
        if (
            ("今天" in text and "订单最多" in text)
            or ("today" in text and "most" in text and "order" in text)
        ):
            return finish(today_top_station(), "today_top_station")

        recent_7 = (
            "最近一周" in text
            or "最近7天" in text
            or "最近 7 天" in text
            or "last 7 days" in text
            or "past 7 days" in text
            or "last week" in text
        )
        revenue_topic = (
            "收入" in text
            or "营收" in text
            or "revenue" in text
            or "income" in text
        )
        if recent_7 and revenue_topic:
            return finish(revenue_summary(7), "revenue_summary")

        if (
            "运营报告" in text
            or "生成报告" in text
            or "operations report" in text
            or "operation report" in text
            or "generate report" in text
        ):
            return finish(operations_report(7), "operations_report")

    if role in ("operator", "technician", "admin"):
        if (
            "设备情况" in text
            or "多少故障" in text
            or "多少设备" in text
            or "device status" in text
            or "devices status" in text
            or "how many faulty" in text
            or "how many devices" in text
            or "faulty devices" in text
        ):
            return finish(device_summary(), "device_summary")

        if (
            "故障次数" in text
            or "故障最多" in text
            or "most faults" in text
            or "highest number of faults" in text
            or "fault most" in text
        ):
            return finish(fault_ranking(), "fault_ranking")

    if english:
        if role == "user":
            examples = (
                "You can ask me:\n"
                "• Where is the nearest available fast charger?\n"
                "• Do I have an active charging order?\n"
                "• What is my balance?\n"
                "• How much did my most recent charging session cost?\n"
                "• Why can't my charger start?"
            )
        else:
            examples = (
                "You can ask me:\n"
                "• Which station has the most orders today?\n"
                "• How has revenue performed over the last 7 days?\n"
                "• How many devices are faulty right now?\n"
                "• Which devices have the most faults?\n"
                "• Generate an operations report for the last 7 days."
            )
    elif role == "user":
        examples = (
            "你可以问我：\n"
            "• 附近哪里有空闲快充？\n"
            "• 我现在有充电订单吗？\n"
            "• 我的余额是多少？\n"
            "• 我最近一次充电花了多少钱？\n"
            "• 为什么我的充电桩无法启动？"
        )
    else:
        examples = (
            "你可以问我：\n"
            "• 今天哪个充电站订单最多？\n"
            "• 最近7天收入怎么样？\n"
            "• 现在有多少故障设备？\n"
            "• 哪些设备故障次数最多？\n"
            "• 生成最近7天运营报告"
        )

    return {
        "answer": examples,
        "intent": "help",
        "data": None,
    }
'''

agent, chat_count = re.subn(
    r"def chat\(\n[\s\S]*\Z",
    lambda _m: new_chat,
    agent,
    count=1,
)
if chat_count != 1:
    raise SystemExit(f"[agent chat replacement] expected 1 match, found {chat_count}")
print("[patch] bilingual local Agent chat")
AGENT.write_text(agent, encoding="utf-8", newline="\n")


# ============================================================================
# 4. GLM Agent: force response language to follow UI and localize tool answers
# ============================================================================
llm = LLM.read_text(encoding="utf-8")

if "localize_result," not in llm:
    marker = '''    operations_report,
)'''
    if marker not in llm:
        raise SystemExit("[GLM import localize_result] import list marker not found")
    llm = llm.replace(
        marker,
        '''    operations_report,
    localize_result,
)''',
        1,
    )
    print("[patch] GLM import localize_result")

if "from .i18n import current_language" not in llm:
    llm = llm.replace(
        "from openai import OpenAI\n",
        "from openai import OpenAI\n\nfrom .i18n import current_language\n",
        1,
    )
    print("[patch] GLM language import")

new_system_prompt = '''def system_prompt(user):
    role = user["role"]

    role_names = {
        "user": ("普通用户", "User"),
        "operator": ("运营人员", "Operator"),
        "technician": ("运维人员", "Technician"),
        "admin": ("系统管理员", "System administrator"),
    }

    english = current_language() == "en"
    role_pair = role_names.get(role, (role, role))
    role_name = role_pair[1] if english else role_pair[0]

    if english:
        return f"""
You are the AI Agent for the NCS Smart Charging Platform.
Current user role: {role_name}.

Task: understand the user's natural-language request and select the appropriate
approved business tool when business data is required.

Rules:
1. For charging stations, chargers, orders, wallets, faults, revenue or operations data, use an approved tool.
2. Only use the tools provided to you. Never access the database directly or generate SQL.
3. Never invent business data.
4. Never reveal passwords, API keys or system secrets.
5. The interface language is English, so always answer in English, even if the user asks in Chinese.
6. Keep ordinary answers concise.
""".strip()

    return f"""
你是 NCS 智能充电平台的 AI Agent。
当前用户角色：{role_name}。

任务：理解用户自然语言，并选择合适的已提供业务工具。

规则：
1. 涉及充电站、充电桩、订单、钱包、故障、营收或运营数据时，必须调用工具。
2. 只能使用当前提供的工具，不得自行访问数据库或生成 SQL。
3. 不得编造业务数据。
4. 不得泄露密码、API Key 或系统密钥。
5. 当前界面语言是中文，因此始终使用中文回答。
6. 如果不需要工具，可以直接简短回答。
""".strip()'''

llm, prompt_count = re.subn(
    r"def system_prompt\(user\):[\s\S]*?(?=\n\n# =========================================================\n# Configuration)",
    lambda _m: new_system_prompt,
    llm,
    count=1,
)
if prompt_count != 1:
    raise SystemExit(
        f"[GLM system prompt replacement] expected 1 match, found {prompt_count}"
    )
print("[patch] GLM UI-language prompt")

execute_block = '''        result = execute_tool(
            user,
            tool_name,
            arguments,
            lat,
            lng,
        )
'''
localized_block = execute_block + '''
        # Rebuild the verified tool answer in the selected UI language.
        result = localize_result(
            tool_name,
            result,
        )
'''
if localized_block not in llm:
    if execute_block not in llm:
        raise SystemExit("[GLM tool localization] execute_tool block not found")
    llm = llm.replace(execute_block, localized_block, 1)
    print("[patch] GLM tool-answer localization")

old_fallback = '''            result.get("answer")
            or "暂时无法生成回答。"'''
new_fallback = '''            result.get("answer")
            or (
                "Unable to generate a response right now."
                if current_language() == "en"
                else "暂时无法生成回答。"
            )'''
if old_fallback in llm:
    llm = llm.replace(old_fallback, new_fallback, 1)
    print("[patch] GLM empty-answer fallback")

LLM.write_text(llm, encoding="utf-8", newline="\n")

print()
print("Done.")
print("Updated:")
for p in required:
    print(" ", p.relative_to(ROOT))
print()
print("Backups:")
for p in required:
    backup = p.with_suffix(p.suffix + ".before-business-agent-english")
    print(" ", backup.relative_to(ROOT))
print()
print(
    "Known current demo/business data is translated from the dictionary. "
    "Completely new arbitrary Chinese user-entered text is preserved unless "
    "you add a translation entry or a separate machine-translation service."
)
