# NCS Charging — 智能充电管理平台

NCS Charging 是一个基于 **Flask + JavaScript + MySQL** 的智能充电管理平台课程项目。

项目包含：

* 用户充电完整闭环
* 电站与电桩管理
* 钱包、结算与欠费
* 分时收费
* 实时设备监控
* 运营与营收统计
* 负荷预测
* RBAC 角色权限
* AI Agent
* GLM / BigModel + Local Agent fallback
* MySQL 连接池
* L1 性能测试
* 中英文与深色模式

> 推荐所有组员第一次配置时按照：
>
> **安装环境 → 安装依赖 → 配置 MySQL → 配置 `.env` → 启动 → 测试**
>
> 当前主要开发分支：`dev`

---

# 目录

1. [环境要求](#1-环境要求)
2. [获取代码](#2-获取代码)
3. [安装 Python 依赖](#3-安装-python-依赖)
4. [配置 MySQL 数据库](#4-配置-mysql-数据库)
5. [配置 `.env`](#5-配置-env)
6. [配置 AI Agent](#6-配置-ai-agent)
7. [启动项目](#7-启动项目)
8. [演示账号](#8-演示账号)
9. [首次启动会自动做什么](#9-首次启动会自动做什么)
10. [功能说明](#10-功能说明)
11. [运行测试](#11-运行测试)
12. [L1 性能测试](#12-l1-性能测试)
13. [手机访问](#13-手机访问)
14. [Docker](#14-docker)
15. [常见问题](#15-常见问题)
16. [项目结构](#16-项目结构)
17. [团队开发建议](#17-团队开发建议)
18. [第一次配置推荐流程](#18-第一次配置推荐流程)
19. [安全说明](#19-安全说明)

---

# 1. 环境要求

## 必装

建议安装：

* **Git**
* **Python 3.11 或以上**

  * 推荐 Python 3.12
* **VS Code**
* **MySQL 8.x**
* Chrome / Edge 浏览器

MySQL Workbench 可选，用于图形化管理数据库。

## VS Code 推荐扩展

建议安装：

* Python
* Python Debugger

如果需要检查 JavaScript：

* Node.js

如果需要容器运行：

* Docker Desktop（可选）

> Docker 不是本项目本地开发的必需条件。
>
> Windows + Python + MySQL 即可运行完整项目。

---

## 检查环境

打开 PowerShell：

```powershell
git --version
python --version
```

如果安装了 Python Launcher：

```powershell
py --version
```

检查 MySQL：

```powershell
mysql --version
```

例如：

```text
Python 3.12.x
MySQL 8.x
```

即可。

---

# 2. 获取代码

Clone 项目：

```powershell
git clone https://github.com/a1re135/NCS_Charging.git
```

进入项目：

```powershell
cd NCS_Charging
```

切换到 `dev`：

```powershell
git checkout dev
git pull origin dev
```

确认：

```powershell
git branch --show-current
```

应该显示：

```text
dev
```

---

# 3. 安装 Python 依赖

项目根目录应该可以看到：

```text
app.py
requirements.txt
ncs/
static/
templates/
tests/
```

---

## Windows 创建虚拟环境

```powershell
py -3 -m venv .venv
```

如果没有 `py`：

```powershell
python -m venv .venv
```

---

## 安装依赖

不需要执行 `Activate.ps1`。

直接使用虚拟环境中的 Python：

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
```

然后：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

当前主要 Python 依赖包括：

```text
Flask
waitress
requests
qrcode
PyMySQL
python-dotenv
Pillow
openai
DBUtils
```

其中：

* `Flask`：Web 后端
* `Waitress`：Web Server
* `PyMySQL`：连接 MySQL
* `DBUtils`：MySQL Connection Pool
* `python-dotenv`：读取 `.env`
* `openai`：连接 OpenAI-compatible 的 BigModel / GLM API
* `qrcode`：生成充电桩二维码
* `Pillow`：头像图片处理

> 项目安装 `openai` SDK 并不代表必须使用 OpenAI API。
>
> 当前 AI Agent 使用该 SDK 连接智谱 BigModel 的 OpenAI-compatible API。

---

## VS Code 选择 Python

在 VS Code：

```text
Ctrl + Shift + P
```

选择：

```text
Python: Select Interpreter
```

然后选择：

```text
.venv\Scripts\python.exe
```

---

# 4. 配置 MySQL 数据库

NCS Charging 使用 **MySQL 8.x** 作为唯一数据库。

项目运行、业务数据、用户数据、订单、电站、电桩、钱包、RBAC、用户偏好和头像数据均存储在 MySQL 中。

自动测试使用独立的 MySQL 测试数据库，避免影响正常开发数据库。

---

## 4.1 安装 MySQL

推荐安装：

```text
MySQL Server 8.x
```

Windows 用户也可以安装：

```text
MySQL Workbench
```

用于图形化管理数据库。

安装 MySQL Server 时，请记住设置的：

```text
root password
```

---

## 4.2 确认 MySQL Server 正常运行

打开 PowerShell：

```powershell
mysql -u root -p
```

输入 MySQL root 密码。

如果进入：

```text
mysql>
```

说明 MySQL Server 已正常运行。

也可以使用 MySQL Workbench：

```text
Host: localhost
Port: 3306
User: root
```

---

## 4.3 创建正常运行数据库

进入 MySQL：

```powershell
mysql -u root -p
```

执行：

```sql
CREATE DATABASE ncs_charging
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

检查：

```sql
SHOW DATABASES;
```

应该可以看到：

```text
ncs_charging
```

---

## 4.4 创建自动测试数据库

自动测试必须使用独立数据库：

```text
ncs_charging_test
```

执行：

```sql
CREATE DATABASE ncs_charging_test
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

检查：

```sql
SHOW DATABASES;
```

应该同时看到：

```text
ncs_charging
ncs_charging_test
```

其中：

```text
ncs_charging
```

用于：

* 正常开发
* 本地运行
* 演示
* 性能测试
* 保存正常业务数据

而：

```text
ncs_charging_test
```

仅用于：

* Python 自动测试
* 回归测试
* 并发测试
* 数据库初始化测试

> **不要把 `MYSQL_TEST_DATABASE` 设置成 `ncs_charging`。**
>
> 测试会清理测试数据库中的表，因此测试数据库必须与正常数据库完全分开。

---

## 4.5 创建项目专用 MySQL 用户

不建议应用直接使用 `root`。

创建：

```sql
CREATE USER 'ncs_app'@'localhost'
IDENTIFIED BY 'CHANGE_THIS_PASSWORD';
```

将：

```text
CHANGE_THIS_PASSWORD
```

替换成自己的密码。

---

## 4.6 给项目用户授权

授权正常数据库：

```sql
GRANT ALL PRIVILEGES
ON ncs_charging.*
TO 'ncs_app'@'localhost';
```

授权测试数据库：

```sql
GRANT ALL PRIVILEGES
ON ncs_charging_test.*
TO 'ncs_app'@'localhost';
```

最后：

```sql
FLUSH PRIVILEGES;
```

检查：

```sql
SHOW GRANTS FOR 'ncs_app'@'localhost';
```

---

## 4.7 数据库配置

项目通过 `.env` 读取 MySQL 配置。

```env
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=ncs_charging
MYSQL_TEST_DATABASE=ncs_charging_test
MYSQL_USER=ncs_app
MYSQL_PASSWORD=CHANGE_THIS_PASSWORD
```

其中：

### `MYSQL_HOST`

本机安装 MySQL：

```env
MYSQL_HOST=localhost
```

### `MYSQL_PORT`

默认：

```env
MYSQL_PORT=3306
```

### `MYSQL_DATABASE`

正常运行：

```env
MYSQL_DATABASE=ncs_charging
```

### `MYSQL_TEST_DATABASE`

自动测试：

```env
MYSQL_TEST_DATABASE=ncs_charging_test
```

### `MYSQL_USER`

```env
MYSQL_USER=ncs_app
```

### `MYSQL_PASSWORD`

填写创建 `ncs_app` 时设置的密码。

---

## 4.8 正常数据库与测试数据库必须分开

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

测试代码包含安全保护：

* `MYSQL_TEST_DATABASE` 不能等于 `MYSQL_DATABASE`
* 测试数据库名称必须以 `_test` 结尾

例如：

```text
ncs_charging_test
```

这样可以避免自动测试误操作正常业务数据库。

---

## 4.9 不需要手动导入 Schema

NCS Charging 会在启动时自动创建需要的数据库结构。

只需要确保：

1. MySQL Server 已运行
2. `ncs_charging` 已创建
3. `ncs_charging_test` 已创建
4. `ncs_app` 已创建
5. `ncs_app` 已获得两个数据库的权限
6. `.env` 配置正确

程序会自动初始化：

* 用户表
* 电站表
* 电桩表
* 订单表
* 钱包流水
* 分时收费规则
* 故障记录
* 操作日志
* RBAC 角色
* RBAC 权限
* 角色权限关系
* 用户偏好
* 用户头像
* 数据迁移记录
* 其他业务表

已有数据库不会因为普通启动而直接清空。

---

## 4.10 检查 MySQL 连接

运行：

```powershell
.\.venv\Scripts\python.exe app.py
```

启动时应该看到类似：

```text
[Database] MySQL localhost:3306/ncs_charging
```

打开：

```text
http://127.0.0.1:5000/api/health
```

正常情况下类似：

```json
{
  "ok": true,
  "service": "ncs-charging",
  "capacity_level": "L1",
  "database": "ok"
}
```

其中：

```json
"database": "ok"
```

表示应用可以正常访问 MySQL。

---

# 5. 配置 `.env`

项目提供：

```text
.env.example
```

复制为：

```text
.env
```

PowerShell：

```powershell
Copy-Item .env.example .env
```

CMD：

```cmd
copy .env.example .env
```

`.env` 已被 `.gitignore` 排除，不应该提交到 GitHub。

---

## 推荐完整 `.env`

```env
# =========================================================
# Application
# =========================================================

NCS_SECRET_KEY=replace-with-a-long-random-secret
NCS_CAPACITY_LEVEL=L1


# =========================================================
# Deployment
# =========================================================

NCS_COOKIE_SECURE=0
NCS_TRUST_PROXY=0


# =========================================================
# MySQL
# =========================================================

MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=ncs_charging
MYSQL_TEST_DATABASE=ncs_charging_test
MYSQL_USER=ncs_app
MYSQL_PASSWORD=CHANGE_THIS_PASSWORD


# =========================================================
# AI Agent - Zhipu BigModel / GLM
# =========================================================

NCS_LLM_ENABLED=0
NCS_LLM_PROVIDER=bigmodel

BIGMODEL_API_KEY=
BIGMODEL_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
BIGMODEL_MODEL=glm-4-flashx-250414


# =========================================================
# Web Server
# =========================================================

NCS_THREADS=48
```

---

## 5.1 `NCS_SECRET_KEY`

每个人建议生成自己的随机 Secret Key。

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

将输出复制到：

```env
NCS_SECRET_KEY=YOUR_RANDOM_SECRET
```

不要把真实 Secret Key 提交到 GitHub。

---

## 5.2 `NCS_THREADS`

项目使用 Waitress。

推荐：

```env
NCS_THREADS=48
```

普通本地开发也可以使用：

```env
NCS_THREADS=16
```

L1 性能测试建议使用项目规定的线程配置。

---

## 5.3 修改端口

默认端口：

```text
5000
```

可以临时使用：

```powershell
$env:NCS_PORT="5001"
```

然后：

```powershell
.\.venv\Scripts\python.exe app.py
```

访问：

```text
http://127.0.0.1:5001
```

---

# 6. 配置 AI Agent

NCS AI Agent 有两种模式：

```text
Local Agent
```

和：

```text
GLM / BigModel Agent
```

---

## 6.1 Local Agent

Local Agent 不需要 API Key。

设置：

```env
NCS_LLM_ENABLED=0
```

工作方式：

```text
用户问题
↓
Local Agent 判断 intent
↓
调用 NCS Python 业务函数
↓
查询 MySQL
↓
返回答案
```

优点：

* 不需要 BigModel API Key
* 不消耗 API 额度
* 网络要求低
* 自动测试可以稳定运行

---

## 6.2 GLM / BigModel Agent

需要：

```text
BIGMODEL_API_KEY
```

设置：

```env
NCS_LLM_ENABLED=1
NCS_LLM_PROVIDER=bigmodel

BIGMODEL_API_KEY=YOUR_REAL_API_KEY
BIGMODEL_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
BIGMODEL_MODEL=glm-4-flashx-250414
```

修改后重新启动：

```powershell
.\.venv\Scripts\python.exe app.py
```

---

## 6.3 AI Agent 工作方式

GLM 不直接连接数据库。

架构：

```text
User
↓
AI Agent UI
↓
/api/agent/chat
↓
GLM
↓
选择允许调用的 NCS Tool
↓
Python 本地业务函数
↓
MySQL
↓
真实业务数据
↓
返回答案
```

也就是说：

```text
LLM = 理解问题
Python Tool = 查询真实业务数据
```

GLM 不能：

* 直接连接 MySQL
* 随意执行 SQL
* 绕过 RBAC
* 调用当前角色没有权限的工具

---

## 6.4 Local fallback

如果出现：

* `NCS_LLM_ENABLED=0`
* 没有填写 API Key
* 网络失败
* API timeout
* API Key 无效
* BigModel 服务异常

系统可以使用：

```text
Local Agent
```

继续完成支持的查询。

---

## 6.5 用户 Agent 示例

普通用户可以问：

```text
附近哪里有空闲快充？
```

```text
我现在有充电订单吗？
```

```text
我的余额是多少？
```

```text
我有欠费吗？
```

```text
我最近一次充电花了多少钱？
```

```text
为什么我的充电桩无法启动？
```

---

## 6.6 运营 / 管理员 Agent

可以查询：

```text
今天哪个充电站订单最多？
```

```text
最近7天收入怎么样？
```

```text
现在有多少故障设备？
```

```text
现在设备情况怎么样？
```

```text
哪些设备故障次数最多？
```

```text
生成最近7天运营报告
```

---

## 6.7 运维人员 Agent

主要可以查询：

```text
现在有多少故障设备？
```

```text
现在设备情况怎么样？
```

```text
哪些设备故障次数最多？
```

---

## 6.8 GLM 没生效怎么办

检查：

```env
NCS_LLM_ENABLED=1
BIGMODEL_API_KEY=YOUR_REAL_API_KEY
```

并确认：

* `.env` 与 `app.py` 同级
* 修改 `.env` 后已经重启 Python
* 网络可以访问 BigModel
* API Key 有效
* requirements 已安装

重新安装：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

---

## 6.9 自动测试

自动测试建议关闭远程 LLM：

```env
NCS_LLM_ENABLED=0
```

这样不会消耗 BigModel API 额度。

---

# 7. 启动项目

确保 MySQL Server 正在运行。

Windows：

```powershell
.\.venv\Scripts\python.exe app.py
```

正常情况下会看到类似：

```text
[Database] MySQL localhost:3306/ncs_charging

NCS Charging: http://127.0.0.1:5000
Waitress threads: 48
Press Ctrl+C to stop.
```

浏览器打开：

```text
http://127.0.0.1:5000
```

---

## 健康检查

打开：

```text
http://127.0.0.1:5000/api/health
```

如果：

```json
"database": "ok"
```

说明后端和 MySQL 正常。

---

## 停止系统

```text
Ctrl + C
```

---

## 下次运行

一般只需要：

```powershell
cd NCS_Charging
.\.venv\Scripts\python.exe app.py
```

不需要每次重新安装 requirements。

---

# 8. 演示账号

系统初始化后提供演示账号：

| 角色     | 账号            | 密码               |
| ------ | ------------- | ---------------- |
| 普通用户   | `13800138000` | `User123456`     |
| 普通用户 2 | `13900139000` | `User123456`     |
| 运营人员   | `operator`    | `Operator123456` |
| 运维人员   | `tech`        | `Tech123456`     |
| 系统管理员  | `admin`       | `Admin123456`    |

登录页面也提供演示账号快捷填入。

---

## 普通用户

可以：

* 找充电站
* 查看电站详情
* 预约
* 开始充电
* 结束充电
* 查看订单
* 钱包充值
* 补缴欠费
* 使用 AI Agent
* 修改个人资料
* 设置语言和主题

---

## 运营人员

主要负责：

* 电站
* 订单
* 分时价格
* 营收
* 运营统计
* 负荷预测

---

## 运维人员

主要负责：

* 电桩
* 设备状态
* 故障
* 维修
* 恢复
* 实时设备数据

---

## 系统管理员

拥有完整管理权限，包括：

* 用户管理
* 角色管理
* 权限管理
* 电站管理
* 电桩管理
* 故障管理
* 营收
* 订单
* 日志

---

# 9. 首次启动会自动做什么

只要 MySQL 配置正确，程序启动时会自动初始化需要的数据结构和演示数据。

包括：

* 创建业务表
* 创建 RBAC tables
* 创建角色
* 创建权限
* 创建 demo users
* 创建电站
* 创建电桩
* 创建价格规则
* 创建演示业务数据
* 创建故障数据
* 创建操作日志相关表
* 创建用户 preferences
* 创建 avatar table
* 扩展演示电站网络

因此正常情况下不需要手动导入 schema。

---

# 10. 功能说明

# 用户端

## 总览

包含：

* 欢迎页面
* 累计充电量
* 已完成订单
* 累计消费
* 最近趋势
* 钱包余额
* 电桩状态
* 最近订单

---

## 附近电站

支持：

* 搜索电站
* 搜索地址
* 浏览器定位
* 区域预置位置
* 有空闲桩筛选
* 快充 / 慢充类型筛选
* 距离最近排序
* 价格最低 / 价格最高排序
* 管理端充电次数排序

每个电站可显示：

```text
快充数量
快充空闲数量
慢充数量
慢充空闲数量
```

---

## 电站详情

包含：

1. 电站信息
2. 分时收费标准
3. 充电桩列表

充电桩状态支持：

```text
全部状态
空闲
预约中
充电中
```

类型支持：

```text
快充
慢充
```

---

## 预约

用户可以预约空闲设备。

预约有效时间：

```text
15 分钟
```

预约期间：

* 可以开始充电
* 可以取消预约
* 超时自动释放

---

## 充电

支持：

* 直接开始
* 预约后开始
* 实时电量
* 实时费用
* 模拟充电时间

系统默认使用时间加速模拟。

---

## 结算

结束充电后系统会：

* 计算最终电量
* 锁定计费快照
* 计算订单金额
* 自动扣除余额
* 更新充电桩状态
* 写入钱包流水
* 保存订单结算结果

---

## 欠费

余额不足时，订单可以产生：

```text
debt_cents
```

用户可以进入：

```text
我的钱包
→ 待补缴金额
→ 查看欠费订单
```

进行：

* 查看欠费订单
* 查看订单详情
* 在线补缴

补缴成功后：

* 钱包余额刷新
* 待补缴金额刷新
* 欠费订单状态刷新

---

## 我的订单

支持：

* 搜索
* 状态过滤
* 欠费状态
* 起始日期
* 结束日期
* 今天
* 最近 7 天
* 最近 30 天
* 订单详情
* 打印小票

---

## 钱包

支持：

* 模拟充值
* 钱包流水
* 当前余额
* 欠费总额
* 欠费订单
* 在线补缴

---

## 路线导航

可选择：

```text
驾车
步行
公交
```

然后打开地图路线。

---

## AI Agent

普通用户可以让 Agent 查询：

* 附近空闲充电站
* 当前充电订单
* 最近订单
* 钱包余额
* 欠费
* 无法开始充电的原因

---

# 管理端

## 运营总览

管理员 / 运营人员可以查看：

* 累计电量
* 已完成订单
* 电站数量
* 营收
* 用户统计
* 设备统计
* 快充 / 慢充统计
* 订单趋势
* 收入趋势

---

## 订单与收入趋势

支持粒度：

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

订单口径支持：

```text
有效完成
全部订单
```

---

## 平台资源统计

可以查看：

* 快充总数
* 快充空闲
* 快充故障
* 慢充总数
* 慢充空闲
* 慢充故障

---

## 实时监控

实时监控页面定时刷新。

包含：

* 设备总数
* 空闲设备
* 使用中设备
* 异常设备
* 电桩状态分布
* 电站利用率
* 系统设备健康率
* 最近设备趋势
* 各电站异常设备

---

## 电站管理

支持：

* 添加
* 编辑
* 删除
* 修改运营状态

排序支持：

```text
充电次数最多
充电次数最少
```

---

## 分时收费

价格管理整合在：

```text
电站详情
→ 分时收费标准
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

---

## 电桩管理

支持：

* 新增
* 编辑
* QR Code
* 快充 / 慢充
* 功率
* 所属电站筛选
* 状态筛选
* 充电次数排序

状态操作：

* 故障
* 维修
* 离线
* 恢复
* 重启
* 删除

---

## 故障管理

支持：

* 登记故障
* 待处理
* 处理中
* 已解决
* 记录处理结果

故障状态会影响对应充电桩状态。

---

## 用户管理

用户状态包括：

```text
正常
欠费
冻结
```

支持：

* 状态筛选
* 注册日期筛选
* 最新注册排序
* 最早注册排序
* 冻结用户
* 启用用户
* 修改角色

---

## 冻结用户规则

冻结用户不能：

```text
创建新的充电订单
```

但仍然可以：

* 取消已有预约
* 结束已有充电
* 钱包充值
* 补缴欠费

这样可以避免被冻结用户无法处理已有订单和欠费。

---

## RBAC

系统角色：

```text
user
operator
technician
admin
```

数据库包含：

```text
roles
permissions
role_permissions
```

前端菜单只负责展示。

真正权限控制在：

```text
Python Backend API
```

没有权限时 API 返回：

```text
403
```

---

## 营收统计

包括：

* 累计实收
* 已结算订单
* 欠费
* 每个电站营收
* 平均每站营收
* 最近 7 天营收

电站营收可以按金额排序。

---

## 负荷预测

根据历史订单提供未来负荷参考。

包括：

* 时间
* 平均负荷
* 预计空闲桩
* 高峰标记

---

## 操作日志

管理员可以查看重要后台操作，例如：

* 设备状态修改
* 电站操作
* 用户管理
* 故障操作

---

# 11. 运行测试

自动测试使用独立的 MySQL 测试数据库：

```text
ncs_charging_test
```

测试启动前会清理该测试数据库中的表，然后重新初始化测试数据。

测试代码包含安全检查：

* `MYSQL_TEST_DATABASE` 不能与 `MYSQL_DATABASE` 相同
* 测试数据库名称必须以 `_test` 结尾

因此正确配置应该是：

```env
MYSQL_DATABASE=ncs_charging
MYSQL_TEST_DATABASE=ncs_charging_test
```

---

## 运行完整测试

Windows：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

---

## 单独运行 Workflow Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_workflows.py" -v
```

---

## 单独运行 Expansion / Avatar Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_expansion_avatars.py" -v
```

---

## 单独运行 Preference Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_preferences.py" -v
```

---

## Python 编译检查

```powershell
.\.venv\Scripts\python.exe -m py_compile app.py
```

检查 `ncs/`：

```powershell
Get-ChildItem ncs\*.py | ForEach-Object {
    .\.venv\Scripts\python.exe -m py_compile $_.FullName
}
```

检查 tests：

```powershell
Get-ChildItem tests\*.py | ForEach-Object {
    .\.venv\Scripts\python.exe -m py_compile $_.FullName
}
```

---

## JavaScript 检查

如果已经安装 Node.js：

```powershell
node --check static/app.js
```

成功时没有输出。

---

## 检查 Git Merge Conflict

```powershell
git grep -n -E '^(<<<<<<<|=======|>>>>>>>)'
```

正常情况下：

```text
没有输出
```

---

## 检查旧数据库代码是否残留

```powershell
git grep -n "DB_BACKEND"
```

```powershell
git grep -ni "INSERT OR IGNORE"
```

```powershell
git grep -ni "BEGIN IMMEDIATE"
```

正常情况下都应该没有输出。

---

# 12. L1 性能测试

项目包含：

```text
prepare_l1_loadtest.py
performance_test.py
performance_report.json
PERFORMANCE_REPORT.md
```

性能测试使用正常的 MySQL 开发 / 演示数据库。

不要对包含重要真实数据的数据库随意执行写入型压力测试。

---

## 12.1 启动服务器

终端 1：

```powershell
.\.venv\Scripts\python.exe app.py
```

---

## 12.2 准备 L1 测试数据

终端 2：

```powershell
.\.venv\Scripts\python.exe prepare_l1_loadtest.py --prepare
```

---

## 12.3 运行基础性能测试

例如：

```powershell
.\.venv\Scripts\python.exe performance_test.py --base-url http://127.0.0.1:5000 --duration 30 --workers 60
```

参数：

```text
--base-url
--duration
--workers
```

测试会记录：

* QPS
* Avg Latency
* P95
* P99
* Error Rate
* 是否达到目标

---

## 12.4 写业务压力测试

如果需要测试真实订单写链路：

```powershell
.\.venv\Scripts\python.exe performance_test.py --base-url http://127.0.0.1:5000 --duration 30 --workers 40 --write-test
```

该模式会调用真实订单接口。

---

## 12.5 压力分级

运行：

```powershell
.\.venv\Scripts\python.exe performance_test.py --base-url http://127.0.0.1:5000 --duration 30 --workers 60 --stages
```

压力阶段：

```text
25%
50%
75%
100%
125%
```

---

## 12.6 Agent 性能测试

如果要测试真实 GLM Agent：

```powershell
.\.venv\Scripts\python.exe performance_test.py --base-url http://127.0.0.1:5000 --duration 30 --workers 60 --agent-test
```

> `--agent-test` 会真实调用远程 AI API，并可能消耗 API 额度。

---

## 12.7 清理性能测试用户

```powershell
.\.venv\Scripts\python.exe prepare_l1_loadtest.py --cleanup
```

---

## 12.8 Waitress Threads

推荐：

```env
NCS_THREADS=48
```

服务器线程数量会影响并发性能。

---

# 13. 手机访问

`app.py` 使用：

```text
0.0.0.0
```

作为服务器监听地址，因此同一局域网内的手机可以访问电脑上的服务。

---

## 查询电脑 IP

Windows：

```powershell
ipconfig
```

找到：

```text
IPv4 Address
```

例如：

```text
192.168.1.100
```

手机打开：

```text
http://192.168.1.100:5000
```

---

## 手机打不开怎么办

检查：

1. Python 是否正在运行
2. 手机与电脑是否连接同一个 Wi-Fi
3. Windows Firewall 是否允许 Python
4. Port 5000 是否被阻止
5. Wi-Fi 是否启用了 Client Isolation

校园网 / 公共 Wi-Fi 可能禁止设备之间互相访问。

这种情况下：

```text
http://127.0.0.1:5000
```

在电脑正常，但手机仍可能无法连接。

---

# 14. Docker

Docker 是可选功能。

普通 Windows 本地开发不需要安装 Docker，只需要：

```text
Python
+
MySQL
```

即可。

项目包含：

```text
Dockerfile
docker-compose.yml
docker-compose.prod.yml
nginx.conf
```

如果没有安装 Docker，可以直接跳过本节。

---

## Docker 架构

推荐 Compose 环境：

```text
Browser
↓
NCS Flask / Waitress
↓
MySQL
```

生产模式可以增加：

```text
Nginx
↓
NCS Flask / Waitress
↓
MySQL
```

---

## Docker Compose

如果已经安装 Docker Desktop：

```powershell
docker compose up -d --build
```

检查：

```powershell
docker compose ps
```

停止：

```powershell
docker compose down
```

Docker 内的 Flask 应用连接 MySQL service 时：

```env
MYSQL_HOST=mysql
```

而普通 Windows 本地运行时：

```env
MYSQL_HOST=localhost
```

这是因为 Docker container 中的：

```text
localhost
```

表示 container 本身。

---

## Docker 健康检查

启动后：

```text
http://127.0.0.1:5000/api/health
```

数据库正常时应返回：

```json
"database": "ok"
```

---

# 15. 常见问题

## 15.1 `Access denied for user 'ncs_app'`

通常表示：

* MySQL password 错误
* MySQL user 不存在
* user 没有数据库权限

检查：

```env
MYSQL_USER=ncs_app
MYSQL_PASSWORD=YOUR_PASSWORD
```

然后在 MySQL：

```sql
SHOW GRANTS FOR 'ncs_app'@'localhost';
```

如果需要重新授权：

```sql
GRANT ALL PRIVILEGES
ON ncs_charging.*
TO 'ncs_app'@'localhost';

GRANT ALL PRIVILEGES
ON ncs_charging_test.*
TO 'ncs_app'@'localhost';

FLUSH PRIVILEGES;
```

---

## 15.2 `Unknown database 'ncs_charging'`

创建：

```sql
CREATE DATABASE ncs_charging
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

---

## 15.3 测试数据库不存在

创建：

```sql
CREATE DATABASE ncs_charging_test
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

并授权：

```sql
GRANT ALL PRIVILEGES
ON ncs_charging_test.*
TO 'ncs_app'@'localhost';

FLUSH PRIVILEGES;
```

---

## 15.4 `Can't connect to MySQL server`

检查 MySQL Server 是否运行。

Windows：

```text
Services
```

找到类似：

```text
MySQL84
```

确认状态：

```text
Running
```

也可以测试：

```powershell
mysql -u root -p
```

---

## 15.5 AI Agent 可以回答，但不是 GLM

检查：

```env
NCS_LLM_ENABLED=1
BIGMODEL_API_KEY=YOUR_REAL_KEY
```

然后重启 Python。

如果远程模型不可用，系统可能使用 Local Agent fallback。

---

## 15.6 修改 `.env` 没有效果

`.env` 在应用启动时读取。

停止：

```text
Ctrl + C
```

重新运行：

```powershell
.\.venv\Scripts\python.exe app.py
```

---

## 15.7 `ModuleNotFoundError`

通常表示：

* requirements 没安装
* 使用了错误 Python
* VS Code interpreter 不正确

运行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

---

## 15.8 `openai` module 找不到

运行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

---

## 15.9 `dbutils` 找不到

运行：

```powershell
.\.venv\Scripts\python.exe -m pip install DBUtils
```

或者直接：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

---

## 15.10 Port 5000 被占用

PowerShell：

```powershell
$env:NCS_PORT="5001"
```

运行：

```powershell
.\.venv\Scripts\python.exe app.py
```

访问：

```text
http://127.0.0.1:5001
```

---

## 15.11 MySQL 数据库想完全重置

> 警告：下面操作会删除正常数据库中的所有数据。

进入 MySQL：

```sql
DROP DATABASE ncs_charging;
```

重新创建：

```sql
CREATE DATABASE ncs_charging
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

重新授权：

```sql
GRANT ALL PRIVILEGES
ON ncs_charging.*
TO 'ncs_app'@'localhost';

FLUSH PRIVILEGES;
```

然后重新运行：

```powershell
.\.venv\Scripts\python.exe app.py
```

系统会重新初始化空数据库。

---

## 15.12 测试失败并提示数据库安全检查

确认：

```env
MYSQL_DATABASE=ncs_charging
MYSQL_TEST_DATABASE=ncs_charging_test
```

不要设置成：

```env
MYSQL_DATABASE=ncs_charging
MYSQL_TEST_DATABASE=ncs_charging
```

测试数据库还必须以：

```text
_test
```

结尾。

---

## 15.13 手机无法访问，但电脑可以

多数情况是：

```text
Windows Firewall
```

或：

```text
Wi-Fi Client Isolation
```

校园网和公共 Wi-Fi 很常见。

---

# 16. 项目结构

```text
NCS_Charging/
│
├─ app.py
├─ requirements.txt
├─ .env.example
├─ .gitignore
│
├─ Dockerfile
├─ docker-compose.yml
├─ docker-compose.prod.yml
├─ nginx.conf
├─ Procfile
│
├─ backup_mysql.ps1
├─ performance_test.py
├─ prepare_l1_loadtest.py
├─ performance_report.json
├─ PERFORMANCE_REPORT.md
│
├─ ncs/
│  ├─ __init__.py
│  ├─ db.py
│  ├─ mysql_schema.py
│  ├─ routes.py
│  ├─ services.py
│  ├─ capacity.py
│  ├─ agent.py
│  ├─ llm_agent.py
│  ├─ preferences.py
│  ├─ avatars.py
│  ├─ expansion.py
│  ├─ i18n.py
│  └─ ...
│
├─ static/
│  ├─ app.js
│  ├─ style.css
│  ├─ preferences.js
│  ├─ logo.svg
│  ├─ hero.svg
│  └─ i18n/
│
├─ templates/
│  └─ index.html
│
├─ tests/
│  ├─ mysql_test_utils.py
│  ├─ test_workflows.py
│  ├─ test_expansion_avatars.py
│  └─ test_preferences.py
│
├─ previews/
│
└─ data/
   └─ secret.key
```

`data/` 是本地运行数据目录，不应该提交到 Git。

如果 `.env` 中提供了：

```env
NCS_SECRET_KEY=...
```

则建议始终使用该环境变量作为应用 Secret Key。

---

# 重要文件说明

| 文件                                | 作用                              |
| --------------------------------- | ------------------------------- |
| `app.py`                          | 启动 Flask + Waitress             |
| `requirements.txt`                | Python dependencies             |
| `.env.example`                    | 环境变量模板                          |
| `ncs/__init__.py`                 | Flask 配置、CSRF、错误处理、数据库初始化       |
| `ncs/db.py`                       | MySQL 连接池、数据库初始化、Seed Data、RBAC |
| `ncs/mysql_schema.py`             | MySQL Schema                    |
| `ncs/routes.py`                   | API Routes                      |
| `ncs/services.py`                 | 预约、充电、结算等核心业务                   |
| `ncs/capacity.py`                 | L1 容量配置                         |
| `ncs/agent.py`                    | Local AI Agent                  |
| `ncs/llm_agent.py`                | GLM + Local fallback            |
| `ncs/preferences.py`              | 用户偏好                            |
| `ncs/avatars.py`                  | 用户头像                            |
| `ncs/expansion.py`                | 演示网络扩展                          |
| `static/app.js`                   | 前端业务逻辑                          |
| `static/style.css`                | UI 样式                           |
| `tests/mysql_test_utils.py`       | MySQL 测试数据库安全与清理工具              |
| `tests/test_workflows.py`         | 核心业务 Regression Tests           |
| `tests/test_expansion_avatars.py` | 网络扩展和头像测试                       |
| `tests/test_preferences.py`       | 偏好设置测试                          |
| `performance_test.py`             | L1 性能测试                         |
| `prepare_l1_loadtest.py`          | L1 测试数据准备                       |
| `backup_mysql.ps1`                | MySQL 数据库备份                     |

---

# 17. 团队开发建议

不建议所有成员长期直接在：

```text
dev
```

上开发。

推荐：

```text
dev
↓
features/name
↓
开发
↓
测试
↓
Pull Request / Integration
↓
dev
```

---

## 开始开发前

```powershell
git checkout dev
git pull origin dev
```

---

## 创建个人 Branch

例如：

```powershell
git checkout -b features/rey
```

或者：

```powershell
git checkout -b features/jiaqi
```

---

## 开发过程中同步 dev

如果团队的 `dev` 更新：

```powershell
git fetch origin
git merge origin/dev
```

如有 conflict，解决后再继续开发。

---

## 开发完成后

先测试：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

如果安装 Node：

```powershell
node --check static/app.js
```

检查 conflict marker：

```powershell
git grep -n -E '^(<<<<<<<|=======|>>>>>>>)'
```

检查状态：

```powershell
git status
```

---

## Commit

```powershell
git add .
```

然后：

```powershell
git commit -m "feat: describe your feature"
```

---

## Push

```powershell
git push -u origin features/your-name
```

然后创建 Pull Request 或交给 Integration branch 合并。

---

## 不要提交这些文件

不要提交：

```text
.env
.venv/
data/
backups/
```

也不要提交：

```text
API Key
MySQL Password
Secret Key
```

Commit 前检查：

```powershell
git status
```

---

# 18. 第一次配置推荐流程

如果刚拿到项目，可以按照下面顺序执行。

## Step 1 — 安装环境

安装：

```text
Git
Python 3.11+
VS Code
MySQL 8.x
```

---

## Step 2 — Clone

```powershell
git clone https://github.com/a1re135/NCS_Charging.git
cd NCS_Charging
git checkout dev
```

---

## Step 3 — 创建 Virtual Environment

```powershell
py -3 -m venv .venv
```

---

## Step 4 — 安装依赖

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

---

## Step 5 — 创建 MySQL 数据库

进入：

```powershell
mysql -u root -p
```

执行：

```sql
CREATE DATABASE ncs_charging
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

CREATE DATABASE ncs_charging_test
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

---

## Step 6 — 创建 MySQL 用户

```sql
CREATE USER 'ncs_app'@'localhost'
IDENTIFIED BY 'YOUR_PASSWORD';

GRANT ALL PRIVILEGES
ON ncs_charging.*
TO 'ncs_app'@'localhost';

GRANT ALL PRIVILEGES
ON ncs_charging_test.*
TO 'ncs_app'@'localhost';

FLUSH PRIVILEGES;
```

---

## Step 7 — 创建 `.env`

```powershell
Copy-Item .env.example .env
```

填写：

```env
NCS_SECRET_KEY=YOUR_RANDOM_SECRET

MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=ncs_charging
MYSQL_TEST_DATABASE=ncs_charging_test
MYSQL_USER=ncs_app
MYSQL_PASSWORD=YOUR_PASSWORD

NCS_LLM_ENABLED=0
NCS_THREADS=48
```

---

## Step 8 — 启动

```powershell
.\.venv\Scripts\python.exe app.py
```

---

## Step 9 — 打开

```text
http://127.0.0.1:5000
```

---

## Step 10 — 登录

管理员：

```text
admin
Admin123456
```

普通用户：

```text
13800138000
User123456
```

---

## Step 11 — 运行测试

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

---

## Step 12 — 检查 JavaScript

如果安装 Node.js：

```powershell
node --check static/app.js
```

---

# 最快正常运行方案

如果只是希望尽快运行项目，需要：

```text
Python
+
MySQL
```

`.env`：

```env
NCS_SECRET_KEY=local-development-secret

MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=ncs_charging
MYSQL_TEST_DATABASE=ncs_charging_test
MYSQL_USER=ncs_app
MYSQL_PASSWORD=YOUR_PASSWORD

NCS_LLM_ENABLED=0
NCS_THREADS=16
```

运行：

```powershell
.\.venv\Scripts\python.exe app.py
```

不需要：

* BigModel API Key
* Docker
* Node.js

---

# 完整演示推荐配置

最终 Demo 推荐：

```text
Python 3.12
+
MySQL 8.x
+
Waitress
+
NCS_THREADS=48
+
GLM Agent
```

`.env`：

```env
NCS_SECRET_KEY=YOUR_RANDOM_SECRET
NCS_CAPACITY_LEVEL=L1

NCS_COOKIE_SECURE=0
NCS_TRUST_PROXY=0

MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=ncs_charging
MYSQL_TEST_DATABASE=ncs_charging_test
MYSQL_USER=ncs_app
MYSQL_PASSWORD=YOUR_PASSWORD

NCS_LLM_ENABLED=1
NCS_LLM_PROVIDER=bigmodel

BIGMODEL_API_KEY=YOUR_API_KEY
BIGMODEL_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
BIGMODEL_MODEL=glm-4-flashx-250414

NCS_THREADS=48
```

---

# 数据库备份

项目提供：

```text
backup_mysql.ps1
```

用于备份 MySQL。

运行备份前确保：

* `mysqldump` 已安装
* MySQL Server 正常运行
* 备份脚本中的数据库信息符合当前环境

备份文件保存到：

```text
backups/
```

建议在：

* 演示前
* 大规模修改数据前
* 数据库结构调整前

执行备份。

---

# GitHub CI

项目使用：

```text
.github/workflows/ci.yml
```

进行自动检查。

CI 应包含：

```text
Checkout
↓
Python 3.12
↓
启动 MySQL Test Service
↓
安装 requirements
↓
Python compile check
↓
运行 tests
↓
Docker build
```

GitHub CI 使用独立的：

```text
ncs_charging_test
```

数据库，不会访问开发者电脑上的本地数据库。

---

# 相关文档

项目还包含：

```text
VALIDATION.md
```

功能验证记录。

```text
PERFORMANCE_REPORT.md
```

L1 性能测试结果。

```text
RBAC_REFACTOR.md
```

RBAC 权限设计。

```text
UPGRADE_I18N_DARK.md
```

中英文与深色模式说明。

```text
deploy.md
```

部署和性能验收说明。

---

# 19. 安全说明

本项目是：

```text
课程项目 / Demo System
```

不应该直接作为真实商业充电平台上线。

当前包括：

* 模拟钱包充值
* 模拟充电
* 模拟设备状态
* 演示用户
* 演示订单

不包含真实：

* 银行支付
* 支付宝 / 微信支付
* 真实充电桩硬件协议
* 真实短信验证码
* 商业级身份验证
* Production Key Management

开发时不要将以下内容提交到 Git：

```text
.env
API Key
MySQL Password
Secret Key
```

---

# NCS Smart Charging

```text
A LITTLE ENERGY.

A BETTER DAY.
```

Smart Charging Management Platform

Course Project / Demonstration System
