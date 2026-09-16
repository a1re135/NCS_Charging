"""Business regression tests using an isolated MySQL test database."""

import os
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

import pymysql
from dotenv import load_dotenv

from ncs import create_app
from ncs.db import get_db


# =========================================================
# Test database configuration
# =========================================================

ROOT = Path(
    __file__
).resolve().parent.parent

load_dotenv(
    ROOT / ".env"
)


def get_test_database_config():
    """
    Return the MySQL configuration used only by automated tests.

    The test suite MUST NEVER use the normal application database.
    """

    host = os.getenv(
        "MYSQL_HOST",
        "localhost",
    )

    port = int(
        os.getenv(
            "MYSQL_PORT",
            "3306",
        )
    )

    user = os.getenv(
        "MYSQL_USER",
        "ncs_app",
    )

    password = os.getenv(
        "MYSQL_PASSWORD",
        "",
    )

    normal_database = os.getenv(
        "MYSQL_DATABASE",
        "ncs_charging",
    )

    test_database = os.getenv(
        "MYSQL_TEST_DATABASE",
        "ncs_charging_test",
    )

    # -----------------------------------------------------
    # VERY IMPORTANT SAFETY CHECK
    # -----------------------------------------------------

    if test_database == normal_database:
        raise RuntimeError(
            "MYSQL_TEST_DATABASE must not be the same "
            "as MYSQL_DATABASE."
        )

    if not test_database.lower().endswith(
        "_test"
    ):
        raise RuntimeError(
            "Refusing to run destructive tests because "
            "MYSQL_TEST_DATABASE does not end with '_test'. "
            f"Current value: {test_database}"
        )

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "database": test_database,
        "charset": "utf8mb4",
        "autocommit": True,
    }


def reset_test_database():
    """
    Drop every table from the dedicated MySQL test database.

    create_app() will recreate the schema and seed demo data
    immediately afterwards.
    """

    config = get_test_database_config()

    try:
        connection = pymysql.connect(
            **config
        )
    except pymysql.err.OperationalError as exc:
        raise RuntimeError(
            "\nUnable to connect to the MySQL test database.\n\n"
            "Make sure the database exists:\n\n"
            "    ncs_charging_test\n\n"
            "and make sure MYSQL_TEST_DATABASE, MYSQL_USER and "
            "MYSQL_PASSWORD are correct in .env.\n"
        ) from exc

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                "SET FOREIGN_KEY_CHECKS=0"
            )

            cursor.execute(
                "SHOW FULL TABLES "
                "WHERE Table_type = 'BASE TABLE'"
            )

            tables = [
                row[0]
                for row in cursor.fetchall()
            ]

            for table in tables:
                safe_table = (
                    str(table)
                    .replace(
                        "`",
                        "``",
                    )
                )

                cursor.execute(
                    f"DROP TABLE IF EXISTS `{safe_table}`"
                )

            cursor.execute(
                "SET FOREIGN_KEY_CHECKS=1"
            )

    finally:
        connection.close()


# =========================================================
# Workflow tests
# =========================================================

class WorkflowTests(
    unittest.TestCase
):

    def setUp(self):
        """
        Every test starts with a completely fresh MySQL database.

        This guarantees that one test cannot affect another test.
        """

        reset_test_database()

        mysql = get_test_database_config()

        self.app = create_app(
            {
                "TESTING": True,
                "SECRET_KEY": "test-only",

                "MYSQL_HOST": mysql[
                    "host"
                ],

                "MYSQL_PORT": mysql[
                    "port"
                ],

                "MYSQL_DATABASE": mysql[
                    "database"
                ],

                "MYSQL_USER": mysql[
                    "user"
                ],

                "MYSQL_PASSWORD": mysql[
                    "password"
                ],
            }
        )

        self.client, self.token = (
            self.login(
                "13800138000",
                "User123456",
            )
        )

    # =====================================================
    # Helpers
    # =====================================================

    def login(
        self,
        user,
        pw,
    ):
        client = (
            self.app.test_client()
        )

        token = client.get(
            "/api/session"
        ).json["csrf"]

        response = client.post(
            "/api/login",
            json={
                "phone": user,
                "password": pw,
            },
            headers={
                "X-CSRF-Token": token
            },
        )

        self.assertEqual(
            response.status_code,
            200,
            response.json,
        )

        return (
            client,
            response.json[
                "csrf"
            ],
        )

    def post(
        self,
        path,
        data=None,
        client=None,
        token=None,
    ):
        return (
            client
            or self.client
        ).post(
            "/api" + path,
            json=(
                data
                or {}
            ),
            headers={
                "X-CSRF-Token":
                    token
                    or self.token
            },
        )

    def sql(
        self,
        query,
        args=(),
    ):
        with self.app.app_context():
            return (
                get_db()
                .execute(
                    query,
                    args,
                )
                .fetchall()
            )

    def start(
        self,
        cid=1,
        mode="start",
    ):
        response = self.post(
            "/orders",
            {
                "charger_id": cid,
                "mode": mode,
            },
        )

        self.assertEqual(
            response.status_code,
            201,
            response.json,
        )

        return response.json[
            "id"
        ]

    def age(
        self,
        oid,
        seconds=60,
    ):
        started_at = (
            datetime.now()
            - timedelta(
                seconds=seconds
            )
        ).isoformat(
            timespec="seconds"
        )

        self.sql(
            """
            UPDATE orders
            SET started_at=?
            WHERE id=?
            """,
            (
                started_at,
                oid,
            ),
        )

    # =====================================================
    # User/profile/wallet
    # =====================================================

    def test_profile_and_exact_recharge_persist_across_login(
        self
    ):
        self.assertEqual(
            self.post(
                "/profile",
                {
                    "nickname":
                        "新昵称",
                    "avatar":
                        "pink",
                },
            ).status_code,
            200,
        )

        for _ in range(10):
            self.assertEqual(
                self.post(
                    "/wallet/recharge",
                    {
                        "amount":
                            "0.10"
                    },
                ).status_code,
                200,
            )

        client, _ = self.login(
            "13800138000",
            "User123456",
        )

        user = client.get(
            "/api/session"
        ).json[
            "user"
        ]

        self.assertEqual(
            user["nickname"],
            "新昵称",
        )

        self.assertEqual(
            user["avatar"],
            "pink",
        )

        self.assertEqual(
            user["balance_cents"],
            28900,
        )

    def test_invalid_money_and_csrf(
        self
    ):
        for value in (
            "NaN",
            "Infinity",
            -1,
            0,
            "1.001",
            100001,
        ):
            self.assertEqual(
                self.post(
                    "/wallet/recharge",
                    {
                        "amount":
                            value
                    },
                ).status_code,
                400,
            )

        self.assertEqual(
            self.client.post(
                "/api/wallet/recharge",
                json={
                    "amount":
                        100
                },
            ).status_code,
            403,
        )

        balance = self.sql(
            """
            SELECT balance_cents
            FROM users
            WHERE id=1
            """
        )[0][0]

        self.assertEqual(
            balance,
            28800,
        )

    # =====================================================
    # Reservation / charging / settlement
    # =====================================================

    def test_reservation_exclusion_and_cancel(
        self
    ):
        oid = self.start(
            mode="reserve"
        )

        response = self.post(
            "/orders",
            {
                "charger_id": 2,
                "mode": "start",
            },
        )

        self.assertEqual(
            response.status_code,
            409,
        )

        self.assertEqual(
            response.json[
                "order_id"
            ],
            oid,
        )

        client, token = self.login(
            "13900139000",
            "User123456",
        )

        self.assertEqual(
            self.post(
                "/orders",
                {
                    "charger_id": 1,
                    "mode": "reserve",
                },
                client,
                token,
            ).status_code,
            409,
        )

        self.assertEqual(
            self.post(
                f"/orders/{oid}/cancel"
            ).status_code,
            200,
        )

        status = self.sql(
            """
            SELECT status
            FROM chargers
            WHERE id=1
            """
        )[0][0]

        self.assertEqual(
            status,
            "idle",
        )

    def test_expiration_releases_charger(
        self
    ):
        oid = self.start(
            mode="reserve"
        )

        self.sql(
            """
            UPDATE orders
            SET expires_at=?
            WHERE id=?
            """,
            (
                "2000-01-01T00:00:00",
                oid,
            ),
        )

        self.client.get(
            "/api/stations"
        )

        status = self.sql(
            """
            SELECT status
            FROM orders
            WHERE id=?
            """,
            (
                oid,
            ),
        )[0][0]

        self.assertEqual(
            status,
            "expired",
        )

        charger_status = self.sql(
            """
            SELECT status
            FROM chargers
            WHERE id=1
            """
        )[0][0]

        self.assertEqual(
            charger_status,
            "idle",
        )

    def test_settlement_snapshots_and_no_double_charge(
        self
    ):
        oid = self.start(
            mode="reserve"
        )

        self.assertEqual(
            self.post(
                f"/orders/{oid}/start"
            ).status_code,
            200,
        )

        snapshot = self.sql(
            """
            SELECT
                price_cents,
                power
            FROM orders
            WHERE id=?
            """,
            (
                oid,
            ),
        )[0]

        self.age(
            oid
        )

        self.sql(
            """
            UPDATE stations
            SET price_cents=999
            WHERE id=1
            """
        )

        self.sql(
            """
            UPDATE pricing_rules
            SET electricity_fee_cents=999
            WHERE station_id=1
            """
        )

        self.sql(
            """
            UPDATE chargers
            SET power=999
            WHERE id=1
            """
        )

        response = self.post(
            f"/orders/{oid}/finish"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        order = response.json[
            "order"
        ]

        self.assertEqual(
            order[
                "price_cents"
            ],
            snapshot[
                "price_cents"
            ],
        )

        self.assertEqual(
            order["power"],
            snapshot["power"],
        )

        self.assertTrue(
            (
                60
                * snapshot[
                    "price_cents"
                ]
                <= order[
                    "amount_cents"
                ]
                <= 64
                * snapshot[
                    "price_cents"
                ]
            ),
            order,
        )

        balance = self.sql(
            """
            SELECT balance_cents
            FROM users
            WHERE id=1
            """
        )[0][0]

        self.assertEqual(
            self.post(
                f"/orders/{oid}/finish"
            ).status_code,
            409,
        )

        balance_after = self.sql(
            """
            SELECT balance_cents
            FROM users
            WHERE id=1
            """
        )[0][0]

        self.assertEqual(
            balance_after,
            balance,
        )

    def test_debt_repayment_and_new_order_block(
        self
    ):
        self.sql(
            """
            UPDATE users
            SET balance_cents=1
            WHERE id=1
            """
        )

        oid = self.start()

        self.age(
            oid
        )

        self.assertEqual(
            self.post(
                f"/orders/{oid}/finish"
            ).status_code,
            200,
        )

        debt = self.sql(
            """
            SELECT debt_cents
            FROM orders
            WHERE id=?
            """,
            (
                oid,
            ),
        )[0][0]

        self.assertGreater(
            debt,
            0,
        )

        self.assertEqual(
            self.post(
                "/orders",
                {
                    "charger_id": 2,
                    "mode": "start",
                },
            ).status_code,
            409,
        )

        self.assertEqual(
            self.post(
                f"/orders/{oid}/pay"
            ).status_code,
            400,
        )

        self.post(
            "/wallet/recharge",
            {
                "amount": 200
            },
        )

        self.assertEqual(
            self.post(
                f"/orders/{oid}/pay"
            ).status_code,
            200,
        )

        self.assertEqual(
            self.post(
                f"/orders/{oid}/pay"
            ).status_code,
            409,
        )

        debt = self.sql(
            """
            SELECT debt_cents
            FROM orders
            WHERE id=?
            """,
            (
                oid,
            ),
        )[0][0]

        self.assertEqual(
            debt,
            0,
        )

    # =====================================================
    # Security / ownership
    # =====================================================

    def test_authorization_and_ownership(
        self
    ):
        self.assertEqual(
            self.client.get(
                "/api/admin/users"
            ).status_code,
            403,
        )

        oid = self.start()

        client, token = self.login(
            "13900139000",
            "User123456",
        )

        self.assertEqual(
            client.get(
                f"/api/orders/{oid}/receipt"
            ).status_code,
            404,
        )

        self.assertEqual(
            self.post(
                f"/orders/{oid}/finish",
                client=client,
                token=token,
            ).status_code,
            404,
        )

    # =====================================================
    # Concurrency
    # =====================================================

    def test_concurrent_users_cannot_claim_same_charger(
        self
    ):
        client, token = self.login(
            "13900139000",
            "User123456",
        )

        with ThreadPoolExecutor(
            max_workers=2
        ) as pool:

            jobs = [
                pool.submit(
                    self.post,
                    "/orders",
                    {
                        "charger_id": 1,
                        "mode": "reserve",
                    },
                    request_client,
                    request_token,
                )
                for (
                    request_client,
                    request_token,
                )
                in [
                    (
                        self.client,
                        self.token,
                    ),
                    (
                        client,
                        token,
                    ),
                ]
            ]

            codes = sorted(
                job.result().status_code
                for job in jobs
            )

        self.assertEqual(
            codes,
            [
                201,
                409,
            ],
        )

        count = self.sql(
            """
            SELECT COUNT(*)
            FROM orders
            WHERE charger_id=1
              AND status='reserved'
            """
        )[0][0]

        self.assertEqual(
            count,
            1,
        )

    def test_concurrent_settlement_only_once(
        self
    ):
        oid = self.start()

        self.age(
            oid
        )

        client, token = self.login(
            "13800138000",
            "User123456",
        )

        with ThreadPoolExecutor(
            max_workers=2
        ) as pool:

            jobs = [
                pool.submit(
                    self.post,
                    f"/orders/{oid}/finish",
                    None,
                    request_client,
                    request_token,
                )
                for (
                    request_client,
                    request_token,
                )
                in [
                    (
                        self.client,
                        self.token,
                    ),
                    (
                        client,
                        token,
                    ),
                ]
            ]

            self.assertEqual(
                sorted(
                    job.result().status_code
                    for job in jobs
                ),
                [
                    200,
                    409,
                ],
            )

        count = self.sql(
            """
            SELECT COUNT(*)
            FROM wallet_log
            WHERE user_id=1
              AND kind='充电结算'
            """
        )[0][0]

        self.assertEqual(
            count,
            1,
        )

    # =====================================================
    # Admin
    # =====================================================

    def test_admin_crud_and_active_device_protection(
        self
    ):
        admin, token = self.login(
            "admin",
            "Admin123456",
        )

        station_data = {
            "name": "测试站",
            "address": "测试地址",
            "lng": 116,
            "lat": 39,
            "price": 1.2,
        }

        response = self.post(
            "/admin/stations",
            station_data,
            admin,
            token,
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        sid = response.json[
            "id"
        ]

        response = self.post(
            "/admin/chargers",
            {
                "station_id": sid,
                "number": "TEST-01",
                "kind": "fast",
                "power": 60,
            },
            admin,
            token,
        )

        self.assertEqual(
            response.status_code,
            200,
            response.json,
        )

        cid = response.json[
            "id"
        ]

        oid = self.start(
            cid
        )

        self.assertEqual(
            self.post(
                f"/admin/chargers/{cid}/action",
                {
                    "action":
                        "fault"
                },
                admin,
                token,
            ).status_code,
            409,
        )

        self.post(
            f"/orders/{oid}/finish"
        )

        self.assertEqual(
            self.post(
                f"/admin/chargers/{cid}/action",
                {
                    "action":
                        "delete"
                },
                admin,
                token,
            ).status_code,
            409,
        )

        self.assertEqual(
            self.post(
                f"/admin/chargers/{cid}/action",
                {
                    "action":
                        "fault"
                },
                admin,
                token,
            ).status_code,
            200,
        )

        self.assertEqual(
            self.post(
                f"/admin/chargers/{cid}/action",
                {
                    "action":
                        "restart"
                },
                admin,
                token,
            ).status_code,
            200,
        )

        self.assertGreater(
            len(
                admin.get(
                    "/api/admin/logs"
                ).json
            ),
            0,
        )

    def test_frozen_user_can_recharge_repay_but_not_new_order(
        self
    ):
        oid = self.start()

        admin, token = self.login(
            "admin",
            "Admin123456",
        )

        self.post(
            "/admin/users/1",
            {
                "active": False
            },
            admin,
            token,
        )

        self.assertEqual(
            self.post(
                "/orders",
                {
                    "charger_id": 2,
                    "mode": "start",
                },
            ).status_code,
            403,
        )

        self.sql(
            """
            UPDATE users
            SET balance_cents=1
            WHERE id=1
            """
        )

        self.age(
            oid,
            10,
        )

        self.assertEqual(
            self.post(
                f"/orders/{oid}/finish"
            ).status_code,
            200,
        )

        debt = self.sql(
            """
            SELECT debt_cents
            FROM orders
            WHERE id=?
            """,
            (
                oid,
            ),
        )[0][0]

        self.assertGreater(
            debt,
            0,
        )

        self.assertEqual(
            self.post(
                "/wallet/recharge",
                {
                    "amount":
                        200
                },
            ).status_code,
            200,
        )

        self.assertEqual(
            self.post(
                f"/orders/{oid}/pay"
            ).status_code,
            200,
        )

        debt = self.sql(
            """
            SELECT debt_cents
            FROM orders
            WHERE id=?
            """,
            (
                oid,
            ),
        )[0][0]

        self.assertEqual(
            debt,
            0,
        )

        self.assertEqual(
            self.post(
                "/orders",
                {
                    "charger_id": 2,
                    "mode": "start",
                },
            ).status_code,
            403,
        )

    # =====================================================
    # Registration / prediction / filters
    # =====================================================

    def test_registration_prediction_export_and_sort(
        self
    ):
        client = (
            self.app.test_client()
        )

        token = client.get(
            "/api/session"
        ).json[
            "csrf"
        ]

        response = self.post(
            "/register",
            {
                "phone":
                    "13700137000",
                "nickname":
                    "新同学",
                "password":
                    "New123456",
            },
            client,
            token,
        )

        self.assertEqual(
            response.status_code,
            201,
        )

        stations = self.client.get(
            "/api/stations"
            "?lat=39.9219"
            "&lng=116.4435"
        ).json

        self.assertEqual(
            stations[0]["id"],
            3,
        )

        admin, token = self.login(
            "admin",
            "Admin123456",
        )

        prediction = admin.get(
            "/api/admin/prediction"
            "?station_id=1"
        ).json

        self.assertEqual(
            len(
                prediction[
                    "points"
                ]
            ),
            12,
        )

        self.assertGreater(
            prediction[
                "sample_count"
            ],
            0,
        )

        response = admin.get(
            "/api/admin/export"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertTrue(
            response.data.startswith(
                b"\xef\xbb\xbf"
            )
        )

    def test_charger_maintenance_and_offline_status(
        self
    ):
        admin, token = self.login(
            "admin",
            "Admin123456",
        )

        for operation in (
            "maintenance",
            "offline",
        ):
            self.assertEqual(
                self.post(
                    "/admin/chargers/1/action",
                    {
                        "action":
                            operation
                    },
                    admin,
                    token,
                ).status_code,
                200,
            )

            status = self.sql(
                """
                SELECT status
                FROM chargers
                WHERE id=1
                """
            )[0][0]

            self.assertEqual(
                status,
                operation,
            )

            self.assertEqual(
                self.post(
                    "/orders",
                    {
                        "charger_id": 1,
                        "mode": "start",
                    },
                ).status_code,
                409,
            )

        self.assertEqual(
            self.post(
                "/admin/chargers/1/action",
                {
                    "action":
                        "restore"
                },
                admin,
                token,
            ).status_code,
            200,
        )

        status = self.sql(
            """
            SELECT status
            FROM chargers
            WHERE id=1
            """
        )[0][0]

        self.assertEqual(
            status,
            "idle",
        )

        self.assertEqual(
            self.post(
                "/admin/chargers/1/action",
                {
                    "action":
                        "bad-op"
                },
                admin,
                token,
            ).status_code,
            400,
        )

    def test_station_filters_and_usage_sort(
        self
    ):
        response = self.client.get(
            "/api/stations?status=idle"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertTrue(
            response.json
        )

        for station in response.json:
            self.assertGreater(
                station["free"],
                0,
            )

        response = self.client.get(
            "/api/stations"
            "?status=maintenance"
        )

        self.assertTrue(
            response.json
        )

        for station in response.json:
            self.assertGreater(
                station[
                    "maintenance"
                ],
                0,
            )

        response = self.client.get(
            "/api/stations"
            "?status=offline"
        )

        self.assertTrue(
            response.json
        )

        for station in response.json:
            self.assertGreater(
                station[
                    "offline"
                ],
                0,
            )

        response = self.client.get(
            "/api/stations?kind=fast"
        )

        self.assertTrue(
            all(
                station["fast"] > 0
                for station
                in response.json
            )
        )

        response = self.client.get(
            "/api/stations?kind=slow"
        )

        self.assertTrue(
            all(
                station["slow"] > 0
                for station
                in response.json
            )
        )

        response = self.client.get(
            "/api/stations?sort=usage"
        )

        usages = [
            station["usage"]
            for station
            in response.json
        ]

        self.assertEqual(
            usages,
            sorted(
                usages,
                reverse=True,
            ),
        )

        response = self.client.get(
            "/api/stations?sort=price"
        )

        prices = [
            station["current_price_cents"]
            for station
            in response.json
        ]

        self.assertEqual(
            prices,
            sorted(prices),
        )

        response = self.client.get(
            "/api/stations?sort=price_desc"
        )

        prices = [
            station["current_price_cents"]
            for station
            in response.json
        ]

        self.assertEqual(
            prices,
            sorted(
                prices,
                reverse=True,
            ),
        )

        for bad in (
            "status=bad",
            "kind=bad",
            "sort=bad",
        ):
            self.assertEqual(
                self.client.get(
                    "/api/stations?"
                    + bad
                ).status_code,
                400,
            )

    # =====================================================
    # Orders / dates
    # =====================================================

    def test_order_date_filter_and_export(
        self
    ):
        self.start()

        today = (
            datetime.now()
            .strftime(
                "%Y-%m-%d"
            )
        )

        response = self.client.get(
            "/api/orders"
            "?date_from="
            + today
            + "&date_to="
            + today
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        for order in response.json:
            self.assertEqual(
                order[
                    "created_at"
                ][
                    :10
                ],
                today,
            )

        self.assertEqual(
            self.client.get(
                "/api/orders"
                "?date_from=2000-01-01"
                "&date_to=2000-01-02"
            ).json,
            [],
        )

        self.assertEqual(
            self.client.get(
                "/api/orders"
                "?date_from=bad"
            ).status_code,
            400,
        )

        self.assertEqual(
            self.client.get(
                "/api/orders"
                "?date_from=2026-01-02"
                "&date_to=2026-01-01"
            ).status_code,
            400,
        )

        admin, token = self.login(
            "admin",
            "Admin123456",
        )

        response = admin.get(
            "/api/admin/export"
            "?date_from="
            + today
            + "&date_to="
            + today
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertTrue(
            response.data.startswith(
                b"\xef\xbb\xbf"
            )
        )

    # =====================================================
    # Users / RBAC
    # =====================================================

    def test_admin_user_status_filters_and_sort(
        self
    ):
        admin, token = self.login(
            "admin",
            "Admin123456",
        )

        response = admin.get(
            "/api/admin/users"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        user3 = next(
            user
            for user
            in response.json
            if user["id"] == 3
        )

        self.assertGreater(
            user3[
                "debt_cents"
            ],
            0,
        )

        response = admin.get(
            "/api/admin/users"
            "?status=debt"
        )

        for user in response.json:
            self.assertGreater(
                user[
                    "debt_cents"
                ],
                0,
            )

        response = admin.get(
            "/api/admin/users"
            "?status=normal"
        )

        for user in response.json:
            self.assertEqual(
                user[
                    "debt_cents"
                ],
                0,
            )

            self.assertEqual(
                user[
                    "active"
                ],
                1,
            )

        self.post(
            "/admin/users/1",
            {
                "active": False
            },
            admin,
            token,
        )

        response = admin.get(
            "/api/admin/users"
            "?status=frozen"
        )

        self.assertTrue(
            any(
                user["id"] == 1
                for user
                in response.json
            )
        )

        self.sql(
            """
            UPDATE users
            SET created_at=?
            WHERE id=3
            """,
            (
                "2025-06-01T10:00:00",
            ),
        )

        response = admin.get(
            "/api/admin/users"
            "?sort=oldest"
        )

        self.assertEqual(
            response.json[0][
                "id"
            ],
            3,
        )

        response = admin.get(
            "/api/admin/users"
            "?sort=newest"
        )

        self.assertNotEqual(
            response.json[0][
                "id"
            ],
            3,
        )

        response = admin.get(
            "/api/admin/users"
            "?date_from=2099-01-01"
            "&date_to=2099-12-31"
        )

        self.assertEqual(
            response.json,
            [],
        )

        self.assertEqual(
            admin.get(
                "/api/admin/users"
                "?status=bad"
            ).status_code,
            400,
        )

        self.assertEqual(
            admin.get(
                "/api/admin/users"
                "?sort=bad"
            ).status_code,
            400,
        )

        self.assertEqual(
            admin.get(
                "/api/admin/users"
                "?date_from=2026-02-02"
                "&date_to=2026-02-01"
            ).status_code,
            400,
        )

    def test_rbac_has_four_roles_and_enforces_permissions(
        self
    ):
        with self.app.app_context():
            roles = (
                get_db()
                .execute(
                    """
                    SELECT `key`
                    FROM roles
                    ORDER BY level
                    """
                )
                .fetchall()
            )

            self.assertEqual(
                [
                    role["key"]
                    for role
                    in roles
                ],
                [
                    "user",
                    "operator",
                    "technician",
                    "admin",
                ],
            )

        operator, token = self.login(
            "operator",
            "Operator123456",
        )

        self.assertEqual(
            operator.get(
                "/api/session"
            ).json[
                "user"
            ][
                "role_name"
            ],
            "运营人员",
        )

        self.assertEqual(
            operator.get(
                "/api/admin/users"
            ).status_code,
            403,
        )

        self.assertEqual(
            operator.get(
                "/api/admin/chargers"
            ).status_code,
            200,
        )

        self.assertEqual(
            operator.post(
                "/api/admin/chargers/1/action",
                json={
                    "action":
                        "restart"
                },
                headers={
                    "X-CSRF-Token":
                        token
                },
            ).status_code,
            403,
        )

        technician, token = self.login(
            "tech",
            "Tech123456",
        )

        self.assertEqual(
            technician.get(
                "/api/admin/logs"
            ).status_code,
            403,
        )

        self.assertEqual(
            technician.get(
                "/api/admin/chargers"
            ).status_code,
            200,
        )

        self.assertEqual(
            technician.post(
                "/api/admin/chargers/1/action",
                json={
                    "action":
                        "restart"
                },
                headers={
                    "X-CSRF-Token":
                        token
                },
            ).status_code,
            200,
        )

        detail = technician.get(
            "/api/stations/1"
        ).json

        self.assertIn(
            "status_summary",
            detail,
        )

    def test_rbac_role_change_and_self_protection(
        self
    ):
        admin, token = self.login(
            "admin",
            "Admin123456",
        )

        self.assertEqual(
            self.post(
                "/admin/users/1/role",
                {
                    "role":
                        "operator"
                },
                admin,
                token,
            ).status_code,
            200,
        )

        role = self.sql(
            """
            SELECT role
            FROM users
            WHERE id=1
            """
        )[0][0]

        self.assertEqual(
            role,
            "operator",
        )

        self.assertEqual(
            self.post(
                "/admin/users/2/role",
                {
                    "role":
                        "user"
                },
                admin,
                token,
            ).status_code,
            409,
        )

        self.post(
            "/admin/users/1/role",
            {
                "role":
                    "user"
            },
            admin,
            token,
        )

    # =====================================================
    # Payment/dashboard
    # =====================================================

    def test_payment_status_and_dashboard_user_stats(
        self
    ):
        oid = self.start()

        self.age(
            oid
        )

        response = self.post(
            f"/orders/{oid}/finish"
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response.json[
                "order"
            ][
                "payment_status"
            ],
            "已支付",
        )

        dashboard = (
            self.client
            .get(
                "/api/dashboard"
            )
            .json
        )

        self.assertIn(
            "user_stats",
            dashboard,
        )

        self.assertGreaterEqual(
            dashboard[
                "user_stats"
            ][
                "total"
            ],
            1,
        )

    # =====================================================
    # Station / pricing / fault / QR
    # =====================================================

    def test_station_info_pricing_fault_and_qr_features(
        self
    ):
        admin, token = self.login(
            "admin",
            "Admin123456",
        )

        station_data = {
            "name":
                "完整信息站",
            "address":
                "北京市测试路 1 号",
            "city":
                "北京市测试区",
            "business_hours":
                "06:00-23:00",
            "contact_phone":
                "010-12345678",
            "operating_status":
                "operating",
            "parking_info":
                "充电前两小时免费",
            "lng":
                116.1,
            "lat":
                39.9,
            "price":
                1.5,
        }

        response = self.post(
            "/admin/stations",
            station_data,
            admin,
            token,
        )

        self.assertEqual(
            response.status_code,
            200,
            response.json,
        )

        sid = response.json[
            "id"
        ]

        detail = admin.get(
            f"/api/stations/{sid}"
        ).json

        self.assertEqual(
            detail[
                "station"
            ][
                "city"
            ],
            "北京市测试区",
        )

        self.assertEqual(
            detail[
                "station"
            ][
                "business_hours"
            ],
            "06:00-23:00",
        )

        self.assertEqual(
            len(
                detail[
                    "pricing"
                ]
            ),
            3,
        )

        rules = admin.get(
            "/api/admin/pricing"
            f"?station_id={sid}"
        ).json

        self.assertEqual(
            len(rules),
            3,
        )

        first = rules[0]

        response = self.post(
            f"/admin/pricing/{first['id']}",
            {
                "station_id":
                    sid,
                "start_time":
                    first[
                        "start_time"
                    ],
                "end_time":
                    first[
                        "end_time"
                    ],
                "electricity_fee":
                    "0.88",
                "service_fee":
                    "0.22",
            },
            admin,
            token,
        )

        self.assertEqual(
            response.status_code,
            200,
            response.json,
        )

        response = self.post(
            "/admin/chargers",
            {
                "station_id":
                    sid,
                "number":
                    "QR-FAULT-01",
                "kind":
                    "fast",
                "power":
                    60,
            },
            admin,
            token,
        )

        self.assertEqual(
            response.status_code,
            200,
            response.json,
        )

        cid = response.json[
            "id"
        ]

        response = self.post(
            "/admin/faults",
            {
                "charger_id":
                    cid,
                "fault_type":
                    "通信故障",
                "description":
                    "无法连接服务器",
            },
            admin,
            token,
        )

        self.assertEqual(
            response.status_code,
            201,
            response.json,
        )

        fid = response.json[
            "id"
        ]

        status = self.sql(
            """
            SELECT status
            FROM chargers
            WHERE id=?
            """,
            (
                cid,
            ),
        )[0][0]

        self.assertEqual(
            status,
            "fault",
        )

        self.assertEqual(
            self.post(
                f"/admin/faults/{fid}",
                {
                    "status":
                        "processing",
                    "resolution":
                        "",
                },
                admin,
                token,
            ).status_code,
            200,
        )

        status = self.sql(
            """
            SELECT status
            FROM chargers
            WHERE id=?
            """,
            (
                cid,
            ),
        )[0][0]

        self.assertEqual(
            status,
            "maintenance",
        )

        self.assertEqual(
            self.post(
                f"/admin/faults/{fid}",
                {
                    "status":
                        "resolved",
                    "resolution":
                        "更换通信模块",
                },
                admin,
                token,
            ).status_code,
            200,
        )

        status = self.sql(
            """
            SELECT status
            FROM chargers
            WHERE id=?
            """,
            (
                cid,
            ),
        )[0][0]

        self.assertEqual(
            status,
            "idle",
        )

        qr = admin.get(
            f"/api/chargers/{cid}/qr"
        )

        self.assertEqual(
            qr.status_code,
            200,
        )

        self.assertIn(
            "image/svg+xml",
            qr.content_type,
        )

        charger = admin.get(
            "/api/chargers/by-number/"
            "QR-FAULT-01"
        ).json

        self.assertEqual(
            charger[
                "id"
            ],
            cid,
        )

        self.assertEqual(
            admin.get(
                "/charge/QR-FAULT-01"
            ).status_code,
            200,
        )

    # =====================================================
    # AI Agent
    # =====================================================

    def test_agent_user_queries_real_business_data(
        self
    ):
        response = self.post(
            "/agent/chat",
            {
                "message":
                    "附近哪里有空闲快充？",
                "lat":
                    39.9593,
                "lng":
                    116.2981,
            },
        )

        self.assertEqual(
            response.status_code,
            200,
            response.json,
        )

        self.assertEqual(
            response.json[
                "intent"
            ],
            "station_recommendation",
        )

        self.assertTrue(
            response.json[
                "data"
            ]
        )

    def test_agent_wallet_and_latest_order(
        self
    ):
        response = self.post(
            "/agent/chat",
            {
                "message":
                    "我的余额是多少？"
            },
        )

        self.assertEqual(
            response.status_code,
            200,
            response.json,
        )

        self.assertEqual(
            response.json[
                "intent"
            ],
            "wallet",
        )

        self.assertIn(
            "balance_cents",
            response.json[
                "data"
            ],
        )

    def test_agent_operator_can_query_operations(
        self
    ):
        operator, token = self.login(
            "operator",
            "Operator123456",
        )

        response = self.post(
            "/agent/chat",
            {
                "message":
                    "最近7天收入怎么样？"
            },
            operator,
            token,
        )

        self.assertEqual(
            response.status_code,
            200,
            response.json,
        )

        self.assertEqual(
            response.json[
                "intent"
            ],
            "revenue_summary",
        )

    # =====================================================
    # Charger kind statistics
    # =====================================================

    def test_station_kind_breakdown_fields(
        self
    ):
        response = self.client.get(
            "/api/stations"
            "?lat=39.9593"
            "&lng=116.2981"
        )

        self.assertEqual(
            response.status_code,
            200,
            response.json,
        )

        for station in response.json:

            for field in (
                "fast_free",
                "slow_free",
                "fast_fault",
                "slow_fault",
                "fast_maintenance",
                "slow_maintenance",
                "fast_offline",
                "slow_offline",
            ):

                self.assertIn(
                    field,
                    station,
                )

                self.assertGreaterEqual(
                    station[
                        field
                    ],
                    0,
                )

            self.assertLessEqual(
                station[
                    "fast_free"
                ],
                station[
                    "fast"
                ],
            )

            self.assertLessEqual(
                station[
                    "slow_free"
                ],
                station[
                    "slow"
                ],
            )

            self.assertEqual(
                (
                    station[
                        "fast_free"
                    ]
                    + station[
                        "slow_free"
                    ]
                ),
                station[
                    "free"
                ],
            )

    # =====================================================
    # Trends
    # =====================================================

    def test_order_trend_endpoint(
        self
    ):
        oid = self.start()

        self.age(
            oid,
            600,
        )

        self.assertEqual(
            self.post(
                f"/orders/{oid}/finish"
            ).status_code,
            200,
        )

        admin, token = self.login(
            "admin",
            "Admin123456",
        )

        response = admin.get(
            "/api/admin/trend"
        )

        self.assertEqual(
            response.status_code,
            200,
            response.json,
        )

        points = response.json[
            "points"
        ]

        self.assertGreaterEqual(
            len(points),
            7,
        )

        for point in points:
            self.assertGreaterEqual(
                point[
                    "done"
                ],
                0,
            )

            self.assertLessEqual(
                point[
                    "done"
                ],
                point[
                    "total"
                ],
            )

            self.assertGreaterEqual(
                point[
                    "cents"
                ],
                0,
            )

        self.assertEqual(
            admin.get(
                "/api/admin/trend"
                "?granularity=week"
                "&range=30"
            ).status_code,
            200,
        )

        self.assertEqual(
            admin.get(
                "/api/admin/trend"
                "?granularity=month"
                "&range=year"
            ).status_code,
            200,
        )

        self.assertEqual(
            admin.get(
                "/api/admin/trend"
                "?granularity=day"
                "&range=7"
                "&station_id=1"
            ).status_code,
            200,
        )

        self.assertEqual(
            admin.get(
                "/api/admin/trend"
                "?granularity=bad"
            ).status_code,
            400,
        )

        self.assertEqual(
            admin.get(
                "/api/admin/trend"
                "?range=bad"
            ).status_code,
            400,
        )

        self.assertEqual(
            admin.get(
                "/api/admin/trend"
                "?station_id=999"
            ).status_code,
            404,
        )

        client2, _ = self.login(
            "13900139000",
            "User123456",
        )

        self.assertEqual(
            client2.get(
                "/api/admin/trend"
            ).status_code,
            403,
        )

    def test_revenue_stations_endpoint(
        self
    ):
        oid = self.start()

        self.age(
            oid,
            600,
        )

        self.assertEqual(
            self.post(
                f"/orders/{oid}/finish"
            ).status_code,
            200,
        )

        admin, token = self.login(
            "admin",
            "Admin123456",
        )

        response = admin.get(
            "/api/admin/revenue_stations"
        )

        self.assertEqual(
            response.status_code,
            200,
            response.json,
        )

        stations = response.json[
            "stations"
        ]

        self.assertEqual(
            len(stations),
            10,
        )

        revenues = [
            station[
                "revenue_cents"
            ]
            for station
            in stations
        ]

        self.assertEqual(
            revenues,
            sorted(
                revenues,
                reverse=True,
            ),
        )

        self.assertGreater(
            revenues[0],
            0,
        )

        self.assertGreaterEqual(
            response.json[
                "average_cents"
            ],
            0,
        )

        self.assertIn(
            "debt_cents",
            stations[0],
        )

        client2, _ = self.login(
            "13900139000",
            "User123456",
        )

        self.assertEqual(
            client2.get(
                "/api/admin/revenue_stations"
            ).status_code,
            403,
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )