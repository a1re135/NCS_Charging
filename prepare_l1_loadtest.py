"""Prepare/clean deterministic L1 load-test fixtures.

Usage:
  python prepare_l1_loadtest.py --prepare
  python prepare_l1_loadtest.py --cleanup

Fixtures are intentionally separate from the three demo accounts and can be
removed after testing.  They are used only by performance_test.py --write-test.
"""
from __future__ import annotations
import argparse
import sqlite3
from pathlib import Path
from werkzeug.security import generate_password_hash

ROOT=Path(__file__).resolve().parent
DB=ROOT/'data'/'ncs.db'
PASSWORD='LoadTest123456'
PHONE_PREFIX='18800000'
USERS=100


def connect():
    db=sqlite3.connect(DB)
    db.execute('PRAGMA foreign_keys=ON')
    return db


def prepare():
    db=connect()
    try:
        db.execute('BEGIN IMMEDIATE')
        # App initialization creates up to 100 chargers; repair/extend in case
        # an older DB was copied in before the L1 migration.
        stations=db.execute('SELECT COUNT(*) FROM stations').fetchone()[0]
        if stations < 10:
            raise SystemExit('请先启动一次新版本 app.py，使 L1 电站/电桩迁移完成。')
        chargers=db.execute('SELECT COUNT(*) FROM chargers').fetchone()[0]
        if chargers < 100:
            raise SystemExit(f'当前只有 {chargers} 台电桩，需要先完成 L1 规模迁移。')
        for i in range(1, USERS+1):
            phone=f'{PHONE_PREFIX}{i:03d}'  # 18800000001 ... 18800000100
            exists=db.execute('SELECT id FROM users WHERE phone=?',(phone,)).fetchone()
            if exists:
                db.execute('UPDATE users SET balance_cents=100000,active=1 WHERE id=?',(exists[0],))
            else:
                db.execute('''INSERT INTO users(phone,nickname,password_hash,role,balance_cents,active,created_at)
                              VALUES(?,?,?,'user',100000,1,datetime('now'))''',
                           (phone,f'L1-LAB-{i:03d}',generate_password_hash(PASSWORD)))
        # Reset only chargers that do not have active business orders.
        db.execute("UPDATE chargers SET status='idle' WHERE id<=100 AND id NOT IN (SELECT charger_id FROM orders WHERE status IN ('reserved','charging'))")
        db.commit()
        print(f'Prepared {USERS} L1 load-test users and up to 100 chargers.')
        print(f'Login password: {PASSWORD}')
    except Exception:
        db.rollback(); raise
    finally:
        db.close()


def cleanup():
    db=connect()
    try:
        db.execute('BEGIN IMMEDIATE')
        rows=db.execute("SELECT id FROM users WHERE phone LIKE '18800000%' ").fetchall()
        ids=[r[0] for r in rows]
        if ids:
            marks=','.join('?'*len(ids))
            # Remove wallet/order data owned by load-test fixtures. Active orders
            # should be cleared first so charger unique indexes remain healthy.
            db.execute(f"UPDATE orders SET status='cancelled',ended_at=datetime('now') WHERE user_id IN ({marks}) AND status IN ('reserved','charging')",ids)
            chargers=db.execute(f"SELECT charger_id FROM orders WHERE user_id IN ({marks})",ids).fetchall()
            db.execute(f"DELETE FROM wallet_log WHERE user_id IN ({marks})",ids)
            db.execute(f"DELETE FROM orders WHERE user_id IN ({marks})",ids)
            db.execute(f"DELETE FROM users WHERE id IN ({marks})",ids)
        db.execute("UPDATE chargers SET status='idle' WHERE status IN ('charging','reserved') AND id<=100")
        db.commit()
        print(f'Cleaned {len(ids)} L1 load-test users and their orders.')
    except Exception:
        db.rollback(); raise
    finally:
        db.close()

if __name__=='__main__':
    ap=argparse.ArgumentParser(); g=ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--prepare',action='store_true'); g.add_argument('--cleanup',action='store_true')
    a=ap.parse_args(); prepare() if a.prepare else cleanup()
