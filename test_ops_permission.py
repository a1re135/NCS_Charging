from ncs import create_app

app = create_app({
    "TESTING": True,
    "DB_BACKEND": "sqlite",
    "DATABASE": "data/ncs.db",
})

with app.test_client() as client:
    with client.session_transaction() as session:
        session["uid"] = 0

    db = None

    with app.app_context():
        from ncs.db import get_db

        db = get_db()

        user = db.execute(
            "SELECT * FROM users WHERE phone=?",
            ("tech",)
        ).fetchone()

        print("USER:")
        print(dict(user) if user else None)

        permission = db.execute(
            """
            SELECT 1
            FROM role_permissions
            WHERE role_key=? AND permission_key=?
            """,
            ("technician", "system.monitor")
        ).fetchone()

        print("\nPERMISSION:")
        print(bool(permission))

        if user:
            session_uid = user["id"]
        else:
            session_uid = None

    with client.session_transaction() as session:
        session["uid"] = session_uid

    response = client.get("/api/admin/ops/health")

    print("\nAPI STATUS:")
    print(response.status_code)

    print("\nAPI RESPONSE:")
    print(response.get_json())