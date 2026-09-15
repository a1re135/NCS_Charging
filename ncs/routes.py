"""JSON routes. Every privileged action is authorized on the server."""
import csv
import io
import re
import secrets
from datetime import datetime,timedelta
from functools import wraps
from flask import Blueprint,request,session,jsonify,g,Response,current_app
from werkzeug.security import check_password_hash,generate_password_hash
from .db import get_db,now
from .services import (BusinessError,transaction,money,number,required,distance,
    expire_reservations,quote,ORDER_SELECT,create_order,act_order,audit)
from .capacity import CAPACITY_LEVEL, get_capacity

api=Blueprint('api',__name__)

def body():
    data=request.get_json(silent=True)
    if not isinstance(data,dict): raise BusinessError('请提交 JSON 对象')
    return data

def day(value,label):
    try: datetime.strptime(value,'%Y-%m-%d')
    except (ValueError,TypeError): raise BusinessError(f'{label}格式应为 YYYY-MM-DD')
    return value

def public_user(u):
    if u is None: return None
    row=dict(u); row['role_name']=get_role_meta(row['role'])['name']; row['permissions']=get_permissions(row['role'])
    return {k:row[k] for k in ('id','phone','nickname','role','role_name','permissions','balance_cents','avatar','active','created_at')}

def get_permissions(role):
    return [r['key'] for r in get_db().execute('SELECT p.key FROM permissions p JOIN role_permissions rp ON rp.permission_key=p.key WHERE rp.role_key=? ORDER BY p.key',(role,)).fetchall()]

def get_role_meta(role):
    r=get_db().execute('SELECT key,name,description,level FROM roles WHERE key=?',(role,)).fetchone()
    return dict(r) if r else {'key':role,'name':role,'description':'','level':0}

def has_permission(role, key):
    return bool(get_db().execute('SELECT 1 FROM role_permissions WHERE role_key=? AND permission_key=?',(role,key)).fetchone())

def permission(key):
    def deco(fn):
        @wraps(fn)
        def wrapped(*args,**kwargs):
            # Permission can be placed outside @auth() on existing routes; load
            # the session user here so authorization is deterministic regardless
            # of decorator order.
            if getattr(g,'user',None) is None:
                uid=session.get('uid')
                if uid is None: raise BusinessError('请先登录',401)
                g.user=get_db().execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
            if g.user is None: raise BusinessError('请先登录',401)
            if not g.user['active']: raise BusinessError('账号已冻结，暂时无法访问',403)
            if not has_permission(g.user['role'],key): raise BusinessError(f'当前角色没有“{key}”权限',403)
            return fn(*args,**kwargs)
        return wrapped
    return deco

def auth(admin=False, allow_frozen=False):
    def deco(fn):
        @wraps(fn)
        def wrapped(*args,**kwargs):
            g.user=get_db().execute('SELECT * FROM users WHERE id=?',(session.get('uid'),)).fetchone()
            if g.user is None: raise BusinessError('请先登录',401)
            if not g.user['active'] and not allow_frozen:raise BusinessError('账号已冻结，暂时无法访问',403)
            if admin and g.user['role']!='admin': raise BusinessError('需要系统管理员权限',403)
            expire_reservations(); return fn(*args,**kwargs)
        return wrapped
    return deco

@api.get('/health')
def health():
    db_ok=True
    try:
        get_db().execute('SELECT 1').fetchone()
    except Exception:
        db_ok=False
    return jsonify(ok=db_ok, service='ncs-charging', capacity_level=CAPACITY_LEVEL, database='ok' if db_ok else 'error')

@api.get('/capacity')
@auth()
def capacity():
    target=get_capacity(); db=get_db()
    actual={
        'registered_users': db.execute("SELECT COUNT(*) FROM users WHERE role='user'").fetchone()[0],
        'stations': db.execute('SELECT COUNT(*) FROM stations').fetchone()[0],
        'chargers': db.execute('SELECT COUNT(*) FROM chargers').fetchone()[0],
        'online_users_approx': db.execute("SELECT COUNT(*) FROM users WHERE active=1").fetchone()[0],
    }
    return jsonify(level=CAPACITY_LEVEL, target=target, actual=actual)

@api.get('/session')
def get_session():
    session.setdefault('csrf',secrets.token_hex(24))
    u=get_db().execute('SELECT * FROM users WHERE id=?',(session.get('uid'),)).fetchone()
    return jsonify(csrf=session['csrf'],user=public_user(u) if u else None,time_scale=current_app.config['TIME_SCALE'])

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
    lat=number(request.args.get('lat',39.9593),-90,90,'纬度'); lng=number(request.args.get('lng',116.2981),-180,180,'经度')
    status=request.args.get('status',''); kind=request.args.get('kind',''); sort=request.args.get('sort','distance')
    if status not in ('','idle','fault','maintenance','offline'): raise BusinessError('电站状态筛选无效')
    if kind not in ('','fast','slow'): raise BusinessError('充电类型筛选无效')
    if sort not in ('distance','usage'): raise BusinessError('排序方式无效')
    sql='''SELECT s.*,COUNT(c.id) total,
     SUM(CASE WHEN c.status='idle' THEN 1 ELSE 0 END) free,
     SUM(CASE WHEN c.kind='fast' THEN 1 ELSE 0 END) fast,
     SUM(CASE WHEN c.kind='slow' THEN 1 ELSE 0 END) slow,
     COALESCE(SUM(c.total_count),0) usage,
     SUM(CASE WHEN c.status='fault' THEN 1 ELSE 0 END) fault,
     SUM(CASE WHEN c.status='maintenance' THEN 1 ELSE 0 END) maintenance,
     SUM(CASE WHEN c.status='offline' THEN 1 ELSE 0 END) offline
     FROM stations s LEFT JOIN chargers c ON c.station_id=s.id'''
    conds=[]; args=[]
    if status: conds.append('EXISTS(SELECT 1 FROM chargers x WHERE x.station_id=s.id AND x.status=?)'); args.append(status)
    if kind: conds.append('EXISTS(SELECT 1 FROM chargers x WHERE x.station_id=s.id AND x.kind=?)'); args.append(kind)
    if conds: sql+=' WHERE '+' AND '.join(conds)
    sql+=' GROUP BY s.id'
    result=[]
    for row in get_db().execute(sql,args):
        r=dict(row); r['distance']=distance(lat,lng,r['lat'],r['lng']); result.append(r)
    if sort=='usage': result.sort(key=lambda r:(-r['usage'],r['distance']))
    else: result.sort(key=lambda r:r['distance'])
    return jsonify(result)

@api.get('/stations/<int:sid>')
@auth()
def station(sid):
    db=get_db(); row=db.execute('SELECT * FROM stations WHERE id=?',(sid,)).fetchone()
    if not row: raise BusinessError('电站不存在',404)
    chargers=[dict(r) for r in db.execute('SELECT * FROM chargers WHERE station_id=? ORDER BY number',(sid,))]
    summary={r['status']:r['n'] for r in db.execute('SELECT status,COUNT(*) n FROM chargers WHERE station_id=? GROUP BY status',(sid,))}
    return jsonify(station=dict(row),chargers=chargers,status_summary=summary)

@api.get('/orders')
@auth()
def orders():
    where='' if has_permission(g.user['role'],'order.view_all') else ' WHERE o.user_id=?'
    args=() if not where else (g.user['id'],)
    conds=[]; params=list(args)
    date_from=request.args.get('date_from',''); date_to=request.args.get('date_to','')
    if date_from: day(date_from,'开始日期'); conds.append('substr(o.created_at,1,10)>=?'); params.append(date_from)
    if date_to: day(date_to,'结束日期'); conds.append('substr(o.created_at,1,10)<=?'); params.append(date_to)
    if date_from and date_to and date_from>date_to: raise BusinessError('开始日期不能晚于结束日期')
    if conds: where=(where+' AND ' if where else ' WHERE ')+' AND '.join(conds)
    return jsonify([quote(r) for r in get_db().execute(ORDER_SELECT+where+' ORDER BY o.id DESC',params)])

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
@auth(allow_frozen=True)
def order_action(oid,action):
    if not g.user['active'] and action != 'finish':
        raise BusinessError('账号已冻结，无法执行该操作',403)

    act_order(g.user['id'],oid,action)

    return jsonify(
        order=quote(
            get_db().execute(
                ORDER_SELECT+' WHERE o.id=?',
                (oid,)
            ).fetchone()
        )
    )

@api.get('/orders/<int:oid>/receipt')
@auth()
def receipt(oid):
    row=get_db().execute(ORDER_SELECT+' WHERE o.id=?',(oid,)).fetchone()
    if not row or (not has_permission(g.user['role'],'order.view_all') and row['user_id']!=g.user['id']): raise BusinessError('订单不存在',404)
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
    db=get_db(); admin=has_permission(g.user['role'],'analytics.view'); uid=g.user['id']
    filt='' if admin else ' AND user_id=?'; args=() if admin else (uid,)
    totals=dict(db.execute("SELECT COUNT(*) orders,COALESCE(SUM(energy),0) energy,COALESCE(SUM(paid_cents),0) paid_cents,COALESCE(SUM(debt_cents),0) debt_cents FROM orders WHERE status='completed'"+filt,args).fetchone())
    counts={r['status']:r['n'] for r in db.execute('SELECT status,COUNT(*) n FROM chargers GROUP BY status')}
    days=[]
    for i in range(6,-1,-1):
        day=(datetime.now()-timedelta(days=i)).strftime('%Y-%m-%d')
        row=db.execute("SELECT COALESCE(SUM(energy),0) energy,COALESCE(SUM(paid_cents),0) cents,COUNT(*) orders FROM orders WHERE status='completed' AND substr(ended_at,1,10)=?"+filt,(day,*args)).fetchone()
        days.append(dict(day=day,**dict(row)))
    active=[quote(r) for r in db.execute(ORDER_SELECT+" WHERE o.status IN ('reserved','charging')"+('' if admin else ' AND o.user_id=?')+' ORDER BY o.id DESC',args)]
    user_stats={'total':db.execute("SELECT COUNT(*) FROM users WHERE role='user'").fetchone()[0],
                'active':db.execute("SELECT COUNT(*) FROM users WHERE role='user' AND active=1").fetchone()[0],
                'new_7d':db.execute("SELECT COUNT(*) FROM users WHERE role='user' AND created_at>=?",((datetime.now()-timedelta(days=7)).isoformat(),)).fetchone()[0]}
    maintenance_stats={r['status']:r['n'] for r in db.execute('SELECT status,COUNT(*) n FROM chargers GROUP BY status')}
    maintenance_stats['total']=db.execute('SELECT COUNT(*) FROM chargers').fetchone()[0]
    return jsonify(totals=totals,counts=counts,days=days,active=active,stations=db.execute('SELECT COUNT(*) FROM stations').fetchone()[0],user_stats=user_stats,maintenance_stats=maintenance_stats)

@api.get('/admin/users')
@permission('user.manage')
@auth()
def users():
    status=request.args.get('status',''); sort=request.args.get('sort','newest')
    date_from=request.args.get('date_from',''); date_to=request.args.get('date_to','')
    if status not in ('','normal','debt','frozen'): raise BusinessError('用户状态筛选无效')
    if sort not in ('newest','oldest'): raise BusinessError('排序方式无效')
    if date_from: day(date_from,'开始日期')
    if date_to: day(date_to,'结束日期')
    if date_from and date_to and date_from>date_to: raise BusinessError('开始日期不能晚于结束日期')
    sql='''SELECT u.*, COALESCE(SUM(o.debt_cents),0) AS debt_cents
     FROM users u LEFT JOIN orders o ON o.user_id=u.id AND o.debt_cents>0'''
    conds=[]; params=[]
    if date_from: conds.append('substr(u.created_at,1,10)>=?'); params.append(date_from)
    if date_to: conds.append('substr(u.created_at,1,10)<=?'); params.append(date_to)
    if conds: sql+=' WHERE '+' AND '.join(conds)
    sql+=' GROUP BY u.id ORDER BY u.created_at '+('DESC' if sort=='newest' else 'ASC')
    rows=[]
    for r in get_db().execute(sql,params):
        row=dict(r)
        row['role_name']=get_role_meta(row['role'])['name']
        row['permissions']=get_permissions(row['role'])
        state='debt' if row['debt_cents']>0 else ('frozen' if not row['active'] else 'normal')
        row['state']=state
        rows.append(row)
    if status: rows=[r for r in rows if r['state']==status]
    return jsonify(rows)

@api.get('/admin/roles')
@permission('role.manage')
@auth()
def roles():
    db=get_db(); roles=[dict(r) for r in db.execute('SELECT * FROM roles ORDER BY level')]
    for r in roles:
        r['permissions']=get_permissions(r['key'])
    return jsonify(roles=roles,permissions=[dict(r) for r in db.execute('SELECT * FROM permissions ORDER BY module,key')])

@api.post('/admin/users/<int:uid>/role')
@permission('role.manage')
@auth()
def user_role_update(uid):
    role=body().get('role'); db=get_db()
    if not db.execute('SELECT 1 FROM roles WHERE key=?',(role,)).fetchone(): raise BusinessError('角色不存在',404)
    target=db.execute('SELECT * FROM users WHERE id=?',(uid,)).fetchone()
    if not target: raise BusinessError('用户不存在',404)
    if uid==g.user['id'] and role!='admin': raise BusinessError('不能取消自己的系统管理员权限',409)
    with transaction() as tx:
        tx.execute('UPDATE users SET role=? WHERE id=?',(role,uid)); audit(g.user['id'],f'调整用户 #{uid} 角色为 {get_role_meta(role)["name"]}')
    return jsonify(ok=True)

@api.post('/admin/users/<int:uid>')
@permission('user.manage')
@auth()
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
@permission('station.manage')
@auth()
def station_save(sid=None):
    d=body(); vals=(required(d.get('name'),'站名',60),required(d.get('address'),'地址',160),number(d.get('lng'),-180,180,'经度'),number(d.get('lat'),-90,90,'纬度'),money(d.get('price'),100))
    with transaction() as db:
        if sid:
            if not db.execute('UPDATE stations SET name=?,address=?,lng=?,lat=?,price_cents=? WHERE id=?',(*vals,sid)).rowcount: raise BusinessError('电站不存在',404)
        else: sid=db.execute('INSERT INTO stations(name,address,lng,lat,price_cents) VALUES(?,?,?,?,?)',vals).lastrowid
        audit(g.user['id'],f'保存电站 #{sid}')
    return jsonify(id=sid)

@api.delete('/admin/stations/<int:sid>')
@permission('station.manage')
@auth()
def station_delete(sid):
    with transaction() as db:
        if db.execute('SELECT 1 FROM chargers WHERE station_id=?',(sid,)).fetchone(): raise BusinessError('请先处理该站充电桩；有历史订单的设备需保留')
        if not db.execute('DELETE FROM stations WHERE id=?',(sid,)).rowcount: raise BusinessError('电站不存在',404)
        audit(g.user['id'],f'删除电站 #{sid}')
    return jsonify(ok=True)

@api.get('/admin/chargers')
@permission('charger.view')
@auth()
def chargers():
    return jsonify([dict(r) for r in get_db().execute('SELECT c.*,s.name station_name FROM chargers c JOIN stations s ON s.id=c.station_id ORDER BY c.id')])

@api.post('/admin/chargers')
@api.post('/admin/chargers/<int:cid>')
@permission('charger.manage')
@auth()
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
@permission('charger.manage')
@auth()
def charger_action(cid):
    action=body().get('action')
    with transaction() as db:
        c=db.execute('SELECT * FROM chargers WHERE id=?',(cid,)).fetchone()
        if not c: raise BusinessError('电桩不存在',404)
        if c['status'] in ('charging','reserved'): raise BusinessError('电桩有未完成订单，不能操作',409)
        if action=='delete': db.execute('DELETE FROM chargers WHERE id=?',(cid,))
        elif action in ('fault','maintenance','offline','restore','restart'):
            db.execute('UPDATE chargers SET status=? WHERE id=?',({'fault':'fault','maintenance':'maintenance','offline':'offline','restore':'idle','restart':'idle'}[action],cid))
        else: raise BusinessError('操作无效')
        audit(g.user['id'],f'电桩 #{cid}：{action}'+('（软件模拟）' if action=='restart' else ''))
    return jsonify(ok=True)

@api.get('/admin/logs')
@permission('log.view')
@auth()
def logs(): return jsonify([dict(r) for r in get_db().execute('SELECT * FROM ops_log ORDER BY id DESC LIMIT 100')])

@api.get('/admin/prediction')
@permission('prediction.view')
@auth()
def prediction():
    sid=request.args.get('station_id',1,type=int); db=get_db()
    if not db.execute('SELECT 1 FROM stations WHERE id=?',(sid,)).fetchone(): raise BusinessError('电站不存在',404)
    rows=db.execute("SELECT o.* FROM orders o JOIN chargers c ON c.id=o.charger_id WHERE c.station_id=? AND o.status='completed' AND o.started_at>=?",(sid,(datetime.now()-timedelta(days=28)).isoformat())).fetchall()
    capacity=db.execute('SELECT COALESCE(SUM(power),0),COUNT(*) FROM chargers WHERE station_id=?',(sid,)).fetchone()
    if not rows: return jsonify(points=[],sample_count=0,method='历史数据不足，请积累充电订单后重试')
    points=[]
    for i in range(1,13):
        t=(datetime.now()+timedelta(hours=i)).replace(minute=0,second=0,microsecond=0)
        # Average historical energy of sessions starting in this hour, over a 28-day window.
        energy=sum(r['energy'] for r in rows if datetime.fromisoformat(r['started_at']).hour==t.hour)/28
        load=min(capacity[0],energy); ratio=load/capacity[0] if capacity[0] else 0
        points.append(dict(time=t.isoformat(),load=round(load,2),free=max(0,round(capacity[1]*(1-ratio))),peak=ratio>=0.7))
    return jsonify(points=points,sample_count=len(rows),method='近 28 天同小时订单电量均值；按装机功率估算空闲数，仅供课程演示')

@api.get('/admin/export')
@permission('order.export')
@auth()
def export():
    out=io.StringIO(); writer=csv.writer(out)
    writer.writerow(['订单号','用户','电站','电桩','状态','电量(kWh)','金额(元)','已付(元)','欠费(元)','开始时间','结束时间'])
    def safe(v):
        s=str(v or '')
        return "'"+s if s[:1] in ('=','+','-','@','\t','\r') else s
    where=''; params=[]
    date_from=request.args.get('date_from',''); date_to=request.args.get('date_to','')
    if date_from: day(date_from,'开始日期'); where+=' WHERE substr(o.created_at,1,10)>=?'; params.append(date_from)
    if date_to: day(date_to,'结束日期'); where+=((' AND ' if where else ' WHERE ')+'substr(o.created_at,1,10)<=?'); params.append(date_to)
    if date_from and date_to and date_from>date_to: raise BusinessError('开始日期不能晚于结束日期')
    for r in get_db().execute(ORDER_SELECT+where+' ORDER BY o.id DESC',params):
        writer.writerow([r['id'],safe(r['nickname']),safe(r['station_name']),safe(r['charger_number']),r['status'],r['energy'],r['amount_cents']/100,r['paid_cents']/100,r['debt_cents']/100,r['started_at'],r['ended_at']])
    return Response('\ufeff'+out.getvalue(),mimetype='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename=ncs-orders.csv'})
