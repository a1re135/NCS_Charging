from ncs import create_app

app = create_app({
    "TESTING": True,
    "DB_BACKEND": "sqlite",
    "DATABASE": "data/loyalty_test.db",
})

client = app.test_client()

# 1. Establish the browser-like session first.
response = client.get("/api/session")

print("SESSION:", response.status_code, response.get_json())
assert response.status_code == 200

session_data = response.get_json()
csrf = session_data["csrf"]

# 2. Login using the CSRF token established by /api/session.
response = client.post(
    "/api/login",
    json={
        "phone": "13800138000",
        "password": "User123456",
    },
    headers={
        "X-CSRF-Token": csrf,
    },
)

print("LOGIN:", response.status_code, response.get_json())
assert response.status_code == 200

login_data = response.get_json()

# Use the token returned by login because login regenerates it.
csrf = login_data["csrf"]

# 3. Member summary.
response = client.get(
    "/api/member/summary",
)

print("SUMMARY:", response.status_code, response.get_json())
assert response.status_code == 200

summary = response.get_json()["summary"]

assert "tier" in summary
assert "points_balance" in summary
assert "lifetime_points" in summary

# 4. Member coupons.
response = client.get(
    "/api/member/coupons",
)

print("COUPONS:", response.status_code, response.get_json())
assert response.status_code == 200

coupon_data = response.get_json()

assert "owned" in coupon_data
assert "available" in coupon_data

# 5. Member points.
response = client.get(
    "/api/member/points",
)

print("POINTS:", response.status_code, response.get_json())
assert response.status_code == 200

points_data = response.get_json()

assert "items" in points_data

# 6. Verify that a mutating request without CSRF is rejected.
response = client.post(
    "/api/member/coupons/1/claim",
    json={},
)

print("NO CSRF CLAIM:", response.status_code)
assert response.status_code == 403

print("\nMEMBER HTTP API TEST OK")