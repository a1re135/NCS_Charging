# RBAC refactor — shared business pages

This patch changes the admin/operations UI from role-specific duplicate pages to shared business pages with permission-controlled actions.

## What changed

- `stations` is now one shared page. Operators/admins can manage stations when `station.manage` is granted; technicians enter the same station detail page as an operations view.
- `stationDetail` now shows device health/status summaries for technicians and exposes authorized charger actions inline, so technicians no longer have to jump from an otherwise-empty “电站管理” page into a duplicate charger page.
- `chargers` is one shared equipment workbench. Operators can view equipment; technicians/admins can perform charger-management actions according to `charger.manage`.
- `orders` is one shared page. Operators/admins can view all orders; regular users see their own orders. Order receipt access is aligned with `order.view_all`.
- User-management actions are shown only when `user.manage` is available.
- Export is shown only when `order.export` is available.
- Technician navigation is relabeled to `电站运维`, `设备运维`, and `运维总览` so the role's purpose is clear without duplicating pages.
- The backend reconciles RBAC mappings on startup and removes stale permissions from older versions.

## Role design

- 普通用户: station.view
- 运营人员: station.view, station.manage, charger.view, order.view_all, order.export, pricing.manage, analytics.view, prediction.view
- 运维人员: station.view, charger.view, charger.manage, fault.manage
- 系统管理员: all permissions

## Files to replace

- `ncs/db.py`
- `ncs/routes.py`
- `static/app.js`
- `tests/test_workflows.py`

## New file

- `RBAC_REFACTOR.md`

Keep the existing database file and let the application reconcile the `roles`, `permissions`, and `role_permissions` tables on startup.
