import random
import threading

import pymysql
from pymysql.cursors import DictCursor
from .mysql_schema import MYSQL_SCHEMA
from dbutils.pooled_db import PooledDB
from datetime import datetime, timedelta
from flask import current_app, g
from werkzeug.security import generate_password_hash

def now():
    return datetime.now().isoformat(timespec='seconds')

class CompatRow(dict):
    """
    Provides dictionary-style row access:
    row["id"] works
    row[0] also works
    """

    def __getitem__(self, key):
        if isinstance(key, int):
            return list(self.values())[key]

        return super().__getitem__(key)


class CompatCursor(DictCursor):
    dict_type = CompatRow

_mysql_pool = None
_mysql_pool_config = None
_mysql_pool_lock = threading.Lock()


def get_mysql_pool():
    """
    Create one shared PyMySQL connection pool for the process.

    Each Flask request borrows a connection and close_db()
    returns it to the pool instead of creating/destroying a
    physical MySQL connection every request.
    """

    global _mysql_pool
    global _mysql_pool_config

    config_key = (
        current_app.config["MYSQL_HOST"],
        current_app.config["MYSQL_PORT"],
        current_app.config["MYSQL_USER"],
        current_app.config["MYSQL_PASSWORD"],
        current_app.config["MYSQL_DATABASE"],
    )

    if (
        _mysql_pool is not None
        and _mysql_pool_config == config_key
    ):
        return _mysql_pool

    with _mysql_pool_lock:
        if (
            _mysql_pool is not None
            and _mysql_pool_config == config_key
        ):
            return _mysql_pool

        # If configuration changed, discard idle
        # connections from the previous pool.
        if _mysql_pool is not None:
            try:
                _mysql_pool.close()
            except Exception:
                pass

        _mysql_pool = PooledDB(
            creator=pymysql,

            # Keep a few ready connections alive.
            mincached=4,

            # Number of idle connections kept ready.
            maxcached=32,

            # Maximum simultaneous DB connections.
            maxconnections=32,

            # Wait for a free pooled connection instead
            # of immediately throwing an exception.
            blocking=True,

            # Check the connection when borrowed.
            ping=1,

            host=current_app.config[
                "MYSQL_HOST"
            ],

            port=current_app.config[
                "MYSQL_PORT"
            ],

            user=current_app.config[
                "MYSQL_USER"
            ],

            password=current_app.config[
                "MYSQL_PASSWORD"
            ],

            database=current_app.config[
                "MYSQL_DATABASE"
            ],

            charset="utf8mb4",

            cursorclass=CompatCursor,

            autocommit=True,

            connect_timeout=10,
            read_timeout=30,
            write_timeout=30,
        )

        _mysql_pool_config = config_key

        return _mysql_pool

class MySQLDatabase:
    def __init__(self, connection):
        self.connection = connection

    def _convert_sql(self, sql):
        sql = sql.strip()

        upper = sql.upper()

        if upper == "BEGIN IMMEDIATE":
            return None

        # Application placeholders -> PyMySQL placeholders
        sql = sql.replace("?", "%s")

        # Normalize application SQL for MySQL
        sql = sql.replace(
            "INSERT OR IGNORE",
            "INSERT IGNORE"
        )

        return sql

    def execute(self, sql, params=()):
        converted = self._convert_sql(sql)

        if converted is None:
            self.connection.begin()
            return None

        cursor = self.connection.cursor()
        cursor.execute(converted, params)

        return cursor

    def begin(self):
        self.connection.begin()

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()

def get_db():
    if "db" not in g:
        pool = get_mysql_pool()

        connection = pool.connection()

        g.db = MySQLDatabase(
            connection
        )

    return g.db

def close_db(_=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def _add_default_pricing(db, station_id, base_price):
    """Three demo time periods around the old station price; total fee stays easy to understand."""
    service = 30
    totals = (max(40, base_price - 20), base_price, base_price + 20)
    periods = ((0, 480, totals[0]), (480, 1080, totals[1]), (1080, 1440, totals[2]))
    for start, end, total in periods:
        db.execute('''INSERT INTO pricing_rules(station_id,start_minute,end_minute,electricity_fee_cents,service_fee_cents)
                      VALUES(?,?,?,?,?)''', (station_id, start, end, max(0, total-service), service))

ROLE_DEFINITIONS = [
    ('user','普通用户','查询、充电、订单与个人账户',1),
    ('operator','运营人员','电站、订单、价格与运营数据',20),
    ('technician','运维人员','设备状态与故障处理',30),
    ('admin','系统管理员','全局用户、角色与系统管理',99),
]

PERMISSION_DEFINITIONS = [
    ('station.view','查看充电站','电站'),
    ('station.manage','管理充电站','电站'),
    ('charger.view','查看充电桩','设备'),
    ('charger.manage','管理充电桩','设备'),
    ('order.view_all','查看全部订单','订单'),
    ('order.export','导出订单','订单'),
    ('pricing.manage','管理价格','价格'),
    ('fault.manage','处理设备故障','故障'),
    ('analytics.view','查看运营数据','分析'),
    ('prediction.view','查看负荷预测','分析'),
    ('user.manage','管理用户','用户'),
    ('role.manage','管理角色与权限','权限'),
    ('log.view','查看操作日志','审计'),
]

ROLE_PERMISSION_KEYS = {
    'user': {'station.view'},
    'operator': {
        'station.view','station.manage','charger.view','order.view_all',
        'order.export','pricing.manage','analytics.view','prediction.view'
    },
    'technician': {'station.view','charger.view','charger.manage','fault.manage'},
    'admin': {k for k,_,_ in PERMISSION_DEFINITIONS},
}

def _ensure_rbac_schema(db, backend):
    if backend == 'mysql':
        statements = [
            """CREATE TABLE IF NOT EXISTS roles(
                `key` VARCHAR(64) NOT NULL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                description VARCHAR(255) NOT NULL,
                level INT NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            """CREATE TABLE IF NOT EXISTS permissions(
                `key` VARCHAR(64) NOT NULL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                module VARCHAR(100) NOT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""",
            """CREATE TABLE IF NOT EXISTS role_permissions(
                role_key VARCHAR(64) NOT NULL,
                permission_key VARCHAR(64) NOT NULL,
                PRIMARY KEY(role_key, permission_key),
                CONSTRAINT fk_role_permission_role
                    FOREIGN KEY(role_key) REFERENCES roles(`key`) ON DELETE CASCADE,
                CONSTRAINT fk_role_permission_permission
                    FOREIGN KEY(permission_key) REFERENCES permissions(`key`) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"""
        ]
        for statement in statements:
            db.execute(statement)

def _ensure_rbac(db):
    for key,name,description,level in ROLE_DEFINITIONS:
        db.execute(
            'INSERT OR IGNORE INTO roles(`key`,name,description,level) VALUES(?,?,?,?)',
            (key,name,description,level)
        )
    for key,name,module in PERMISSION_DEFINITIONS:
        db.execute(
            'INSERT OR IGNORE INTO permissions(`key`,name,module) VALUES(?,?,?)',
            (key,name,module)
        )
    for role, keys in ROLE_PERMISSION_KEYS.items():
        db.execute('DELETE FROM role_permissions WHERE role_key=?',(role,))
        for key in sorted(keys):
            db.execute(
                'INSERT OR IGNORE INTO role_permissions(role_key,permission_key) VALUES(?,?)',
                (role,key)
            )

    demos = [
        ('operator','运营演示','operator','Operator123456'),
        ('tech','运维演示','technician','Tech123456'),
    ]
    for account,nickname,role,password in demos:
        row=db.execute('SELECT id FROM users WHERE phone=?',(account,)).fetchone()
        if row:
            db.execute('UPDATE users SET role=? WHERE id=?',(role,row['id']))
        else:
            db.execute(
                'INSERT INTO users(phone,nickname,password_hash,role,balance_cents,created_at) '
                'VALUES(?,?,?,?,?,?)',
                (account,nickname,generate_password_hash(password),role,0,now())
            )

    db.execute("UPDATE users SET role='admin' WHERE phone='admin'")


def init_db():
    db = get_db()

    # =====================================================
    # 1. Create MySQL tables
    # =====================================================
    for statement in MYSQL_SCHEMA:
        db.execute(statement)

    # =====================================================
    # 2. Create preferences table
    # =====================================================
    from .preferences import MYSQL_SCHEMA as PREF_MYSQL

    db.execute(PREF_MYSQL)

    # =====================================================
    # 3. Initialize RBAC tables
    # =====================================================
    _ensure_rbac_schema(
        db,
        "mysql",
    )

    # =====================================================
    # 4. Initialize avatar table
    # =====================================================
    from .avatars import init_avatars
    from .expansion import expand_network

    init_avatars(db)

    # =====================================================
    # 5. Check whether demo data already exists
    # =====================================================
    count = db.execute(
        "SELECT COUNT(*) AS count FROM users"
    ).fetchone()

    # Existing database:
    # only ensure newer demo expansion / RBAC data exists.
    if count["count"] > 0:
        expand_network(db)

        _ensure_rbac(db)

        return

    # =====================================================
    # 6. First-time database initialization
    # =====================================================
    db.begin()

    try:
        # -------------------------------------------------
        # Demo users
        # -------------------------------------------------
        users = [
            (
                "13800138000",
                "小林",
                "user",
                28800,
                "User123456",
            ),
            (
                "admin",
                "管理员",
                "admin",
                0,
                "Admin123456",
            ),
            (
                "13900139000",
                "小明",
                "user",
                16800,
                "User123456",
            ),
        ]

        for (
            phone,
            name,
            role,
            balance,
            password,
        ) in users:
            db.execute(
                """
                INSERT INTO users(
                    phone,
                    nickname,
                    password_hash,
                    role,
                    balance_cents,
                    created_at
                )
                VALUES(?,?,?,?,?,?)
                """,
                (
                    phone,
                    name,
                    generate_password_hash(
                        password
                    ),
                    role,
                    balance,
                    now(),
                ),
            )

        # -------------------------------------------------
        # Demo stations
        # -------------------------------------------------
        stations = [
            (
                "海淀 · 智慧充电站",
                "北京市海淀区中关村大街",
                "北京市海淀区",
                "00:00-24:00",
                "010-62500001",
                "operating",
                "停车前 30 分钟免费，之后按停车场标准收费",
                116.2981,
                39.9593,
                160,
            ),
            (
                "城市中心 · 绿能站",
                "北京市东城区中心区域",
                "北京市东城区",
                "06:00-23:00",
                "010-65200002",
                "operating",
                "充电车辆前 2 小时免停车费",
                116.4074,
                39.9042,
                150,
            ),
            (
                "朝阳 · 阳光充电站",
                "北京市朝阳区朝阳公园南路",
                "北京市朝阳区",
                "00:00-24:00",
                "010-65000003",
                "operating",
                "地下停车场 B2 层，按场内标准收费",
                116.4435,
                39.9219,
                155,
            ),
            (
                "丰台 · 花园充电站",
                "北京市丰台区丰台北路",
                "北京市丰台区",
                "07:00-22:00",
                "010-63800004",
                "operating",
                "充电期间停车优惠以现场公告为准",
                116.2869,
                39.8584,
                145,
            ),
            (
                "石景山 · 星光充电站",
                "北京市石景山区石景山路",
                "北京市石景山区",
                "00:00-24:00",
                "010-68800005",
                "operating",
                "地面停车位，充电车辆优先",
                116.2229,
                39.9062,
                150,
            ),
        ]

        for sid, item in enumerate(
            stations,
            1,
        ):
            db.execute(
                """
                INSERT INTO stations(
                    id,
                    name,
                    address,
                    city,
                    business_hours,
                    contact_phone,
                    operating_status,
                    parking_info,
                    lng,
                    lat,
                    price_cents
                )
                VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    sid,
                    *item,
                ),
            )

            _add_default_pricing(
                db,
                sid,
                item[-1],
            )

            # ---------------------------------------------
            # Create 6 chargers for initial demo stations
            # ---------------------------------------------
            for j in range(
                1,
                7,
            ):
                status = "idle"

                if j == 6:
                    status = {
                        2: "maintenance",
                        3: "fault",
                        4: "offline",
                    }.get(
                        sid,
                        "idle",
                    )

                cur = db.execute(
                    """
                    INSERT INTO chargers(
                        station_id,
                        number,
                        kind,
                        power,
                        status
                    )
                    VALUES(?,?,?,?,?)
                    """,
                    (
                        sid,
                        f"NCS-{sid:02d}{j:02d}",
                        (
                            "fast"
                            if j < 5
                            else "slow"
                        ),
                        (
                            60
                            if j < 5
                            else 7
                        ),
                        status,
                    ),
                )

                # Create an example fault record.
                if status == "fault":
                    db.execute(
                        """
                        INSERT INTO fault_records(
                            charger_id,
                            fault_type,
                            description,
                            status,
                            reported_at,
                            reporter_id
                        )
                        VALUES(
                            ?,
                            ?,
                            '演示数据：设备通信异常',
                            'pending',
                            ?,
                            2
                        )
                        """,
                        (
                            cur.lastrowid,
                            "通信故障",
                            now(),
                        ),
                    )

        # =================================================
        # 7. Generate demo historical orders
        # =================================================
        rng = random.Random(26)

        for days in range(
            28,
            0,
            -1,
        ):
            for k in range(
                rng.randint(
                    3,
                    7,
                )
            ):
                cid = rng.randint(
                    1,
                    30,
                )

                charger = db.execute(
                    """
                    SELECT
                        c.*,
                        s.price_cents
                    FROM chargers c
                    JOIN stations s
                        ON s.id = c.station_id
                    WHERE c.id=?
                    """,
                    (
                        cid,
                    ),
                ).fetchone()

                start = (
                    datetime.now()
                    - timedelta(
                        days=days
                    )
                ).replace(
                    hour=rng.choice(
                        [
                            8,
                            9,
                            12,
                            15,
                            18,
                            19,
                            20,
                        ]
                    ),
                    minute=rng.randint(
                        0,
                        59,
                    ),
                    second=0,
                    microsecond=0,
                )

                minutes = rng.randint(
                    18,
                    70,
                )

                energy = round(
                    charger["power"]
                    * minutes
                    / 60,
                    3,
                )

                amount = round(
                    energy
                    * charger[
                        "price_cents"
                    ]
                )

                uid = (
                    1
                    if k == 0
                    else 3
                )

                # Give demo user 3 one unpaid order
                # from yesterday.
                paid = (
                    0
                    if (
                        uid == 3
                        and days == 1
                        and k == 2
                    )
                    else amount
                )

                electricity = max(
                    0,
                    charger[
                        "price_cents"
                    ]
                    - 30,
                )

                service = (
                    charger[
                        "price_cents"
                    ]
                    - electricity
                )

                db.execute(
                    """
                    INSERT INTO orders(
                        user_id,
                        charger_id,
                        status,
                        created_at,
                        started_at,
                        ended_at,
                        price_cents,
                        electricity_fee_cents,
                        service_fee_cents,
                        power,
                        time_scale,
                        energy,
                        amount_cents,
                        paid_cents,
                        debt_cents,
                        simulated_seconds
                    )
                    VALUES(
                        ?,
                        ?,
                        'completed',
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?,
                        1,
                        ?,
                        ?,
                        ?,
                        ?,
                        ?
                    )
                    """,
                    (
                        uid,
                        cid,
                        start.isoformat(),
                        start.isoformat(),
                        (
                            start
                            + timedelta(
                                minutes=minutes
                            )
                        ).isoformat(),
                        charger[
                            "price_cents"
                        ],
                        electricity,
                        service,
                        charger["power"],
                        energy,
                        amount,
                        paid,
                        amount - paid,
                        minutes * 60,
                    ),
                )

                db.execute(
                    """
                    UPDATE chargers
                    SET
                        total_count =
                            total_count + 1,
                        total_minutes =
                            total_minutes + ?
                    WHERE id=?
                    """,
                    (
                        minutes,
                        cid,
                    ),
                )

        # =================================================
        # 8. Commit initial seed data
        # =================================================
        db.commit()

    except Exception:
        db.rollback()
        raise

    # =====================================================
    # 9. Expand demo network to latest project version
    # =====================================================
    expand_network(db)

    # =====================================================
    # 10. Create/update RBAC demo roles and permissions
    # =====================================================
    _ensure_rbac(db)
