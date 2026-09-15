"""Preference persistence, data preservation and localized responses."""
import tempfile
import unittest
from pathlib import Path
from ncs import create_app
from ncs.db import get_db

class PreferenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.config={'TESTING':True,'SECRET_KEY':'preference-tests','DATABASE':str(Path(self.tmp.name)/'prefs.db')}
        self.app=create_app(self.config)
        self.c,self.csrf=self.login()
    def tearDown(self): self.tmp.cleanup()
    def login(self,phone='13800138000',password='User123456',app=None):
        c=(app or self.app).test_client();token=c.get('/api/session').json['csrf']
        r=c.post('/api/login',json={'phone':phone,'password':password},headers={'X-CSRF-Token':token})
        self.assertEqual(r.status_code,200,r.json)
        return c,r.json['csrf']
    def save(self,data,client=None,csrf=None):
        return (client or self.c).post('/api/preferences',json=data,headers={'X-CSRF-Token':csrf or self.csrf})
    def test_preferences_persist_after_restart_without_business_changes(self):
        with self.app.app_context():
            before=dict(get_db().execute('SELECT * FROM users WHERE id=1').fetchone())
            count=get_db().execute('SELECT COUNT(*) FROM orders').fetchone()[0]
        self.assertIsNone(self.c.get('/api/preferences').json['preferences'])
        self.assertEqual(self.save({'language':'en','theme':'dark'}).status_code,200)
        restarted=create_app(self.config);c,_=self.login(app=restarted)
        self.assertEqual(c.get('/api/session').json['user']['preferences'],{'language':'en','theme':'dark'})
        with restarted.app_context():
            self.assertEqual(dict(get_db().execute('SELECT * FROM users WHERE id=1').fetchone()),before)
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM orders').fetchone()[0],count)
    def test_existing_database_gets_preferences_table_without_reset(self):
        with self.app.app_context():
            db=get_db();db.execute('DROP TABLE user_preferences');db.execute("UPDATE users SET nickname='我的名称' WHERE id=1")
        updated=create_app(self.config);c,t=self.login(app=updated)
        self.assertEqual(c.get('/api/session').json['user']['nickname'],'我的名称')
        self.assertEqual(self.save({'language':'zh','theme':'system'},c,t).status_code,200)
    def test_preferences_cannot_target_other_accounts(self):
        self.save({'language':'en','theme':'dark','user_id':2})
        admin,t=self.login('admin','Admin123456')
        self.assertIsNone(admin.get('/api/preferences').json['preferences'])
        self.save({'language':'zh','theme':'light'},admin,t)
        self.assertEqual(self.c.get('/api/preferences').json['preferences']['theme'],'dark')
        self.assertEqual(admin.get('/api/preferences').json['preferences']['theme'],'light')
    def test_validation_and_authentication(self):
        for d in [{'language':'fr','theme':'dark'},{'language':'en','theme':'black'},{'language':[],'theme':'dark'},{'language':'en','theme':None}]:
            self.assertEqual(self.save(d).status_code,400)
        self.assertEqual(self.c.post('/api/preferences',json={'language':'en','theme':'dark'}).status_code,403)
        anonymous=self.app.test_client();self.assertEqual(anonymous.get('/api/preferences').status_code,401)
        t=anonymous.get('/api/session').json['csrf']
        self.assertEqual(self.save({'language':'en','theme':'dark'},anonymous,t).status_code,401)
    def test_english_errors_and_chinese_compatibility(self):
        h={'X-CSRF-Token':self.csrf,'X-NCS-Language':'en'}
        r=self.c.post('/api/wallet/recharge',json={'amount':'NaN'},headers=h)
        self.assertEqual(r.status_code,400);self.assertIn('Amount must',r.json['error']);self.assertEqual(r.headers['Content-Language'],'en')
        r=self.c.post('/api/profile',json={'nickname':'','avatar':'pink'},headers=h)
        self.assertIn('Nickname',r.json['error'])
        r=self.c.post('/api/preferences',json={'language':'bad','theme':'dark'},headers=h)
        self.assertEqual(r.json['error'],'Invalid language preference')
        r=self.save({'language':'bad','theme':'dark'})
        self.assertEqual(r.json['error'],'语言设置无效')
    def test_english_export_and_data_remain_original(self):
        admin,_=self.login('admin','Admin123456')
        text=admin.get('/api/admin/export?lang=en').data.decode('utf-8-sig')
        self.assertTrue(text.startswith('Order ID,User,Station,Charger,Status'));self.assertIn('小林',text)
        s=self.c.get('/api/stations',headers={'X-NCS-Language':'en'}).json[0]
        self.assertIn('海淀',s['name'])
    def test_concurrent_preference_saves_do_not_duplicate_rows(self):
        from concurrent.futures import ThreadPoolExecutor
        other,token=self.login()
        with ThreadPoolExecutor(2) as pool:
            jobs=[pool.submit(self.save,{'language':'en','theme':theme},c,t) for theme,c,t in [('dark',self.c,self.csrf),('light',other,token)]]
            self.assertEqual([j.result().status_code for j in jobs],[200,200])
        with self.app.app_context():
            self.assertEqual(get_db().execute('SELECT COUNT(*) FROM user_preferences WHERE user_id=1').fetchone()[0],1)

if __name__=='__main__':unittest.main()
