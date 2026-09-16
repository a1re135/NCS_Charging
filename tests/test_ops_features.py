import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from flask import Flask

from ncs.ops_features import ops_api, _ensure_feature_schema


class FakeUserDB:
    def __init__(self, conn):
        self.conn = conn


class OpsFeatureUnitTests(unittest.TestCase):
    def test_schema_is_idempotent(self):
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        conn.execute('CREATE TABLE users(id INTEGER PRIMARY KEY, phone TEXT, nickname TEXT, role TEXT, balance_cents INTEGER, active INTEGER, created_at TEXT)')
        conn.execute('CREATE TABLE permissions(key TEXT PRIMARY KEY, name TEXT, module TEXT)')
        conn.execute('CREATE TABLE role_permissions(role_key TEXT, permission_key TEXT)')
        conn.execute('CREATE TABLE ops_log(id INTEGER PRIMARY KEY, actor_id INTEGER, operation TEXT, created_at TEXT)')
        _ensure_feature_schema(conn)
        _ensure_feature_schema(conn)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn('notifications', tables)
        self.assertIn('ops_feature_kv', tables)

    def test_backup_inventory_filename_rule(self):
        self.assertRegex('ncs-20260915-235959.db', r'^ncs-\d{8}-\d{6}\.db$')
        self.assertNotRegex('../ncs.db', r'^ncs-\d{8}-\d{6}\.db$')


if __name__ == '__main__':
    unittest.main()
