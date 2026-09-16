#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys
import os

ROOT = Path.cwd()

def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"{label}: expected 1 match, found {count}. "
            "Stop instead of applying an unsafe patch."
        )
    return text.replace(old, new, 1)

def run(*args, check=True):
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    p = subprocess.run(
        list(args),
        cwd=ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
    )
    if check and p.returncode != 0:
        raise RuntimeError(
            f"Command failed ({p.returncode}): {' '.join(args)}\n{p.stdout}"
        )
    return p

def main():
    if not (ROOT / ".git").exists():
        raise RuntimeError("Run this from the NCS_Charging project root.")

    branch = run("git", "branch", "--show-current").stdout.strip()
    print("Current branch:", branch)

    if not branch.startswith("integration/dev-lim-"):
        raise RuntimeError(
            "This fix is intended for the DEV+LIM integration branch. "
            f"Current branch is: {branch}"
        )

    dirty = run(
        "git", "status", "--porcelain", "--untracked-files=no"
    ).stdout.strip()
    if dirty:
        raise RuntimeError(
            "Tracked files already have uncommitted changes. "
            "Commit/stash them first:\n" + dirty
        )

    paths = [
        ROOT / "ncs" / "loyalty.py",
        ROOT / "ncs" / "notifications.py",
        ROOT / "ncs" / "ops_features.py",
    ]
    for p in paths:
        if not p.exists():
            raise RuntimeError(f"Missing required file: {p}")

    print("[1/5] Fixing loyalty MySQL FK/id types...")
    p = ROOT / "ncs" / "loyalty.py"
    text = p.read_text(encoding="utf-8-sig")

    replacements = [
        ("user_id INT PRIMARY KEY,", "user_id BIGINT UNSIGNED PRIMARY KEY,"),
        ("id INT PRIMARY KEY AUTO_INCREMENT,", "id BIGINT UNSIGNED PRIMARY KEY AUTO_INCREMENT,"),
        ("user_id INT NOT NULL,", "user_id BIGINT UNSIGNED NOT NULL,"),
        ("order_id INT NULL,", "order_id BIGINT UNSIGNED NULL,"),
        ("coupon_id INT NOT NULL,", "coupon_id BIGINT UNSIGNED NOT NULL,"),
        ("order_id INT PRIMARY KEY,", "order_id BIGINT UNSIGNED PRIMARY KEY,"),
        ("coupon_id INT NULL,", "coupon_id BIGINT UNSIGNED NULL,"),
    ]

    # Some patterns occur more than once intentionally. Replace all in the MySQL
    # schema section only, before the SQLite "else:" block.
    marker = "\n    else:\n"
    if marker not in text:
        raise RuntimeError("Could not locate SQLite branch in ncs/loyalty.py")

    mysql_part, sqlite_part = text.split(marker, 1)

    for old, new in replacements:
        mysql_part = mysql_part.replace(old, new)

    # Verify core referenced columns now match DEV's BIGINT UNSIGNED IDs.
    required = [
        "user_id BIGINT UNSIGNED PRIMARY KEY",
        "user_id BIGINT UNSIGNED NOT NULL",
        "order_id BIGINT UNSIGNED NULL",
        "coupon_id BIGINT UNSIGNED NOT NULL",
        "order_id BIGINT UNSIGNED PRIMARY KEY",
        "coupon_id BIGINT UNSIGNED NULL",
    ]
    for needle in required:
        if needle not in mysql_part:
            raise RuntimeError(f"Missing expected patched type: {needle}")

    p.write_text(mysql_part + marker + sqlite_part, encoding="utf-8")

    print("[2/5] Fixing notification table user-id type...")
    p = ROOT / "ncs" / "notifications.py"
    text = p.read_text(encoding="utf-8-sig")
    text = replace_once(
        text,
        "            user_id INTEGER,\n",
        "            user_id BIGINT UNSIGNED,\n",
        "notifications.py user_id type",
    )

    # Use cross-database column types that are valid in both MySQL and SQLite.
    text = text.replace(
        "            kind TEXT NOT NULL,\n",
        "            kind VARCHAR(32) NOT NULL,\n",
    )
    text = text.replace(
        "            title TEXT NOT NULL,\n",
        "            title VARCHAR(255) NOT NULL,\n",
    )
    text = text.replace(
        "            level TEXT NOT NULL DEFAULT 'info',\n",
        "            level VARCHAR(16) NOT NULL DEFAULT 'info',\n",
    )
    text = text.replace(
        "            read INTEGER NOT NULL DEFAULT 0,\n",
        "            read TINYINT(1) NOT NULL DEFAULT 0,\n",
    )
    text = text.replace(
        "            created_at TEXT NOT NULL,\n",
        "            created_at VARCHAR(32) NOT NULL,\n",
    )
    text = text.replace(
        "            ref_type TEXT,\n",
        "            ref_type VARCHAR(64),\n",
    )
    text = text.replace(
        "            ref_id TEXT\n",
        "            ref_id VARCHAR(128)\n",
    )
    p.write_text(text, encoding="utf-8")

    print("[3/5] Fixing Operations Center notification schema...")
    p = ROOT / "ncs" / "ops_features.py"
    text = p.read_text(encoding="utf-8-sig")
    text = replace_once(
        text,
        "            user_id INTEGER REFERENCES users(id),\n",
        "            user_id BIGINT UNSIGNED REFERENCES users(id),\n",
        "ops_features.py user_id FK type",
    )
    text = text.replace(
        "            kind TEXT NOT NULL,\n",
        "            kind VARCHAR(32) NOT NULL,\n",
    )
    text = text.replace(
        "            title TEXT NOT NULL,\n",
        "            title VARCHAR(255) NOT NULL,\n",
    )
    text = text.replace(
        "            level TEXT NOT NULL DEFAULT 'info',\n",
        "            level VARCHAR(16) NOT NULL DEFAULT 'info',\n",
    )
    text = text.replace(
        "            read INTEGER NOT NULL DEFAULT 0,\n",
        "            read TINYINT(1) NOT NULL DEFAULT 0,\n",
    )
    text = text.replace(
        "            created_at TEXT NOT NULL,\n",
        "            created_at VARCHAR(32) NOT NULL,\n",
    )
    text = text.replace(
        "            ref_type TEXT,\n",
        "            ref_type VARCHAR(64),\n",
    )
    text = text.replace(
        "            ref_id TEXT\n",
        "            ref_id VARCHAR(128)\n",
    )
    p.write_text(text, encoding="utf-8")

    print("[4/5] Running Python syntax checks...")
    for rel in [
        "ncs/loyalty.py",
        "ncs/notifications.py",
        "ncs/ops_features.py",
    ]:
        run(sys.executable, "-m", "py_compile", rel)

    print("[5/5] Committing schema compatibility fix...")
    run(
        "git", "add",
        "ncs/loyalty.py",
        "ncs/notifications.py",
        "ncs/ops_features.py",
    )
    run(
        "git", "commit",
        "-m", "fix: align LIM MySQL foreign keys with DEV bigint ids",
    )

    commit = run("git", "rev-parse", "HEAD").stdout.strip()

    report = f"""LIM MySQL schema compatibility fix
====================================
branch: {branch}
commit: {commit}

Fixed:
- member_accounts.user_id -> BIGINT UNSIGNED
- points_ledger user/order IDs -> BIGINT UNSIGNED
- coupons / user_coupons IDs -> BIGINT UNSIGNED where referenced
- order_loyalty order/coupon IDs -> BIGINT UNSIGNED
- notifications.user_id -> BIGINT UNSIGNED
- Operations Center notifications.user_id -> BIGINT UNSIGNED
- notification VARCHAR/TINYINT types made MySQL-safe

Syntax checks: PASS

Now rerun:
.\\.venv\\Scripts\\python.exe -m unittest discover -s tests -v
"""
    (ROOT / "LIM_MYSQL_SCHEMA_FIX_REPORT.txt").write_text(
        report, encoding="utf-8"
    )
    print()
    print(report)

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print()
        print("FIX STOPPED:", exc)
        print("No force reset was performed.")
        sys.exit(1)
