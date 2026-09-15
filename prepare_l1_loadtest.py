"""
Prepare or clean deterministic L1 load-test users.

This version uses the application's configured database,
so it works with both MySQL and SQLite.

Usage:

    python prepare_l1_loadtest.py --prepare
    python prepare_l1_loadtest.py --cleanup
"""

from __future__ import annotations

import argparse

from werkzeug.security import generate_password_hash

from ncs import create_app
from ncs.db import get_db, now


PASSWORD = "LoadTest123456"
PHONE_PREFIX = "18800000"
USERS = 100


def phone_for(index):
    return f"{PHONE_PREFIX}{index:03d}"


def prepare():
    app = create_app()

    with app.app_context():
        db = get_db()

        stations = db.execute(
            "SELECT COUNT(*) AS n FROM stations"
        ).fetchone()["n"]

        chargers = db.execute(
            "SELECT COUNT(*) AS n FROM chargers"
        ).fetchone()["n"]

        if stations < 10:
            raise SystemExit(
                "当前充电站数量不足 10，"
                "请先完成 L1 网络数据初始化。"
            )

        if chargers < 100:
            raise SystemExit(
                f"当前只有 {chargers} 台电桩，"
                "需要至少 100 台。"
            )

        created = 0
        updated = 0

        for i in range(
            1,
            USERS + 1,
        ):
            phone = phone_for(i)

            existing = db.execute(
                """
                SELECT id
                FROM users
                WHERE phone=?
                """,
                (phone,),
            ).fetchone()

            if existing:
                db.execute(
                    """
                    UPDATE users
                    SET
                        balance_cents=?,
                        active=1
                    WHERE id=?
                    """,
                    (
                        100000,
                        existing["id"],
                    ),
                )

                updated += 1

            else:
                db.execute(
                    """
                    INSERT INTO users(
                        phone,
                        nickname,
                        password_hash,
                        role,
                        balance_cents,
                        active,
                        created_at
                    )
                    VALUES(
                        ?, ?, ?, 'user',
                        ?, 1, ?
                    )
                    """,
                    (
                        phone,
                        f"L1-LAB-{i:03d}",
                        generate_password_hash(
                            PASSWORD
                        ),
                        100000,
                        now(),
                    ),
                )

                created += 1

        # Restore available state for test chargers
        # that are not actually occupied.
        db.execute(
            """
            UPDATE chargers
            SET status='idle'
            WHERE id<=100
              AND status IN (
                  'charging',
                  'reserved'
              )
              AND id NOT IN (
                  SELECT charger_id
                  FROM orders
                  WHERE status IN (
                      'charging',
                      'reserved'
                  )
              )
            """
        )

        db.commit()

        count = db.execute(
            """
            SELECT COUNT(*) AS n
            FROM users
            WHERE phone LIKE ?
            """,
            (
                PHONE_PREFIX + "%",
            ),
        ).fetchone()["n"]

        print()
        print(
            "Database backend:",
            app.config[
                "DB_BACKEND"
            ],
        )

        print(
            f"Created: {created}"
        )

        print(
            f"Updated: {updated}"
        )

        print(
            f"Load-test users now: {count}"
        )

        print(
            "Password:",
            PASSWORD,
        )


def cleanup():
    app = create_app()

    with app.app_context():
        db = get_db()

        rows = db.execute(
            """
            SELECT id
            FROM users
            WHERE phone LIKE ?
            """,
            (
                PHONE_PREFIX + "%",
            ),
        ).fetchall()

        ids = [
            row["id"]
            for row in rows
        ]

        if not ids:
            print(
                "No L1 load-test users found."
            )
            return

        marks = ",".join(
            "?"
            for _ in ids
        )

        # Close active test orders first.
        db.execute(
            f"""
            UPDATE orders
            SET
                status='cancelled',
                ended_at=?
            WHERE user_id IN ({marks})
              AND status IN (
                  'reserved',
                  'charging'
              )
            """,
            (
                now(),
                *ids,
            ),
        )

        db.execute(
            f"""
            DELETE FROM wallet_log
            WHERE user_id IN ({marks})
            """,
            tuple(ids),
        )

        db.execute(
            f"""
            DELETE FROM orders
            WHERE user_id IN ({marks})
            """,
            tuple(ids),
        )

        db.execute(
            f"""
            DELETE FROM users
            WHERE id IN ({marks})
            """,
            tuple(ids),
        )

        db.execute(
            """
            UPDATE chargers
            SET status='idle'
            WHERE id<=100
              AND status IN (
                  'charging',
                  'reserved'
              )
              AND id NOT IN (
                  SELECT charger_id
                  FROM orders
                  WHERE status IN (
                      'charging',
                      'reserved'
                  )
              )
            """
        )

        db.commit()

        print(
            f"Cleaned {len(ids)} "
            "L1 load-test users."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    group = (
        parser
        .add_mutually_exclusive_group(
            required=True
        )
    )

    group.add_argument(
        "--prepare",
        action="store_true",
    )

    group.add_argument(
        "--cleanup",
        action="store_true",
    )

    args = parser.parse_args()

    if args.prepare:
        prepare()
    else:
        cleanup()