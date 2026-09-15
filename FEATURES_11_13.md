# Features 11–13 patch

This patch is intended to be applied on top of the NCS Charging version that already contains the L1 capacity/performance/cloud-deployment work.

## Replace existing files
- `ncs/db.py`
- `ncs/services.py`
- `ncs/routes.py`
- `static/app.js`
- `static/style.css`
- `tests/test_workflows.py`
- `README.md`

## No database replacement
Keep the existing `data/ncs.db` and `data/secret.key`. On startup the application creates/migrates the RBAC tables and adds the operator/technician demo accounts only when they do not already exist.

## New RBAC demo accounts
- 运营人员: `operator / Operator123456`
- 运维人员: `tech / Tech123456`

Existing accounts remain unchanged:
- 普通用户: `13800138000 / User123456`
- 系统管理员: `admin / Admin123456`
