from datetime import datetime, timedelta

from .db import get_db
from .services import distance, pricing_for_station


def normalize(text):
    return (text or "").strip().lower()


def user_context(user):
    return {
        "id": user["id"],
        "role": user["role"],
        "nickname": user["nickname"],
    }


def station_recommendation(user, lat, lng, fast_only=False):
    db = get_db()

    sql = """
        SELECT
            s.*,

            COUNT(c.id) AS total,

            SUM(
                CASE
                    WHEN c.status='idle'
                    THEN 1 ELSE 0
                END
            ) AS free,

            SUM(
                CASE
                    WHEN c.status='idle'
                     AND c.kind='fast'
                    THEN 1 ELSE 0
                END
            ) AS free_fast,

            SUM(
                CASE
                    WHEN c.kind='fast'
                    THEN 1 ELSE 0
                END
            ) AS fast_count

        FROM stations s

        LEFT JOIN chargers c
            ON c.station_id=s.id

        WHERE s.operating_status='operating'

        GROUP BY s.id
    """

    candidates = []

    for row in db.execute(sql).fetchall():
        station = dict(row)

        available = (
            station["free_fast"]
            if fast_only
            else station["free"]
        )

        if not available:
            continue

        station["distance"] = distance(
            lat,
            lng,
            station["lat"],
            station["lng"],
        )

        tariff = pricing_for_station(
            db,
            station["id"],
        )

        station["price_cents"] = tariff[
            "price_cents"
        ]

        candidates.append(station)

    candidates.sort(
        key=lambda x: (
            x["distance"],
            x["price_cents"],
        )
    )

    if not candidates:
        return {
            "answer": (
                "当前附近没有符合条件的空闲充电设备。"
            ),
            "data": [],
        }

    station = candidates[0]

    if fast_only:
        available_text = (
            f"{station['free_fast']} 个空闲快充"
        )
    else:
        available_text = (
            f"{station['free']} 个空闲充电桩"
        )

    return {
        "answer": (
            f"推荐你前往“{station['name']}”。"
            f"距离约 {station['distance']} km，"
            f"目前有 {available_text}，"
            f"当前价格约 ¥"
            f"{station['price_cents'] / 100:.2f}/度。"
        ),

        "data": [
            {
                "station_id": station["id"],
                "station_name": station["name"],
                "distance": station["distance"],
                "free": station["free"],
                "free_fast": station["free_fast"],
                "price_cents": station[
                    "price_cents"
                ],
            }
        ],
    }


def current_order(user_id):
    db = get_db()

    order = db.execute(
        """
        SELECT
            o.*,
            s.name AS station_name,
            c.number AS charger_number

        FROM orders o

        JOIN chargers c
            ON c.id=o.charger_id

        JOIN stations s
            ON s.id=c.station_id

        WHERE o.user_id=?
          AND o.status IN ('reserved','charging')

        ORDER BY o.id DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()

    if not order:
        return {
            "answer": "你当前没有未完成的充电订单。",
            "data": None,
        }

    order = dict(order)

    return {
        "answer": (
            f"你当前在“{order['station_name']}”"
            f"有一个{order['status']}订单，"
            f"设备编号为 "
            f"{order['charger_number']}。"
        ),
        "data": order,
    }


def latest_order(user_id):
    db = get_db()

    order = db.execute(
        """
        SELECT
            o.*,
            s.name AS station_name,
            c.number AS charger_number

        FROM orders o

        JOIN chargers c
            ON c.id=o.charger_id

        JOIN stations s
            ON s.id=c.station_id

        WHERE o.user_id=?
          AND o.status='completed'

        ORDER BY o.ended_at DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()

    if not order:
        return {
            "answer": "你目前还没有已完成的充电订单。",
            "data": None,
        }

    order = dict(order)

    return {
        "answer": (
            f"你最近一次充电是在"
            f"“{order['station_name']}”，"
            f"充电量 {order['energy']:.2f} kWh，"
            f"订单金额 ¥"
            f"{order['amount_cents'] / 100:.2f}，"
            f"实际支付 ¥"
            f"{order['paid_cents'] / 100:.2f}。"
        ),
        "data": order,
    }


def wallet_info(user_id):
    db = get_db()

    user = db.execute(
        """
        SELECT id, balance_cents
        FROM users
        WHERE id=?
        """,
        (user_id,),
    ).fetchone()

    debt = db.execute(
        """
        SELECT
            COALESCE(
                SUM(debt_cents),
                0
            ) AS debt

        FROM orders

        WHERE user_id=?
        """,
        (user_id,),
    ).fetchone()

    balance = user["balance_cents"]
    debt_cents = debt["debt"]

    return {
        "answer": (
            f"你的当前余额为 "
            f"¥{balance / 100:.2f}，"
            f"未补缴欠费为 "
            f"¥{debt_cents / 100:.2f}。"
        ),
        "data": {
            "balance_cents": balance,
            "debt_cents": debt_cents,
        },
    }


def fault_help(user_id):
    db = get_db()

    order = db.execute(
        """
        SELECT
            o.id,
            o.status AS order_status,

            c.id AS charger_id,
            c.number,
            c.status AS charger_status,

            s.name AS station_name,
            s.operating_status

        FROM orders o

        JOIN chargers c
            ON c.id=o.charger_id

        JOIN stations s
            ON s.id=c.station_id

        WHERE o.user_id=?
          AND o.status IN ('reserved','charging')

        ORDER BY o.id DESC
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()

    if not order:
        return {
            "answer": (
                "你当前没有进行中的预约或充电订单。"
                "如果是扫码后无法开始，请检查设备是否"
                "处于空闲状态，并确认账号没有欠费或被冻结。"
            ),
            "data": None,
        }

    order = dict(order)

    charger_status = order["charger_status"]

    if charger_status == "fault":
        advice = (
            "该设备目前处于故障状态，无法开始充电。"
            "建议选择其他空闲设备，并联系工作人员处理故障。"
        )

    elif charger_status == "offline":
        advice = (
            "该设备目前离线，平台暂时无法与设备通信。"
            "建议更换其他充电桩。"
        )

    elif charger_status == "maintenance":
        advice = (
            "该设备正在维修中，目前不能使用。"
            "请更换其他空闲设备。"
        )

    elif order["operating_status"] != "operating":
        advice = (
            "当前充电站暂停运营或处于维护状态，"
            "暂时无法开始充电。"
        )

    else:
        advice = (
            "设备状态目前正常。"
            "如果仍无法启动，请检查预约状态、"
            "账户余额和未补缴订单。"
        )

    return {
        "answer": (
            f"设备 {order['number']}：{advice}"
        ),
        "data": order,
    }


def today_top_station():
    db = get_db()

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    row = db.execute(
        """
        SELECT
            s.id,
            s.name,
            COUNT(o.id) AS orders

        FROM stations s

        LEFT JOIN chargers c
            ON c.station_id=s.id

        LEFT JOIN orders o
            ON o.charger_id=c.id
           AND substr(o.created_at,1,10)=?

        GROUP BY s.id

        ORDER BY orders DESC
        LIMIT 1
        """,
        (today,),
    ).fetchone()

    if not row or not row["orders"]:
        return {
            "answer": "今天暂时还没有充电订单。",
            "data": None,
        }

    return {
        "answer": (
            f"今天订单最多的充电站是"
            f"“{row['name']}”，"
            f"目前共有 {row['orders']} 笔订单。"
        ),
        "data": dict(row),
    }


def revenue_summary(days=7):
    db = get_db()

    since = (
        datetime.now()
        - timedelta(days=days - 1)
    ).strftime("%Y-%m-%d")

    row = db.execute(
        """
        SELECT
            COUNT(*) AS orders,
            COALESCE(
                SUM(paid_cents),
                0
            ) AS revenue,

            COALESCE(
                SUM(energy),
                0
            ) AS energy

        FROM orders

        WHERE status='completed'
          AND substr(ended_at,1,10)>=?
        """,
        (since,),
    ).fetchone()

    return {
        "answer": (
            f"最近 {days} 天共有 "
            f"{row['orders']} 笔已结算订单，"
            f"实收 ¥{row['revenue'] / 100:.2f}，"
            f"累计充电量 "
            f"{row['energy']:.2f} kWh。"
        ),
        "data": dict(row),
    }


def device_summary():
    db = get_db()

    rows = db.execute(
        """
        SELECT
            status,
            COUNT(*) AS n
        FROM chargers
        GROUP BY status
        """
    ).fetchall()

    counts = {
        "idle": 0,
        "reserved": 0,
        "charging": 0,
        "fault": 0,
        "offline": 0,
        "maintenance": 0,
    }

    for row in rows:
        counts[row["status"]] = row["n"]

    abnormal = (
        counts["fault"]
        + counts["offline"]
        + counts["maintenance"]
    )

    return {
        "answer": (
            f"当前设备情况："
            f"{counts['idle']} 台空闲，"
            f"{counts['charging']} 台充电中，"
            f"{counts['reserved']} 台已预约，"
            f"{counts['fault']} 台故障，"
            f"{counts['maintenance']} 台维修中，"
            f"{counts['offline']} 台离线。"
            f"异常设备共 {abnormal} 台。"
        ),
        "data": counts,
    }


def fault_ranking():
    db = get_db()

    rows = db.execute(
        """
        SELECT
            c.number,
            s.name AS station_name,
            COUNT(f.id) AS faults

        FROM fault_records f

        JOIN chargers c
            ON c.id=f.charger_id

        JOIN stations s
            ON s.id=c.station_id

        GROUP BY c.id

        ORDER BY faults DESC
        LIMIT 5
        """
    ).fetchall()

    if not rows:
        return {
            "answer": "目前没有设备故障记录。",
            "data": [],
        }

    top = rows[0]

    return {
        "answer": (
            f"故障次数最多的是设备 "
            f"{top['number']}，"
            f"位于“{top['station_name']}”，"
            f"累计记录 {top['faults']} 次故障。"
        ),
        "data": [
            dict(row)
            for row in rows
        ],
    }


def operations_report(days=7):
    db = get_db()

    since = (
        datetime.now()
        - timedelta(days=days - 1)
    ).strftime("%Y-%m-%d")

    business = db.execute(
        """
        SELECT
            COUNT(*) AS orders,

            COALESCE(
                SUM(paid_cents),
                0
            ) AS revenue,

            COALESCE(
                SUM(energy),
                0
            ) AS energy

        FROM orders

        WHERE status='completed'
          AND substr(ended_at,1,10)>=?
        """,
        (since,),
    ).fetchone()

    users = db.execute(
        """
        SELECT COUNT(*) AS total
        FROM users
        WHERE role='user'
        """
    ).fetchone()

    faults = db.execute(
        """
        SELECT COUNT(*) AS total
        FROM fault_records
        WHERE status IN (
            'pending',
            'processing'
        )
        """
    ).fetchone()

    devices = db.execute(
        """
        SELECT
            COUNT(*) AS total,

            SUM(
                CASE
                    WHEN status='idle'
                    THEN 1 ELSE 0
                END
            ) AS idle

        FROM chargers
        """
    ).fetchone()

    return {
        "answer": (
            f"最近 {days} 天运营报告：\n"
            f"1. 已结算订单：{business['orders']} 笔。\n"
            f"2. 实收收入：¥"
            f"{business['revenue'] / 100:.2f}。\n"
            f"3. 总充电量："
            f"{business['energy']:.2f} kWh。\n"
            f"4. 注册普通用户："
            f"{users['total']} 人。\n"
            f"5. 设备总数："
            f"{devices['total']} 台，"
            f"其中空闲 "
            f"{devices['idle'] or 0} 台。\n"
            f"6. 当前未解决故障："
            f"{faults['total']} 条。"
        ),
        "data": {
            "orders": business["orders"],
            "revenue_cents": business[
                "revenue"
            ],
            "energy": business["energy"],
            "users": users["total"],
            "devices": devices["total"],
            "open_faults": faults["total"],
        },
    }

def chat(
    user,
    message,
    lat=39.9593,
    lng=116.2981,
):
    text = normalize(message)

    if not text:
        return {
            "answer": "请输入你想咨询的问题。",
            "intent": "empty",
        }

    role = user["role"]

    # -----------------------------
    # Ordinary user tools
    # -----------------------------

    if (
        "附近" in text
        and (
            "快充" in text
            or "充电站" in text
            or "充电桩" in text
        )
    ):
        result = station_recommendation(
            user,
            lat,
            lng,
            fast_only="快充" in text,
        )

        result["intent"] = (
            "station_recommendation"
        )

        return result

    if (
        "最近一次" in text
        or "上一次" in text
    ) and (
        "充电" in text
        or "花了多少钱" in text
    ):
        result = latest_order(
            user["id"]
        )

        result["intent"] = (
            "latest_order"
        )

        return result

    if (
        "余额" in text
        or "欠费" in text
    ):
        result = wallet_info(
            user["id"]
        )

        result["intent"] = "wallet"

        return result

    if (
        "为什么" in text
        and (
            "无法" in text
            or "不能" in text
            or "启动" in text
        )
    ):
        result = fault_help(
            user["id"]
        )

        result["intent"] = (
            "charging_fault_help"
        )

        return result

    if (
        "当前订单" in text
        or "现在有订单" in text
        or "正在充电" in text
    ):
        result = current_order(
            user["id"]
        )

        result["intent"] = (
            "current_order"
        )

        return result

    # -----------------------------
    # Staff tools
    # -----------------------------

    if role in (
        "operator",
        "admin",
    ):

        if (
            "今天" in text
            and "订单最多" in text
        ):
            result = today_top_station()

            result["intent"] = (
                "today_top_station"
            )

            return result

        if (
            "最近一周" in text
            or "最近7天" in text
            or "最近 7 天" in text
        ) and (
            "收入" in text
            or "营收" in text
        ):
            result = revenue_summary(7)

            result["intent"] = (
                "revenue_summary"
            )

            return result

        if (
            "运营报告" in text
            or "生成报告" in text
        ):
            result = operations_report(
                7
            )

            result["intent"] = (
                "operations_report"
            )

            return result

    if role in (
        "operator",
        "technician",
        "admin",
    ):

        if (
            "设备情况" in text
            or "多少故障" in text
            or "多少设备" in text
        ):
            result = device_summary()

            result["intent"] = (
                "device_summary"
            )

            return result

        if (
            "故障次数" in text
            or "故障最多" in text
        ):
            result = fault_ranking()

            result["intent"] = (
                "fault_ranking"
            )

            return result

    # -----------------------------
    # Fallback
    # -----------------------------

    if role == "user":
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