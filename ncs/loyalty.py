"""NCS membership, points, and coupon system."""

from datetime import datetime
from decimal import Decimal, ROUND_DOWN

from flask import Blueprint, jsonify, g

from .db import get_db, now
from .services import BusinessError, transaction, lock_sql
from .routes import auth

member_api = Blueprint("member_api", __name__)


TIERS = [
    (
        "bronze",
        "青铜会员",
        "基础会员权益",
        0,
        0,
        1.0,
    ),
    (
        "silver",
        "白银会员",
        "每次充电享 2% 会员折扣，并获得 1.1 倍积分",
        1000,
        2,
        1.1,
    ),
    (
        "gold",
        "黄金会员",
        "每次充电享 5% 会员折扣，并获得 1.25 倍积分",
        3000,
        5,
        1.25,
    ),
    (
        "platinum",
        "铂金会员",
        "每次充电享 8% 会员折扣，并获得 1.5 倍积分",
        8000,
        8,
        1.5,
    ),
]


COUPONS = [
    (
        "WELCOME10",
        "新会员充电券",
        "满 50 元减 10 元",
        "fixed",
        1000,
        5000,
        0,
        0,
        None,
        None,
    ),
    (
        "GREEN15",
        "绿色出行券",
        "满 80 元享 85 折，最高减 15 元",
        "percent",
        15,
        8000,
        1500,
        0,
        None,
        None,
    ),
    (
        "POINTS5",
        "积分兑换券 5 元",
        "500 积分兑换，满 30 元可用",
        "fixed",
        500,
        3000,
        0,
        500,
        None,
        None,
    ),
    (
        "POINTS12",
        "积分兑换券 12 元",
        "1000 积分兑换，满 80 元可用",
        "fixed",
        1200,
        8000,
        0,
        1000,
        None,
        None,
    ),
]


def _mysql(db):
    return db.__class__.__name__ == "MySQLDatabase"


def ensure_schema(db):
    """Create loyalty tables and seed the default tiers/coupons."""

    if _mysql(db):
        statements = [
            """
            CREATE TABLE IF NOT EXISTS membership_tiers (
                tier_key VARCHAR(32) PRIMARY KEY,
                name VARCHAR(64) NOT NULL,
                description VARCHAR(255) NOT NULL,
                min_points INT NOT NULL DEFAULT 0,
                discount_pct DECIMAL(5,2) NOT NULL DEFAULT 0,
                points_multiplier DECIMAL(5,2) NOT NULL DEFAULT 1
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS member_accounts (
                user_id BIGINT UNSIGNED PRIMARY KEY,
                tier_key VARCHAR(32) NOT NULL,
                points_balance INT NOT NULL DEFAULT 0,
                lifetime_points INT NOT NULL DEFAULT 0,
                created_at VARCHAR(32) NOT NULL,
                updated_at VARCHAR(32) NOT NULL,
                FOREIGN KEY(user_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS points_ledger (
                id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
                user_id BIGINT UNSIGNED NOT NULL,
                amount INT NOT NULL,
                balance_after INT NOT NULL,
                kind VARCHAR(32) NOT NULL,
                note VARCHAR(255) NOT NULL,
                order_id BIGINT UNSIGNED NULL,
                created_at VARCHAR(32) NOT NULL,
                FOREIGN KEY(user_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE,
                INDEX points_user(user_id, created_at)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS coupons (
                id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
                code VARCHAR(64) NOT NULL UNIQUE,
                name VARCHAR(128) NOT NULL,
                description VARCHAR(255) NOT NULL,
                discount_type VARCHAR(16) NOT NULL,
                discount_value INT NOT NULL,
                min_spend_cents INT NOT NULL DEFAULT 0,
                max_discount_cents INT NOT NULL DEFAULT 0,
                points_cost INT NOT NULL DEFAULT 0,
                total_limit INT NULL,
                claimed_count INT NOT NULL DEFAULT 0,
                expires_at VARCHAR(32) NULL,
                active INT NOT NULL DEFAULT 1
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS user_coupons (
                id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,
                user_id BIGINT UNSIGNED NOT NULL,
                coupon_id BIGINT UNSIGNED NOT NULL,
                status VARCHAR(16) NOT NULL DEFAULT 'available',
                claimed_at VARCHAR(32) NOT NULL,
                used_at VARCHAR(32) NULL,
                order_id BIGINT UNSIGNED NULL,
                FOREIGN KEY(user_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE,
                FOREIGN KEY(coupon_id)
                    REFERENCES coupons(id)
                    ON DELETE CASCADE,
                UNIQUE KEY uq_user_coupon(user_id, coupon_id),
                INDEX user_coupon_lookup(user_id, status)
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS order_loyalty (
                order_id BIGINT UNSIGNED PRIMARY KEY,
                original_amount_cents INT NOT NULL,
                membership_discount_cents INT NOT NULL DEFAULT 0,
                coupon_discount_cents INT NOT NULL DEFAULT 0,
                final_amount_cents INT NOT NULL DEFAULT 0,
                coupon_id BIGINT UNSIGNED NULL,
                points_earned INT NOT NULL DEFAULT 0,
                FOREIGN KEY(order_id)
                    REFERENCES orders(id)
                    ON DELETE CASCADE
            )
            """,
        ]

    else:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS membership_tiers (
                tier_key TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                min_points INTEGER NOT NULL DEFAULT 0,
                discount_pct REAL NOT NULL DEFAULT 0,
                points_multiplier REAL NOT NULL DEFAULT 1
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS member_accounts (
                user_id INTEGER PRIMARY KEY,
                tier_key TEXT NOT NULL,
                points_balance INTEGER NOT NULL DEFAULT 0,
                lifetime_points INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS points_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                balance_after INTEGER NOT NULL,
                kind TEXT NOT NULL,
                note TEXT NOT NULL,
                order_id INTEGER,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS points_user
            ON points_ledger(user_id, created_at)
            """,
            """
            CREATE TABLE IF NOT EXISTS coupons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                discount_type TEXT NOT NULL,
                discount_value INTEGER NOT NULL,
                min_spend_cents INTEGER NOT NULL DEFAULT 0,
                max_discount_cents INTEGER NOT NULL DEFAULT 0,
                points_cost INTEGER NOT NULL DEFAULT 0,
                total_limit INTEGER,
                claimed_count INTEGER NOT NULL DEFAULT 0,
                expires_at TEXT,
                active INTEGER NOT NULL DEFAULT 1
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS user_coupons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                coupon_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'available',
                claimed_at TEXT NOT NULL,
                used_at TEXT,
                order_id INTEGER,
                FOREIGN KEY(user_id)
                    REFERENCES users(id)
                    ON DELETE CASCADE,
                FOREIGN KEY(coupon_id)
                    REFERENCES coupons(id)
                    ON DELETE CASCADE,
                UNIQUE(user_id, coupon_id)
            )
            """,
            """
            CREATE INDEX IF NOT EXISTS user_coupon_lookup
            ON user_coupons(user_id, status)
            """,
            """
            CREATE TABLE IF NOT EXISTS order_loyalty (
                order_id INTEGER PRIMARY KEY,
                original_amount_cents INTEGER NOT NULL,
                membership_discount_cents INTEGER NOT NULL DEFAULT 0,
                coupon_discount_cents INTEGER NOT NULL DEFAULT 0,
                final_amount_cents INTEGER NOT NULL DEFAULT 0,
                coupon_id INTEGER,
                points_earned INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY(order_id)
                    REFERENCES orders(id)
                    ON DELETE CASCADE
            )
            """,
        ]

    for statement in statements:
        db.execute(statement)

    for row in TIERS:
        if not db.execute(
            "SELECT 1 FROM membership_tiers WHERE tier_key=?",
            (row[0],),
        ).fetchone():
            db.execute(
                """
                INSERT INTO membership_tiers(
                    tier_key,
                    name,
                    description,
                    min_points,
                    discount_pct,
                    points_multiplier
                )
                VALUES(?,?,?,?,?,?)
                """,
                row,
            )

    for row in COUPONS:
        if not db.execute(
            "SELECT 1 FROM coupons WHERE code=?",
            (row[0],),
        ).fetchone():
            db.execute(
                """
                INSERT INTO coupons(
                    code,
                    name,
                    description,
                    discount_type,
                    discount_value,
                    min_spend_cents,
                    max_discount_cents,
                    points_cost,
                    total_limit,
                    expires_at,
                    active
                )
                VALUES(?,?,?,?,?,?,?,?,?,?,1)
                """,
                row,
            )


def _ensure_member(db, uid):
    row = db.execute(
        "SELECT * FROM member_accounts WHERE user_id=?",
        (uid,),
    ).fetchone()

    if row:
        return dict(row)

    timestamp = now()

    db.execute(
        """
        INSERT INTO member_accounts(
            user_id,
            tier_key,
            points_balance,
            lifetime_points,
            created_at,
            updated_at
        )
        VALUES(?,?,?,?,?,?)
        """,
        (
            uid,
            "bronze",
            0,
            0,
            timestamp,
            timestamp,
        ),
    )

    return dict(
        db.execute(
            "SELECT * FROM member_accounts WHERE user_id=?",
            (uid,),
        ).fetchone()
    )


def _tier(db, points):
    return dict(
        db.execute(
            """
            SELECT *
            FROM membership_tiers
            WHERE min_points<=?
            ORDER BY min_points DESC
            LIMIT 1
            """,
            (int(points),),
        ).fetchone()
    )


def _refresh_tier(db, uid):
    member = _ensure_member(db, uid)
    tier = _tier(db, member["lifetime_points"])

    if member["tier_key"] != tier["tier_key"]:
        db.execute(
            """
            UPDATE member_accounts
            SET tier_key=?, updated_at=?
            WHERE user_id=?
            """,
            (
                tier["tier_key"],
                now(),
                uid,
            ),
        )

    return (
        dict(
            db.execute(
                "SELECT * FROM member_accounts WHERE user_id=?",
                (uid,),
            ).fetchone()
        ),
        tier,
    )


def change_points(
    db,
    uid,
    amount,
    kind,
    note,
    order_id=None,
):
    member = _ensure_member(db, uid)

    new_balance = (
        int(member["points_balance"])
        + int(amount)
    )

    if new_balance < 0:
        raise BusinessError("积分不足")

    lifetime = (
        int(member["lifetime_points"])
        + max(0, int(amount))
    )

    db.execute(
        """
        UPDATE member_accounts
        SET
            points_balance=?,
            lifetime_points=?,
            updated_at=?
        WHERE user_id=?
        """,
        (
            new_balance,
            lifetime,
            now(),
            uid,
        ),
    )

    db.execute(
        """
        INSERT INTO points_ledger(
            user_id,
            amount,
            balance_after,
            kind,
            note,
            order_id,
            created_at
        )
        VALUES(?,?,?,?,?,?,?)
        """,
        (
            uid,
            int(amount),
            new_balance,
            kind,
            note,
            order_id,
            now(),
        ),
    )

    _refresh_tier(db, uid)

    return new_balance


def coupon_discount(coupon, amount):
    if amount < int(coupon["min_spend_cents"]):
        return 0

    if coupon["discount_type"] == "fixed":
        return min(
            amount,
            int(coupon["discount_value"]),
        )

    raw = int(
        (
            Decimal(amount)
            * Decimal(str(coupon["discount_value"]))
            / Decimal(100)
        ).quantize(
            Decimal("1"),
            rounding=ROUND_DOWN,
        )
    )

    cap = int(coupon["max_discount_cents"] or 0)

    if cap:
        return min(amount, raw, cap)

    return min(amount, raw)


def _eligible(db, uid, amount):
    rows = db.execute(
        """
        SELECT
            uc.id AS user_coupon_id,
            c.*
        FROM user_coupons uc
        JOIN coupons c
            ON c.id=uc.coupon_id
        WHERE
            uc.user_id=?
            AND uc.status='available'
            AND c.active=1
        """,
        (uid,),
    ).fetchall()

    result = []

    for row in rows:
        coupon = dict(row)

        if (
            coupon["expires_at"]
            and coupon["expires_at"] <= now()
        ):
            continue

        discount = coupon_discount(
            coupon,
            amount,
        )

        if discount:
            result.append(
                (
                    discount,
                    coupon,
                )
            )

    return sorted(
        result,
        key=lambda x: (
            x[0],
            x[1]["id"],
        ),
        reverse=True,
    )


def settle_with_loyalty(
    db,
    uid,
    order_id,
    quote_result,
    user_row,
    payload=None,
):
    payload = payload or {}

    original = int(
        quote_result["amount_cents"]
    )

    _member, tier = _refresh_tier(
        db,
        uid,
    )

    membership_discount = int(
        (
            Decimal(original)
            * Decimal(str(tier["discount_pct"]))
            / Decimal(100)
        ).quantize(
            Decimal("1"),
            rounding=ROUND_DOWN,
        )
    )

    after_member = max(
        0,
        original - membership_discount,
    )

    eligible = _eligible(
        db,
        uid,
        after_member,
    )

    chosen = None

    coupon_id_value = payload.get("coupon_id")

    if coupon_id_value not in (None, ""):
        try:
            requested = int(coupon_id_value)
        except (TypeError, ValueError):
            raise BusinessError("优惠券编号无效")

        chosen = next(
            (
                item
                for item in eligible
                if int(item[1]["id"]) == requested
            ),
            None,
        )

        if chosen is None:
            raise BusinessError("优惠券无效")
    coupon_id = None
    coupon_discount_cents = 0

    if chosen:
        coupon_discount_cents = int(
            chosen[0]
        )
        coupon_id = int(
            chosen[1]["id"]
        )

    final_amount = max(
        0,
        after_member - coupon_discount_cents,
    )

    balance = int(
        user_row["balance_cents"]
    )

    paid = min(
        balance,
        final_amount,
    )

    debt = final_amount - paid
    balance_after = balance - paid

    end = datetime.now().isoformat(
        timespec="seconds"
    )

    seconds = int(
        quote_result.get(
            "simulated_seconds",
            0,
        )
        or 0
    )

    db.execute(
        """
        UPDATE orders
        SET
            status='completed',
            ended_at=?,
            energy=?,
            amount_cents=?,
            paid_cents=?,
            debt_cents=?,
            balance_after=?,
            simulated_seconds=?
        WHERE id=?
        """,
        (
            end,
            quote_result["energy"],
            final_amount,
            paid,
            debt,
            balance_after,
            seconds,
            order_id,
        ),
    )

    db.execute(
        """
        UPDATE users
        SET balance_cents=balance_cents-?
        WHERE id=?
        """,
        (
            paid,
            uid,
        ),
    )

    if chosen:
        db.execute(
            """
            UPDATE user_coupons
            SET
                status='used',
                used_at=?,
                order_id=?
            WHERE
                id=?
                AND status='available'
            """,
            (
                end,
                order_id,
                int(
                    chosen[1]["user_coupon_id"]
                ),
            ),
        )

    db.execute(
        """
        UPDATE chargers
        SET
            status=CASE
                WHEN status='charging'
                THEN 'idle'
                ELSE status
            END,
            total_count=total_count+1,
            total_minutes=total_minutes+?
        WHERE id=?
        """,
        (
            seconds // 60,
            quote_result["charger_id"],
        ),
    )

    db.execute(
        """
        INSERT INTO wallet_log(
            user_id,
            amount_cents,
            kind,
            created_at
        )
        VALUES(?,?,'充电结算',?)
        """,
        (
            uid,
            -paid,
            now(),
        ),
    )

    points = (
        int(
            (
                Decimal(paid)
                / Decimal(100)
                * Decimal(
                    str(
                        tier[
                            "points_multiplier"
                        ]
                    )
                )
            ).quantize(
                Decimal("1"),
                rounding=ROUND_DOWN,
            )
        )
        if paid > 0
        else 0
    )

    if points:
        change_points(
            db,
            uid,
            points,
            "earn",
            "充电消费积分",
            order_id,
        )

    from .notifications import create_notification
    if debt > 0:
        create_notification(
            db,
            uid,
            'charging_completed',
            '充电完成',
            f'充电已完成，最终费用 ¥{final_amount / 100:.2f}，余额不足，需补缴 ¥{debt / 100:.2f}。',
            'warning',
            'order',
            order_id,
        )
    else:
        coupon_text = '，优惠券已使用' if coupon_id else ''
        create_notification(
            db,
            uid,
            'charging_completed',
            '充电完成',
            f'充电已完成，最终费用 ¥{final_amount / 100:.2f}{coupon_text}。',
            'success',
            'order',
            order_id,
        )

    db.execute(
        """
        INSERT INTO order_loyalty(
            order_id,
            original_amount_cents,
            membership_discount_cents,
            coupon_discount_cents,
            final_amount_cents,
            coupon_id,
            points_earned
        )
        VALUES(?,?,?,?,?,?,?)
        """,
        (
            order_id,
            original,
            membership_discount,
            coupon_discount_cents,
            final_amount,
            coupon_id,
            points,
        ),
    )


def summary(uid):
    db = get_db()

    member, tier = _refresh_tier(
        db,
        uid,
    )

    tiers = [
        dict(row)
        for row in db.execute(
            """
            SELECT *
            FROM membership_tiers
            ORDER BY min_points
            """
        ).fetchall()
    ]

    next_tier = next(
        (
            item
            for item in tiers
            if int(item["min_points"])
            > int(member["lifetime_points"])
        ),
        None,
    )

    if next_tier:
        base = int(tier["min_points"])
        target = int(
            next_tier["min_points"]
        )

        progress = max(
            0,
            min(
                100,
                round(
                    (
                        int(member["lifetime_points"])
                        - base
                    )
                    * 100
                    / max(1, target - base)
                ),
            ),
        )
    else:
        progress = 100

    return {
        "points_balance": int(
            member["points_balance"]
        ),
        "lifetime_points": int(
            member["lifetime_points"]
        ),
        "tier": tier,
        "next_tier": next_tier,
        "progress_pct": progress,
    }


def order_loyalty(order_id):
    row = get_db().execute(
        """
        SELECT
            ol.*,
            c.name AS coupon_name
        FROM order_loyalty ol
        LEFT JOIN coupons c
            ON c.id=ol.coupon_id
        WHERE ol.order_id=?
        """,
        (order_id,),
    ).fetchone()

    return dict(row) if row else None


@member_api.get("/member/summary")
@auth()
def member_summary():
    return jsonify(
        summary=summary(
            g.user["id"]
        )
    )


@member_api.get("/member/coupons")
@auth()
def member_coupons():
    db = get_db()
    uid = g.user["id"]

    current = summary(uid)
    points_balance = current["points_balance"]

    owned = db.execute(
        """
        SELECT
            uc.id AS user_coupon_id,
            uc.status,
            uc.claimed_at,
            uc.used_at,
            uc.order_id,
            c.*
        FROM user_coupons uc
        JOIN coupons c
            ON c.id=uc.coupon_id
        WHERE uc.user_id=?
        ORDER BY uc.id DESC
        """,
        (uid,),
    ).fetchall()

    available = db.execute(
        """
        SELECT c.*
        FROM coupons c
        LEFT JOIN user_coupons uc
            ON uc.coupon_id=c.id
            AND uc.user_id=?
        WHERE
            c.active=1
            AND uc.id IS NULL
        ORDER BY c.points_cost,c.id
        """,
        (uid,),
    ).fetchall()

    def normalize(row):
        data = dict(row)

        for key in (
            "discount_value",
            "min_spend_cents",
            "max_discount_cents",
            "points_cost",
        ):
            data[key] = int(data[key])

        return data

    return jsonify(
        owned=[
            normalize(row)
            for row in owned
            if row["status"] == "available"
        ],
        available=[
            {
                **normalize(row),
                "affordable":
                    points_balance
                    >= int(row["points_cost"]),
            }
            for row in available
            if (
                not row["expires_at"]
                or row["expires_at"] > now()
            )
        ],
    )


@member_api.post(
    "/member/coupons/<int:coupon_id>/claim"
)
@auth()
def claim_coupon(coupon_id):
    uid = g.user["id"]

    with transaction() as db:
        coupon = db.execute(
            lock_sql(
                "SELECT * FROM coupons WHERE id=?"
            ),
            (coupon_id,),
        ).fetchone()

        if not coupon or not coupon["active"]:
            raise BusinessError(
                "优惠券不存在或已失效",
                404,
            )

        if (
            coupon["expires_at"]
            and coupon["expires_at"] <= now()
        ):
            raise BusinessError(
                "优惠券已失效"
            )

        if (
            int(coupon["total_limit"] or 0) > 0
            and int(coupon["claimed_count"])
            >= int(coupon["total_limit"])
        ):
            raise BusinessError(
                "优惠券已领完"
            )

        if db.execute(
            """
            SELECT 1
            FROM user_coupons
            WHERE user_id=? AND coupon_id=?
            """,
            (
                uid,
                coupon_id,
            ),
        ).fetchone():
            raise BusinessError(
                "你已经领取过该优惠券"
            )

        cost = int(
            coupon["points_cost"]
        )

        if cost:
            change_points(
                db,
                uid,
                -cost,
                "redeem",
                f'兑换优惠券 {coupon["name"]}',
            )

        db.execute(
            """
            INSERT INTO user_coupons(
                user_id,
                coupon_id,
                status,
                claimed_at
            )
            VALUES(?,?,'available',?)
            """,
            (
                uid,
                coupon_id,
                now(),
            ),
        )

        db.execute(
            """
            UPDATE coupons
            SET claimed_count=claimed_count+1
            WHERE id=?
            """,
            (coupon_id,),
        )

        from .notifications import create_notification
        expiry = coupon['expires_at']
        expiry_text = f' 有效期至 {expiry}。' if expiry else ''
        create_notification(
            db,
            uid,
            'coupon_available',
            '优惠券已到账',
            f'你已领取「{coupon["name"]}」充电优惠券。{expiry_text}',
            'success',
            'coupon',
            coupon_id,
        )

    return jsonify(ok=True)


@member_api.get("/member/points")
@auth()
def member_points():
    rows = get_db().execute(
        """
        SELECT *
        FROM points_ledger
        WHERE user_id=?
        ORDER BY id DESC
        LIMIT 100
        """,
        (g.user["id"],),
    ).fetchall()

    return jsonify(
        items=[
            dict(row)
            for row in rows
        ]
    )
