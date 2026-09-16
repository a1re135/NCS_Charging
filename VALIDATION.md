# NCS Charging 验证记录

本文档记录 NCS Charging 的功能验证、回归测试、前端检查、MySQL 验证以及最终交付前的验收要求。

当前项目数据库架构已经统一为：

```text
MySQL 8.x
```

当前正式开发数据库：

```text
ncs_charging
```

自动测试数据库：

```text
ncs_charging_test
```

两个数据库必须完全分离。

---

# 1. 当前验证环境

推荐当前最终验证环境：

```text
Windows
Python 3.11 / 3.12
MySQL 8.x
Flask
Waitress
Node.js
Chrome / Edge
```

数据库访问架构：

```text
Flask
↓
DBUtils PooledDB
↓
PyMySQL
↓
MySQL 8.x
```

并发业务使用：

```text
MySQL InnoDB Transaction
+
SELECT ... FOR UPDATE
```

---

# 2. 自动测试数据库安全

自动测试只允许使用：

```text
ncs_charging_test
```

正常数据库：

```text
ncs_charging
```

不得用于自动测试清理。

正确：

```env
MYSQL_DATABASE=ncs_charging
MYSQL_TEST_DATABASE=ncs_charging_test
```

错误：

```env
MYSQL_DATABASE=ncs_charging
MYSQL_TEST_DATABASE=ncs_charging
```

测试保护规则：

* `MYSQL_TEST_DATABASE` 不能等于 `MYSQL_DATABASE`
* 测试数据库名称必须以 `_test` 结尾
* 测试开始前只清理测试数据库
* 正常业务数据库不参与自动测试 reset

---

# 3. 基础业务回归验证

项目早期基础功能验证覆盖以下业务。

1. 昵称、头像、主题等个人设置可以持久化。
2. 钱包充值参数校验：

   * 拒绝非有限数
   * 拒绝负数
   * 拒绝零
   * 拒绝超额金额
   * 拒绝超过两位小数
3. 写请求缺少 CSRF Token 时拒绝。
4. 同一用户不能同时创建多个未完成订单。
5. 其他用户不能占用已经被预约的充电桩。
6. 取消预约后正确释放充电桩。
7. 预约超时后可以自动释放。
8. 订单保存单价和功率快照。
9. 订单结算金额正确。
10. 重复结算请求被拒绝。
11. 余额不足时产生欠费。
12. 欠费可以通过充值和补缴处理。
13. 已补缴订单不能重复补缴。
14. 普通用户不能访问管理接口。
15. 用户不能读取或结算其他用户订单。
16. 两个用户并发抢同一个充电桩时只允许一个成功。
17. 两个并发结算请求只产生一次实际扣款。
18. 管理员可以新增电站和电桩。
19. 使用中的充电桩受到删除保护。
20. 有历史订单关联的设备受到数据完整性保护。
21. 故障、维修、离线与恢复流程可以正常更新设备状态。
22. 关键管理操作写入操作日志。
23. 用户注册正常。
24. 电站可以按照坐标和业务指标查询。
25. 负荷预测接口可以生成基础预测输出。
26. 管理端 CSV 导出正常。

这些功能构成后续回归测试的基础。

---

# 4. 设备状态功能验证

新增充电桩状态：

```text
maintenance
offline
```

当前设备主要状态包括：

```text
空闲
预约中
充电中
故障
维修中
离线
```

已验证逻辑包括：

* 管理端可以切换故障状态
* 管理端可以切换维修状态
* 管理端可以设置离线
* 管理端可以恢复设备
* 维修中的设备不能预约
* 离线设备不能预约
* 故障设备不能开始充电
* 维修中的设备不能开始充电
* 离线设备不能开始充电
* 用户端与管理端状态显示保持一致
* 状态筛选正常

---

# 5. 电站查询与排序验证

电站查询支持：

```text
搜索
状态筛选
距离排序
充电次数排序
```

用户端“附近电站”：

```text
按距离排序
充电次数最多
```

管理端电站管理：

```text
充电次数最多
充电次数最少
```

后台接口支持：

```text
sort=usage
sort=usage_asc
```

其中：

```text
usage
```

表示充电次数从高到低。

```text
usage_asc
```

表示充电次数从低到高。

MySQL 环境已经验证 `usage_asc` 和 `usage` 可以正常返回排序结果。

---

# 6. 电桩筛选验证

电桩管理支持：

* 所属电站筛选
* 快充 / 慢充筛选
* 状态筛选
* 搜索
* 编号排序
* 充电次数从高到低
* 充电次数从低到高

电站详情支持：

### 状态

```text
全部状态
空闲
预约中
充电中
```

选择“全部状态”时仍然可以显示故障、维修和离线设备。

### 类型

使用：

```text
快充
慢充
```

两个切换按钮。

逻辑：

```text
都不选
→ 显示全部

只选快充
→ 只显示快充

只选慢充
→ 只显示慢充

两个都选
→ 显示快充和慢充
```

---

# 7. 用户管理验证

用户状态分为：

```text
正常
欠费
冻结
```

其中：

### 正常

```text
没有未补缴欠费
且
账号未被冻结
```

### 欠费

存在：

```text
debt_cents > 0
```

的未补缴订单。

### 冻结

管理员将用户账号设为不可用。

用户管理支持：

* 状态筛选
* 注册起始日期
* 注册结束日期
* 最近 30 天
* 全部
* 最新注册排序
* 最早注册排序
* 冻结用户
* 启用用户
* 修改角色

非法日期参数返回：

```text
400
```

起始日期晚于结束日期同样返回：

```text
400
```

---

# 8. 冻结用户业务规则验证

当前规则：

冻结用户：

### 不允许

```text
创建新的充电订单
```

### 允许

* 取消已有预约
* 结束已经开始的充电
* 钱包充值
* 补缴已有欠费

这样避免出现：

```text
用户被冻结
↓
无法充值
↓
无法补缴
↓
欠费无法处理
```

的问题。

---

# 9. 欠费闭环验证

当前欠费流程：

```text
订单结束
↓
余额不足
↓
生成 debt_cents
↓
订单显示“欠费”
↓
钱包显示待补缴金额
↓
用户查看欠费订单
↓
进行补缴
↓
欠费清零
```

“我的钱包”支持：

```text
待补缴金额
→ 查看欠费订单
```

欠费订单弹窗包含：

* 订单号
* 电站
* 电桩
* 欠费金额
* 创建时间
* 小票详情
* 补缴按钮

补缴成功后即时刷新：

* 钱包余额
* 待补缴金额
* 欠费订单列表

无需整页刷新。

---

# 10. 订单筛选验证

用户订单和管理端订单支持：

* 状态
* 欠费状态
* 起始日期
* 结束日期
* 今天
* 最近 7 天
* 最近 30 天
* 全部

管理员 CSV 导出同步使用日期范围。

非法日期：

```text
400
```

起止日期颠倒：

```text
400
```

欠费订单在状态列显示：

```text
欠费
```

而不是错误显示为：

```text
已结算
```

---

# 11. 营收统计验证

营收模块包括：

* 累计实收
* 已结算订单
* 欠费
* 各电站营收
* 平均每站营收
* 最近 7 天营收

各站营收：

```text
从高到低排序
```

后端使用真实订单数据聚合。

---

# 12. Dashboard 趋势验证

后台首页包含：

```text
订单趋势
收入趋势
```

支持时间粒度：

```text
按天
按周
按月
```

支持范围：

```text
最近 7 天
最近 30 天
本年度
```

支持：

```text
全部电站
指定电站
```

订单口径：

```text
有效完成
全部订单
```

趋势数据来源：

```text
orders
```

业务表实时聚合。

---

# 13. MySQL 数字类型验证

MySQL 对：

```text
SUM
AVG
```

等聚合函数可能返回：

```text
DECIMAL
```

项目已经增加 JSON 序列化处理，使前端收到：

```text
number
```

而不是数字字符串。

该修复用于避免类似：

```text
0 + "8" + "8" + "6"
```

产生字符串拼接的问题。

MySQL 环境验证过的典型字段包括：

```text
fast
slow
fast_free
slow_free
fast_fault
slow_fault
usage
revenue_cents
trend cents
```

这些字段在 JSON 中应该保持数字类型。

---

# 14. 快充 / 慢充统计验证

用户端电站信息可以显示：

```text
快充总数
快充空闲
慢充总数
慢充空闲
```

管理端支持：

```text
快充总量
快充空闲
快充故障
慢充总量
慢充空闲
慢充故障
```

MySQL 聚合结果已用于实际接口检查。

---

# 15. 分时收费验证

分时收费已经整合到：

```text
电站详情
→ 分时收费标准
```

页面结构：

```text
电站信息
↓
分时收费标准
↓
选择你的充电桩
```

管理员可以：

* 添加价格时段
* 编辑价格
* 删除价格

价格组成：

```text
电费
+
服务费
=
最终单价
```

价格表单默认使用当前电站。

---

# 16. 左侧导航验证

已经从侧栏移除：

```text
偏好设置
价格管理
```

其中：

### 偏好设置

保留在：

```text
头像
→ 个人主页
→ 偏好设置
```

### 价格管理

移动到：

```text
电站详情
→ 分时收费标准
```

侧栏滚动位置在页面切换后保持，不会自动跳回顶部。

---

# 17. RBAC 验证

角色：

```text
user
operator
technician
admin
```

数据库表：

```text
roles
permissions
role_permissions
```

权限检查在：

```text
Python Backend API
```

而不是只依赖前端隐藏菜单。

未授权用户调用管理 API 应返回：

```text
403
```

---

# 18. 并发事务验证

关键业务需要保证：

### 同一充电桩并发抢占

两个用户同时尝试占用同一个充电桩：

```text
只允许一个成功
```

### 并发结算

两个请求同时结算同一订单：

```text
只允许一次真实结算
```

### 实现基础

当前 MySQL 使用：

```text
InnoDB
+
Transaction
+
SELECT ... FOR UPDATE
```

保护核心订单流程。

---

# 19. 前端验证

主要前端文件：

```text
static/app.js
```

语法检查：

```powershell
node --check static/app.js
```

正确情况下：

```text
没有输出
```

历史功能迭代中已经使用 DOM 冒烟测试验证过：

* 电站筛选
* 电桩筛选
* 用户状态
* 日期查询
* 排序
* 欠费弹窗
* 快慢充统计
* Dashboard
* 营收页面
* 价格管理
* 导航
* 钱包即时刷新

---

# 20. 浏览器流程验证

已进行过的浏览器业务流程包括：

```text
用户登录
↓
电站详情
↓
预约
↓
开始充电
↓
结束充电
↓
结算
↓
小票
```

同时覆盖：

* 修改个人资料
* 保存偏好
* 模拟充值
* 管理员登录
* 管理菜单
* 电桩管理表单
* 窄屏响应式布局

历史浏览器流程没有发现 JavaScript 运行错误。

---

# 21. 历史功能验证里程碑

## 2026-09-13

完成初始核心业务验证。

当时基础回归：

```text
12 / 12
```

通过。

主要覆盖：

* 用户
* 钱包
* 预约
* 充电
* 结算
* 欠费
* 权限
* 并发
* 管理功能
* 注册
* 预测
* CSV

---

## 2026-09-14

增加：

* maintenance
* offline
* 订单日期筛选
* 电站筛选
* 用户状态筛选

当时业务回归扩展到：

```text
16 / 16
```

通过。

同时完成：

* HTTP 端到端检查
* JavaScript 语法检查
* DOM 冒烟测试

---

## 2026-09-15 — 管理功能扩展

增加：

* 电桩所属电站筛选
* 电桩类型筛选
* 电桩多种排序
* 用户三态
* 注册日期筛选
* 欠费显示

当时相关业务验证通过。

---

## 2026-09-15 — 欠费与营收扩展

增加：

* 欠费订单弹窗
* 在线补缴
* 欠费状态
* 各电站营收
* 平均营收
* 订单趋势
* 快慢充分型统计
* 冻结用户业务规则修复

业务回归扩大到：

```text
38 / 38
```

并完成 HTTP 和 DOM 冒烟验证。

---

## 2026-09-15 — Dashboard / UI 修复

完成：

* 钱包补缴即时刷新
* MySQL DECIMAL JSON 数字化
* 管理端电站排序
* 导航整理
* 分时收费移动
* 侧栏滚动位置保持
* 电站详情筛选调整

真实 MySQL 环境对以下数据进行了只读查询验证：

* 快充统计
* 慢充统计
* Dashboard totals
* 各站营收
* 趋势金额
* 电站 usage 排序

结果正常。

---

## 2026-09-15 — 第五轮 UI 调整

完成：

* 快充 / 慢充胶囊筛选按钮
* Dashboard 数字额外 `Number()` 保护
* 分时收费独立卡片
* `usage_asc` 排序验证

MySQL 环境验证：

```text
sort=usage_asc
```

可以正确按充电次数升序返回结果。

```text
sort=usage
```

可以正常按降序返回。

---

# 22. MySQL-only 迁移验证

数据库架构统一后，需要使用当前代码重新完成最终验证。

以下项目必须通过后，才可以认为 MySQL-only 迁移完成。

---

## 22.1 Python 编译

```powershell
.\.venv\Scripts\python.exe -m py_compile app.py
```

```powershell
Get-ChildItem ncs\*.py | ForEach-Object {
    .\.venv\Scripts\python.exe -m py_compile $_.FullName
}
```

```powershell
Get-ChildItem tests\*.py | ForEach-Object {
    .\.venv\Scripts\python.exe -m py_compile $_.FullName
}
```

成功标准：

```text
没有错误输出
```

---

## 22.2 JavaScript 检查

```powershell
node --check static/app.js
```

成功标准：

```text
没有输出
```

---

## 22.3 完整 MySQL 测试

确认：

```env
MYSQL_DATABASE=ncs_charging
MYSQL_TEST_DATABASE=ncs_charging_test
```

然后：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

最终结果必须：

```text
OK
```

不能有：

```text
FAILED
ERROR
```

---

## 22.4 应用启动

运行：

```powershell
.\.venv\Scripts\python.exe app.py
```

应显示类似：

```text
[Database] MySQL localhost:3306/ncs_charging
```

---

## 22.5 Health Check

打开：

```text
http://127.0.0.1:5000/api/health
```

应包含：

```json
{
  "database": "ok"
}
```

---

## 22.6 用户流程

最终重新检查：

```text
登录
↓
查找电站
↓
预约
↓
开始充电
↓
结束充电
↓
结算
↓
订单
↓
钱包
```

---

## 22.7 管理员流程

检查：

```text
登录
↓
Dashboard
↓
电站
↓
电桩
↓
故障
↓
订单
↓
用户
↓
营收
↓
负荷预测
↓
操作日志
```

---

# 23. 数据库残留检查

最终 MySQL-only 版本不应该存在旧数据库选择逻辑。

执行：

```powershell
git grep -ni "DB_BACKEND"
```

```powershell
git grep -ni "NCS_DATABASE"
```

```powershell
git grep -ni "SQLITE_SCHEMA"
```

```powershell
git grep -ni "BEGIN IMMEDIATE"
```

```powershell
git grep -ni "INSERT OR IGNORE"
```

以上命令：

```text
应该没有输出
```

---

# 24. Merge Conflict 检查

执行：

```powershell
git grep -n -E '^(<<<<<<<|=======|>>>>>>>)'
```

正确情况下：

```text
没有输出
```

---

# 25. Git 状态检查

最终提交前：

```powershell
git status
```

检查：

* 没有 `.env`
* 没有密码
* 没有 API Key
* 没有数据库备份
* 没有虚拟环境
* 没有临时文件
* 没有测试输出垃圾文件

---

# 26. 当前最终验收清单

```text
[ ] Python 全部可以编译
[ ] JavaScript 语法检查通过
[ ] MySQL Test Database 配置正确
[ ] 自动测试全部通过
[ ] 正常数据库未被自动测试修改
[ ] 应用可以正常启动
[ ] /api/health database=ok
[ ] 用户完整充电流程正常
[ ] 钱包正常
[ ] 欠费正常
[ ] 管理端正常
[ ] RBAC 正常
[ ] 电站筛选与排序正常
[ ] 电桩筛选与排序正常
[ ] Dashboard 正常
[ ] 营收统计正常
[ ] 趋势图正常
[ ] AI Agent 正常
[ ] node --check 正常
[ ] 无 Merge Conflict
[ ] 无旧数据库选择逻辑
[ ] 无敏感信息被提交
```

全部完成后，当前版本才可以作为最终 MySQL-only 交付版本。

---

# 27. 未纳入真实商业验证范围

本课程项目没有接入真实：

* 银行支付
* 支付宝
* 微信支付
* 商业充电桩硬件
* 短信验证码
* 商业身份认证
* 商业 Secret Management
* 大规模生产流量

因此当前验证结果只代表：

```text
课程项目
+
演示系统
+
L1 功能与性能验证
```

不代表真实商业充电平台生产认证。


---

# 28. 第六轮改动验证记录（2026-09-16）

本轮为纯前端改动（i18n 补全 / 用户端排序下拉移除 / 充电桩工具栏重排 / 支付状态样式统一），
未改动任何后端代码与数据库结构。

## 改动文件

* `static/app.js` — 25 处替换：支付状态文案走翻译（`tr(paymentNames[status] || status)`）、
  侧边栏角色名翻译、20 处电站名渲染点包 `tr()`、用户端附近电站排序下拉移除（管理端保留）、
  充电桩工具栏重排（编号排序 → 全部状态 → 快慢充勾选）。
* `static/i18n/en.json` — 567 → 587 keys，新增导航三项、运维角色三个页面名、5 个支付状态、
  4 个角色名、5 个演示电站名英文。
* `static/style.css` — `.pay-badge` 与 `.badge` 风格统一（圆角 6px、5px 8px、字号 10px）。
* `static/themes.css` — 深色模式新增 `.pay-badge` 三条配色（默认/红粉/黄橙）。

## 验证结果

| 检查项 | 结果 |
| --- | --- |
| `node --check static/app.js` | 通过 |
| `en.json` JSON 解析 + 587 key | 通过 |
| i18n 行为冒烟（Node + DOM 桩，25 项） | 25/25 通过（导航/站名/支付状态/角色名翻译、中文兜底、zh 模式原文返回） |
| HTTP 冒烟（临时 SQLite 起真实服务，17 项） | 17/17 通过（静态资源 200、en.json 新 key、pay-badge 新样式与深色样式、登录、stations 返回中文站名、admin 三种排序接口） |
| 充电桩工具栏 DOM 顺序 | 确认：`#charger-filter-sort` → `#charger-filter-status` → 快慢充勾选，事件绑定 id 未变 |

## 环境阻塞说明

* 完整 `tests/test_workflows.py` 回归无法运行：测试脚本强制使用 MySQL 测试库
  `ncs_charging_test`，当前账号 `ncs_app@localhost` 对该库无权限
  （`OperationalError 1044 Access denied`），与本次改动无关（本次未动后端）。
  如需恢复完整回归，需先处理 MySQL 测试库授权（建库或授权或调整 `.env`）。
* 项目根无 `node_modules`，DOM 冒烟使用自建轻量桩（`_report_tmp/smoke_r6_i18n.js`）。
