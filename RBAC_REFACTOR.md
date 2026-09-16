# RBAC Refactor — Shared Business Pages

This refactor changes the admin / operations UI from role-specific duplicate pages to shared business pages controlled by backend permissions.

The current NCS Charging system uses:

```text
MySQL 8.x
```

as its only database backend.

---

# 1. Main Changes

## Shared Station Page

`stations` is now a shared business page.

Operators and administrators can manage stations when they have:

```text
station.manage
```

Technicians use the same station detail page as an operational view.

This avoids maintaining separate station pages for each role.

---

## Shared Station Detail

`stationDetail` is shared across authorized roles.

It can display:

* Station information
* Charger status
* Device health summaries
* Time-of-use pricing
* Charger filters
* Authorized equipment operations

Technicians can perform charger-related actions directly from the same operational interface when their role has the required permissions.

---

## Shared Charger Workbench

`chargers` is one shared equipment-management page.

Operators can view charger information.

Technicians and administrators can perform charger-management actions when granted:

```text
charger.manage
```

Possible equipment actions include:

* Fault
* Maintenance
* Offline
* Restore
* Restart
* Delete

Actual actions are still checked by the backend.

---

## Shared Orders Page

`orders` is one shared page.

Regular users can access their own orders.

Authorized staff can access broader order information when granted:

```text
order.view_all
```

Order receipt access follows the same authorization rules.

---

## User Management

User-management actions are only available when the current role has:

```text
user.manage
```

This includes actions such as:

* Freeze user
* Enable user
* Change role
* View management-level user information

---

## Order Export

CSV export is available only when the role has:

```text
order.export
```

Hiding the button in the UI is not the security mechanism.

The backend API independently checks the permission.

---

# 2. Role Design

Current main roles:

```text
user
operator
technician
admin
```

---

## Regular User

Base permissions include:

```text
station.view
```

Regular users interact primarily with:

* Stations
* Reservations
* Charging
* Orders
* Wallet
* Debt repayment
* Personal profile
* AI Agent

They do not have management permissions.

---

## Operator

Operator permissions include business-operation capabilities such as:

```text
station.view
station.manage
charger.view
order.view_all
order.export
pricing.manage
analytics.view
prediction.view
```

Operators mainly work with:

* Stations
* Orders
* Pricing
* Revenue
* Analytics
* Prediction

---

## Technician

Technician permissions include:

```text
station.view
charger.view
charger.manage
fault.manage
```

Technicians mainly work with:

* Station operational information
* Charger status
* Device maintenance
* Fault handling
* Equipment recovery

---

## Administrator

Administrator has access to all system permissions.

Administrative functions include:

* User management
* Role management
* Permission management
* Station management
* Charger management
* Fault management
* Order management
* Revenue
* Analytics
* Logs

---

# 3. RBAC Database Tables

RBAC is stored in MySQL.

Main tables:

```text
roles
permissions
role_permissions
```

The application also stores each user's assigned role in the user data.

---

## `roles`

Stores role definitions such as:

```text
user
operator
technician
admin
```

---

## `permissions`

Stores individual permissions such as:

```text
station.view
station.manage
charger.view
charger.manage
fault.manage
order.view_all
order.export
pricing.manage
analytics.view
prediction.view
user.manage
```

---

## `role_permissions`

Maps roles to their permissions.

Example:

```text
technician
↓
charger.manage
```

This allows permission behavior to be managed independently from page layout.

---

# 4. Startup Reconciliation

During application startup, the backend ensures the RBAC schema exists and reconciles the role definitions.

The application can:

* Create missing roles
* Create missing permissions
* Rebuild role-permission mappings
* Remove stale mappings
* Ensure demo accounts use the expected roles

This means the RBAC configuration in application code remains aligned with the MySQL database.

---

# 5. MySQL Initialization

The application automatically creates required RBAC tables if they do not exist.

Manual schema import is normally unnecessary.

Required database configuration:

```env
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=ncs_charging
MYSQL_USER=ncs_app
MYSQL_PASSWORD=YOUR_PASSWORD
```

The MySQL user must have sufficient permission to create or update the required application tables.

---

# 6. Existing Business Data

Applying the RBAC refactor should not require deleting the normal MySQL database.

Normal database:

```text
ncs_charging
```

Existing business information such as:

* Users
* Orders
* Stations
* Chargers
* Wallet data
* Pricing data
* Fault records

should remain available during a normal application upgrade.

Before major database changes, creating a backup is recommended.

---

# 7. Demo RBAC Accounts

## Operator

```text
Account: operator
Password: Operator123456
Role: operator
```

## Technician

```text
Account: tech
Password: Tech123456
Role: technician
```

## Administrator

```text
Account: admin
Password: Admin123456
Role: admin
```

## Regular User

```text
Account: 13800138000
Password: User123456
Role: user
```

---

# 8. Backend Authorization

The frontend navigation is only a presentation layer.

Actual security checks happen in:

```text
Python Backend API
```

Therefore:

```text
Hidden Menu ≠ Permission Protection
```

Even if a user manually sends an API request, the backend checks their permissions.

Unauthorized requests should return:

```text
403
```

---

# 9. Shared Page Design

The purpose of this refactor is:

```text
One Business Function
↓
One Shared Page
↓
Different Roles
↓
Different Allowed Actions
```

instead of:

```text
Operator Station Page
Technician Station Page
Admin Station Page
```

with duplicated implementations.

Benefits:

* Less duplicated frontend code
* Easier maintenance
* Consistent UI
* Centralized permission behavior
* Lower risk of role-specific page divergence

---

# 10. Files Involved

The RBAC refactor primarily affects:

```text
ncs/db.py
ncs/routes.py
static/app.js
tests/test_workflows.py
```

Related supporting files may include:

```text
ncs/services.py
README.md
VALIDATION.md
```

---

# 11. Database Backup

Before large RBAC or database changes, use the MySQL backup workflow.

Project backup script:

```text
backup_mysql.ps1
```

Do not commit database backup files to Git.

---

# 12. Test Database

Automated tests use:

```text
ncs_charging_test
```

Normal development uses:

```text
ncs_charging
```

They must remain separate.

Example:

```env
MYSQL_DATABASE=ncs_charging
MYSQL_TEST_DATABASE=ncs_charging_test
```

The automated test database is allowed to be reset.

The normal development database must not be used for destructive test initialization.

---

# 13. Regression Test

After RBAC changes, run:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Important scenarios include:

* Regular users cannot call management APIs
* Operators can access permitted business functions
* Technicians can access maintenance functions
* Technicians cannot access unrelated management functions
* Admin can access all management functions
* Order export requires `order.export`
* User management requires `user.manage`
* Charger operations require `charger.manage`
* Fault operations require `fault.manage`

---

# 14. Frontend Check

Run:

```powershell
node --check static/app.js
```

Success produces no output.

Also check for unresolved merge conflicts:

```powershell
git grep -n -E '^(<<<<<<<|=======|>>>>>>>)'
```

Success should produce no output.

---

# 15. Final RBAC Architecture

```text
User Login
↓
User Role
↓
RBAC Permission Mapping
↓
Flask Backend Permission Check
↓
Authorized Business API
↓
MySQL
```

The frontend reads available permissions to decide which actions to display, while the backend remains the final authority.

This ensures the RBAC design is based on permissions rather than duplicated role-specific pages.
