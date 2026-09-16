from datetime import datetime, timedelta

from ncs import create_app
from ncs.db import get_db
from ncs.services import create_order, act_order

app = create_app({
    "TESTING": True,
    "DB_BACKEND": "sqlite",
    "DATABASE": "data/loyalty_test.db",
})

with app.app_context():
    db = get_db()

    user = db.execute(
        "SELECT id, balance_cents FROM users WHERE phone='13800138000'"
    ).fetchone()

    charger = db.execute(
        """
        SELECT c.id, c.number
        FROM chargers c
        WHERE c.status='idle'
        ORDER BY c.id
        LIMIT 1
        """
    ).fetchone()

    assert user is not None
    assert charger is not None

    oid = create_order(user["id"], charger["id"], False)

    started = (
        datetime.now() - timedelta(minutes=10)
    ).isoformat(timespec="seconds")

    db.execute(
        "UPDATE orders SET started_at=? WHERE id=?",
        (started, oid),
    )
    db.commit()

    act_order(
        user["id"],
        oid,
        "finish",
        {},
    )

    order = db.execute(
        """
        SELECT
            id,
            status,
            amount_cents,
            paid_cents,
            debt_cents,
            energy,
            simulated_seconds
        FROM orders
        WHERE id=?
        """,
        (oid,),
    ).fetchone()

    member = db.execute(
        """
        SELECT
            tier_key,
            points_balance,
            lifetime_points
        FROM member_accounts
        WHERE user_id=?
        """,
        (user["id"],),
    ).fetchone()

    loyalty = db.execute(
        """
        SELECT
            original_amount_cents,
            membership_discount_cents,
            coupon_discount_cents,
            final_amount_cents,
            coupon_id,
            points_earned
        FROM order_loyalty
        WHERE order_id=?
        """,
        (oid,),
    ).fetchone()

    print("ORDER:", dict(order))
    print("MEMBER:", dict(member))
    print("LOYALTY:", dict(loyalty))

    assert order["status"] == "completed"
    assert order["simulated_seconds"] > 0
    assert order["energy"] > 0
    assert order["amount_cents"] > 0

    assert loyalty["original_amount_cents"] > 0
    assert loyalty["final_amount_cents"] > 0
    assert loyalty["coupon_id"] is None
    assert loyalty["membership_discount_cents"] == 0
    assert loyalty["coupon_discount_cents"] == 0
    assert loyalty["points_earned"] > 0

    assert member["points_balance"] == loyalty["points_earned"]
    assert member["lifetime_points"] == loyalty["points_earned"]

    print("\nNON-ZERO LOYALTY SETTLEMENT OK")
