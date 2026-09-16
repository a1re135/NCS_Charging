# Features 11–13 Patch

This patch is intended to be applied on top of the NCS Charging version that already contains the L1 capacity, performance, and cloud deployment work.

The current NCS Charging database architecture uses:

```text
MySQL 8.x
```

as the only supported database.

---

## Files Updated

The Features 11–13 update primarily changes:

```text
ncs/db.py
ncs/services.py
ncs/routes.py
static/app.js
static/style.css
tests/test_workflows.py
README.md
```

---

## Database

Do not delete or recreate the existing MySQL database when applying this patch unless a full reset is intentionally required.

Normal application database:

```text
ncs_charging
```

Automated test database:

```text
ncs_charging_test
```

The application automatically creates or reconciles required tables and initialization data during startup.

This includes RBAC-related tables such as:

```text
roles
permissions
role_permissions
```

and ensures that the operator and technician demo accounts exist.

Existing business data should remain unchanged during a normal application startup.

---

## MySQL Configuration

The application reads its database configuration from environment variables:

```env
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=ncs_charging
MYSQL_USER=ncs_app
MYSQL_PASSWORD=YOUR_PASSWORD
```

Automated tests use:

```env
MYSQL_TEST_DATABASE=ncs_charging_test
```

The normal and test databases must be different.

---

## New RBAC Demo Accounts

### Operator

```text
Account: operator
Password: Operator123456
```

### Technician

```text
Account: tech
Password: Tech123456
```

---

## Existing Demo Accounts

### Regular User

```text
Account: 13800138000
Password: User123456
```

### System Administrator

```text
Account: admin
Password: Admin123456
```

---

## RBAC Initialization

During startup, the backend reconciles:

```text
roles
permissions
role_permissions
```

with the role definitions contained in the application.

This allows newer permission mappings to be added while keeping existing business records.

The application also ensures the demo operator and technician accounts are assigned their correct roles.

---

## Applying the Patch

Before applying changes:

```text
1. Stop the application
2. Back up the MySQL database if important data exists
3. Update the source files
4. Keep the existing .env configuration
5. Restart the application
6. Run regression tests
```

Run:

```powershell
.\.venv\Scripts\python.exe app.py
```

Then verify:

```text
http://127.0.0.1:5000/api/health
```

The response should report:

```json
"database": "ok"
```

---

## Regression Test

Before merging the patch:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The automated test suite uses the dedicated:

```text
ncs_charging_test
```

database and must never use the normal:

```text
ncs_charging
```

database for destructive test resets.
