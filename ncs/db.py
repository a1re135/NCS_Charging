"""SQLite schema, lightweight migrations, and reproducible course-demo seed data."""
import random
import sqlite3
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
CREATE TABLE IF NOT EXISTS stations(
 id INTEGER PRIMARY KEY, name TEXT NOT NULL, address TEXT NOT NULL,
 city TEXT NOT NULL DEFAULT '北京市', business_hours TEXT NOT NULL DEFAULT '00:00-24:00',
 contact_phone TEXT NOT NULL DEFAULT '010-00000000', operating_status TEXT NOT NULL DEFAULT 'operating',
 parking_info TEXT NOT NULL DEFAULT '以现场停车规定为准',
 lng REAL NOT NULL, lat REAL NOT NULL, price_cents INTEGER NOT NULL CHECK(price_cents>0));
CREATE TABLE IF NOT EXISTS chargers(
 id INTEGER PRIMARY KEY, station_id INTEGER NOT NULL REFERENCES stations(id),
 number TEXT UNIQUE NOT NULL, kind TEXT NOT NULL, power REAL NOT NULL CHECK(power>0),
 status TEXT NOT NULL DEFAULT 'idle', total_count INTEGER NOT NULL DEFAULT 0, total_minutes INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS orders(
 id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
 charger_id INTEGER NOT NULL REFERENCES chargers(id), status TEXT NOT NULL,
 created_at TEXT NOT NULL, expires_at TEXT, started_at TEXT, ended_at TEXT,
 price_cents INTEGER NOT NULL, electricity_fee_cents INTEGER NOT NULL DEFAULT 0,
 service_fee_cents INTEGER NOT NULL DEFAULT 0, power REAL NOT NULL, time_scale INTEGER NOT NULL,
 energy REAL NOT NULL DEFAULT 0, amount_cents INTEGER NOT NULL DEFAULT 0,
 paid_cents INTEGER NOT NULL DEFAULT 0, debt_cents INTEGER NOT NULL DEFAULT 0,
 balance_after INTEGER, simulated_seconds INTEGER NOT NULL DEFAULT 0);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_user ON orders(user_id) WHERE status IN ('reserved','charging');
CREATE UNIQUE INDEX IF NOT EXISTS one_active_charger ON orders(charger_id) WHERE status IN ('reserved','charging');
CREATE TABLE IF NOT EXISTS pricing_rules(
 id INTEGER PRIMARY KEY, station_id INTEGER NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
 start_minute INTEGER NOT NULL CHECK(start_minute>=0 AND start_minute<1440),
 end_minute INTEGER NOT NULL CHECK(end_minute>0 AND end_minute<=1440 AND end_minute>start_minute),
 electricity_fee_cents INTEGER NOT NULL CHECK(electricity_fee_cents>=0),
 service_fee_cents INTEGER NOT NULL CHECK(service_fee_cents>=0));
CREATE INDEX IF NOT EXISTS pricing_station ON pricing_rules(station_id,start_minute);
CREATE TABLE IF NOT EXISTS fault_records(
 id INTEGER PRIMARY KEY, charger_id INTEGER NOT NULL REFERENCES chargers(id),
 fault_type TEXT NOT NULL, description TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
 reported_at TEXT NOT NULL, handled_at TEXT, resolution TEXT,
 reporter_id INTEGER REFERENCES users(id), handler_id INTEGER REFERENCES users(id));
CREATE UNIQUE INDEX IF NOT EXISTS one_open_fault ON fault_records(charger_id) WHERE status IN ('pending','processing');
CREATE INDEX IF NOT EXISTS fault_charger ON fault_records(charger_id,reported_at);
CREATE TABLE IF NOT EXISTS wallet_log(
 id INTEGER PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id),
 amount_cents INTEGER NOT NULL,kind TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ops_log(
 id INTEGER PRIMARY KEY,actor_id INTEGER REFERENCES users(id),operation TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS order_user ON orders(user_id,created_at);
'''

def now():
    return datetime.now().isoformat(timespec='seconds')

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(current_app.config['DATABASE'], timeout=15, isolation_level=None)
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA foreign_keys=ON')
    return g.db

def close_db(_=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def _columns(db, table):
    return {r['name'] for r in db.execute(f'PRAGMA table_info({table})')}

def _ensure_column(db, table, name, definition):
    if name not in _columns(db, table):
        db.execute(f'ALTER TABLE {table} ADD COLUMN {name} {definition}')

def _add_default_pricing(db, station_id, base_price):
    """Three demo time periods around the old station price; total fee stays easy to understand."""
    service = 30
    totals = (max(40, base_price - 20), base_price, base_price + 20)
    periods = ((0, 480, totals[0]), (480, 1080, totals[1]), (1080, 1440, totals[2]))
    for start, end, total in periods:
        db.execute('''INSERT INTO pricing_rules(station_id,start_minute,end_minute,electricity_fee_cents,service_fee_cents)
                      VALUES(?,?,?,?,?)''', (station_id, start, end, max(0, total-service), service))

def migrate_db(db):
    """Keep existing local ncs.db files usable after pulling newer source code."""
    for name, definition in [
        ('city', "TEXT NOT NULL DEFAULT '北京市'"),
        ('business_hours', "TEXT NOT NULL DEFAULT '00:00-24:00'"),
        ('contact_phone', "TEXT NOT NULL DEFAULT '010-00000000'"),
        ('operating_status', "TEXT NOT NULL DEFAULT 'operating'"),
        ('parking_info', "TEXT NOT NULL DEFAULT '以现场停车规定为准'")]:
        _ensure_column(db, 'stations', name, definition)
    _ensure_column(db, 'orders', 'electricity_fee_cents', 'INTEGER NOT NULL DEFAULT 0')
    _ensure_column(db, 'orders', 'service_fee_cents', 'INTEGER NOT NULL DEFAULT 0')
    db.execute('''UPDATE orders SET electricity_fee_cents=CASE WHEN price_cents>=30 THEN price_cents-30 ELSE price_cents END,
                  service_fee_cents=CASE WHEN price_cents>=30 THEN 30 ELSE 0 END
                  WHERE electricity_fee_cents=0 AND service_fee_cents=0''')
    # Existing projects used a single station price. Convert it into three editable time periods once.
    for s in db.execute('SELECT id,price_cents FROM stations').fetchall():
        if not db.execute('SELECT 1 FROM pricing_rules WHERE station_id=? LIMIT 1', (s['id'],)).fetchone():
            _add_default_pricing(db, s['id'], s['price_cents'])
    # Existing chargers that were already marked fault should also appear in fault management.
    for c in db.execute("SELECT id FROM chargers WHERE status='fault'").fetchall():
        if not db.execute("SELECT 1 FROM fault_records WHERE charger_id=? AND status IN ('pending','processing')", (c['id'],)).fetchone():
            db.execute('''INSERT INTO fault_records(charger_id,fault_type,description,status,reported_at)
                          VALUES(?,?,'由旧版设备故障状态自动迁移','pending',?)''', (c['id'], '设备异常', now()))

def init_db():
    Path(current_app.config['DATABASE']).parent.mkdir(parents=True, exist_ok=True)
    db = get_db()
    db.execute('PRAGMA journal_mode=WAL')
    db.executescript(SCHEMA)
    migrate_db(db)
    if db.execute('SELECT COUNT(*) FROM users').fetchone()[0]:
        return
    db.execute('BEGIN IMMEDIATE')
    try:
        for phone, name, role, balance, password in [
            ('13800138000','小林','user',28800,'User123456'),
            ('admin','管理员','admin',0,'Admin123456'),
            ('13900139000','小明','user',16800,'User123456')]:
            db.execute('INSERT INTO users(phone,nickname,password_hash,role,balance_cents,created_at) VALUES(?,?,?,?,?,?)',
                       (phone,name,generate_password_hash(password),role,balance,now()))
        stations = [
            ('海淀 · 智慧充电站','北京市海淀区中关村大街','北京市海淀区','00:00-24:00','010-62500001','operating','停车前 30 分钟免费，之后按停车场标准收费',116.2981,39.9593,160),
            ('城市中心 · 绿能站','北京市东城区中心区域','北京市东城区','06:00-23:00','010-65200002','operating','充电车辆前 2 小时免停车费',116.4074,39.9042,150),
            ('朝阳 · 阳光充电站','北京市朝阳区朝阳公园南路','北京市朝阳区','00:00-24:00','010-65000003','operating','地下停车场 B2 层，按场内标准收费',116.4435,39.9219,155),
            ('丰台 · 花园充电站','北京市丰台区丰台北路','北京市丰台区','07:00-22:00','010-63800004','operating','充电期间停车优惠以现场公告为准',116.2869,39.8584,145),
            ('石景山 · 星光充电站','北京市石景山区石景山路','北京市石景山区','00:00-24:00','010-68800005','operating','地面停车位，充电车辆优先',116.2229,39.9062,150)]
        for sid, item in enumerate(stations,1):
            db.execute('''INSERT INTO stations(id,name,address,city,business_hours,contact_phone,operating_status,parking_info,lng,lat,price_cents)
                          VALUES(?,?,?,?,?,?,?,?,?,?,?)''', (sid,*item))
            _add_default_pricing(db, sid, item[-1])
            for j in range(1,7):
                status='fault' if j==6 and sid in (2,4) else 'idle'
                cur=db.execute('INSERT INTO chargers(station_id,number,kind,power,status) VALUES(?,?,?,?,?)',
                    (sid,f'NCS-{sid:02d}{j:02d}','fast' if j<5 else 'slow',60 if j<5 else 7,status))
                if status=='fault':
                    db.execute('''INSERT INTO fault_records(charger_id,fault_type,description,status,reported_at,reporter_id)
                                  VALUES(?,?,'演示数据：设备通信异常','pending',?,2)''', (cur.lastrowid, '通信故障', now()))
        rng = random.Random(26)
        for days in range(28,0,-1):
            for k in range(rng.randint(3,7)):
                cid=rng.randint(1,30)
                c=db.execute('SELECT c.*,s.price_cents FROM chargers c JOIN stations s ON s.id=c.station_id WHERE c.id=?',(cid,)).fetchone()
                start=(datetime.now()-timedelta(days=days)).replace(hour=rng.choice([8,9,12,15,18,19,20]),minute=rng.randint(0,59),second=0,microsecond=0)
                minutes=rng.randint(18,70); energy=round(c['power']*minutes/60,3); amount=round(energy*c['price_cents'])
                electricity=max(0,c['price_cents']-30); service=c['price_cents']-electricity
                db.execute('''INSERT INTO orders(user_id,charger_id,status,created_at,started_at,ended_at,price_cents,electricity_fee_cents,service_fee_cents,power,time_scale,energy,amount_cents,paid_cents,simulated_seconds)
                VALUES(?,?,'completed',?,?,?,?,?,?,?,1,?,?,?,?)''',
                (1 if k==0 else 3,cid,start.isoformat(),start.isoformat(),(start+timedelta(minutes=minutes)).isoformat(),c['price_cents'],electricity,service,c['power'],energy,amount,amount,minutes*60))
                db.execute('UPDATE chargers SET total_count=total_count+1,total_minutes=total_minutes+? WHERE id=?',(minutes,cid))
        db.commit()
    except Exception:
        db.rollback(); raise
