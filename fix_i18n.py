from pathlib import Path
import json
import shutil
import re

ROOT = Path(".")

APP = ROOT / "static" / "app.js"
OPS = ROOT / "static" / "ops_features.js"
EN = ROOT / "static" / "i18n" / "en.json"

for path in (APP, OPS, EN):
    if not path.exists():
        raise SystemExit(f"Missing file: {path}")

# ============================================================
# BACKUPS
# ============================================================

shutil.copy2(
    APP,
    APP.with_name("app.before-i18n-fix.js")
)

shutil.copy2(
    OPS,
    OPS.with_name("ops_features.before-i18n-fix.js")
)

shutil.copy2(
    EN,
    EN.with_name("en.before-i18n-fix.json")
)

app = APP.read_text(encoding="utf-8")
ops = OPS.read_text(encoding="utf-8")

# ============================================================
# ENGLISH TRANSLATION DICTIONARY
# ============================================================

en_text = EN.read_text(encoding="utf-8")

# Fix the comma that was missing in the current en.json.
en_text = en_text.replace(
    '  "筛选结果": "Filtered results"\n',
    '  "筛选结果": "Filtered results",\n',
    1
)

en = json.loads(en_text)

translations = {
    # --------------------------------------------------------
    # Navigation / roles
    # --------------------------------------------------------
    "运营中心": "Operations Center",
    "角色与权限": "Roles & Permissions",
    "运维总览": "Operations Overview",
    "电站运维": "Station Operations",
    "设备运维": "Equipment Operations",
    "普通用户": "Regular User",
    "运营人员": "Operator",
    "运维人员": "Maintenance Staff",
    "系统管理员": "System Administrator",
    "用户": "User",
    "运营": "Operations",
    "运维": "Maintenance",
    "管理员": "Administrator",
    "技术员": "Technician",
    "设备": "Devices",
    "仅查看": "View only",

    # --------------------------------------------------------
    # Users / RBAC
    # --------------------------------------------------------
    "四种角色统一管理":
        "Unified management of four roles",

    "权限在服务端强制校验，页面只展示当前角色可用的功能。":
        "Permissions are enforced on the server; this page only shows functions available to the current role.",

    "后端按权限强制校验；这里显示四种业务角色的权限矩阵。":
        "Permissions are enforced by the backend; this page shows the permission matrix for the four business roles.",

    "查询、充电、订单与个人账户":
        "Charging, orders, and personal account",

    "电站、订单、价格与运营数据":
        "Stations, orders, pricing, and operations data",

    "设备状态与故障处理":
        "Device status and fault handling",

    "全局用户、角色与系统管理":
        "Global user, role, and system administration",

    # --------------------------------------------------------
    # RBAC permission names
    # --------------------------------------------------------
    "查看充电站":
        "View charging stations",

    "管理充电站":
        "Manage charging stations",

    "查看充电桩":
        "View chargers",

    "管理充电桩":
        "Manage chargers",

    "查看全部订单":
        "View all orders",

    "导出订单":
        "Export orders",

    "管理价格":
        "Manage pricing",

    "处理设备故障":
        "Handle device faults",

    "查看运营数据":
        "View operations data",

    "查看负荷预测":
        "View load forecasts",

    "管理用户":
        "Manage users",

    "管理角色与权限":
        "Manage roles & permissions",

    "查看操作日志":
        "View activity logs",

    "查看系统运行监控":
        "View system monitoring",

    "查看设备利用率分析":
        "View utilization analytics",

    "查看增强审计日志":
        "View enhanced audit logs",

    "管理数据库备份":
        "Manage database backups",

    "查看通知中心":
        "View notification center",

    # --------------------------------------------------------
    # Activity log
    # --------------------------------------------------------
    "最近操作":
        "Recent activity",

    "创建数据库备份":
        "Created database backup",

    # --------------------------------------------------------
    # Pricing
    # --------------------------------------------------------
    "分时计价":
        "Time-of-use pricing",

    "电费 + 服务费 = 用户实际单价":
        "Energy fee + service fee = customer rate",

    "时段不能重叠。若需要跨午夜，请拆成 18:00-24:00 和 00:00-08:00 两条规则。":
        "Time periods cannot overlap. Split periods that cross midnight, for example 18:00–24:00 and 00:00–08:00.",

    # --------------------------------------------------------
    # Technician overview
    # --------------------------------------------------------
    "让每一台设备，":
        "Keep every device",

    "都保持在最佳状态。":
        "in top condition.",

    "统一查看电站健康度、设备状态与异常情况，":
        "View station health, device status, and anomalies in one place.",

    "直接从电站进入设备运维。":
        "Go directly from a station into device operations.",

    # --------------------------------------------------------
    # Operations Center
    # --------------------------------------------------------
    "暂无数据":
        "No data yet",

    "天":
        "days",

    "小时":
        "hours",

    "分钟":
        "min",

    "系统健康":
        "System health",

    "数据库":
        "Database",

    "正常":
        "Normal",

    "数据库延迟":
        "Database latency",

    "进程内存":
        "Process memory",

    "运行时长":
        "Uptime",

    "实时读取 ECS / 容器内应用运行状态；":
        "Reads the live ECS/container application status.",

    "不依赖额外监控服务。":
        "No additional monitoring service is required.",

    "● 正常":
        "● Healthy",

    "● 异常":
        "● Unhealthy",

    "连接正常":
        "Connected",

    "连接失败":
        "Connection failed",

    "系统内存":
        "System memory",

    "已使用":
        "Used",

    "可用":
        "Available",

    "总计":
        "Total",

    "磁盘":
        "Disk",

    "系统负载 1m":
        "System load 1m",

    "最近检查":
        "Last checked",

    "已完成":
        "Completed",

    "快":
        "Fast",

    "慢":
        "Slow",

    "近 28 天订单":
        "Orders — last 28 days",

    "笔":
        "orders",

    "笔订单；":
        "orders;",

    "充电电量":
        "Energy charged",

    "实收营收":
        "Collected revenue",

    "平均利用率":
        "Average utilization",

    "峰值时段":
        "Peak period",

    "共":
        "Total",

    "可用于容量与负荷预测的运营依据。":
        "Useful operational data for capacity and load forecasting.",

    "活跃用户":
        "Active users",

    "电站利用率分析":
        "Station utilization analytics",

    "按近 28 天已完成订单的实际充电分钟数 ÷ 电桩可服务分钟数计算。":
        "Based on actual charging minutes from completed orders in the last 28 days divided by available charger service minutes.",

    "排名":
        "Rank",

    "电桩":
        "Chargers",

    "类型":
        "Type",

    "订单":
        "Orders",

    "电量":
        "Energy",

    "实收":
        "Collected",

    "利用率":
        "Utilization",

    "平均时长":
        "Average duration",

    "利用率 Top 5":
        "Top 5 by utilization",

    "优先关注高负载站点。":
        "Prioritize high-load stations.",

    "用户行为":
        "User behavior",

    "回访与消费概况。":
        "Return visits and spending overview.",

    "指标":
        "Metric",

    "值":
        "Value",

    "人均订单":
        "Orders per user",

    "人均电量":
        "Energy per user",

    "人均消费":
        "Spend per user",

    "回访用户":
        "Returning users",

    "24 小时使用分布":
        "24-hour usage distribution",

    "订单量、电量和充电时长的时段分布。":
        "Time-of-day distribution of orders, energy, and charging duration.",

    "时段":
        "Time period",

    "充电时长":
        "Charging duration",

    # --------------------------------------------------------
    # Audit
    # --------------------------------------------------------
    "操作审计":
        "Audit log",

    "查看增强审计日志需要相应的审计权限。":
        "Viewing enhanced audit logs requires the appropriate audit permission.",

    "无访问权限":
        "Access restricted",

    "当前角色无法查看增强审计日志。":
        "The current role cannot view enhanced audit logs.",

    "支持按操作人、关键词和日期范围查询关键管理行为。":
        "Search key administrative actions by operator, keyword, and date range.",

    "暂无分类":
        "No categories",

    "搜索操作内容":
        "Search activity",

    "操作人":
        "Operator",

    "操作内容":
        "Activity",

    "操作人 ID":
        "Operator ID",

    "查询":
        "Search",

    # --------------------------------------------------------
    # Notifications
    # --------------------------------------------------------
    "通知中心":
        "Notification center",

    "条未读通知 ·":
        "unread notifications ·",

    "系统会根据当前业务状态自动生成提醒。":
        "The system generates alerts from current business activity.",

    "全部已读":
        "Mark all as read",

    "新":
        "New",

    "标记已读":
        "Mark as read",

    "暂无通知":
        "No notifications",

    # --------------------------------------------------------
    # Backup
    # --------------------------------------------------------
    "数据库备份与恢复":
        "Database backup & recovery",

    "数据备份与恢复需要系统管理员权限。":
        "Database backup and recovery requires system administrator access.",

    "当前角色无法执行数据库备份与恢复。":
        "The current role cannot perform database backup and recovery.",

    "数据备份":
        "Database backup",

    "当前数据库后端为":
        "Current database backend:",

    "本页面仅提供 SQLite 文件备份；":
        "This page provides SQLite file backups only;",

    "MySQL 请使用数据库原生备份。":
        "for MySQL, use the database's native backup tools.",

    "下载":
        "Download",

    "备份文件":
        "Backup file",

    "大小":
        "Size",

    "操作":
        "Actions",

    "创建 SQLite 热备并保留最近 10 份文件；":
        "Create a live SQLite backup and keep the latest 10 files;",

    "下载后可用于灾备恢复。":
        "downloaded files can be used for disaster recovery.",

    "立即备份":
        "Back up now",

    "设备利用率":
        "Device utilization",

    "云端运行":
        "Running in cloud",

    "运营中心加载失败":
        "Operations Center failed to load",

    "当前后端不支持本地 SQLite 备份":
        "The current backend does not support local SQLite backups",

    "备份成功：":
        "Backup successful:",

    "如需查看，请使用具有 audit.view 权限的运营人员或管理员账号。":
        "To view this section, use an operator or administrator account with audit.view permission.",
}

for key, value in translations.items():
    en[key] = value

EN.write_text(
    json.dumps(en, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)

# ============================================================
# APP.JS
# ============================================================

def replace_once(text, old, new, name):
    if old not in text:
        raise SystemExit(
            f"Could not find expected code for: {name}"
        )
    return text.replace(old, new, 1)

# Technician overview.
app = replace_once(
    app,
    '<h2>让每一台设备，<br>都保持在最佳状态。</h2>',
    '<h2>${tr("让每一台设备，")}<br>${tr("都保持在最佳状态。")}</h2>',
    "technician overview title",
)

app = replace_once(
    app,
    """            <p>
              统一查看电站健康度、设备状态与异常情况，<br>
              直接从电站进入设备运维。
            </p>""",
    """            <p>
              ${tr("统一查看电站健康度、设备状态与异常情况，")}<br>
              ${tr("直接从电站进入设备运维。")}
            </p>""",
    "technician overview description",
)

app = replace_once(
    app,
    "            <small>设备</small>",
    '            <small>${tr("设备")}</small>',
    "technician device label",
)

# Pricing.
app = replace_once(
    app,
    """        <h2>
          分时计价
        </h2>""",
    """        <h2>
          ${tr("分时计价")}
        </h2>""",
    "pricing title",
)

app = replace_once(
    app,
    """        <small>
          电费 + 服务费 =
          用户实际单价
        </small>""",
    """        <small>
          ${tr("电费 + 服务费 = 用户实际单价")}
        </small>""",
    "pricing formula",
)

app = replace_once(
    app,
    """      <div class="note">
        时段不能重叠。
        若需要跨午夜，
        请拆成
        18:00-24:00
        和
        00:00-08:00
        两条规则。
      </div>""",
    """      <div class="note">
        ${tr("时段不能重叠。若需要跨午夜，请拆成 18:00-24:00 和 00:00-08:00 两条规则。")}
      </div>""",
    "pricing note",
)

# Users RBAC.
app = replace_once(
    app,
    "<h2>四种角色统一管理</h2>",
    '<h2>${tr("四种角色统一管理")}</h2>',
    "users RBAC title",
)

app = replace_once(
    app,
    "            权限在服务端强制校验，页面只展示当前角色可用的功能。\n",
    '            ${tr("权限在服务端强制校验，页面只展示当前角色可用的功能。")}\n',
    "users RBAC description",
)

# Roles page.
app = replace_once(
    app,
    "            后端按权限强制校验；这里显示四种业务角色的权限矩阵。\n",
    '            ${tr("后端按权限强制校验；这里显示四种业务角色的权限矩阵。")}\n',
    "roles description",
)

app = replace_once(
    app,
    "${esc(role.name)}",
    "${esc(tr(role.name))}",
    "role name translation",
)

app = replace_once(
    app,
    "${esc(role.description)}",
    "${esc(tr(role.description))}",
    "role description translation",
)

app = replace_once(
    app,
    """${esc(
                          permissionMap[key]?.name ||
                            key,
                        )}""",
    """${esc(
                          tr(
                            permissionMap[key]?.name ||
                              key,
                          ),
                        )}""",
    "permission name translation",
)

# Activity log dynamic operation text.
if "const translateOperation = (value)" not in app:
    marker = """const roleNames = {
  user: "普通用户",
  operator: "运营人员",
  technician: "运维人员",
  admin: "系统管理员",
};

"""
    helper = marker + """const translateOperation = (value) => {
  const text = String(value ?? "");
  const prefix = "创建数据库备份";

  if (text === prefix) {
    return tr(prefix);
  }

  if (text.startsWith(prefix + " ")) {
    return tr(prefix) + text.slice(prefix.length);
  }

  return tr(text);
};

"""
    app = replace_once(
        app,
        marker,
        helper,
        "activity log translation helper",
    )

app = replace_once(
    app,
    """        最近操作
""",
    """        ${tr("最近操作")}
""",
    "activity log title",
)

app = replace_once(
    app,
    """                ${esc(
                  l.operation_display ||
                    l.operation,
                )}""",
    """                ${esc(
                  translateOperation(
                    l.operation_display ||
                      l.operation,
                  ),
                )}""",
    "activity log operation translation",
)

# Preserve the working Operations Center renderer contract.
renderer_old = """    'ops-center': async () => {
    await window.NCSOpsFeatures.renderOpsCenter(
    S.user?.role || 'user'
    );
    return document.querySelector('#content').innerHTML;
}
"""

renderer_new = """  'ops-center': async () => {
    return await window.NCSOpsFeatures.renderOpsCenter(
      S.user?.role || 'user'
    );
  }
"""

if renderer_old in app:
    app = app.replace(
        renderer_old,
        renderer_new,
        1,
    )

APP.write_text(
    app,
    encoding="utf-8",
)

# ============================================================
# OPS_FEATURES.JS
# ============================================================

# Access the SAME tr() already used by app.js.
if "const tr0 =" not in ops:
    marker = """  const api0 = window.api;

"""
    helper = """  const api0 = window.api;

  const tr0 = (value) => {
    try {
      if (typeof tr === 'function') {
        return tr(value);
      }
    } catch (_) {}

    return value;
  };

  const translateOperation0 = (value) => {
    const text = String(value ?? '');
    const prefix = '创建数据库备份';

    if (text === prefix) {
      return tr0(prefix);
    }

    if (text.startsWith(prefix + ' ')) {
      return tr0(prefix) + text.slice(prefix.length);
    }

    return tr0(text);
  };

"""
    ops = replace_once(
        ops,
        marker,
        helper,
        "ops translation helper",
    )

# Generic helpers.
app_old = "${esc0(title)}"
app_new = "${esc0(tr0(title))}"
if app_old in ops:
    ops = ops.replace(app_old, app_new, 1)

unit_old = "${esc0(unit || '')}"
unit_new = "${esc0(tr0(unit || ''))}"
if unit_old in ops:
    ops = ops.replace(unit_old, unit_new, 1)

table_old = "${headers\n                .map(h => `<th>${h}</th>`)"
table_new = "${headers\n                .map(h => `<th>${esc0(tr0(h))}</th>`)"
if table_old in ops:
    ops = ops.replace(table_old, table_new, 1)

empty_old = "                      暂无数据"
empty_new = "                      ${tr0('暂无数据')}"
if empty_old in ops:
    ops = ops.replace(empty_old, empty_new, 1)

# Strings used as function arguments.
for phrase in [
    "数据库",
    "正常",
    "数据库延迟",
    "进程内存",
    "运行时长",
    "近 28 天订单",
    "充电电量",
    "实收营收",
    "平均利用率",
]:
    ops = ops.replace(
        f"'{phrase}'",
        f"tr0('{phrase}')",
    )

# Ternary status strings.
ops = ops.replace(
    "? '● 正常'",
    "? tr0('● 正常')",
)

ops = ops.replace(
    ": '● 异常'",
    ": tr0('● 异常')",
)

ops = ops.replace(
    "? '连接正常'",
    "? tr0('连接正常')",
)

ops = ops.replace(
    ": '连接失败'",
    ": tr0('连接失败')",
)

# Standalone template text lines.
line_phrases = [
    "系统健康",
    "实时读取 ECS / 容器内应用运行状态；",
    "不依赖额外监控服务。",
    "数据库",
    "系统内存",
    "磁盘",
    "系统负载 1m",
    "最近检查",
    "已完成",
    "可用",
    "总计",
    "活跃用户",
    "电站利用率分析",
    "利用率 Top 5",
    "优先关注高负载站点。",
    "用户行为",
    "回访与消费概况。",
    "人均订单",
    "人均电量",
    "人均消费",
    "回访用户",
    "24 小时使用分布",
    "订单量、电量和充电时长的时段分布。",
    "操作审计",
    "查看增强审计日志需要相应的审计权限。",
    "无访问权限",
    "当前角色无法查看增强审计日志。",
    "支持按操作人、关键词和日期范围查询关键管理行为。",
    "暂无分类",
    "搜索操作内容",
    "操作人 ID",
    "查询",
    "通知中心",
    "全部已读",
    "新",
    "标记已读",
    "暂无通知",
    "数据库备份与恢复",
    "数据备份",
    "当前数据库后端为",
    "本页面仅提供 SQLite 文件备份；",
    "MySQL 请使用数据库原生备份。",
    "下载",
    "备份文件",
    "大小",
    "时间",
    "操作",
    "创建 SQLite 热备并保留最近 10 份文件；",
    "下载后可用于灾备恢复。",
    "立即备份",
    "云端运行",
    "通知",
    "设备利用率",
    "数据备份",
]

for phrase in line_phrases:
    pattern = re.compile(
        rf"^(?P<i>\s*){re.escape(phrase)}\s*$",
        re.M,
    )

    ops = pattern.sub(
        lambda m, p=phrase:
            f'{m.group("i")}${{tr0("{p}")}}',
        ops,
    )

# Dynamic labels.
ops = ops.replace(
    """              ${pct(mem.used_pct)}
              已使用""",
    """              ${pct(mem.used_pct)}
              ${tr0("已使用")}""",
)

ops = ops.replace(
    """              ${pct(disk.used_pct)}
              已使用""",
    """              ${pct(disk.used_pct)}
              ${tr0("已使用")}""",
)

ops = ops.replace(
    "                快 ${x.fast}",
    '                ${tr0("快")} ${x.fast}',
)

ops = ops.replace(
    "                慢 ${x.slow}",
    '                ${tr0("慢")} ${x.slow}',
)

ops = ops.replace(
    """            ${peak.orders || 0}
            笔订单；""",
    """            ${peak.orders || 0}
            ${tr0("笔订单；")}""",
)

# Dynamic notification text: translate only if it matches
# an existing translation key.
ops = ops.replace(
    "${esc0(n.title)}",
    "${esc0(tr0(n.title))}",
)

ops = ops.replace(
    "${esc0(n.body)}",
    "${esc0(tr0(n.body))}",
)

# Audit operation text such as:
# 创建数据库备份 backup.sqlite
ops = ops.replace(
    """${esc0(
                      x.operation
                    )}""",
    """${esc0(
                      translateOperation0(
                        x.operation
                      )
                    )}""",
)

# Audit "用户 #123".
ops = ops.replace(
    "'用户 #' +",
    "tr0('用户 #') +",
)

# Role fallback strings.
for old, new in [
    (
        "text.includes('系统管理员')",
        "text.includes(tr0('系统管理员'))",
    ),
    (
        "nickname:'系统管理员'",
        "nickname:tr0('系统管理员')",
    ),
    (
        "text.includes('运营人员')",
        "text.includes(tr0('运营人员'))",
    ),
    (
        "nickname:'运营人员'",
        "nickname:tr0('运营人员')",
    ),
    (
        "text.includes('维护人员')",
        "text.includes(tr0('维护人员'))",
    ),
    (
        "text.includes('技术员')",
        "text.includes(tr0('技术员'))",
    ),
    (
        "nickname:'维护人员'",
        "nickname:tr0('维护人员')",
    ),
]:
    ops = ops.replace(old, new)

OPS.write_text(
    ops,
    encoding="utf-8",
)

print("")
print("==========================================")
print("i18n fix completed successfully")
print("==========================================")
print("")
print("Modified:")
print("  static/app.js")
print("  static/ops_features.js")
print("  static/i18n/en.json")
print("")
print("Backups:")
print("  static/app.before-i18n-fix.js")
print("  static/ops_features.before-i18n-fix.js")
print("  static/i18n/en.before-i18n-fix.json")
print("")