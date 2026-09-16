"""Operational excellence features for the NCS charging demo.

Adds five independent capabilities without changing the existing business
state machine:
1. system-health monitoring
2. utilization / operations analytics
3. SQLite backup and recovery inventory
4. notification center
5. richer audit-log browsing

The module is intentionally additive: existing /api routes continue to work.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
try:
    import resource
except ImportError:
    resource = None
import shutil
import sqlite3
import time
from collections import deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request, send_file, session, g

from .db import get_db, now
from .services import BusinessError

ops_api = Blueprint("ops_features", __name__)
_STARTED_AT = time.time()


def _backend() -> str:
    configured = current_app.config.get("DB_BACKEND")
    if configured:
        return str(configured).lower()
    # Infer the backend for projects where DB_BACKEND is not explicitly set.
    return "mysql" if type(get_db()).__name__ == "MySQLDatabase" else "sqlite"


def _is_sqlite() -> bool:
    return _backend() in ("sqlite", "sqlite3", "", "none")


def _safe_identifier(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(value))


def _permission_exists(db, key: str) -> bool:
    try:
        return bool(db.execute("SELECT 1 FROM permissions WHERE key=?", (key,)).fetchone())
    except Exception:
        return False


def _has_permission(db, role: str, key: str) -> bool:
    try:
        return bool(db.execute(
            "SELECT 1 FROM role_permissions WHERE role_key=? AND permission_key=?",
            (role, key),
        ).fetchone())
    except Exception:
        return role == "admin"


def _ensure_feature_schema(db) -> None:
    """Create only additive feature tables; safe to run on every request."""
    statements = [
        """CREATE TABLE IF NOT EXISTS notifications(
            id VARCHAR(64) PRIMARY KEY,
            user_id BIGINT UNSIGNED REFERENCES users(id),
            kind VARCHAR(32) NOT NULL,
            title VARCHAR(255) NOT NULL,
            body TEXT NOT NULL,
            level VARCHAR(16) NOT NULL DEFAULT 'info',
            `read` TINYINT(1) NOT NULL DEFAULT 0,
            created_at VARCHAR(32) NOT NULL,
            ref_type VARCHAR(64),
            ref_id VARCHAR(128)
        )""",
        """CREATE INDEX IF NOT EXISTS notification_user_read
            ON notifications(user_id, `read`, created_at)""",
        """CREATE TABLE IF NOT EXISTS ops_feature_kv(
            `key` VARCHAR(64) PRIMARY KEY,
            value TEXT NOT NULL
        )""",
    ]
    for statement in statements:
        try:
            db.execute(statement)
        except Exception:
            # A partially upgraded/legacy database should not break the whole app.
            pass

    # Additive RBAC permissions. Missing tables/permissions are tolerated so
    # the feature layer can also run against a legacy database during migration.
    new_permissions = [
        ("system.monitor", "查看系统运行监控", "运维"),
        ("analytics.utilization", "查看设备利用率分析", "分析"),
        ("audit.view", "查看增强审计日志", "审计"),
        ("backup.manage", "管理数据库备份", "可靠性"),
        ("notification.view", "查看通知中心", "通知"),
    ]
    for key, name, module in new_permissions:
        try:
            db.execute(
                "INSERT OR IGNORE INTO permissions(key,name,module) VALUES(?,?,?)",
                (key, name, module),
            )
        except Exception:
            try:
                if not db.execute("SELECT 1 FROM permissions WHERE key=?", (key,)).fetchone():
                    db.execute("INSERT INTO permissions(key,name,module) VALUES(?,?,?)", (key, name, module))
            except Exception:
                pass

    mappings = {
        "admin": {"system.monitor", "analytics.utilization", "audit.view", "backup.manage", "notification.view"},
        "operator": {"system.monitor", "analytics.utilization", "audit.view", "notification.view"},
        "technician": {"system.monitor", "analytics.utilization", "notification.view"},
        "user": {"notification.view"},
    }
    for role, keys in mappings.items():
        for key in keys:
            try:
                if not db.execute(
                    "SELECT 1 FROM role_permissions WHERE role_key=? AND permission_key=?",
                    (role, key),
                ).fetchone():
                    db.execute(
                        "INSERT INTO role_permissions(role_key,permission_key) VALUES(?,?)",
                        (role, key),
                    )
            except Exception:
                pass


def _current_user() -> Any:
    uid = session.get("uid")
    if not uid:
        raise BusinessError("请先登录", 401)
    user = get_db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if user is None:
        raise BusinessError("请先登录", 401)
    return user


def _require_capability(*keys: str, admin_only: bool = False):
    db = get_db()
    _ensure_feature_schema(db)
    user = _current_user()
    if not user["active"]:
        raise BusinessError("账号已冻结，暂时无法访问", 403)
    if admin_only:
        if user["role"] != "admin":
            raise BusinessError("需要系统管理员权限", 403)
        return user
    if user["role"] == "admin":
        return user
    if not any(_has_permission(db, user["role"], key) for key in keys):
        raise BusinessError("当前角色没有所需权限", 403)
    return user


def _memory_mb() -> float:
    """Return the current RSS of this Flask process in MB."""
    # Linux: current resident set from procfs (not the historical max RSS).
    status = Path("/proc/self/status")
    if status.exists():
        try:
            for line in status.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("VmRSS:"):
                    return round(float(line.split()[1]) / 1024.0, 1)
        except Exception:
            pass

    # Windows: current process working-set size via Win32.
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", wintypes.DWORD),
                    ("PageFaultCount", wintypes.DWORD),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]

            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            fn = ctypes.windll.psapi.GetProcessMemoryInfo
            fn.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS), wintypes.DWORD]
            fn.restype = wintypes.BOOL
            if fn(handle, ctypes.byref(counters), counters.cb):
                return round(counters.WorkingSetSize / 1024 / 1024, 1)
        except Exception:
            pass

    # macOS / other POSIX fallback.
    if resource is not None:
        try:
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            if sys_platform_is_darwin():
                return round(rss / 1024 / 1024, 1)
            return round(rss / 1024, 1)
        except Exception:
            pass

    return 0.0


def sys_platform_is_darwin() -> bool:
    return os.sys.platform == "darwin"


_LOAD_HISTORY: deque[tuple[float, float]] = deque(maxlen=900)


def _windows_cpu_load() -> float:
    """Sample whole-system CPU busy time and express load relative to cores."""
    try:
        import ctypes
        from ctypes import wintypes

        class FILETIME(ctypes.Structure):
            _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]

        idle1 = FILETIME(); kernel1 = FILETIME(); user1 = FILETIME()
        if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle1), ctypes.byref(kernel1), ctypes.byref(user1)):
            return 0.0

        def ft(v):
            return (v.dwHighDateTime << 32) | v.dwLowDateTime

        k1, u1, i1 = ft(kernel1), ft(user1), ft(idle1)
        time.sleep(0.10)
        idle2 = FILETIME(); kernel2 = FILETIME(); user2 = FILETIME()
        if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle2), ctypes.byref(kernel2), ctypes.byref(user2)):
            return 0.0
        k2, u2, i2 = ft(kernel2), ft(user2), ft(idle2)
        total = (k2 - k1) + (u2 - u1)
        busy = max(total - (i2 - i1), 0)
        cpu_fraction = (busy / total) if total else 0.0
        return round(cpu_fraction * max(os.cpu_count() or 1, 1), 2)
    except Exception:
        return 0.0


def _system_load() -> dict[str, float]:
    """Return 1/5/15-minute load averages, with a real Windows fallback."""
    try:
        load1, load5, load15 = os.getloadavg()
        return {"1m": round(load1, 2), "5m": round(load5, 2), "15m": round(load15, 2)}
    except (AttributeError, OSError):
        pass

    sample = _windows_cpu_load() if os.name == "nt" else 0.0
    now_ts = time.monotonic()
    _LOAD_HISTORY.append((now_ts, sample))

    def avg(seconds: int) -> float:
        cutoff = now_ts - seconds
        values = [value for ts, value in _LOAD_HISTORY if ts >= cutoff]
        return round(sum(values) / len(values), 2) if values else round(sample, 2)

    return {"1m": avg(60), "5m": avg(300), "15m": avg(900)}


def _system_memory() -> dict[str, float]:
    """Return real system-wide memory usage across Linux, Windows, and macOS."""
    # Linux: /proc/meminfo gives total and available system memory.
    path = Path("/proc/meminfo")
    if path.exists():
        raw: dict[str, float] = {}
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            parts = value.strip().split()
            if parts:
                try:
                    raw[key] = float(parts[0]) / 1024.0
                except ValueError:
                    pass
        total = raw.get("MemTotal", 0.0)
        available = raw.get("MemAvailable", raw.get("MemFree", 0.0))
        used = max(total - available, 0.0)
        return {
            "total_mb": round(total, 1),
            "available_mb": round(available, 1),
            "used_pct": round((used / total * 100.0) if total else 0.0, 1),
        }

    # Windows: GlobalMemoryStatusEx reports actual physical memory.
    if os.name == "nt":
        try:
            import ctypes
            from ctypes import wintypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", wintypes.DWORD),
                    ("dwMemoryLoad", wintypes.DWORD),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MEMORYSTATUSEX()
            status.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            fn = ctypes.windll.kernel32.GlobalMemoryStatusEx
            fn.argtypes = [ctypes.POINTER(MEMORYSTATUSEX)]
            fn.restype = wintypes.BOOL
            if fn(ctypes.byref(status)):
                total_mb = status.ullTotalPhys / 1024**2
                available_mb = status.ullAvailPhys / 1024**2
                used_pct = (
                    (status.ullTotalPhys - status.ullAvailPhys)
                    / status.ullTotalPhys
                    * 100.0
                    if status.ullTotalPhys
                    else 0.0
                )
                return {
                    "total_mb": round(total_mb, 1),
                    "available_mb": round(available_mb, 1),
                    "used_pct": round(used_pct, 1),
                }
        except Exception:
            pass

    # macOS / other platforms: use sysconf when available.
    try:
        page_size = os.sysconf("SC_PAGE_SIZE")
        total_pages = os.sysconf("SC_PHYS_PAGES")
        avail_pages = os.sysconf("SC_AVPHYS_PAGES")
        total = float(page_size * total_pages)
        available = float(page_size * avail_pages)
        used = max(total - available, 0.0)
        return {
            "total_mb": round(total / 1024**2, 1),
            "available_mb": round(available / 1024**2, 1),
            "used_pct": round((used / total * 100.0) if total else 0.0, 1),
        }
    except Exception:
        return {"total_mb": 0.0, "available_mb": 0.0, "used_pct": 0.0}


def _disk_usage() -> dict[str, float]:
    db_path = Path(str(current_app.config.get("DATABASE", "."))).resolve()
    target = db_path.parent
    usage = shutil.disk_usage(target)
    return {
        "total_gb": round(usage.total / 1024**3, 2),
        "used_gb": round((usage.total - usage.free) / 1024**3, 2),
        "free_gb": round(usage.free / 1024**3, 2),
        "used_pct": round((usage.total - usage.free) / usage.total * 100.0, 1) if usage.total else 0.0,
    }


def _db_latency_ms(db) -> float:
    start = time.perf_counter()
    db.execute("SELECT 1").fetchone()
    return round((time.perf_counter() - start) * 1000.0, 2)


@ops_api.get("/admin/ops/health")
def ops_health():
    _require_capability("system.monitor")
    db = get_db()
    started = time.perf_counter()
    db_ok = True
    try:
        db.execute("SELECT 1").fetchone()
    except Exception:
        db_ok = False
    response_ms = round((time.perf_counter() - started) * 1000.0, 2)
    disk = _disk_usage()
    memory = _system_memory()
    load = _system_load()

    return jsonify(
        ok=db_ok,
        database="ok" if db_ok else "error",
        database_latency_ms=response_ms,
        process_uptime_seconds=int(max(time.time() - _STARTED_AT, 0)),
        process_memory_mb=_memory_mb(),
        memory=memory,
        disk=disk,
        load=load,
        python=os.sys.version.split()[0],
        pid=os.getpid(),
        db_backend=_backend(),
        timestamp=now(),
    )


def _fetch_completed_orders(db, days: int = 28):
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    return db.execute(
        """SELECT o.id,o.user_id,o.charger_id,o.started_at,o.ended_at,o.energy,
                  o.amount_cents,o.paid_cents,o.simulated_seconds,
                  c.station_id,c.number,c.kind,c.power,s.name station_name,
                  u.nickname,u.phone
           FROM orders o
           JOIN chargers c ON c.id=o.charger_id
           JOIN stations s ON s.id=c.station_id
           JOIN users u ON u.id=o.user_id
          WHERE o.status='completed' AND o.ended_at>=?
          ORDER BY o.ended_at DESC""",
        (cutoff,),
    ).fetchall()


@ops_api.get("/admin/ops/analytics")
def ops_analytics():
    _require_capability("analytics.utilization", "analytics.view")
    db = get_db()
    days = min(max(request.args.get("days", 28, type=int) or 28, 1), 90)
    orders = [dict(r) for r in _fetch_completed_orders(db, days)]
    window_minutes = days * 24 * 60

    stations = [dict(r) for r in db.execute("SELECT id,name FROM stations ORDER BY id").fetchall()]
    charger_counts = {}
    for row in db.execute("SELECT station_id,COUNT(*) total,SUM(CASE WHEN kind='fast' THEN 1 ELSE 0 END) fast,SUM(CASE WHEN kind='slow' THEN 1 ELSE 0 END) slow FROM chargers GROUP BY station_id").fetchall():
        charger_counts[row["station_id"]] = dict(row)

    station_stats = []
    for s in stations:
        sid = s["id"]
        c = charger_counts.get(sid, {"total": 0, "fast": 0, "slow": 0})
        rows = [o for o in orders if o["station_id"] == sid]
        charging_minutes = sum((o.get("simulated_seconds") or 0) / 60.0 for o in rows)
        utilization = charging_minutes / (max(int(c.get("total") or 0), 1) * window_minutes) * 100.0 if c.get("total") else 0.0
        energy = sum(float(o.get("energy") or 0) for o in rows)
        revenue = sum(int(o.get("paid_cents") or 0) for o in rows)
        station_stats.append({
            "station_id": sid,
            "station_name": s["name"],
            "chargers": int(c.get("total") or 0),
            "fast": int(c.get("fast") or 0),
            "slow": int(c.get("slow") or 0),
            "orders": len(rows),
            "energy_kwh": round(energy, 2),
            "revenue_cents": revenue,
            "charging_minutes": round(charging_minutes, 1),
            "utilization_pct": round(min(utilization, 100.0), 1),
            "avg_session_minutes": round(charging_minutes / len(rows), 1) if rows else 0.0,
        })

    station_stats.sort(key=lambda x: (x["utilization_pct"], x["revenue_cents"]), reverse=True)

    hour_bins = [{"hour": h, "orders": 0, "energy_kwh": 0.0, "charging_minutes": 0.0} for h in range(24)]
    daily_orders = {}
    user_sessions = {}
    for o in orders:
        if o.get("started_at"):
            try:
                h = datetime.fromisoformat(o["started_at"]).hour
                hour_bins[h]["orders"] += 1
                hour_bins[h]["energy_kwh"] += float(o.get("energy") or 0)
                hour_bins[h]["charging_minutes"] += (o.get("simulated_seconds") or 0) / 60.0
            except (TypeError, ValueError):
                pass
        if o.get("ended_at"):
            day = str(o["ended_at"])[:10]
            daily_orders.setdefault(day, {"day": day, "orders": 0, "energy_kwh": 0.0, "revenue_cents": 0})
            daily_orders[day]["orders"] += 1
            daily_orders[day]["energy_kwh"] += float(o.get("energy") or 0)
            daily_orders[day]["revenue_cents"] += int(o.get("paid_cents") or 0)
        uid = o.get("user_id")
        user_sessions.setdefault(uid, {"orders": 0, "energy": 0.0, "paid": 0, "minutes": 0.0})
        user_sessions[uid]["orders"] += 1
        user_sessions[uid]["energy"] += float(o.get("energy") or 0)
        user_sessions[uid]["paid"] += int(o.get("paid_cents") or 0)
        user_sessions[uid]["minutes"] += (o.get("simulated_seconds") or 0) / 60.0

    for h in hour_bins:
        h["energy_kwh"] = round(h["energy_kwh"], 2)
        h["charging_minutes"] = round(h["charging_minutes"], 1)
    peak = max(hour_bins, key=lambda x: (x["orders"], x["energy_kwh"])) if hour_bins else {"hour": 0, "orders": 0}

    total_orders = len(orders)
    total_minutes = sum(v["charging_minutes"] for v in station_stats)
    total_energy = sum(float(o.get("energy") or 0) for o in orders)
    total_revenue = sum(int(o.get("paid_cents") or 0) for o in orders)
    total_sessions_users = len(user_sessions)
    user_order_values = list(user_sessions.values())

    return jsonify(
        days=days,
        summary={
            "orders": total_orders,
            "energy_kwh": round(total_energy, 2),
            "revenue_cents": total_revenue,
            "stations": len(station_stats),
            "users": total_sessions_users,
            "avg_order_cents": round(total_revenue / total_orders) if total_orders else 0,
            "avg_session_minutes": round(total_minutes / total_orders, 1) if total_orders else 0.0,
            "avg_user_orders": round(total_orders / total_sessions_users, 1) if total_sessions_users else 0.0,
        },
        peak_hour={"hour": peak["hour"], "orders": peak["orders"]},
        station_utilization=station_stats,
        hourly=hour_bins,
        daily=sorted(
            [
                {
                    **v,
                    "energy_kwh": round(v["energy_kwh"], 2),
                }
                for v in daily_orders.values()
            ],
            key=lambda x: x["day"],
        ),
        top_stations=station_stats[:5],
        user_behavior={
            "sessions_users": total_sessions_users,
            "avg_sessions_per_user": round(total_orders / total_sessions_users, 1) if total_sessions_users else 0.0,
            "avg_energy_per_user_kwh": round(total_energy / total_sessions_users, 2) if total_sessions_users else 0.0,
            "avg_spend_per_user_cents": round(total_revenue / total_sessions_users) if total_sessions_users else 0,
            "returning_users": sum(1 for v in user_order_values if v["orders"] >= 2),
        },
    )


def _notification_id(user_id: int | None, kind: str, ref_id: str | int | None) -> str:
    raw = f"{user_id or 'system'}|{kind}|{ref_id or ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]


def _upsert_notification(db, user_id, kind, title, body, level="info", ref_type=None, ref_id=None):
    nid = _notification_id(user_id, kind, ref_id)
    exists = db.execute("SELECT 1 FROM notifications WHERE id=?", (nid,)).fetchone()
    if exists:
        return
    db.execute(
        """INSERT INTO notifications(id,user_id,kind,title,body,level,`read`,created_at,ref_type,ref_id)
           VALUES(?,?,?,?,?,?,0,?,?,?)""",
        (nid, user_id, kind, title, body, level, now(), ref_type, str(ref_id) if ref_id is not None else None),
    )


def _refresh_notifications(db, user):
    uid = user["id"]
    # User-facing state alerts.
    if user["role"] == "user":
        if int(user["balance_cents"] or 0) <= 1000:
            _upsert_notification(db, uid, "low_balance", "余额提醒", "当前余额不足 ¥10，充电前建议及时充值。", "warning")
        debt = db.execute("SELECT COALESCE(SUM(debt_cents),0) v FROM orders WHERE user_id=? AND debt_cents>0", (uid,)).fetchone()["v"]
        if debt:
            _upsert_notification(db, uid, "debt", "存在待补缴订单", f"当前有 ¥{debt/100:.2f} 欠费，请补缴后再开始下一次充电。", "danger")
        active = db.execute(
            """
            SELECT
                o.id AS id,
                o.status AS status,
                s.name AS station_name
            FROM orders o
            JOIN chargers c
                ON c.id = o.charger_id
            JOIN stations s
                ON s.id = c.station_id
            WHERE
                o.user_id = ?
                AND o.status IN ('reserved', 'charging')
            ORDER BY o.id DESC
            LIMIT 1
            """,
            (uid,),
        ).fetchone()
        if active:
            text = "预约中的充电订单仍在保留。" if active["status"] == "reserved" else "你有一个正在充电的订单。"
            _upsert_notification(db, uid, "active_order", "充电状态提醒", f"{active['station_name']}：{text}", "info", "order", active["id"])

    # Operator / technician / admin fault reminders.
    if user["role"] in ("operator", "technician", "admin"):
        try:
            faults = db.execute(
                """SELECT f.id,f.status,c.number,s.name station_name
                     FROM fault_records f JOIN chargers c ON c.id=f.charger_id JOIN stations s ON s.id=c.station_id
                    WHERE f.status IN ('pending','processing')
                    ORDER BY f.id DESC LIMIT 20"""
            ).fetchall()
        except Exception:
            faults = []
        for f in faults:
            _upsert_notification(
                db,
                uid,
                "fault",
                "设备故障待处理",
                f"{f['station_name']} · {f['number']} 当前状态：{f['status']}。",
                "danger",
                "fault",
                f["id"],
            )

    # Persist a backup reminder if there has never been a backup.
    if user["role"] == "admin":
        row = db.execute("SELECT value FROM ops_feature_kv WHERE `key`='last_backup' LIMIT 1").fetchone()
        if not row:
            _upsert_notification(db, uid, "backup", "建议建立首个数据库备份", "当前还没有检测到数据库备份，建议先建立一份可恢复备份。", "warning")


@ops_api.get("/notifications")
def notifications():
    user = _require_capability("notification.view")
    db = get_db()
    _refresh_notifications(db, user)
    rows = [dict(r) for r in db.execute(
        "SELECT * FROM notifications WHERE user_id=? ORDER BY `read` ASC, created_at DESC LIMIT 100",
        (user["id"],),
    ).fetchall()]
    unread = sum(1 for r in rows if not r["read"])
    return jsonify(items=rows, unread=unread)


@ops_api.post("/notifications/<nid>/read")
def notification_read(nid):
    user = _require_capability("notification.view")
    db = get_db()
    row = db.execute("UPDATE notifications SET `read`=1 WHERE id=? AND user_id=?", (nid, user["id"]))
    return jsonify(ok=True, updated=bool(getattr(row, "rowcount", 0)))


@ops_api.post("/notifications/read-all")
def notifications_read_all():
    user = _require_capability("notification.view")
    db = get_db()
    db.execute("UPDATE notifications SET `read`=1 WHERE user_id=?", (user["id"],))
    return jsonify(ok=True)


@ops_api.get("/admin/ops/audit")
def audit_log():
    _require_capability("audit.view", "log.view")
    db = get_db()
    actor = request.args.get("actor", "").strip()
    keyword = request.args.get("q", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    limit = min(max(request.args.get("limit", 100, type=int) or 100, 1), 200)

    where = []
    params = []
    if actor:
        where.append("CAST(l.actor_id AS TEXT)=?")
        params.append(actor)
    if keyword:
        where.append("LOWER(l.operation) LIKE ?")
        params.append(f"%{keyword.lower()}%")
    if date_from:
        where.append("substr(l.created_at,1,10)>=?")
        params.append(date_from)
    if date_to:
        where.append("substr(l.created_at,1,10)<=?")
        params.append(date_to)
    sql = """SELECT l.id,l.actor_id,l.operation,l.created_at,u.nickname,u.phone
               FROM ops_log l LEFT JOIN users u ON u.id=l.actor_id"""
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY l.id DESC LIMIT ?"
    params.append(limit)
    rows = [dict(r) for r in db.execute(sql, tuple(params)).fetchall()]

    category_counts: dict[str, int] = {}
    for r in rows:
        op = str(r["operation"] or "")
        category = "其他"
        if "电桩" in op:
            category = "设备"
        elif "电站" in op:
            category = "电站"
        elif "用户" in op or "角色" in op:
            category = "用户/权限"
        elif "价格" in op:
            category = "价格"
        elif "故障" in op:
            category = "故障"
        category_counts[category] = category_counts.get(category, 0) + 1
    return jsonify(items=rows, total=len(rows), category_counts=category_counts)


def _backup_dir() -> Path:
    base = Path(str(current_app.config.get("NCS_BACKUP_DIR", ""))).expanduser()
    if not str(base):
        db_file = Path(str(current_app.config.get("DATABASE", "data/ncs.db"))).resolve()
        base = db_file.parent / "backups"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _backup_inventory() -> list[dict[str, Any]]:
    items = []
    for p in sorted(_backup_dir().glob("ncs-*.db"), key=lambda x: x.stat().st_mtime, reverse=True):
        stat = p.stat()
        items.append({
            "filename": p.name,
            "size_bytes": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        })
    return items


@ops_api.get("/admin/ops/backups")
def backups_list():
    _require_capability("backup.manage", admin_only=True)
    return jsonify(
        supported=_is_sqlite(),
        backend=_backend(),
        items=_backup_inventory() if _is_sqlite() else [],
    )


@ops_api.post("/admin/ops/backups")
def backup_create():
    user = _require_capability("backup.manage", admin_only=True)
    if not _is_sqlite():
        raise BusinessError("当前数据库后端不支持本地 SQLite 备份，请使用数据库原生备份方案", 409)

    db_file = Path(str(current_app.config["DATABASE"])).resolve()
    if not db_file.exists():
        raise BusinessError("数据库文件不存在，无法备份", 404)

    target_dir = _backup_dir()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = target_dir / f"ncs-{stamp}.db"
    source = sqlite3.connect(str(db_file), timeout=30)
    destination = sqlite3.connect(str(target), timeout=30)
    try:
        source.backup(destination)
        destination.execute("PRAGMA integrity_check")
        destination.commit()
    finally:
        source.close()
        destination.close()

    inventory = _backup_inventory()
    for old in inventory[10:]:
        try:
            (target_dir / old["filename"]).unlink()
        except OSError:
            pass

    db = get_db()
    db.execute(
        "INSERT OR REPLACE INTO ops_feature_kv(`key`,value) VALUES(?,?)",
        ("last_backup", json.dumps({"filename": target.name, "created_at": now()})),
    )
    try:
        db.execute("INSERT INTO ops_log(actor_id,operation,created_at) VALUES(?,?,?)", (user["id"], f"创建数据库备份 {target.name}", now()))
    except Exception:
        pass
    return jsonify(ok=True, filename=target.name, backups=_backup_inventory())


@ops_api.get("/admin/ops/backups/<path:filename>")
def backup_download(filename: str):
    _require_capability("backup.manage", admin_only=True)
    if not _is_sqlite():
        raise BusinessError("当前数据库后端不支持本地备份下载", 409)
    filename = _safe_identifier(filename)
    if not re.fullmatch(r"ncs-\d{8}-\d{6}\.db", filename):
        raise BusinessError("备份文件名无效", 400)
    base = _backup_dir().resolve()
    target = (base / filename).resolve()
    if base not in target.parents or not target.exists():
        raise BusinessError("备份文件不存在", 404)
    return send_file(target, as_attachment=True, download_name=target.name, mimetype="application/octet-stream")
