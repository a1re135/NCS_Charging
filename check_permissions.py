import sqlite3

conn = sqlite3.connect("data/ncs.db")

print("USER:")
print(
    conn.execute(
        "SELECT phone, nickname, role, active FROM users WHERE phone = ?",
        ("tech",)
    ).fetchall()
)

print("\nPERMISSION:")
print(
    conn.execute(
        "SELECT * FROM role_permissions WHERE role_key = ? AND permission_key = ?",
        ("technician", "system.monitor")
    ).fetchall()
)

conn.close()