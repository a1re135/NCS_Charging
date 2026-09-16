import os
from pathlib import Path

import pymysql
from dotenv import load_dotenv


ROOT = (
    Path(__file__)
    .resolve()
    .parent
    .parent
)

load_dotenv(
    ROOT / ".env"
)


def get_mysql_test_settings():
    normal_database = os.getenv(
        "MYSQL_DATABASE",
        "ncs_charging",
    )

    test_database = os.getenv(
        "MYSQL_TEST_DATABASE",
        "ncs_charging_test",
    )

    # =====================================================
    # SAFETY: NEVER allow tests to use the real database.
    # =====================================================

    if test_database == normal_database:
        raise RuntimeError(
            "MYSQL_TEST_DATABASE must not be "
            "the same as MYSQL_DATABASE."
        )

    if not test_database.lower().endswith(
        "_test"
    ):
        raise RuntimeError(
            "Refusing to run destructive tests. "
            "MYSQL_TEST_DATABASE must end in '_test'. "
            f"Current database: {test_database}"
        )

    return {
        "host": os.getenv(
            "MYSQL_HOST",
            "localhost",
        ),

        "port": int(
            os.getenv(
                "MYSQL_PORT",
                "3306",
            )
        ),

        "user": os.getenv(
            "MYSQL_USER",
            "ncs_app",
        ),

        "password": os.getenv(
            "MYSQL_PASSWORD",
            "",
        ),

        "database": test_database,
    }


def mysql_test_app_config(
    secret="test-only",
):
    mysql = (
        get_mysql_test_settings()
    )

    return {
        "TESTING": True,

        "SECRET_KEY":
            secret,

        "MYSQL_HOST":
            mysql["host"],

        "MYSQL_PORT":
            mysql["port"],

        "MYSQL_DATABASE":
            mysql["database"],

        "MYSQL_USER":
            mysql["user"],

        "MYSQL_PASSWORD":
            mysql["password"],
    }


def reset_mysql_test_database():
    mysql = (
        get_mysql_test_settings()
    )

    try:
        connection = pymysql.connect(
            host=mysql["host"],
            port=mysql["port"],
            user=mysql["user"],
            password=mysql["password"],
            database=mysql["database"],
            charset="utf8mb4",
            autocommit=True,
        )

    except pymysql.err.OperationalError as exc:
        raise RuntimeError(
            "Unable to connect to "
            f"MySQL test database "
            f"'{mysql['database']}'. "
            "Make sure ncs_charging_test "
            "exists and .env is correct."
        ) from exc

    try:
        with connection.cursor() as cursor:

            cursor.execute(
                "SET FOREIGN_KEY_CHECKS=0"
            )

            try:
                cursor.execute(
                    "SHOW FULL TABLES "
                    "WHERE Table_type='BASE TABLE'"
                )

                tables = [
                    row[0]
                    for row
                    in cursor.fetchall()
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
                        "DROP TABLE IF EXISTS "
                        f"`{safe_table}`"
                    )

            finally:
                cursor.execute(
                    "SET FOREIGN_KEY_CHECKS=1"
                )

    finally:
        connection.close()