"""Transactions, tariff lookup, and charging state machine, independent of page layout."""
import math
from contextlib import contextmanager
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from flask import current_app
from .db import get_db, now

class BusinessError(Exception):
    def __init__(self, message, status=400, **extra):
        self.message=message; self.status=status; self.extra=extra

@contextmanager
def transaction():
    db = get_db()

    if current_app.config.get("DB_BACKEND") == "mysql":
        db.begin()
    else:
        db.execute("BEGIN IMMEDIATE")

    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise

def lock_sql(sql):
    """
    MySQL/InnoDB uses SELECT ... FOR UPDATE.
    SQLite tests use the original SELECT statement.
    """
    if current_app.config.get("DB_BACKEND") == "mysql":
        return sql.rstrip() + " FOR UPDATE"

    return sql

def money(value, maximum=100000, allow_zero=False):
    try:
        n=Decimal(str(value))
        if not n.is_finite() or n<0 or (n==0 and not allow_zero) or n>maximum or n*100 != (n*100).to_integral_value():
            raise ValueError()
        return int(n*100)
    except (InvalidOperation,ValueError,TypeError):
        lower='大于等于 0' if allow_zero else '大于 0'
        raise BusinessError(f'金额须{lower}、不超过 {maximum} 元，最多两位小数')

def number(value, low, high, label):
    try:
        n=float(value)
        if not math.isfinite(n) or not low<=n<=high: raise ValueError()
        return n
    except (ValueError,TypeError): raise BusinessError(f'{label}须在 {low} 到 {high} 之间')

def required(value, label, limit=100):
    if not isinstance(value,str) or not value.strip() or len(value.strip())>limit:
        raise BusinessError(f'请填写{label}（1–{limit} 个字符）')
    return value.strip()

def distance(lat,lng,lat2,lng2):
    a,b=map(math.radians,(lat,lat2)); dl=math.radians(lng2-lng)
    h=math.sin((b-a)/2)**2+math.cos(a)*math.cos(b)*math.sin(dl/2)**2
    return round(6371*2*math.asin(math.sqrt(min(1,max(0,h)))),1)

def minute_of_day(at=None):
    at=at or datetime.now()
    return at.hour*60+at.minute

def pricing_for_station(db, station_id, at=None):
    """Return the active tariff. Fall back to legacy station price if a rule is missing."""
    minute=minute_of_day(at)
    rule=db.execute('''SELECT * FROM pricing_rules WHERE station_id=? AND start_minute<=? AND end_minute>?
                       ORDER BY start_minute DESC LIMIT 1''',(station_id,minute,minute)).fetchone()
    if rule:
        r=dict(rule); r['price_cents']=r['electricity_fee_cents']+r['service_fee_cents']; return r
    station=db.execute('SELECT price_cents FROM stations WHERE id=?',(station_id,)).fetchone()
    if not station: raise BusinessError('电站不存在',404)
    return dict(id=None,station_id=station_id,start_minute=0,end_minute=1440,
                electricity_fee_cents=station['price_cents'],service_fee_cents=0,price_cents=station['price_cents'])

def expire_reservations():
    with transaction() as db:
        sql = """
            SELECT id, charger_id
            FROM orders
            WHERE status='reserved'
            AND expires_at<=?
        """

        if current_app.config.get("DB_BACKEND") == "mysql":
            sql += " FOR UPDATE"

        rows = db.execute(
            sql,
            (now(),)
        ).fetchall()
        for row in rows:
            db.execute("UPDATE orders SET status='expired',ended_at=? WHERE id=?",(now(),row['id']))
            db.execute("UPDATE chargers SET status='idle' WHERE id=? AND status='reserved'",(row['charger_id'],))

def quote(order, at=None):
    o=dict(order)
    if o['status']=='charging':
        seconds=max(0,int(((at or datetime.now())-datetime.fromisoformat(o['started_at'])).total_seconds()))*o['time_scale']
        energy=Decimal(str(o['power']))*Decimal(seconds)/Decimal(3600)
        o.update(simulated_seconds=seconds,energy=round(float(energy),3),amount_cents=int((energy*o['price_cents']).quantize(Decimal('1'),rounding=ROUND_HALF_UP)))
    amount=int(o.get('amount_cents') or 0); paid=int(o.get('paid_cents') or 0); debt=int(o.get('debt_cents') or 0)
    if o.get('status') in ('reserved','charging'): status='待结算'
    elif debt>0: status='待补缴'
    elif amount<=0: status='无需支付'
    elif paid>=amount: status='已支付'
    elif paid>0: status='部分支付'
    else: status='支付失败'
    o['payment_status']=status
    return o

ORDER_SELECT='''SELECT o.*,s.name station_name,s.address,s.city,s.lat,s.lng,c.number charger_number,u.nickname,u.phone
 FROM orders o JOIN chargers c ON c.id=o.charger_id JOIN stations s ON s.id=c.station_id JOIN users u ON u.id=o.user_id'''

def create_order(uid,cid,reserve):
    with transaction() as db:
        user = db.execute(
            lock_sql(
                "SELECT * FROM users WHERE id=?"
            ),
            (uid,)
        ).fetchone()
        if not user['active']: raise BusinessError('账号已冻结，请联系管理员',403)
        existing=db.execute("SELECT id FROM orders WHERE user_id=? AND status IN ('reserved','charging')",(uid,)).fetchone()
        if existing: raise BusinessError('您有未完成的充电订单，请先处理',409,order_id=existing['id'])
        if db.execute('SELECT 1 FROM orders WHERE user_id=? AND debt_cents>0',(uid,)).fetchone():
            raise BusinessError('您有欠费订单，请先充值并补缴欠费',409)
        if user['balance_cents']<=0:
            from .notifications import create_notification
            create_notification(
                db,
                uid,
                'insufficient_balance',
                '余额不足',
                '当前余额为 ¥0.00，无法开始充电，请先充值。',
                'danger',
                'wallet',
                f'attempt:{now()}',
            )
            raise BusinessError('请先充值后再预约或充电')
        c = db.execute(
            lock_sql(
                """
                SELECT
                    c.*,
                    s.price_cents,
                    s.operating_status
                FROM chargers c
                JOIN stations s
                    ON s.id = c.station_id
                WHERE c.id=?
                """
            ),
            (cid,)
        ).fetchone()
        if c is None: raise BusinessError('充电桩不存在',404)
        if c['operating_status']!='operating': raise BusinessError('该充电站当前暂停运营，暂时不能充电',409)
        if c['status']!='idle': raise BusinessError('充电桩已被占用、离线或处于故障/维修状态',409)
        tariff=pricing_for_station(db,c['station_id'])
        status='reserved' if reserve else 'charging'; t=now()
        cur=db.execute('''INSERT INTO orders(user_id,charger_id,status,created_at,expires_at,started_at,
                          price_cents,electricity_fee_cents,service_fee_cents,power,time_scale)
                          VALUES(?,?,?,?,?,?,?,?,?,?,?)''',
                       (uid,cid,status,t,(datetime.now()+timedelta(minutes=15)).isoformat(timespec='seconds') if reserve else None,
                        None if reserve else t,tariff['price_cents'],tariff['electricity_fee_cents'],tariff['service_fee_cents'],
                        c['power'],current_app.config['TIME_SCALE']))
        db.execute('UPDATE chargers SET status=? WHERE id=?',(status,cid))
        return cur.lastrowid

def act_order(uid,oid,action,payload=None):
    with transaction() as db:
        o = db.execute(
            lock_sql(
                """
                SELECT *
                FROM orders
                WHERE id=? AND user_id=?
                """
            ),
            (oid, uid)
        ).fetchone()
        if not o: raise BusinessError('订单不存在',404)
        c = db.execute(
            lock_sql(
                """
                SELECT
                    c.*,
                    s.operating_status
                FROM chargers c
                JOIN stations s
                    ON s.id = c.station_id
                WHERE c.id=?
                """
            ),
            (o["charger_id"],)
        ).fetchone()
        u = db.execute(
            lock_sql(
                """
                SELECT *
                FROM users
                WHERE id=?
                """
            ),
            (uid,)
        ).fetchone()
        if action=='start':
            if o['status']!='reserved': raise BusinessError('订单不是有效预约',409)
            if not u['active'] or c['operating_status']!='operating': raise BusinessError('账号冻结或电站暂停运营，暂时无法开始')
            tariff=pricing_for_station(db,c['station_id'])
            db.execute('''UPDATE orders SET status='charging',started_at=?,expires_at=NULL,price_cents=?,
                          electricity_fee_cents=?,service_fee_cents=? WHERE id=?''',
                       (now(),tariff['price_cents'],tariff['electricity_fee_cents'],tariff['service_fee_cents'],oid))
            db.execute("UPDATE chargers SET status='charging' WHERE id=?",(c['id'],))
        elif action=='cancel':
            if o['status']!='reserved': raise BusinessError('只能取消预约订单',409)
            db.execute("UPDATE orders SET status='cancelled',ended_at=? WHERE id=?",(now(),oid))
            db.execute("UPDATE chargers SET status='idle' WHERE id=? AND status='reserved'",(c['id'],))
        elif action=='finish':
            if o['status']!='charging': raise BusinessError('订单已处理或未开始，不能重复结算',409)
            end=datetime.now()
            q=quote(o,end)
            q['charger_id']=c['id']

            from .loyalty import settle_with_loyalty

            settle_with_loyalty(
                db,
                uid,
                oid,
                q,
                u,
                payload or {},
            )
        elif action=='pay':
            if o['debt_cents']<=0: raise BusinessError('该订单没有欠费',409)
            if u['balance_cents']<o['debt_cents']: raise BusinessError('余额不足，请先充值')
            db.execute('UPDATE users SET balance_cents=balance_cents-? WHERE id=?',(o['debt_cents'],uid))
            db.execute('UPDATE orders SET paid_cents=paid_cents+debt_cents,debt_cents=0 WHERE id=?',(oid,))
            db.execute("INSERT INTO wallet_log(user_id,amount_cents,kind,created_at) VALUES(?,?,'补缴欠费',?)",(uid,-o['debt_cents'],now()))
        else: raise BusinessError('不支持的操作',404)

def audit(actor,text):
    get_db().execute('INSERT INTO ops_log(actor_id,operation,created_at) VALUES(?,?,?)',(actor,text,now()))
