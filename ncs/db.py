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

def init_db():
    Path(current_app.config['DATABASE']).parent.mkdir(parents=True, exist_ok=True)
    db = get_db()
    db.execute('PRAGMA journal_mode=WAL')
    db.executescript(SCHEMA)
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
            ('海淀 · 智慧充电站','北京市海淀区中关村大街',116.2981,39.9593,160),
            ('城市中心 · 绿能站','北京市东城区中心区域',116.4074,39.9042,150),
            ('朝阳 · 阳光充电站','北京市朝阳区朝阳公园南路',116.4435,39.9219,155),
            ('丰台 · 花园充电站','北京市丰台区丰台北路',116.2869,39.8584,145),
            ('石景山 · 星光充电站','北京市石景山区石景山路',116.2229,39.9062,150)]
        for sid, item in enumerate(stations,1):
            db.execute('INSERT INTO stations VALUES(?,?,?,?,?,?)',(sid,*item))
            for j in range(1,7):
                status='idle'
                if j==6: status={2:'maintenance',3:'fault',4:'offline'}.get(sid,'idle')
                db.execute('INSERT INTO chargers(station_id,number,kind,power,status) VALUES(?,?,?,?,?)',
                    (sid,f'NCS-{sid:02d}{j:02d}','fast' if j<5 else 'slow',60 if j<5 else 7,status))
        rng = random.Random(26)
        for days in range(28,0,-1):
            for k in range(rng.randint(3,7)):
                cid=rng.randint(1,30)
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
