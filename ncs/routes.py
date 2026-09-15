"""JSON routes. Every privileged action is authorized on the server."""
import csv
import io
import re
import secrets
import pymysql
from datetime import datetime,timedelta
from functools import wraps
from flask import Blueprint,request,session,jsonify,g,Response,current_app
from werkzeug.security import check_password_hash,generate_password_hash
import qrcode
import qrcode.image.svg
from .db import get_db,now
from .services import (BusinessError,transaction,money,number,required,distance,
    expire_reservations,quote,ORDER_SELECT,create_order,act_order,audit,pricing_for_station)
from .capacity import CAPACITY_LEVEL, get_capacity
from .preferences import get_preferences, save_preferences
from .avatars import avatar_url, store_avatar, MAX_BYTES
from .i18n import translate, current_language, operation_display

api=Blueprint('api',__name__)

def body():
    data=request.get_json(silent=True)
    if not isinstance(data,dict): raise BusinessError('请提交 JSON 对象')
    return data

def public_user(u):
    result = {k:u[k] for k in ('id','phone','nickname','role','balance_cents','avatar','active','created_at')}
    result['preferences'] = get_preferences(u['id'])
    result['avatar_url'] = avatar_url(u['id'])
    return result

def day(value, field):
    try:
        return datetime.strptime(
            value,
            "%Y-%m-%d"
        ).date()
    except (TypeError, ValueError):
        raise BusinessError(
            f"{field}格式不正确，应为 YYYY-MM-DD"
        )

def auth(admin=False):
    def deco(fn):
        @wraps(fn)
        def wrapped(*args,**kwargs):
            g.user=get_db().execute('SELECT * FROM users WHERE id=?',(session.get('uid'),)).fetchone()
            if g.user is None: raise BusinessError('请先登录',401)
            if admin and (g.user['role']!='admin' or not g.user['active']): raise BusinessError('需要管理员权限',403)
            expire_reservations()
            return fn(*args,**kwargs)
        return wrapped
    return deco

def parse_clock(value,label,allow_24=False):
    if not isinstance(value,str) or not re.fullmatch(r'\d{2}:\d{2}',value):
        raise BusinessError(f'{label}格式应为 HH:MM')
    h,m=map(int,value.split(':'))
    if allow_24 and h==24 and m==0: return 1440
    if not (0<=h<=23 and 0<=m<=59): raise BusinessError(f'{label}无效')
    return h*60+m

def clock_text(minute):
    return '24:00' if minute==1440 else f'{minute//60:02d}:{minute%60:02d}'

def pricing_json(row):
    r=dict(row)
    r['start_time']=clock_text(r['start_minute']); r['end_time']=clock_text(r['end_minute'])
    r['price_cents']=r['electricity_fee_cents']+r['service_fee_cents']
    return r

def add_default_pricing(db,sid,base):
    service=30; totals=(max(40,base-20),base,base+20)
    for start,end,total in ((0,480,totals[0]),(480,1080,totals[1]),(1080,1440,totals[2])):
        db.execute('''INSERT INTO pricing_rules(station_id,start_minute,end_minute,electricity_fee_cents,service_fee_cents)
                      VALUES(?,?,?,?,?)''',(sid,start,end,max(0,total-service),service))

@api.get('/session')
def get_session():
    session.setdefault('csrf',secrets.token_hex(24))
    u=get_db().execute('SELECT * FROM users WHERE id=?',(session.get('uid'),)).fetchone()
    return jsonify(csrf=session['csrf'],user=public_user(u) if u else None,time_scale=current_app.config['TIME_SCALE'])

@api.get('/preferences')
@auth()
def read_preferences():
    return jsonify(preferences=get_preferences(g.user['id']))

@api.post('/preferences')
@auth()
def update_preferences():
    data = body()
    language = data.get('language')
    theme = data.get('theme')
    if not isinstance(language, str) or language not in ('zh', 'en'):
        raise BusinessError('语言设置无效')
    if not isinstance(theme, str) or theme not in ('light', 'dark', 'system'):
        raise BusinessError('外观设置无效')
    # The target user is always the authenticated user, never a client-supplied ID.
    preferences = save_preferences(g.user['id'], language, theme, current_app.config['DB_BACKEND'])
    return jsonify(preferences=preferences)

@api.get("/health")
def health():
    db_ok = True

    try:
        get_db().execute("SELECT 1").fetchone()
    except Exception:
        db_ok = False

    return jsonify(
        ok=db_ok,
        service="ncs-charging",
        capacity_level=CAPACITY_LEVEL,
        database="ok" if db_ok else "error",
    )


@api.get("/capacity")
@auth()
def capacity():
    target = get_capacity()
    db = get_db()

    actual = {
        "registered_users": db.execute(
            "SELECT COUNT(*) FROM users WHERE role='user'"
        ).fetchone()[0],

        "stations": db.execute(
            "SELECT COUNT(*) FROM stations"
        ).fetchone()[0],

        "chargers": db.execute(
            "SELECT COUNT(*) FROM chargers"
        ).fetchone()[0],

        "online_users_approx": db.execute(
            "SELECT COUNT(*) FROM users WHERE active=1"
        ).fetchone()[0],
    }

    return jsonify(
        level=CAPACITY_LEVEL,
        target=target,
        actual=actual,
    )

@api.post('/login')
def login():
    d=body(); account=required(d.get('phone'),'账号'); password=required(d.get('password'),'密码',128)
    u=get_db().execute('SELECT * FROM users WHERE phone=?',(account,)).fetchone()
    if not u or not check_password_hash(u['password_hash'],password): raise BusinessError('账号或密码不正确',401)
    session.clear(); session.update(uid=u['id'],csrf=secrets.token_hex(24))
    return jsonify(user=public_user(u),csrf=session['csrf'])

@api.post('/register')
def register():
    d=body(); phone=required(d.get('phone'),'手机号'); password=required(d.get('password'),'密码',128)
    if not re.fullmatch(r'1[3-9]\d{9}',phone): raise BusinessError('请输入有效的 11 位手机号')
    if len(password)<8: raise BusinessError('密码至少 8 位')
    name=required(d.get('nickname'),'昵称',24)
    with transaction() as db:
        cur=db.execute('INSERT INTO users(phone,nickname,password_hash,created_at) VALUES(?,?,?,?)',(phone,name,generate_password_hash(password),now()))
        uid=cur.lastrowid
    session.clear(); session.update(uid=uid,csrf=secrets.token_hex(24))
    return jsonify(csrf=session['csrf'],user=public_user(get_db().execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone())),201

@api.post('/logout')
def logout():
    session.clear(); return jsonify(ok=True)

@api.get('/stations')
@auth()
def stations():
    lat = number(
        request.args.get('lat', 39.9593),
        -90, 90, '纬度'
    )
    lng = number(
        request.args.get('lng', 116.2981),
        -180, 180, '经度'
    )

    status = request.args.get('status', '')
    kind = request.args.get('kind', '')
    sort = request.args.get('sort', 'distance')

    if status not in ('', 'idle', 'fault', 'maintenance', 'offline'):
        raise BusinessError('电站状态筛选无效')

    if kind not in ('', 'fast', 'slow'):
        raise BusinessError('充电类型筛选无效')

    if sort not in ('distance', 'usage'):
        raise BusinessError('排序方式无效')

    db = get_db()

    sql = '''
        SELECT
            s.*,

            COUNT(c.id) AS total,

            SUM(
                CASE WHEN c.status='idle'
                THEN 1 ELSE 0 END
            ) AS free,

            SUM(
                CASE WHEN c.kind='fast'
                THEN 1 ELSE 0 END
            ) AS fast,

            SUM(
                CASE WHEN c.kind='slow'
                THEN 1 ELSE 0 END
            ) AS slow,

            COALESCE(SUM(c.total_count), 0) AS `usage`,

            SUM(
                CASE WHEN c.status='fault'
                THEN 1 ELSE 0 END
            ) AS fault,

            SUM(
                CASE WHEN c.status='maintenance'
                THEN 1 ELSE 0 END
            ) AS maintenance,

            SUM(
                CASE WHEN c.status='offline'
                THEN 1 ELSE 0 END
            ) AS offline

        FROM stations s

        LEFT JOIN chargers c
            ON c.station_id = s.id
    '''

    conditions = []
    args = []

    if status:
        conditions.append(
            '''
            EXISTS(
                SELECT 1
                FROM chargers x
                WHERE x.station_id=s.id
                AND x.status=?
            )
            '''
        )
        args.append(status)

    if kind:
        conditions.append(
            '''
            EXISTS(
                SELECT 1
                FROM chargers x
                WHERE x.station_id=s.id
                AND x.kind=?
            )
            '''
        )
        args.append(kind)

    if conditions:
        sql += ' WHERE ' + ' AND '.join(conditions)

    sql += ' GROUP BY s.id'

    result = []

    for row in db.execute(sql, args):
        r = dict(row)

        # Keep Rey frontend compatibility
        r['fast_count'] = r['fast']
        r['slow_count'] = r['slow']

        tariff = pricing_for_station(
            db,
            r['id']
        )

        r.update(
            current_price_cents=tariff['price_cents'],
            electricity_fee_cents=tariff['electricity_fee_cents'],
            service_fee_cents=tariff['service_fee_cents'],
        )

        r['distance'] = distance(
            lat,
            lng,
            r['lat'],
            r['lng']
        )

        result.append(r)

    if sort == 'usage':
        result.sort(
            key=lambda r: (
                -r['usage'],
                r['distance']
            )
        )
    else:
        result.sort(
            key=lambda r: r['distance']
        )

    return jsonify(result)

@api.get('/stations/<int:sid>')
@auth()
def station(sid):
    db=get_db(); row=db.execute('SELECT * FROM stations WHERE id=?',(sid,)).fetchone()
    if not row: raise BusinessError('电站不存在',404)
    station_data=dict(row); tariff=pricing_for_station(db,sid)
    station_data.update(current_price_cents=tariff['price_cents'],electricity_fee_cents=tariff['electricity_fee_cents'],service_fee_cents=tariff['service_fee_cents'])
    rules=[pricing_json(r) for r in db.execute('SELECT * FROM pricing_rules WHERE station_id=? ORDER BY start_minute',(sid,))]
    return jsonify(station=station_data,
                   chargers=[dict(r) for r in db.execute('SELECT * FROM chargers WHERE station_id=? ORDER BY number',(sid,))],
                   pricing=rules)

@api.get('/chargers/by-number/<string:number_value>')
@auth()
def charger_by_number(number_value):
    row=get_db().execute('''SELECT c.*,s.name station_name,s.address,s.city,s.business_hours,s.operating_status,
                            s.parking_info FROM chargers c JOIN stations s ON s.id=c.station_id WHERE c.number=?''',(number_value,)).fetchone()
    if not row: raise BusinessError('二维码对应的充电桩不存在',404)
    return jsonify(dict(row))

@api.get('/chargers/<int:cid>/qr')
@auth()
def charger_qr(cid):
    c=get_db().execute('SELECT id,number FROM chargers WHERE id=?',(cid,)).fetchone()
    if not c: raise BusinessError('充电桩不存在',404)
    charge_url=request.host_url.rstrip('/')+'/charge/'+c['number']
    image=qrcode.make(charge_url,image_factory=qrcode.image.svg.SvgPathImage,box_size=8,border=2)
    out=io.BytesIO(); image.save(out)
    return Response(out.getvalue(),mimetype='image/svg+xml',headers={'Cache-Control':'no-store','Content-Disposition':f'inline; filename={c["number"]}.svg'})

@api.get('/orders')
@auth()
def orders():
    if g.user['role'] == 'admin':
        where = ''
        params = []
    else:
        where = ' WHERE o.user_id=?'
        params = [g.user['id']]

    conditions = []

    date_from = request.args.get(
        'date_from',
        ''
    )

    date_to = request.args.get(
        'date_to',
        ''
    )

    if date_from:
        day(
            date_from,
            '开始日期'
        )

        conditions.append(
            'substr(o.created_at,1,10)>=?'
        )

        params.append(date_from)

    if date_to:
        day(
            date_to,
            '结束日期'
        )

        conditions.append(
            'substr(o.created_at,1,10)<=?'
        )

        params.append(date_to)

    if (
        date_from
        and date_to
        and date_from > date_to
    ):
        raise BusinessError(
            '开始日期不能晚于结束日期'
        )

    if conditions:
        where += (
            ' AND '
            if where
            else ' WHERE '
        )

        where += ' AND '.join(
            conditions
        )

    rows = get_db().execute(
        ORDER_SELECT
        + where
        + ' ORDER BY o.id DESC',
        params,
    )

    return jsonify([
        quote(r)
        for r in rows
    ])

@api.post('/orders')
@auth()
def new_order():
    if g.user['role']!='user': raise BusinessError('请使用用户账号预约充电')
    d=body()
    if d.get('mode') not in ('reserve','start'): raise BusinessError('请选择预约或开始充电')
    if not isinstance(d.get('charger_id'),int): raise BusinessError('充电桩编号无效')
    oid=create_order(g.user['id'],d['charger_id'],d['mode']=='reserve')
    return jsonify(id=oid),201

@api.post('/orders/<int:oid>/<action>')
@auth()
def order_action(oid,action):
    act_order(g.user['id'],oid,action)
    return jsonify(order=quote(get_db().execute(ORDER_SELECT+' WHERE o.id=?',(oid,)).fetchone()))

@api.get('/orders/<int:oid>/receipt')
@auth()
def receipt(oid):
    row=get_db().execute(ORDER_SELECT+' WHERE o.id=?',(oid,)).fetchone()
    if not row or (g.user['role']!='admin' and row['user_id']!=g.user['id']): raise BusinessError('订单不存在',404)
    return jsonify(quote(row))

@api.post('/profile')
@auth()
def profile():
    d=body(); name=required(d.get('nickname'),'昵称',24)
    avatar=d.get('avatar','lavender')
    if avatar not in ('lavender','pink','blue','mint'): raise BusinessError('头像主题无效')
    get_db().execute('UPDATE users SET nickname=?,avatar=? WHERE id=?',(name,avatar,g.user['id']))
    return jsonify(ok=True)

@api.post('/profile/password')
@auth()
def password():
    d=body()
    if not check_password_hash(g.user['password_hash'],str(d.get('old_password',''))): raise BusinessError('原密码不正确')
    pw=required(d.get('new_password'),'新密码',128)
    if len(pw)<8: raise BusinessError('密码至少 8 位')
    get_db().execute('UPDATE users SET password_hash=? WHERE id=?',(generate_password_hash(pw),g.user['id']))
    return jsonify(ok=True)

@api.post('/wallet/recharge')
@auth()
def recharge():
    if not g.user['active']: raise BusinessError('账号已冻结，暂时无法充值',403)
    cents=money(body().get('amount'))
    with transaction() as db:
        db.execute('UPDATE users SET balance_cents=balance_cents+? WHERE id=?',(cents,g.user['id']))
        db.execute("INSERT INTO wallet_log(user_id,amount_cents,kind,created_at) VALUES(?,?,'模拟充值',?)",(g.user['id'],cents,now()))
    return jsonify(ok=True)

@api.get('/wallet')
@auth()
def wallet():
    return jsonify([dict(r) for r in get_db().execute('SELECT * FROM wallet_log WHERE user_id=? ORDER BY id DESC LIMIT 100',(g.user['id'],))])

@api.get('/dashboard')
@auth()
def dashboard():
    db=get_db(); admin=g.user['role']=='admin'; uid=g.user['id']
    filt='' if admin else ' AND user_id=?'; args=() if admin else (uid,)
    totals=dict(db.execute("SELECT COUNT(*) orders,COALESCE(SUM(energy),0) energy,COALESCE(SUM(paid_cents),0) paid_cents,COALESCE(SUM(debt_cents),0) debt_cents FROM orders WHERE status='completed'"+filt,args).fetchone())
    counts={r['status']:r['n'] for r in db.execute('SELECT status,COUNT(*) n FROM chargers GROUP BY status')}
    days=[]
    for i in range(6,-1,-1):
        day=(datetime.now()-timedelta(days=i)).strftime('%Y-%m-%d')
        row=db.execute("SELECT COALESCE(SUM(energy),0) energy,COALESCE(SUM(paid_cents),0) cents,COUNT(*) orders FROM orders WHERE status='completed' AND substr(ended_at,1,10)=?"+filt,(day,*args)).fetchone()
        days.append(dict(day=day,**dict(row)))
    active=[quote(r) for r in db.execute(ORDER_SELECT+" WHERE o.status IN ('reserved','charging')"+('' if admin else ' AND o.user_id=?')+' ORDER BY o.id DESC',args)]
    return jsonify(totals=totals,counts=counts,days=days,active=active,
                   stations=db.execute('SELECT COUNT(*) FROM stations').fetchone()[0],
                   users=db.execute("SELECT COUNT(*) FROM users WHERE role='user'").fetchone()[0],
                   open_faults=db.execute("SELECT COUNT(*) FROM fault_records WHERE status IN ('pending','processing')").fetchone()[0])

@api.get('/admin/users')
@auth(True)
def users():
    status = request.args.get('status', '')
    sort = request.args.get('sort', 'newest')

    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    if status not in (
        '',
        'normal',
        'debt',
        'frozen'
    ):
        raise BusinessError(
            '用户状态筛选无效'
        )

    if sort not in (
        'newest',
        'oldest'
    ):
        raise BusinessError(
            '排序方式无效'
        )

    if date_from:
        day(
            date_from,
            '开始日期'
        )

    if date_to:
        day(
            date_to,
            '结束日期'
        )

    if (
        date_from
        and date_to
        and date_from > date_to
    ):
        raise BusinessError(
            '开始日期不能晚于结束日期'
        )

    sql = '''
        SELECT
            u.id,
            u.phone,
            u.nickname,
            u.role,
            u.balance_cents,
            u.avatar,
            u.active,
            u.created_at,

            COALESCE(
                SUM(o.debt_cents),
                0
            ) AS debt_cents

        FROM users u

        LEFT JOIN orders o
            ON o.user_id = u.id
            AND o.debt_cents > 0

        WHERE u.role='user'
    '''

    conditions = []
    params = []

    if date_from:
        conditions.append(
            'substr(u.created_at,1,10)>=?'
        )
        params.append(date_from)

    if date_to:
        conditions.append(
            'substr(u.created_at,1,10)<=?'
        )
        params.append(date_to)

    if conditions:
        sql += (
            ' AND '
            + ' AND '.join(conditions)
        )

    sql += ' GROUP BY u.id'

    rows = [
        dict(r)
        for r in get_db().execute(
            sql,
            params
        )
    ]

    def state(row):
        if row['debt_cents'] > 0:
            return 'debt'

        if not row['active']:
            return 'frozen'

        return 'normal'

    if status:
        rows = [
            r
            for r in rows
            if state(r) == status
        ]

    rows.sort(
        key=lambda r: r['created_at'],
        reverse=(sort == 'newest')
    )

    return jsonify(rows)

@api.post('/admin/users/<int:uid>')
@auth(True)
def user_update(uid):
    active=body().get('active')
    if type(active) is not bool: raise BusinessError('用户状态无效')
    with transaction() as db:
        cur=db.execute("UPDATE users SET active=? WHERE id=? AND role='user'",(int(active),uid))
        if not cur.rowcount: raise BusinessError('用户不存在',404)
        audit(g.user['id'],f'{"启用" if active else "冻结"}用户 #{uid}')
    return jsonify(ok=True)

@api.post('/admin/stations')
@api.post('/admin/stations/<int:sid>')
@auth(True)
def station_save(sid=None):
    d=body(); status=d.get('operating_status','operating')
    if status not in ('operating','paused','maintenance'): raise BusinessError('运营状态无效')
    vals=(required(d.get('name'),'站名',60),required(d.get('address'),'地址',160),required(d.get('city','北京市'),'所属城市',60),
          required(d.get('business_hours','00:00-24:00'),'营业时间',60),required(d.get('contact_phone','010-00000000'),'联系方式',40),status,
          required(d.get('parking_info','以现场停车规定为准'),'停车说明',240),number(d.get('lng'),-180,180,'经度'),number(d.get('lat'),-90,90,'纬度'),money(d.get('price'),100))
    with transaction() as db:
        if sid:
            if not db.execute('''UPDATE stations SET name=?,address=?,city=?,business_hours=?,contact_phone=?,operating_status=?,parking_info=?,lng=?,lat=?,price_cents=? WHERE id=?''',(*vals,sid)).rowcount:
                raise BusinessError('电站不存在',404)
        else:
            sid=db.execute('''INSERT INTO stations(name,address,city,business_hours,contact_phone,operating_status,parking_info,lng,lat,price_cents)
                              VALUES(?,?,?,?,?,?,?,?,?,?)''',vals).lastrowid
            add_default_pricing(db,sid,vals[-1])
        audit(g.user['id'],f'保存电站 #{sid}')
    return jsonify(id=sid)

@api.delete('/admin/stations/<int:sid>')
@auth(True)
def station_delete(sid):
    with transaction() as db:
        if db.execute('SELECT 1 FROM chargers WHERE station_id=?',(sid,)).fetchone(): raise BusinessError('请先处理该站充电桩；有历史订单的设备需保留')
        if not db.execute('DELETE FROM stations WHERE id=?',(sid,)).rowcount: raise BusinessError('电站不存在',404)
        audit(g.user['id'],f'删除电站 #{sid}')
    return jsonify(ok=True)

@api.get('/admin/pricing')
@auth(True)
def pricing_list():
    sid=request.args.get('station_id',type=int); db=get_db()
    if sid and not db.execute('SELECT 1 FROM stations WHERE id=?',(sid,)).fetchone(): raise BusinessError('电站不存在',404)
    sql='''SELECT p.*,s.name station_name FROM pricing_rules p JOIN stations s ON s.id=p.station_id'''
    args=()
    if sid: sql+=' WHERE p.station_id=?'; args=(sid,)
    sql+=' ORDER BY s.id,p.start_minute'
    return jsonify([pricing_json(r) for r in db.execute(sql,args)])

@api.post('/admin/pricing')
@api.post('/admin/pricing/<int:pid>')
@auth(True)
def pricing_save(pid=None):
    d=body(); sid=d.get('station_id')
    if not isinstance(sid,int): raise BusinessError('电站编号无效')
    start=parse_clock(d.get('start_time'),'开始时间'); end=parse_clock(d.get('end_time'),'结束时间',True)
    if end<=start: raise BusinessError('结束时间必须晚于开始时间；跨午夜请拆成两个时段')
    electricity=money(d.get('electricity_fee'),100,allow_zero=True); service=money(d.get('service_fee'),100,allow_zero=True)
    if electricity+service<=0: raise BusinessError('电费和服务费不能同时为 0')
    with transaction() as db:
        if not db.execute('SELECT 1 FROM stations WHERE id=?',(sid,)).fetchone(): raise BusinessError('电站不存在',404)
        clash=db.execute('''SELECT id FROM pricing_rules WHERE station_id=? AND start_minute<? AND end_minute>?
                            AND (? IS NULL OR id<>?) LIMIT 1''',(sid,end,start,pid,pid)).fetchone()
        if clash: raise BusinessError('该时段与已有价格规则重叠，请先调整时间')
        if pid:
            cur=db.execute('''UPDATE pricing_rules SET station_id=?,start_minute=?,end_minute=?,electricity_fee_cents=?,service_fee_cents=? WHERE id=?''',
                           (sid,start,end,electricity,service,pid))
            if not cur.rowcount: raise BusinessError('价格规则不存在',404)
        else:
            pid=db.execute('''INSERT INTO pricing_rules(station_id,start_minute,end_minute,electricity_fee_cents,service_fee_cents)
                              VALUES(?,?,?,?,?)''',(sid,start,end,electricity,service)).lastrowid
        audit(g.user['id'],f'保存分时价格规则 #{pid}')
    return jsonify(id=pid)

@api.delete('/admin/pricing/<int:pid>')
@auth(True)
def pricing_delete(pid):
    with transaction() as db:
        row=db.execute('SELECT * FROM pricing_rules WHERE id=?',(pid,)).fetchone()
        if not row: raise BusinessError('价格规则不存在',404)
        if db.execute('SELECT COUNT(*) FROM pricing_rules WHERE station_id=?',(row['station_id'],)).fetchone()[0]<=1:
            raise BusinessError('每个电站至少保留一条价格规则')
        db.execute('DELETE FROM pricing_rules WHERE id=?',(pid,))
        audit(g.user['id'],f'删除分时价格规则 #{pid}')
    return jsonify(ok=True)

@api.get('/admin/chargers')
@auth(True)
def chargers():
    return jsonify([dict(r) for r in get_db().execute('SELECT c.*,s.name station_name FROM chargers c JOIN stations s ON s.id=c.station_id ORDER BY c.id')])

@api.post('/admin/chargers')
@api.post('/admin/chargers/<int:cid>')
@auth(True)
def charger_save(cid=None):
    d=body(); kind=d.get('kind')
    if kind not in ('fast','slow'): raise BusinessError('电桩类型无效')
    sid=d.get('station_id')
    if not isinstance(sid,int): raise BusinessError('电站编号无效')
    vals=(sid,required(d.get('number'),'电桩编号',30),kind,number(d.get('power'),1,1000,'功率'))
    with transaction() as db:
        if cid:
            c=db.execute('SELECT * FROM chargers WHERE id=?',(cid,)).fetchone()
            if not c: raise BusinessError('电桩不存在',404)
            if c['status'] in ('charging','reserved'): raise BusinessError('使用中的电桩不能编辑')
            if c['station_id']!=sid and db.execute('SELECT 1 FROM orders WHERE charger_id=?',(cid,)).fetchone(): raise BusinessError('有历史订单的电桩不能迁移电站')
            db.execute('UPDATE chargers SET station_id=?,number=?,kind=?,power=? WHERE id=?',(*vals,cid))
        else: cid=db.execute('INSERT INTO chargers(station_id,number,kind,power) VALUES(?,?,?,?)',vals).lastrowid
        audit(g.user['id'],f'保存电桩 #{cid}')
    return jsonify(id=cid)

@api.post('/admin/chargers/<int:cid>/action')
@auth(True)
def charger_action(cid):
    action=body().get('action')
    with transaction() as db:
        c=db.execute('SELECT * FROM chargers WHERE id=?',(cid,)).fetchone()
        if not c: raise BusinessError('电桩不存在',404)
        if c['status'] in ('charging','reserved'): raise BusinessError('电桩有未完成订单，不能操作',409)
        if action=='delete':
            db.execute('DELETE FROM chargers WHERE id=?',(cid,))
        elif action=='fault':
            if not db.execute("SELECT 1 FROM fault_records WHERE charger_id=? AND status IN ('pending','processing')",(cid,)).fetchone():
                db.execute('''INSERT INTO fault_records(charger_id,fault_type,description,status,reported_at,reporter_id)
                              VALUES(?,?,'由设备管理页面手动标记','pending',?,?)''',(cid,'设备异常',now(),g.user['id']))
            db.execute("UPDATE chargers SET status='fault' WHERE id=?",(cid,))
        elif action in ('restore','restart'):
            db.execute("UPDATE fault_records SET status='resolved',handled_at=?,resolution=COALESCE(resolution,?),handler_id=? WHERE charger_id=? AND status IN ('pending','processing')",
                       (now(),'软件重启恢复' if action=='restart' else '管理员手动恢复',g.user['id'],cid))
            db.execute("UPDATE chargers SET status='idle' WHERE id=?",(cid,))
        elif action in ('offline','maintenance'):
            db.execute('UPDATE chargers SET status=? WHERE id=?',(action,cid))
        else: raise BusinessError('操作无效')
        audit(g.user['id'],f'电桩 #{cid}：{action}'+('（软件模拟）' if action=='restart' else ''))
    return jsonify(ok=True)

@api.get('/admin/faults')
@auth(True)
def faults():
    return jsonify([dict(r) for r in get_db().execute('''SELECT f.*,c.number charger_number,s.name station_name
        FROM fault_records f JOIN chargers c ON c.id=f.charger_id JOIN stations s ON s.id=c.station_id
        ORDER BY CASE f.status WHEN 'pending' THEN 0 WHEN 'processing' THEN 1 ELSE 2 END,f.id DESC''')])

@api.post('/admin/faults')
@auth(True)
def fault_create():
    d=body(); cid=d.get('charger_id')
    if not isinstance(cid,int): raise BusinessError('充电桩编号无效')
    fault_type=required(d.get('fault_type'),'故障类型',60); description=required(d.get('description'),'故障描述',300)
    with transaction() as db:
        c=db.execute('SELECT * FROM chargers WHERE id=?',(cid,)).fetchone()
        if not c: raise BusinessError('充电桩不存在',404)
        if c['status'] in ('reserved','charging'): raise BusinessError('设备正在被订单占用，不能登记故障',409)
        if db.execute("SELECT 1 FROM fault_records WHERE charger_id=? AND status IN ('pending','processing')",(cid,)).fetchone():
            raise BusinessError('该设备已有未处理故障',409)
        fid=db.execute('''INSERT INTO fault_records(charger_id,fault_type,description,status,reported_at,reporter_id)
                          VALUES(?,?,?,'pending',?,?)''',(cid,fault_type,description,now(),g.user['id'])).lastrowid
        db.execute("UPDATE chargers SET status='fault' WHERE id=?",(cid,))
        audit(g.user['id'],f'登记故障 #{fid} / 电桩 #{cid}')
    return jsonify(id=fid),201

@api.post('/admin/faults/<int:fid>')
@auth(True)
def fault_update(fid):
    d=body(); status=d.get('status')
    if status not in ('pending','processing','resolved'): raise BusinessError('故障处理状态无效')
    resolution=str(d.get('resolution') or '').strip()
    if status=='resolved' and not resolution: raise BusinessError('解决故障时请填写处理结果')
    with transaction() as db:
        f=db.execute('SELECT * FROM fault_records WHERE id=?',(fid,)).fetchone()
        if not f: raise BusinessError('故障记录不存在',404)
        handled=now() if status=='resolved' else None
        db.execute('''UPDATE fault_records SET status=?,handled_at=?,resolution=?,handler_id=? WHERE id=?''',
                   (status,handled,resolution or None,g.user['id'],fid))
        target={'pending':'fault','processing':'maintenance','resolved':'idle'}[status]
        db.execute('UPDATE chargers SET status=? WHERE id=?',(target,f['charger_id']))
        audit(g.user['id'],f'更新故障 #{fid}：{status}')
    return jsonify(ok=True)

@api.get('/admin/logs')
@auth(True)
def logs():
    rows = [dict(r) for r in get_db().execute('SELECT * FROM ops_log ORDER BY id DESC LIMIT 100')]
    for row in rows:
        row['operation_display'] = operation_display(row['operation'])
    return jsonify(rows)

@api.get('/admin/prediction')
@auth(True)
def prediction():
    sid=request.args.get('station_id',1,type=int); db=get_db()
    if not db.execute('SELECT 1 FROM stations WHERE id=?',(sid,)).fetchone(): raise BusinessError('电站不存在',404)
    rows=db.execute("SELECT o.* FROM orders o JOIN chargers c ON c.id=o.charger_id WHERE c.station_id=? AND o.status='completed' AND o.started_at>=?",(sid,(datetime.now()-timedelta(days=28)).isoformat())).fetchall()
    capacity=db.execute('SELECT COALESCE(SUM(power),0),COUNT(*) FROM chargers WHERE station_id=?',(sid,)).fetchone()
    if not rows: return jsonify(points=[],sample_count=0,method='历史数据不足，请积累充电订单后重试')
    points=[]
    for i in range(1,13):
        t=(datetime.now()+timedelta(hours=i)).replace(minute=0,second=0,microsecond=0)
        energy=sum(r['energy'] for r in rows if datetime.fromisoformat(r['started_at']).hour==t.hour)/28
        load=min(capacity[0],energy); ratio=load/capacity[0] if capacity[0] else 0
        points.append(dict(time=t.isoformat(),load=round(load,2),free=max(0,round(capacity[1]*(1-ratio))),peak=ratio>=0.7))
    return jsonify(points=points,sample_count=len(rows),method='近 28 天同小时订单电量均值；按装机功率估算空闲数，仅供课程演示')

@api.get('/admin/export')
@auth(True)
def export():
    out=io.StringIO(); writer=csv.writer(out)
    writer.writerow([translate(label) for label in ['订单号','用户编号','电站','电桩','状态','电量(kWh)','金额(元)','已付(元)','欠费(元)','开始时间','结束时间']])
    def safe(v):
        s=str(v or '')
        return "'"+s if s[:1] in ('=','+','-','@','\t','\r') else s
    for r in get_db().execute(ORDER_SELECT+' ORDER BY o.id DESC'):
        writer.writerow([r['id'],r['user_id'],safe(r['station_name']),safe(r['charger_number']),r['status'],r['energy'],r['amount_cents']/100,r['paid_cents']/100,r['debt_cents']/100,r['started_at'],r['ended_at']])
    return Response('\ufeff'+out.getvalue(),mimetype='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename=ncs-orders.csv'})


@api.get('/profile/avatar')
@auth()
def get_avatar():
    row = get_db().execute('SELECT image_data FROM user_avatars WHERE user_id=?', (g.user['id'],)).fetchone()
    if not row:
        raise BusinessError('尚未上传头像', 404)
    response = Response(bytes(row['image_data']), mimetype='image/jpeg')
    response.headers['Cache-Control'] = 'private, no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response

@api.post('/profile/avatar')
@auth()
def upload_avatar():
    image = request.files.get('image')
    if image is None:
        raise BusinessError('请选择头像图片')
    url = store_avatar(g.user['id'], image.read(MAX_BYTES + 1), current_app.config['DB_BACKEND'])
    return jsonify(ok=True, avatar_url=url)

@api.delete('/profile/avatar')
@auth()
def reset_avatar():
    get_db().execute('DELETE FROM user_avatars WHERE user_id=?', (g.user['id'],))
    return jsonify(ok=True, avatar_url=None)
