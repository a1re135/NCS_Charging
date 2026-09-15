"""Business regression tests; isolated temporary databases, no modification of demo data."""
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta
from pathlib import Path
from ncs import create_app
from ncs.db import get_db

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.app=create_app({'TESTING':True,'SECRET_KEY':'test-only','DATABASE':str(Path(self.tmp.name)/'test.db')})
        self.client,self.token=self.login('13800138000','User123456')
    def tearDown(self): self.tmp.cleanup()
    def login(self,user,pw):
        c=self.app.test_client();token=c.get('/api/session').json['csrf']
        r=c.post('/api/login',json={'phone':user,'password':pw},headers={'X-CSRF-Token':token})
        self.assertEqual(r.status_code,200)
        return c,r.json['csrf']
    def post(self,path,data=None,client=None,token=None):
        return (client or self.client).post('/api'+path,json=data or {},headers={'X-CSRF-Token':token or self.token})
    def sql(self,query,args=()):
        with self.app.app_context(): return get_db().execute(query,args).fetchall()
    def start(self,cid=1,mode='start'):
        r=self.post('/orders',{'charger_id':cid,'mode':mode});self.assertEqual(r.status_code,201,r.json);return r.json['id']
    def age(self,oid,seconds=60):
        self.sql('UPDATE orders SET started_at=? WHERE id=?',((datetime.now()-timedelta(seconds=seconds)).isoformat(timespec='seconds'),oid))
    def test_profile_and_exact_recharge_persist_across_login(self):
        self.assertEqual(self.post('/profile',{'nickname':'新昵称','avatar':'pink'}).status_code,200)
        for _ in range(10): self.assertEqual(self.post('/wallet/recharge',{'amount':'0.10'}).status_code,200)
        c,_=self.login('13800138000','User123456');u=c.get('/api/session').json['user']
        self.assertEqual(u['nickname'],'新昵称');self.assertEqual(u['avatar'],'pink');self.assertEqual(u['balance_cents'],28900)
    def test_invalid_money_and_csrf(self):
        for value in ['NaN','Infinity',-1,0,'1.001',100001]: self.assertEqual(self.post('/wallet/recharge',{'amount':value}).status_code,400)
        self.assertEqual(self.client.post('/api/wallet/recharge',json={'amount':100}).status_code,403)
        self.assertEqual(self.sql('SELECT balance_cents FROM users WHERE id=1')[0][0],28800)
    def test_reservation_exclusion_and_cancel(self):
        oid=self.start(mode='reserve')
        r=self.post('/orders',{'charger_id':2,'mode':'start'});self.assertEqual(r.status_code,409);self.assertEqual(r.json['order_id'],oid)
        c,t=self.login('13900139000','User123456');self.assertEqual(self.post('/orders',{'charger_id':1,'mode':'reserve'},c,t).status_code,409)
        self.assertEqual(self.post(f'/orders/{oid}/cancel').status_code,200)
        self.assertEqual(self.sql('SELECT status FROM chargers WHERE id=1')[0][0],'idle')
    def test_expiration_releases_charger(self):
        oid=self.start(mode='reserve');self.sql('UPDATE orders SET expires_at=? WHERE id=?',('2000-01-01T00:00:00',oid))
        self.client.get('/api/stations')
        self.assertEqual(self.sql('SELECT status FROM orders WHERE id=?',(oid,))[0][0],'expired')
        self.assertEqual(self.sql('SELECT status FROM chargers WHERE id=1')[0][0],'idle')
    def test_settlement_snapshots_and_no_double_charge(self):
        oid=self.start(mode='reserve');self.assertEqual(self.post(f'/orders/{oid}/start').status_code,200)
        self.age(oid);self.sql('UPDATE stations SET price_cents=999 WHERE id=1');self.sql('UPDATE chargers SET power=999 WHERE id=1')
        r=self.post(f'/orders/{oid}/finish');self.assertEqual(r.status_code,200);o=r.json['order']
        self.assertEqual(o['price_cents'],160);self.assertEqual(o['power'],60);self.assertTrue(9600<=o['amount_cents']<=10080,o)
        balance=self.sql('SELECT balance_cents FROM users WHERE id=1')[0][0]
        self.assertEqual(self.post(f'/orders/{oid}/finish').status_code,409)
        self.assertEqual(self.sql('SELECT balance_cents FROM users WHERE id=1')[0][0],balance)
    def test_debt_repayment_and_new_order_block(self):
        self.sql('UPDATE users SET balance_cents=1 WHERE id=1');oid=self.start();self.age(oid)
        self.assertEqual(self.post(f'/orders/{oid}/finish').status_code,200)
        debt=self.sql('SELECT debt_cents FROM orders WHERE id=?',(oid,))[0][0];self.assertGreater(debt,0)
        self.assertEqual(self.post('/orders',{'charger_id':2,'mode':'start'}).status_code,409)
        self.assertEqual(self.post(f'/orders/{oid}/pay').status_code,400)
        self.post('/wallet/recharge',{'amount':200});self.assertEqual(self.post(f'/orders/{oid}/pay').status_code,200)
        self.assertEqual(self.post(f'/orders/{oid}/pay').status_code,409)
        self.assertEqual(self.sql('SELECT debt_cents FROM orders WHERE id=?',(oid,))[0][0],0)
    def test_authorization_and_ownership(self):
        self.assertEqual(self.client.get('/api/admin/users').status_code,403)
        oid=self.start();c,t=self.login('13900139000','User123456')
        self.assertEqual(c.get(f'/api/orders/{oid}/receipt').status_code,404)
        self.assertEqual(self.post(f'/orders/{oid}/finish',client=c,token=t).status_code,404)
    def test_concurrent_users_cannot_claim_same_charger(self):
        c,t=self.login('13900139000','User123456')
        with ThreadPoolExecutor(2) as pool:
            jobs=[pool.submit(self.post,'/orders',{'charger_id':1,'mode':'reserve'},cl,tk) for cl,tk in [(self.client,self.token),(c,t)]]
            codes=sorted(j.result().status_code for j in jobs)
        self.assertEqual(codes,[201,409])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM orders WHERE charger_id=1 AND status='reserved'")[0][0],1)
    def test_concurrent_settlement_only_once(self):
        oid=self.start();self.age(oid);c,t=self.login('13800138000','User123456')
        with ThreadPoolExecutor(2) as pool:
            jobs=[pool.submit(self.post,f'/orders/{oid}/finish',None,cl,tk) for cl,tk in [(self.client,self.token),(c,t)]]
            self.assertEqual(sorted(j.result().status_code for j in jobs),[200,409])
        self.assertEqual(self.sql("SELECT COUNT(*) FROM wallet_log WHERE user_id=1 AND kind='充电结算'")[0][0],1)
    def test_admin_crud_and_active_device_protection(self):
        a,t=self.login('admin','Admin123456');data={'name':'测试站','address':'测试地址','lng':116,'lat':39,'price':1.2}
        r=self.post('/admin/stations',data,a,t);self.assertEqual(r.status_code,200);sid=r.json['id']
        r=self.post('/admin/chargers',{'station_id':sid,'number':'TEST-01','kind':'fast','power':60},a,t);cid=r.json['id']
        oid=self.start(cid)
        self.assertEqual(self.post(f'/admin/chargers/{cid}/action',{'action':'fault'},a,t).status_code,409)
        self.post(f'/orders/{oid}/finish')
        self.assertEqual(self.post(f'/admin/chargers/{cid}/action',{'action':'delete'},a,t).status_code,409)
        self.assertEqual(self.post(f'/admin/chargers/{cid}/action',{'action':'fault'},a,t).status_code,200)
        self.assertEqual(self.post(f'/admin/chargers/{cid}/action',{'action':'restart'},a,t).status_code,200)
        self.assertGreater(len(a.get('/api/admin/logs').json),0)
    def test_frozen_user_can_settle_but_not_recharge(self):
        oid=self.start();a,t=self.login('admin','Admin123456');self.post('/admin/users/1',{'active':False},a,t)
        self.assertEqual(self.post('/wallet/recharge',{'amount':100}).status_code,403)
        self.assertEqual(self.post(f'/orders/{oid}/finish').status_code,200)
        self.assertEqual(self.post('/orders',{'charger_id':2,'mode':'start'}).status_code,403)
    def test_registration_prediction_export_and_sort(self):
        c=self.app.test_client();t=c.get('/api/session').json['csrf']
        r=self.post('/register',{'phone':'13700137000','nickname':'新同学','password':'New123456'},c,t);self.assertEqual(r.status_code,201)
        self.assertEqual(self.client.get('/api/stations?lat=39.9219&lng=116.4435').json[0]['id'],3)
        a,t=self.login('admin','Admin123456');p=a.get('/api/admin/prediction?station_id=1').json
        self.assertEqual(len(p['points']),12);self.assertGreater(p['sample_count'],0)
        r=a.get('/api/admin/export');self.assertEqual(r.status_code,200);self.assertTrue(r.data.startswith(b'\xef\xbb\xbf'))

    def test_rbac_has_four_roles_and_enforces_permissions(self):
        with self.app.app_context():
            roles=get_db().execute('SELECT key FROM roles ORDER BY level').fetchall()
            self.assertEqual([r['key'] for r in roles],['user','operator','technician','admin'])
        operator,token=self.login('operator','Operator123456')
        self.assertEqual(operator.get('/api/session').json['user']['role_name'],'运营人员')
        self.assertEqual(operator.get('/api/admin/users').status_code,403)
        self.assertEqual(operator.get('/api/admin/chargers').status_code,200)
        self.assertEqual(operator.post('/api/admin/chargers/1/action',json={'action':'restart'},headers={'X-CSRF-Token':token}).status_code,403)
        tech,token=self.login('tech','Tech123456')
        self.assertEqual(tech.get('/api/admin/logs').status_code,403)
        self.assertEqual(tech.get('/api/admin/chargers').status_code,200)
        self.assertEqual(tech.post('/api/admin/chargers/1/action',json={'action':'restart'},headers={'X-CSRF-Token':token}).status_code,200)
        detail=tech.get('/api/stations/1').json
        self.assertIn('status_summary',detail)

    def test_rbac_role_change_and_self_protection(self):
        admin,token=self.login('admin','Admin123456')
        self.assertEqual(self.post('/admin/users/1/role',{'role':'operator'},admin,token).status_code,200)
        self.assertEqual(self.sql('SELECT role FROM users WHERE id=1')[0][0],'operator')
        self.assertEqual(self.post('/admin/users/2/role',{'role':'user'},admin,token).status_code,409)
        # restore demo user for remaining tests
        self.post('/admin/users/1/role',{'role':'user'},admin,token)

    def test_payment_status_and_dashboard_user_stats(self):
        oid=self.start();self.age(oid)
        r=self.post(f'/orders/{oid}/finish');self.assertEqual(r.status_code,200)
        self.assertEqual(r.json['order']['payment_status'],'已支付')
        d=self.client.get('/api/dashboard').json
        self.assertIn('user_stats',d);self.assertGreaterEqual(d['user_stats']['total'],1)

if __name__=='__main__': unittest.main(verbosity=2)
