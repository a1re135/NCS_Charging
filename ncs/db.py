"""SQLite schema and reproducible course-demo seed data. Money is integer cents."""
import sqlite3
import random
from datetime import datetime, timedelta
from pathlib import Path
from flask import current_app, g
from werkzeug.security import generate_password_hash

SCHEMA = '''
CREATE TABLE IF NOT EXISTS users(
 id INTEGER PRIMARY KEY, phone TEXT UNIQUE NOT NULL, nickname TEXT NOT NULL,
 password_hash TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'user',
 balance_cents INTEGER NOT NULL DEFAULT 0 CHECK(balance_cents>=0),
 avatar TEXT NOT NULL DEFAULT 'lavender', active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS roles(
 key TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT NOT NULL, level INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS permissions(
 key TEXT PRIMARY KEY, name TEXT NOT NULL, module TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS role_permissions(
 role_key TEXT NOT NULL REFERENCES roles(key) ON DELETE CASCADE,
 permission_key TEXT NOT NULL REFERENCES permissions(key) ON DELETE CASCADE,
 PRIMARY KEY(role_key,permission_key));
CREATE TABLE IF NOT EXISTS stations(
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, address TEXT NOT NULL,
 lng REAL NOT NULL, lat REAL NOT NULL, price_cents INTEGER NOT NULL CHECK(price_cents>0));
CREATE TABLE IF NOT EXISTS chargers(
 id INTEGER PRIMARY KEY, station_id INTEGER NOT NULL REFERENCES stations(id),
 number TEXT UNIQUE NOT NULL, kind TEXT NOT NULL, power REAL NOT NULL CHECK(power>0),
 status TEXT NOT NULL DEFAULT 'idle', total_count INTEGER NOT NULL DEFAULT 0, total_minutes INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS orders(
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
 charger_id INTEGER NOT NULL REFERENCES chargers(id), status TEXT NOT NULL,
 created_at TEXT NOT NULL, expires_at TEXT, started_at TEXT, ended_at TEXT,
 price_cents INTEGER NOT NULL, power REAL NOT NULL, time_scale INTEGER NOT NULL,
 energy REAL NOT NULL DEFAULT 0, amount_cents INTEGER NOT NULL DEFAULT 0,
 paid_cents INTEGER NOT NULL DEFAULT 0, debt_cents INTEGER NOT NULL DEFAULT 0,
 balance_after INTEGER, simulated_seconds INTEGER NOT NULL DEFAULT 0);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_user ON orders(user_id) WHERE status IN ('reserved','charging');
CREATE UNIQUE INDEX IF NOT EXISTS one_active_charger ON orders(charger_id) WHERE status IN ('reserved','charging');
CREATE TABLE IF NOT EXISTS wallet_log(
 id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),
 amount_cents INTEGER NOT NULL,kind TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ops_log(
 id INTEGER PRIMARY KEY,actor_id INTEGER REFERENCES users(id),operation TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS order_user ON orders(user_id,created_at);
CREATE INDEX IF NOT EXISTS order_status_created ON orders(status,created_at);
CREATE INDEX IF NOT EXISTS order_charger_status ON orders(charger_id,status);
CREATE INDEX IF NOT EXISTS charger_station_status ON chargers(station_id,status);
CREATE INDEX IF NOT EXISTS user_role_active ON users(role,active);
'''

DEMO_STATIONS = [
    ('海淀 · 智慧充电站','北京市海淀区中关村大街',116.2981,39.9593,160),
    ('城市中心 · 绿能站','北京市东城区中心区域',116.4074,39.9042,150),
    ('朝阳 · 阳光充电站','北京市朝阳区朝阳公园南路',116.4435,39.9219,155),
    ('丰台 · 花园充电站','北京市丰台区丰台北路',116.2869,39.8584,145),
    ('石景山 · 星光充电站','北京市石景山区石景山路',116.2229,39.9062,150),
    ('西城 · 智慧绿能站','北京市西城区西直门外',116.3565,39.9418,152),
    ('通州 · 运河充电站','北京市通州区运河商务区',116.6586,39.9097,148),
    ('亦庄 · 新城充电站','北京市大兴区亦庄开发区',116.5067,39.7954,146),
    ('昌平 · 北城充电站','北京市昌平区回龙观',116.3365,40.0708,149),
    ('顺义 · 空港充电站','北京市顺义区空港工业区',116.5551,40.1260,151),
]


def now():
    return datetime.now().isoformat(timespec='seconds')


def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'], timeout=15, isolation_level=None)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys=ON')
        g.db.execute('PRAGMA busy_timeout=15000')
    return g.db


def close_db(_=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def _ensure_l1_scale(db):
    """Bring the demo installation to the declared L1 footprint without
    deleting or modifying user-generated records. This makes the L1 target
    visible in the running dataset while keeping the initial seed small.
    """
    station_count = db.execute('SELECT COUNT(*) FROM stations').fetchone()[0]
    if station_count < 10:
        for item in DEMO_STATIONS[station_count:10]:
            db.execute('INSERT INTO stations(name,address,lng,lat,price_cents) VALUES(?,?,?,?,?)', item)

    # Ensure each of the 10 demo stations has 10 chargers: 100 total.
    for sid in range(1, 11):
        existing = db.execute('SELECT COUNT(*) FROM chargers WHERE station_id=?', (sid,)).fetchone()[0]
        for j in range(existing + 1, 11):
            kind = 'fast' if j <= 7 else 'slow'
            power = 60 if kind == 'fast' else 7
            status = 'idle'
            if sid in (2, 4) and j == 10:
                status = 'fault'
            db.execute(
                'INSERT OR IGNORE INTO chargers(station_id,number,kind,power,status) VALUES(?,?,?,?,?)',
                (sid, f'NCS-{sid:02d}{j:02d}', kind, power, status),
            )


def _seed_initial(db):
    db.execute('BEGIN IMMEDIATE')
    try:
        for phone, name, role, balance, password in [
            ('13800138000','小林','user',28800,'User123456'),
            ('admin','管理员','admin',0,'Admin123456'),
            ('13900139000','小明','user',16800,'User123456')]:
            db.execute('INSERT INTO users(phone,nickname,password_hash,role,balance_cents,created_at) VALUES(?,?,?,?,?,?)',
                       (phone,name,generate_password_hash(password),role,balance,now()))
        for sid, item in enumerate(DEMO_STATIONS,1):
            db.execute('INSERT INTO stations VALUES(?,?,?,?,?,?)',(sid,*item))
            for j in range(1,11):
                kind='fast' if j<=7 else 'slow'; power=60 if kind=='fast' else 7
                status='idle'
                if j==10 and sid in (2,4): status='fault'
                if j==6 and sid==2: status='maintenance'
                if j==6 and sid==3: status='fault'
                if j==6 and sid==4: status='offline'
                db.execute('INSERT INTO chargers(station_id,number,kind,power,status) VALUES(?,?,?,?,?)',
                           (sid,f'NCS-{sid:02d}{j:02d}',kind,power,status))
        rng = random.Random(26)
        for days in range(28,0,-1):
            for k in range(rng.randint(3,7)):
                cid=rng.randint(1,100)
                c=db.execute('SELECT c.*,s.price_cents FROM chargers c JOIN stations s ON s.id=c.station_id WHERE c.id=?',(cid,)).fetchone()
                start=(datetime.now()-timedelta(days=days)).replace(hour=rng.choice([8,9,12,15,18,19,20]),minute=rng.randint(0,59),second=0,microsecond=0)
                minutes=rng.randint(18,70); energy=round(c['power']*minutes/60,3); amount=round(energy*c['price_cents'])
                uid=1 if k==0 else 3
                paid=0 if (uid==3 and days==1 and k==2) else amount
                db.execute('''INSERT INTO orders(user_id,charger_id,status,created_at,started_at,ended_at,price_cents,power,time_scale,energy,amount_cents,paid_cents,debt_cents,simulated_seconds)
                VALUES(?,?,'completed',?,?,?,?,?,1,?,?,?,?,?)''',
                (uid,cid,start.isoformat(),start.isoformat(),(start+timedelta(minutes=minutes)).isoformat(),c['price_cents'],c['power'],energy,amount,paid,amount-paid,minutes*60))
                db.execute('UPDATE chargers SET total_count=total_count+1,total_minutes=total_minutes+? WHERE id=?',(minutes,cid))
        db.commit()
    except Exception:
        db.rollback(); raise


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
# Permissions intentionally follow the four business roles in the project brief:
# operator manages stations/orders/pricing/operations; technician manages equipment/faults.
ROLE_PERMISSION_KEYS = {
    'user': {'station.view'},
    'operator': {'station.view','station.manage','charger.view','order.view_all','order.export','pricing.manage','analytics.view','prediction.view'},
    'technician': {'station.view','charger.view','charger.manage','fault.manage'},
    'admin': {k for k,_,_ in PERMISSION_DEFINITIONS},
}

def _ensure_rbac(db):
    db.executemany('INSERT OR IGNORE INTO roles(key,name,description,level) VALUES(?,?,?,?)', ROLE_DEFINITIONS)
    db.executemany('INSERT OR IGNORE INTO permissions(key,name,module) VALUES(?,?,?)', PERMISSION_DEFINITIONS)
    # Reconcile mappings every startup so role definitions remain authoritative
    # after an earlier version granted a broader permission set.
    for role, keys in ROLE_PERMISSION_KEYS.items():
        db.execute('DELETE FROM role_permissions WHERE role_key=?',(role,))
        db.executemany('INSERT OR IGNORE INTO role_permissions(role_key,permission_key) VALUES(?,?)', [(role,k) for k in sorted(keys)])
    demos=[
        ('operator','运营演示','operator','Operator123456'),
        ('tech','运维演示','technician','Tech123456'),
    ]
    for account,nickname,role,password in demos:
        row=db.execute('SELECT id FROM users WHERE phone=?',(account,)).fetchone()
        if row:
            db.execute('UPDATE users SET role=? WHERE id=?',(role,row['id']))
        else:
            db.execute('INSERT INTO users(phone,nickname,password_hash,role,balance_cents,created_at) VALUES(?,?,?,?,?,?)',
                       (account,nickname,generate_password_hash(password),role,0,now()))
    # The course demo administrator is always a real system administrator.
    db.execute("UPDATE users SET role='admin' WHERE phone='admin'")

def init_db():
    Path(current_app.config['DATABASE']).parent.mkdir(parents=True, exist_ok=True)
    db = get_db()
    db.execute('PRAGMA journal_mode=WAL')
    db.executescript(SCHEMA)
    if db.execute('SELECT COUNT(*) FROM users').fetchone()[0] == 0:
        _seed_initial(db)
    else:
        _ensure_l1_scale(db)
    _ensure_rbac(db)
    db.commit()
