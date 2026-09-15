"""Network upgrade, user ID consistency, avatar persistence and upload isolation."""
import csv
import io
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from ncs import create_app
from ncs.db import get_db

class ExpansionAvatarTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.config={'TESTING':True,'SECRET_KEY':'avatar-tests','DATABASE':str(Path(self.tmp.name)/'test.db')}
        self.app=create_app(self.config)
        self.c,self.token=self.login()
    def tearDown(self):self.tmp.cleanup()
    def login(self,phone='13800138000',password='User123456',app=None):
        c=(app or self.app).test_client();t=c.get('/api/session').json['csrf']
        r=c.post('/api/login',json={'phone':phone,'password':password},headers={'X-CSRF-Token':t})
        self.assertEqual(r.status_code,200,r.json)
        return c,r.json['csrf']
    def picture(self):
        buffer=io.BytesIO();image=Image.new('RGBA',(600,400),(255,0,0,100));image.save(buffer,'PNG')
        return buffer.getvalue()
    def upload(self,data=None,client=None,token=None):
        return (client or self.c).post('/api/profile/avatar',data={'image':(io.BytesIO(self.picture() if data is None else data),'photo.png')},headers={'X-CSRF-Token':token or self.token})
    def test_default_network_has_ten_stations_and_one_hundred_unique_chargers(self):
        stations=self.c.get('/api/stations').json
        self.assertEqual(len(stations),10)
        self.assertTrue(any('房山' in s['name'] for s in stations));self.assertTrue(any('大兴' in s['name'] for s in stations))
        numbers=[]
        for s in stations:
            detail=self.c.get('/api/stations/'+str(s['id'])).json
            self.assertEqual(len(detail['chargers']),10);self.assertTrue(detail['pricing'])
            numbers.extend(c['number'] for c in detail['chargers'])
        self.assertEqual(len(set(numbers)),100)
    def test_upgrade_preserves_business_data_and_does_not_repeat(self):
        with self.app.app_context():
            db=get_db()
            # Reconstruct the previous five-station/six-charger layout.
            db.execute('DELETE FROM chargers WHERE id>30')
            db.execute('DELETE FROM pricing_rules WHERE station_id>5')
            db.execute('DELETE FROM stations WHERE id>5')
            db.execute('DELETE FROM ncs_data_migrations')
            db.execute("UPDATE users SET nickname='保留的昵称',balance_cents=12345 WHERE id=1")
            before_users=[dict(x) for x in db.execute('SELECT * FROM users ORDER BY id').fetchall()]
            before_orders=[dict(x) for x in db.execute('SELECT * FROM orders ORDER BY id').fetchall()]
            before_chargers=[dict(x) for x in db.execute('SELECT * FROM chargers ORDER BY id').fetchall()]
        for _ in range(2):
            updated=create_app(self.config)
            with updated.app_context():
                db=get_db()
                self.assertEqual([dict(x) for x in db.execute('SELECT * FROM users ORDER BY id').fetchall()],before_users)
                self.assertEqual([dict(x) for x in db.execute('SELECT * FROM orders ORDER BY id').fetchall()],before_orders)
                self.assertEqual([dict(x) for x in db.execute('SELECT * FROM chargers WHERE id<=30 ORDER BY id').fetchall()],before_chargers)
                self.assertEqual(db.execute('SELECT COUNT(*) FROM chargers').fetchone()[0],100)
    def test_completed_migration_does_not_recreate_later_deleted_chargers(self):
        with self.app.app_context():get_db().execute('DELETE FROM chargers WHERE id=100')
        updated=create_app(self.config)
        with updated.app_context():self.assertEqual(get_db().execute('SELECT COUNT(*) FROM chargers').fetchone()[0],99)
    def test_upload_normalizes_and_survives_restart_without_changing_profile(self):
        before=self.c.get('/api/session').json['user']
        r=self.upload();self.assertEqual(r.status_code,200,r.json)
        saved=self.c.get('/api/session').json['user'];self.assertEqual(saved['avatar_url'],r.json['avatar_url'])
        image=self.c.get(saved['avatar_url']);self.assertEqual(image.mimetype,'image/jpeg')
        decoded=Image.open(io.BytesIO(image.data));self.assertEqual(decoded.size,(256,256));self.assertFalse(decoded.getexif())
        for key in ['id','nickname','balance_cents']:self.assertEqual(saved[key],before[key])
        restarted=create_app(self.config);c,_=self.login(app=restarted)
        self.assertEqual(c.get('/api/profile/avatar').data,image.data)
    def test_bad_upload_preserves_existing_avatar(self):
        self.assertEqual(self.upload().status_code,200)
        old=self.c.get('/api/profile/avatar').data
        for data in [b'',b'<svg><script>alert(1)</script></svg>',b'not a png',b'x'*(5*1024*1024+1)]:
            self.assertEqual(self.upload(data).status_code,400)
            self.assertEqual(self.c.get('/api/profile/avatar').data,old)
    def test_avatar_isolation_csrf_reset_and_english_error(self):
        self.upload();other,t=self.login('13900139000','User123456')
        self.assertEqual(other.get('/api/profile/avatar?user_id=1').status_code,404)
        self.assertEqual(other.get('/api/session').json['user']['avatar_url'],None)
        self.assertEqual(self.c.post('/api/profile/avatar',data={'image':(io.BytesIO(self.picture()),'a.png')}).status_code,403)
        self.assertEqual(self.app.test_client().get('/api/profile/avatar').status_code,401)
        r=self.c.post('/api/profile/avatar',headers={'X-CSRF-Token':self.token,'X-NCS-Language':'en'})
        self.assertEqual(r.json['error'],'Choose an avatar image.')
        self.assertEqual(self.c.delete('/api/profile/avatar',headers={'X-CSRF-Token':self.token}).status_code,200)
        self.assertIsNone(self.c.get('/api/session').json['user']['avatar_url'])
    def test_new_registration_uses_default_purple_avatar(self):
        c=self.app.test_client();t=c.get('/api/session').json['csrf']
        r=c.post('/api/register',json={'phone':'13700137000','nickname':'新用户','password':'Hello12345'},headers={'X-CSRF-Token':t})
        self.assertEqual(r.status_code,201,r.json)
        self.assertEqual(r.json['user']['avatar'],'lavender');self.assertIsNone(r.json['user']['avatar_url'])
    def test_order_export_uses_same_user_id_as_user_management(self):
        c,_=self.login('admin','Admin123456')
        users={str(u['id']) for u in c.get('/api/admin/users').json}
        orders=c.get('/api/orders').json
        self.assertTrue(all(str(o['user_id']) in users for o in orders))
        rows=list(csv.reader(io.StringIO(c.get('/api/admin/export?lang=en').data.decode('utf-8-sig'))))
        self.assertEqual(rows[0][1],'User ID');self.assertTrue(all(row[1] in users for row in rows[1:]))

if __name__=='__main__':unittest.main()
