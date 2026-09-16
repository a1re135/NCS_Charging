"""Transactions and charging state machine, independent of page layout."""
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
    db=get_db(); db.execute('BEGIN IMMEDIATE')
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback(); raise

def money(value, maximum=100000):
    try:
        n=Decimal(str(value))
        if not n.is_finite() or n<=0 or n>maximum or n*100 != (n*100).to_integral_value():
            raise ValueError()
        return int(n*100)
    except (InvalidOperation,ValueError,TypeError):
        raise BusinessError(f'閲戦椤诲ぇ浜?0銆佷笉瓒呰繃 {maximum} 鍏冿紝鏈€澶氫袱浣嶅皬鏁?)

def number(value, low, high, label):
    try:
        n=float(value)
        if not math.isfinite(n) or not low<=n<=high: raise ValueError()
        return n
    except (ValueError,TypeError): raise BusinessError(f'{label}椤诲湪 {low} 鍒?{high} 涔嬮棿')

def required(value, label, limit=100):
    if not isinstance(value,str) or not value.strip() or len(value.strip())>limit:
        raise BusinessError(f'璇峰～鍐檣label}锛?鈥搟limit} 涓瓧绗︼級')
    return value.strip()

def distance(lat,lng,lat2,lng2):
    a,b=map(math.radians,(lat,lat2)); dl=math.radians(lng2-lng)
    h=math.sin((b-a)/2)**2+math.cos(a)*math.cos(b)*math.sin(dl/2)**2
    return round(6371*2*math.asin(math.sqrt(min(1,max(0,h)))),1)

def expire_reservations():
    with transaction() as db:
        rows=db.execute("SELECT id,charger_id FROM orders WHERE status='reserved' AND expires_at<=?",(now(),)).fetchall()
        for row in rows:
            db.execute("UPDATE orders SET status='expired',ended_at=? WHERE id=?",(now(),row['id']))
            db.execute("UPDATE chargers SET status='idle' WHERE id=? AND status='reserved'",(row['charger_id'],))

def quote(order, at=None):
    o=dict(order)
    if o['status']=='charging':
        seconds=max(0,int(((at or datetime.now())-datetime.fromisoformat(o['started_at'])).total_seconds()))*o['time_scale']
        energy=Decimal(str(o['power']))*Decimal(seconds)/Decimal(3600)
        o.update(simulated_seconds=seconds,energy=round(float(energy),3),amount_cents=int((energy*o['price_cents']).quantize(Decimal('1'),rounding=ROUND_HALF_UP)))
    return o

ORDER_SELECT='''SELECT o.*,s.name station_name,s.address,s.lat,s.lng,c.number charger_number,u.nickname,u.phone
 FROM orders o JOIN chargers c ON c.id=o.charger_id JOIN stations s ON s.id=c.station_id JOIN users u ON u.id=o.user_id'''

def create_order(uid,cid,reserve):
    with transaction() as db:
        user=db.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
        if not user['active']: raise BusinessError('璐﹀彿宸插喕缁擄紝璇疯仈绯荤鐞嗗憳',403)
        existing=db.execute("SELECT id FROM orders WHERE user_id=? AND status IN ('reserved','charging')",(uid,)).fetchone()
        if existing: raise BusinessError('鎮ㄦ湁鏈畬鎴愮殑鍏呯數璁㈠崟锛岃鍏堝鐞?,409,order_id=existing['id'])
        if db.execute('SELECT 1 FROM orders WHERE user_id=? AND debt_cents>0',(uid,)).fetchone():
            raise BusinessError('鎮ㄦ湁娆犺垂璁㈠崟锛岃鍏堝厖鍊煎苟琛ョ即娆犺垂',409)
        if user['balance_cents']<=0: raise BusinessError('璇峰厛鍏呭€煎悗鍐嶉绾︽垨鍏呯數')
        c=db.execute('SELECT c.*,s.price_cents FROM chargers c JOIN stations s ON s.id=c.station_id WHERE c.id=?',(cid,)).fetchone()
        if c is None: raise BusinessError('鍏呯數妗╀笉瀛樺湪',404)
        if c['status']!='idle': raise BusinessError('鍏呯數妗╁凡琚崰鐢ㄦ垨澶勪簬鏁呴殰鐘舵€?,409)
        status='reserved' if reserve else 'charging'; t=now()
        cur=db.execute('''INSERT INTO orders(user_id,charger_id,status,created_at,expires_at,started_at,price_cents,power,time_scale)
        VALUES(?,?,?,?,?,?,?,?,?)''',(uid,cid,status,t,(datetime.now()+timedelta(minutes=15)).isoformat(timespec='seconds') if reserve else None,None if reserve else t,c['price_cents'],c['power'],current_app.config['TIME_SCALE']))
        db.execute('UPDATE chargers SET status=? WHERE id=?',(status,cid))
        return cur.lastrowid

def act_order(uid,oid,action):
    with transaction() as db:
        o=db.execute('SELECT * FROM orders WHERE id=? AND user_id=?',(oid,uid)).fetchone()
        if not o: raise BusinessError('璁㈠崟涓嶅瓨鍦?,404)
        c=db.execute('SELECT * FROM chargers WHERE id=?',(o['charger_id'],)).fetchone()
        u=db.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
        if action=='start':
            if o['status']!='reserved': raise BusinessError('璁㈠崟涓嶆槸鏈夋晥棰勭害',409)
            if not u['active'] or c['status']=='fault': raise BusinessError('璐﹀彿鍐荤粨鎴栬澶囨晠闅滐紝鏆傛椂鏃犳硶寮€濮?)
            db.execute("UPDATE orders SET status='charging',started_at=?,expires_at=NULL WHERE id=?",(now(),oid))
            db.execute("UPDATE chargers SET status='charging' WHERE id=?",(c['id'],))
        elif action=='cancel':
            if o['status']!='reserved': raise BusinessError('鍙兘鍙栨秷棰勭害璁㈠崟',409)
            db.execute("UPDATE orders SET status='cancelled',ended_at=? WHERE id=?",(now(),oid))
            db.execute("UPDATE chargers SET status='idle' WHERE id=? AND status='reserved'",(c['id'],))
        elif action=='finish':
            if o['status']!='charging': raise BusinessError('璁㈠崟宸插鐞嗘垨鏈紑濮嬶紝涓嶈兘閲嶅缁撶畻',409)
            end=datetime.now(); q=quote(o,end); paid=min(u['balance_cents'],q['amount_cents'])
            db.execute('''UPDATE orders SET status='completed',ended_at=?,energy=?,amount_cents=?,paid_cents=?,debt_cents=?,balance_after=?,simulated_seconds=? WHERE id=?''',
                (end.isoformat(timespec='seconds'),q['energy'],q['amount_cents'],paid,q['amount_cents']-paid,u['balance_cents']-paid,q['simulated_seconds'],oid))
            db.execute('UPDATE users SET balance_cents=balance_cents-? WHERE id=?',(paid,uid))
            db.execute("UPDATE chargers SET status=CASE WHEN status='charging' THEN 'idle' ELSE status END,total_count=total_count+1,total_minutes=total_minutes+? WHERE id=?",(q['simulated_seconds']//60,c['id']))
            db.execute("INSERT INTO wallet_log(user_id,amount_cents,kind,created_at) VALUES(?,?,'鍏呯數缁撶畻',?)",(uid,-paid,now()))
        elif action=='pay':
            if o['debt_cents']<=0: raise BusinessError('璇ヨ鍗曟病鏈夋瑺璐?,409)
            if u['balance_cents']<o['debt_cents']: raise BusinessError('浣欓涓嶈冻锛岃鍏堝厖鍊?)
            db.execute('UPDATE users SET balance_cents=balance_cents-? WHERE id=?',(o['debt_cents'],uid))
            db.execute('UPDATE orders SET paid_cents=paid_cents+debt_cents,debt_cents=0 WHERE id=?',(oid,))
            db.execute("INSERT INTO wallet_log(user_id,amount_cents,kind,created_at) VALUES(?,?,'琛ョ即娆犺垂',?)",(uid,-o['debt_cents'],now()))
        else: raise BusinessError('涓嶆敮鎸佺殑鎿嶄綔',404)

def audit(actor,text):
    get_db().execute('INSERT INTO ops_log(actor_id,operation,created_at) VALUES(?,?,?)',(actor,text,now()))
