#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

EXPECTED_DEV = "2ce7a388d5a149e1ffe500cf2216e089e23e721e"
EXPECTED_LIM = "3d4717e1a3a500c3f8418b48c3c647e4bdab70d5"
EXPECTED_BASE = "1c13063b7abe8ed41cad69b8e17a2a30080e0fa9"
KIT_VERSION = "2.0-dev-lim-explicit-hooks"
ROOT = Path.cwd()

JUNK = [
    "check_permissions.py",
    "fix_i18n.py",
    "fix_remaining_i18n.py",
    "ncs/services.before-clean-restore.py",
    "services_initial_test.py",
    "static/app.before-i18n-fix.js",
    "static/app.before-remaining-i18n-fix.js",
    "static/app.js.backup",
    "static/app.js.backup-coupon",
    "static/app.js.before-coupon-fix",
    "static/app.js.before-coupon-restore",
    "static/app.js.before-currency-unicode-fix",
    "static/app.js.before-final-i18n-fix",
    "static/app.js.before-final-payment-fix",
    "static/app.js.before-final-restore",
    "static/app.js.before-payment-i18n-fix",
    "static/app.js.before-price-breakdown",
    "static/app.js.before-settlement-currency-fix",
    "static/app.js.before-yen-fix",
    "static/app.js.pre-coupon-safe",
    "static/i18n/en.before-i18n-fix.json",
    "static/i18n/en.before-remaining-i18n-fix.json",
    "static/i18n/en.json.backup",
    "static/i18n/en.json.backup2",
    "static/i18n/en.json.before-final-i18n-fix",
    "static/ops_features.before-i18n-fix.js",
    "static/ops_features.before-remaining-i18n-fix.js",
    "static/preferences.js.before-final-i18n-fix",
    "test_loyalty_nonzero.py",
    "test_member_api.py",
    "test_ops_permission.py",
]

REQUIRED_FILES = [
    "ncs/loyalty.py",
    "ncs/notifications.py",
    "ncs/ops_features.py",
    "static/ops_features.css",
    "static/ops_features.js",
    "tests/test_ops_features.py",
]


def run(*args, check=True):
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    p = subprocess.run(
        list(args), cwd=ROOT, text=True, encoding="utf-8", errors="replace",
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
    )
    if check and p.returncode != 0:
        raise RuntimeError(f"Command failed ({p.returncode}): {' '.join(args)}\n{p.stdout}")
    return p


def replace_once(content, old, new, label):
    count = content.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 safe patch location, found {count}")
    return content.replace(old, new, 1)


def require_contains(path, needles, label):
    content = (ROOT / path).read_text(encoding="utf-8-sig")
    missing = [n for n in needles if n not in content]
    if missing:
        raise RuntimeError(label + " missing:\n" + "\n".join("  - " + x for x in missing))


def apply_hooks():
    # Loyalty schema initialization in current DEV db.py.
    p = ROOT / "ncs/db.py"
    s = p.read_text(encoding="utf-8")
    if "ensure_loyalty_schema" not in s:
        anchor = "    _ensure_rbac_schema(db)\n"
        s = replace_once(
            s, anchor,
            anchor
            + "\n    # LIM membership / points / coupon schema\n"
            + "    from .loyalty import ensure_schema as ensure_loyalty_schema\n"
            + "    ensure_loyalty_schema(db)\n",
            "db.py loyalty hook",
        )
        p.write_text(s, encoding="utf-8")

    # Blueprint registration in newer DEV app factory.
    p = ROOT / "ncs/__init__.py"
    s = p.read_text(encoding="utf-8")
    if "from .ops_features import ops_api" not in s:
        s = replace_once(
            s,
            "    from .routes import api\n",
            "    from .routes import api\n    from .ops_features import ops_api\n    from .loyalty import member_api\n",
            "__init__.py imports",
        )
    if "app.register_blueprint(ops_api" not in s:
        block = "    app.register_blueprint(\n        api,\n        url_prefix=\"/api\",\n    )\n"
        s = replace_once(
            s, block,
            block
            + "\n    app.register_blueprint(\n        ops_api,\n        url_prefix=\"/api\",\n    )\n"
            + "\n    app.register_blueprint(\n        member_api,\n        url_prefix=\"/api\",\n    )\n",
            "__init__.py registrations",
        )
    p.write_text(s, encoding="utf-8")

    # Service hooks while preserving DEV's newer concurrency/expiry logic.
    p = ROOT / "ncs/services.py"
    s = p.read_text(encoding="utf-8")
    if "def act_order(uid,oid,action,payload=None):" not in s:
        s = replace_once(s, "def act_order(uid,oid,action):\n", "def act_order(uid,oid,action,payload=None):\n", "services payload")
    if "insufficient_balance" not in s:
        old = "        if user['balance_cents']<=0: raise BusinessError('请先充值后再预约或充电')\n"
        new = (
            "        if user['balance_cents']<=0:\n"
            "            from .notifications import create_notification\n"
            "            create_notification(\n"
            "                db, uid, 'insufficient_balance', '余额不足',\n"
            "                '当前余额为 ¥0.00，无法开始充电，请先充值。',\n"
            "                'danger', 'wallet', f'attempt:{now()}',\n"
            "            )\n"
            "            raise BusinessError('请先充值后再预约或充电')\n"
        )
        s = replace_once(s, old, new, "services notification hook")
    if "from .loyalty import settle_with_loyalty" not in s:
        start = s.find("            end=datetime.now(); q=quote(o,end); paid=min(u['balance_cents'],q['amount_cents'])\n")
        end_marker = "            db.execute(\"INSERT INTO wallet_log(user_id,amount_cents,kind,created_at) VALUES(?,?,'充电结算',?)\",(uid,-paid,now()))\n"
        if start < 0:
            raise RuntimeError("services loyalty hook: finish block start not found")
        end = s.find(end_marker, start)
        if end < 0:
            raise RuntimeError("services loyalty hook: finish block end not found")
        end += len(end_marker)
        replacement = (
            "            end=datetime.now()\n"
            "            q=quote(o,end)\n"
            "            q['charger_id']=c['id']\n\n"
            "            from .loyalty import settle_with_loyalty\n\n"
            "            settle_with_loyalty(\n"
            "                db,\n                uid,\n                oid,\n                q,\n                u,\n                payload or {},\n            )\n"
        )
        s = s[:start] + replacement + s[end:]
    p.write_text(s, encoding="utf-8")

    # Forward coupon_id payload from finish route.
    p = ROOT / "ncs/routes.py"
    s = p.read_text(encoding="utf-8")
    if "data = body() if action == 'finish' else {}" not in s:
        s = replace_once(
            s,
            "    act_order(g.user['id'],oid,action)\n",
            "    data = body() if action == 'finish' else {}\n    act_order(g.user['id'],oid,action,data)\n",
            "routes coupon payload",
        )
    p.write_text(s, encoding="utf-8")

    # Preserve DEV cache versions while loading LIM ops assets.
    p = ROOT / "templates/index.html"
    s = p.read_text(encoding="utf-8")
    if "/static/ops_features.css" not in s:
        anchor = '<link rel="stylesheet" href="/static/themes.css?v=20260916a">\n'
        s = replace_once(s, anchor, anchor + '<link rel="stylesheet" href="/static/ops_features.css?v=20260916lim">\n', "index ops css")
    if "/static/ops_features.js" not in s:
        anchor = '<script src="/static/avatars.js?v=20260916a" defer></script>\n'
        s = replace_once(s, anchor, anchor + '<script src="/static/ops_features.js?v=20260916lim" defer></script>\n', "index ops js")
    p.write_text(s, encoding="utf-8")

    # Translation union: preserve DEV values, append every LIM-only key.
    dev_en = json.loads(run("git", "show", "origin/dev:static/i18n/en.json").stdout.lstrip("\ufeff"))
    lim_en = json.loads(run("git", "show", "origin/lim:static/i18n/en.json").stdout.lstrip("\ufeff"))
    added = 0
    for k, v in lim_en.items():
        if k not in dev_en:
            dev_en[k] = v
            added += 1
    (ROOT / "static/i18n/en.json").write_text(json.dumps(dev_en, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return added


def main():
    if not (ROOT / ".git").exists():
        raise RuntimeError("Run from the NCS_Charging project root.")
    dirty = run("git", "status", "--porcelain", "--untracked-files=no").stdout.strip()
    if dirty:
        raise RuntimeError("Tracked files are not clean. Commit/stash first:\n" + dirty)

    print("[1/10] Fetching dev and lim...")
    run("git", "fetch", "origin", "+refs/heads/dev:refs/remotes/origin/dev", "+refs/heads/lim:refs/remotes/origin/lim")
    dev = run("git", "rev-parse", "origin/dev").stdout.strip()
    lim = run("git", "rev-parse", "origin/lim").stdout.strip()
    base = run("git", "merge-base", "origin/dev", "origin/lim").stdout.strip()
    if (dev, lim, base) != (EXPECTED_DEV, EXPECTED_LIM, EXPECTED_BASE):
        raise RuntimeError(f"Branches moved.\nExpected dev {EXPECTED_DEV}\nCurrent dev {dev}\nExpected lim {EXPECTED_LIM}\nCurrent lim {lim}\nExpected base {EXPECTED_BASE}\nCurrent base {base}")

    print("[2/10] Preparing safety/integration branches...")
    run("git", "checkout", "dev")
    run("git", "merge", "--ff-only", "origin/dev")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = f"backup-before-dev-lim-{stamp}"
    integration = f"integration/dev-lim-{stamp}"
    run("git", "branch", backup)
    run("git", "checkout", "-b", integration)

    print("[3/10] Three-way merge, preferring DEV only on conflicting hunks...")
    m = run("git", "merge", "--no-commit", "--no-ff", "-X", "ours", "origin/lim", check=False)
    unresolved = run("git", "diff", "--name-only", "--diff-filter=U").stdout.strip()
    if unresolved:
        raise RuntimeError("Unexpected unresolved conflicts:\n" + unresolved)

    print("[4/10] Removing LIM development snapshots...")
    for rel in JUNK:
        if (ROOT / rel).exists():
            run("git", "rm", "-f", "--ignore-unmatch", rel, check=False)

    print("[5/10] Restoring explicit LIM integration hooks...")
    added_i18n = apply_hooks()

    print("[6/10] Verifying LIM features...")
    for rel in REQUIRED_FILES:
        if not (ROOT / rel).exists():
            raise RuntimeError("Missing LIM runtime file: " + rel)
    require_contains("ncs/db.py", ["ensure_loyalty_schema"], "loyalty schema")
    require_contains("ncs/__init__.py", ["ops_api", "member_api", "register_blueprint(ops_api", "register_blueprint(member_api"], "blueprints")
    require_contains("ncs/services.py", ["settle_with_loyalty", "insufficient_balance", ".notifications"], "service integration")
    require_contains("ncs/routes.py", ["data = body() if action == 'finish' else {}", "act_order(g.user['id'],oid,action,data)"], "coupon route")
    require_contains("ncs/loyalty.py", ["membership_tiers", "member_accounts", "points_ledger", "coupons", "user_coupons", "order_loyalty", "/member/summary", "/member/coupons", "/member/points", "settle_with_loyalty"], "loyalty module")
    require_contains("ncs/ops_features.py", ["/admin/ops/health", "/admin/ops/analytics", "/notifications", "/admin/ops/audit", "/admin/ops/backups", "system.monitor", "analytics.utilization", "notification.view"], "ops module")
    require_contains("static/app.js", ["memberPage", "/member/summary", "/member/coupons", "/member/points", "member-claim-coupon", "finishOrderModal", "finish-submit", "case \"order-finish\"", "await finishOrderModal(id)", "refreshUserNotifications", "notification-read"], "LIM frontend")
    require_contains("templates/index.html", ["ops_features.css", "ops_features.js"], "ops assets")

    print("[7/10] Verifying newer DEV features...")
    require_contains("ncs/routes.py", ["agent_chat", "station_cache_begin_refresh", "'price'", "'price_desc'", "maybe_expire_reservations"], "DEV backend")
    require_contains("static/app.js", ["const dataText", "const roleLabel", 'id="station-kind"', 'value="price_desc"', "agentSuggestions", "sendAgentMessage"], "DEV frontend")
    require_contains("Dockerfile", ["ENV PYTHONUNBUFFERED=1 \\", "PYTHONDONTWRITEBYTECODE=1 \\", "HEALTHCHECK --interval=30s"], "Docker fix")

    print("[8/10] Syntax checks...")
    for rel in ["app.py", "ncs/__init__.py", "ncs/db.py", "ncs/routes.py", "ncs/services.py", "ncs/loyalty.py", "ncs/notifications.py", "ncs/ops_features.py"]:
        run(sys.executable, "-m", "py_compile", rel)
    json.loads((ROOT / "static/i18n/en.json").read_text(encoding="utf-8"))
    node_result = "SKIPPED"
    if shutil.which("node"):
        run("node", "--check", "static/app.js")
        run("node", "--check", "static/ops_features.js")
        node_result = "PASS"
    markers = run("git", "grep", "-n", "-E", "^(<<<<<<<|=======|>>>>>>>)", check=False)
    if markers.returncode == 0 and markers.stdout.strip():
        raise RuntimeError("Conflict markers remain:\n" + markers.stdout)

    print("[9/10] Writing report...")
    report = f"""NCS Charging dev + lim merge report\n===================================\nkit version: {KIT_VERSION}\ndev pinned: {EXPECTED_DEV}\nlim pinned: {EXPECTED_LIM}\nmerge base: {EXPECTED_BASE}\nintegration branch: {integration}\nsafety branch: {backup}\n\nLIM verified:\n- membership tiers / points / coupons\n- coupon-aware charging settlement\n- Member Center frontend\n- Operations Center / health / analytics / audit / backups\n- notification center + user notification UI\n- operations RBAC hooks\n- ops JS/CSS assets\n- LIM-only English keys added: {added_i18n}\n\nDEV verified preserved:\n- AI Agent\n- station cache\n- fast/slow station filtering\n- nearest/price sorting\n- dataText()/roleLabel() translation architecture\n- Docker/CI fix\n\nValidation:\n- Python compile: PASS\n- en.json parse: PASS\n- Node checks: {node_result}\n- conflict marker scan: PASS\n\nNext:\n1. Run .\\.venv\\Scripts\\python.exe -m unittest discover -s tests -v\n2. Test Member Center, coupons, finish charging, notifications, Operations Center, AI Agent, station filters.\n3. Push only after validation.\n"""
    (ROOT / "MERGE_DEV_LIM_REPORT.txt").write_text(report, encoding="utf-8")

    print("[10/10] Committing integration branch...")
    run("git", "add", "-A")
    run("git", "commit", "-m", "merge: integrate lim membership and operations features into dev")
    print(report)
    print("SUCCESS")
    print("Current branch:", integration)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("\nMERGE STOPPED:", exc)
        if (ROOT / ".git" / "MERGE_HEAD").exists():
            subprocess.run(["git", "merge", "--abort"], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("The incomplete Git merge was automatically aborted.")
        print("No force reset was performed.")
        sys.exit(1)
