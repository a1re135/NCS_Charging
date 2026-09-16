"""Shared user notification helpers."""
from __future__ import annotations

import hashlib
from .db import now


def ensure_notification_table(db) -> None:
    db.execute(
        """CREATE TABLE IF NOT EXISTS notifications(
            id VARCHAR(64) PRIMARY KEY,
            user_id INTEGER,
            kind TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            level TEXT NOT NULL DEFAULT 'info',
            read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            ref_type TEXT,
            ref_id TEXT
        )"""
    )
    try:
        db.execute(
            "CREATE INDEX IF NOT EXISTS notification_user_read ON notifications(user_id, read, created_at)"
        )
    except Exception:
        pass


def create_notification(db, user_id, kind, title, body, level="info", ref_type=None, ref_id=None):
    ensure_notification_table(db)
    raw = f"{user_id or 'system'}|{kind}|{ref_id or ''}"
    nid = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]
    exists = db.execute("SELECT 1 FROM notifications WHERE id=?", (nid,)).fetchone()
    if exists:
        return nid
    db.execute(
        """INSERT INTO notifications(id,user_id,kind,title,body,level,read,created_at,ref_type,ref_id)
           VALUES(?,?,?,?,?,?,0,?,?,?)""",
        (
            nid,
            user_id,
            kind,
            title,
            body,
            level,
            now(),
            ref_type,
            str(ref_id) if ref_id is not None else None,
        ),
    )
    return nid
