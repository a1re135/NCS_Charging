# NCS Charging — 智能充电管理平台

NCS Charging 是一个基于 **Flask + JavaScript + MySQL/SQLite** 的智能充电管理平台课程项目。

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
> **安装环境 → 安装依赖 → 配置数据库 → 配置 `.env` → 配置 AI Agent → 启动 → 测试**
>
> 当前主要开发分支：`dev`

---

# 目录

1. [环境要求](#1-环境要求)
2. [获取代码](#2-获取代码)
3. [安装 Python 依赖](#3-安装-python-依赖)
4. [选择数据库：SQLite 或 MySQL](#4-选择数据库sqlite-或-mysql)
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

---

# 1. 环境要求

## 必装

建议安装：

* **Git**
* **Python 3.11 或以上**

  * 推荐 Python 3.12
* **VS Code**
* Chrome / Edge 浏览器

## VS Code 推荐扩展

安装：

* Python
* Python Debugger

## 完整模式推荐额外安装

如果要使用完整 MySQL 环境：

* **MySQL 8.x**
* MySQL Workbench（可选）

如果需要做 JavaScript 语法检查：

* Node.js

如果需要容器运行：

* Docker Desktop

---

## 检查环境

打开 PowerShell：

```powershell
git --version
python --version
```

Windows 如果安装了 Python Launcher：

```powershell
py --version
```

例如：

```text
Python 3.12.x
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
* `Waitress`：运行 Web Server
* `PyMySQL`：连接 MySQL
* `DBUtils`：MySQL connection pool
* `python-dotenv`：读取 `.env`
* `openai`：用于连接 OpenAI-compatible 的 BigModel / GLM API
* `qrcode`：生成充电桩二维码
* `Pillow`：图片相关处理

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

# 4. 选择数据库：SQLite 或 MySQL

NCS Charging 同时支持：

### SQLite

优点：

* 最简单
* 不需要安装 MySQL
* 适合第一次运行
* 适合 UI 开发
* 适合功能测试

### MySQL

优点：

* 推荐完整演示
* 推荐多人统一开发
* 推荐 L1 性能测试
* 支持 connection pooling
* 更接近正式部署环境

当前项目默认：

```text
DB_BACKEND=mysql
```

因此第一次运行之前，请明确选择数据库。

---

# 4.1 SQLite 快速启动

如果只是想最快把整个系统跑起来，推荐先使用 SQLite。

创建 `.env` 后写：

```env
DB_BACKEND=sqlite
NCS_DATABASE=data/ncs.db
```

第一次运行时系统会自动创建：

```text
data/ncs.db
```

并自动：

* 建表
* 创建演示账号
* 创建电站
* 创建电桩
* 创建历史订单
* 创建 RBAC 权限
* 创建分时价格
* 创建示例故障数据

不需要自己导入 SQL。

---

# 4.2 MySQL 完整模式

推荐项目最终演示和性能测试使用 MySQL。

## 安装 MySQL

推荐：

```text
MySQL 8.x
```

Windows 可以安装：

* MySQL Server
* MySQL Workbench

安装时记住：

```text
root password
```

---

## 创建数据库

进入 MySQL：

```powershell
mysql -u root -p
```

或者直接使用 MySQL Workbench。

执行：

```sql
CREATE DATABASE ncs_charging
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

---

## 创建项目专用 MySQL 用户

建议不要让项目直接使用 `root`。

执行：

```sql
CREATE USER 'ncs_app'@'localhost'
IDENTIFIED BY 'CHANGE_THIS_PASSWORD';
```

授权：

```sql
GRANT ALL PRIVILEGES
ON ncs_charging.*
TO 'ncs_app'@'localhost';
```

然后：

```sql
FLUSH PRIVILEGES;
```

---

## MySQL `.env`

例如：

```env
DB_BACKEND=mysql

MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=ncs_charging
MYSQL_USER=ncs_app
MYSQL_PASSWORD=CHANGE_THIS_PASSWORD
```

其中：

```text
MYSQL_PASSWORD
```

必须与你刚才创建 MySQL user 时设置的密码一致。

---

## 不需要手动导入 schema

只需要：

1. MySQL Server 已运行
2. `ncs_charging` database 已存在
3. MySQL user 可以访问 database

启动 NCS 后，Python 会自动创建项目需要的数据表。

---

## 判断是否使用 MySQL

启动时终端会显示类似：

```text
[Database] MySQL localhost:3306/ncs_charging
```

表示当前正在使用 MySQL。

如果使用 SQLite，则会看到类似：

```text
[Database] SQLite ...\data\ncs.db
```

---

# 5. 配置 `.env`

项目已经提供：

```text
.env.example
```

请复制为：

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

`.env` 已经被 `.gitignore` 排除，因此正常情况下不会提交到 GitHub。

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
# Database
# =========================================================

DB_BACKEND=mysql

MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=ncs_charging
MYSQL_USER=ncs_app
MYSQL_PASSWORD=CHANGE_THIS_PASSWORD


# =========================================================
# SQLite alternative
# =========================================================

# DB_BACKEND=sqlite
# NCS_DATABASE=data/ncs.db


# =========================================================
# AI Agent - Zhipu BigModel / GLM
# =========================================================

NCS_LLM_ENABLED=0
NCS_LLM_PROVIDER=bigmodel

BIGMODEL_API_KEY=
BIGMODEL_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
BIGMODEL_MODEL=glm-4-flashx-250414


# =========================================================
# Web server
# =========================================================

NCS_THREADS=48
```

---

# 5.1 NCS_SECRET_KEY

建议每个人生成自己的随机 Secret Key。

运行：

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

例如输出：

```text
52c7d4....
```

复制到：

```env
NCS_SECRET_KEY=52c7d4....
```

不要把真实 Secret Key 提交到 GitHub。

---

# 5.2 NCS_THREADS

当前 Web Server 使用 Waitress。

例如：

```env
NCS_THREADS=48
```

表示 Waitress 最多使用 48 个 worker threads 处理请求。

本地普通开发也可以降低，例如：

```env
NCS_THREADS=16
```

但性能测试推荐保持项目指定值。

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

# 6.1 Local Agent

Local Agent 不需要任何 API Key。

只要：

```env
NCS_LLM_ENABLED=0
```

即可。

此时：

```text
用户问题
↓
本地 Agent 判断 intent
↓
调用 NCS Python 业务函数
↓
查询真实业务数据
↓
返回答案
```

优点：

* 不需要联网
* 不消耗 API 额度
* 不需要 BigModel Key
* 更稳定
* 自动测试使用该模式

---

# 6.2 GLM / BigModel Agent

如果希望使用真正的 LLM 做自然语言理解，可以开启 GLM。

需要获取：

```text
BIGMODEL_API_KEY
```

然后修改 `.env`：

```env
NCS_LLM_ENABLED=1

NCS_LLM_PROVIDER=bigmodel

BIGMODEL_API_KEY=YOUR_REAL_API_KEY

BIGMODEL_BASE_URL=https://open.bigmodel.cn/api/paas/v4/

BIGMODEL_MODEL=glm-4-flashx-250414
```

保存后必须重启项目。

停止：

```text
Ctrl + C
```

重新：

```powershell
.\.venv\Scripts\python.exe app.py
```

---

# 6.3 AI Agent 的工作方式

GLM **不会直接连接数据库**。

架构是：

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
MySQL / SQLite
 ↓
真实业务数据
 ↓
返回答案
```

也就是说：

```text
LLM = 理解问题
Python Tool = 读取真实业务数据
```

GLM 不能：

* 自己写 SQL
* 直接访问数据库
* 越过 RBAC
* 调用当前角色没有权限的工具

---

# 6.4 Local fallback

如果发生：

* `NCS_LLM_ENABLED=0`
* 没有填写 API Key
* 网络失败
* BigModel API timeout
* API Key 无效
* BigModel 服务异常

系统会自动：

```text
GLM
 ↓ 失败
Local Agent
 ↓
继续回答
```

因此 AI Agent 页面不会因为 GLM 服务出问题而完全不能使用。

终端可能会看到：

```text
GLM Agent failed; using local fallback
```

这是 fallback 机制正常工作的表现。

---

# 6.5 AI Agent 用户问题示例

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

# 6.6 运营 / 管理员 Agent

运营人员 / 管理员可以问：

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

# 6.7 运维人员 Agent

运维人员主要可以查询：

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

# 6.8 GLM 没生效怎么办

检查 `.env`：

```env
NCS_LLM_ENABLED=1
```

以及：

```env
BIGMODEL_API_KEY=真实APIKey
```

确认：

* `.env` 与 `app.py` 同级
* 修改 `.env` 后重启 Python
* 网络能访问 BigModel
* API Key 有效
* `openai` package 已安装

可以重新安装 requirements：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

---

## 自动测试不会调用 GLM

当 Flask 运行：

```python
TESTING=True
```

时，系统强制使用：

```text
Local Agent
```

所以运行测试：

```powershell
python -m unittest
```

不会消耗 BigModel API 额度。

---

# 7. 启动项目

Windows：

```powershell
.\.venv\Scripts\python.exe app.py
```

正常情况下会看到：

```text
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

浏览器打开：

```text
http://127.0.0.1:5000/api/health
```

如果返回系统信息，说明后端正常。

---

## 停止系统

终端：

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

不需要每次重新：

```text
pip install
```

---

# 8. 演示账号

系统初始化后提供以下演示账号。

| 角色     | 账号            | 密码               |
| ------ | ------------- | ---------------- |
| 普通用户   | `13800138000` | `User123456`     |
| 普通用户 2 | `13900139000` | `User123456`     |
| 运营人员   | `operator`    | `Operator123456` |
| 运维人员   | `tech`        | `Tech123456`     |
| 系统管理员  | `admin`       | `Admin123456`    |

登录页面也有演示账号快捷填入按钮。

---

## 角色说明

### 普通用户

可以：

* 找充电站
* 预约
* 充电
* 查看订单
* 钱包充值
* 处理欠费
* 使用 AI Agent
* 修改个人资料

---

### 运营人员

主要负责：

* 电站
* 订单
* 分时价格
* 营收
* 运营统计
* 负荷预测

---

### 运维人员

主要负责：

* 电桩
* 设备状态
* 故障
* 维修
* 恢复
* 实时设备数据

---

### 系统管理员

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

只要数据库连接成功，系统启动时会自动初始化数据库。

包括：

* 创建数据表
* 创建 RBAC tables
* 创建角色
* 创建权限
* 创建 demo users
* 创建电站
* 创建电桩
* 创建价格规则
* 创建历史订单
* 创建钱包数据
* 创建故障演示数据
* 创建操作日志相关表
* 创建用户 preferences
* 初始化 avatar 数据
* 扩展演示电站网络

因此正常情况下不需要运行：

```text
schema.sql
```

或手动导入数据库结构。

---

# 10. 功能说明

# 用户端

## 总览

包含：

* 欢迎页面
* 累计充电量
* 已完成订单
* 累计消费
* 最近 7 天趋势
* 钱包余额
* 电桩实时状态
* 最近订单

---

## 附近电站

支持：

* 搜索电站
* 搜索地址
* 浏览器定位
* 区域预置位置
* 有空闲桩筛选
* 距离排序
* 充电次数排序

每个电站显示：

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
3. 选择充电桩

充电桩支持：

* 全部状态
* 空闲
* 预约中
* 充电中

类型筛选：

```text
快充
慢充
```

可以：

* 都不选 → 显示全部
* 只选快充
* 只选慢充
* 两个都选

---

## 预约

用户可以预约空闲设备。

预约时间：

```text
15 分钟
```

预约期间：

* 可以开始充电
* 可以取消
* 超时后自动释放

---

## 充电

支持：

* 直接开始
* 预约后开始
* 实时电量
* 实时费用
* 模拟充电时间

系统默认：

```text
60× 时间模拟
```

---

## 结算

结束充电后：

* 计算最终能量
* 锁定计费快照
* 计算订单金额
* 自动扣除余额
* 更新 charger
* 写入 wallet log
* 保存 order receipt

---

## 欠费

余额不足时：

```text
订单完成
+
产生 debt_cents
```

用户可以在：

```text
我的钱包
→ 待补缴金额
→ 查看欠费订单
```

直接：

* 查看欠费订单
* 查看详情
* 补缴

补缴成功后：

* 钱包余额立即刷新
* 待补缴金额立即刷新
* 欠费列表立即刷新

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

---

## 路线导航

可选择：

```text
驾车
步行
公交
```

然后打开腾讯地图路线。

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

# 运营总览

管理员 / 运营人员可以看到：

* 累计电量
* 已完成订单
* 电站数量
* 营收
* 用户统计
* 设备统计

---

## 订单与收入趋势

支持：

### 粒度

```text
按天
按周
按月
```

### 范围

```text
最近 7 天
最近 30 天
本年度
```

### 电站

```text
全部电站
指定电站
```

### 订单口径

```text
有效完成
全部订单
```

同时显示：

* 订单趋势
* 收入趋势

---

## 快充 / 慢充平台资源统计

总览会统计：

* 快充总数量
* 快充空闲
* 快充故障
* 慢充总数量
* 慢充空闲
* 慢充故障

---

# 实时监控

实时监控页面每：

```text
5 秒
```

刷新一次。

包含：

* 设备总数
* 空闲设备
* 使用中设备
* 异常设备
* 电桩状态分布
* 电站利用率
* 系统设备健康率
* 最近 5 分钟设备趋势
* 各电站异常设备

状态趋势包括：

```text
空闲
使用中
异常
```

---

# 电站管理

支持：

* 添加
* 编辑
* 删除
* 运营状态

排序：

```text
充电次数最多
充电次数最少
```

---

# 分时收费

价格管理已经整合到：

```text
电站详情
→ 分时收费标准
```

不再作为独立侧栏页面。

管理员可以：

* 添加价格时段
* 编辑价格
* 删除价格

价格由：

```text
电费
+
服务费
=
最终单价
```

组成。

---

# 电桩管理

支持：

* 新增
* 编辑
* QR Code
* 快充 / 慢充
* 功率
* 电站筛选
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

# 故障管理

支持：

* 登记故障
* 待处理
* 处理中
* 已解决
* 记录处理结果

故障状态会同步更新 charger 状态。

---

# 用户管理

用户有三类状态：

```text
正常
欠费
冻结
```

可以：

* 状态筛选
* 注册日期筛选
* 最新注册排序
* 最早注册排序
* 冻结用户
* 启用用户
* 修改角色

---

## 冻结用户规则

冻结用户：

### 不可以

```text
创建新的充电订单
```

### 仍然可以

* 取消已有预约
* 结束正在进行的充电
* 钱包充值
* 补缴欠费

这样避免：

```text
用户被冻结
↓
无法充值
↓
无法补缴
↓
欠费永远无法处理
```

---

# RBAC

系统有四个角色：

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

前端菜单只是展示层。

真正权限检查在：

```text
Python Backend API
```

即使用户手动调用 API，没有权限也会返回：

```text
403
```

---

# 营收统计

包括：

* 累计实收
* 已结算订单
* 欠费
* 每个电站营收
* 平均每站营收
* 最近 7 天营收

电站营收：

```text
从高到低排序
```

---

# 负荷预测

根据历史订单提供：

```text
未来 12 小时
```

负荷参考。

包括：

* 时间
* 平均负荷
* 预计空闲桩
* 高峰标记

---

# 操作日志

管理员可以查看重要后台操作记录。

例如：

* 设备状态修改
* 电站操作
* 用户管理
* 故障操作

---

# 11. 运行测试

合并代码或 Push 前推荐运行完整测试。

Windows：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

自动测试使用：

```text
temporary SQLite databases
```

不会修改：

* MySQL 正式数据
* 本地 demo SQLite
* 当前用户数据

---

## Python 编译检查

```powershell
.\.venv\Scripts\python.exe -m compileall app.py ncs tests
```

---

## JavaScript 检查

如果安装 Node.js：

```powershell
node --check static/app.js
```

成功时没有输出。

---

## 检查 Git Merge Conflict

```powershell
git grep -n -E "^(<<<<<<<|=======|>>>>>>>)"
```

正常情况下：

```text
没有输出
```

---

# 12. L1 性能测试

项目包含：

```text
prepare_l1_loadtest.py
performance_test.py
performance_report.json
PERFORMANCE_REPORT.md
```

L1 测试推荐：

```text
MySQL mode
```

---

## 启动服务器

终端 1：

```powershell
.\.venv\Scripts\python.exe app.py
```

---

## 准备 L1 测试数据

终端 2：

```powershell
.\.venv\Scripts\python.exe prepare_l1_loadtest.py --prepare
```

---

## 运行测试

例如：

```powershell
.\.venv\Scripts\python.exe performance_test.py --base-url http://127.0.0.1:5000 --duration 15 --concurrency 20
```

测试会统计：

* QPS
* 平均延迟
* P95
* P99
* Error Rate

---

## 清理测试数据

```powershell
.\.venv\Scripts\python.exe prepare_l1_loadtest.py --cleanup
```

---

## Waitress threads

性能测试时注意：

```env
NCS_THREADS=48
```

服务器线程数会影响高并发结果。

---

# 13. 手机访问

`app.py` 使用：

```text
0.0.0.0
```

因此可以让同一局域网内的手机访问。

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

确认：

1. Python 正在运行
2. 手机和电脑连接同一个 Wi-Fi
3. Windows Firewall 允许 Python
4. Port 5000 没有被拦截
5. Wi-Fi 没有启用 Client Isolation

公共 Wi-Fi 很可能禁止设备之间通信。

这种情况下电脑自己访问：

```text
127.0.0.1
```

正常，但手机仍然无法连接。

---

# 14. Docker

项目包含：

```text
Dockerfile
docker-compose.yml
Procfile
```

---

# Docker + SQLite

最容易测试的方法：

```bash
docker build -t ncs-charging .
```

然后：

```bash
docker run --rm \
  -p 5000:5000 \
  -e DB_BACKEND=sqlite \
  -e NCS_SECRET_KEY=change-me \
  -v ncs-data:/app/data \
  ncs-charging
```

访问：

```text
http://127.0.0.1:5000
```

---

# Docker + MySQL

如果 Flask 在 Docker 中，而 MySQL 在其他地方，需要配置：

```text
DB_BACKEND=mysql
MYSQL_HOST
MYSQL_PORT
MYSQL_DATABASE
MYSQL_USER
MYSQL_PASSWORD
```

例如：

```env
DB_BACKEND=mysql

MYSQL_HOST=host.docker.internal
MYSQL_PORT=3306

MYSQL_DATABASE=ncs_charging
MYSQL_USER=ncs_app
MYSQL_PASSWORD=YOUR_PASSWORD
```

如果 MySQL 在 Windows Host，Docker Desktop 中：

```text
localhost
```

通常表示 Docker container 自己，而不是 Windows Host。

因此可以尝试：

```text
host.docker.internal
```

---

## 当前 docker-compose 注意事项

当前：

```text
docker-compose.yml
```

主要配置的是：

```text
NCS Web Application
```

它目前 **不会自动帮你创建 MySQL Server**。

所以直接运行：

```bash
docker compose up -d --build
```

之前，需要确保：

### 方案 1

明确设置：

```text
DB_BACKEND=sqlite
```

或者：

### 方案 2

已经有可访问的 MySQL，并传入完整 MySQL 配置。

---

# 15. 常见问题

# 15.1 `Access denied for user 'ncs_app'`

通常表示：

* MySQL password 错误
* user 不存在
* user 没有权限

检查 `.env`：

```env
MYSQL_USER=ncs_app
MYSQL_PASSWORD=...
```

MySQL：

```sql
GRANT ALL PRIVILEGES
ON ncs_charging.*
TO 'ncs_app'@'localhost';

FLUSH PRIVILEGES;
```

---

# 15.2 `Unknown database 'ncs_charging'`

创建：

```sql
CREATE DATABASE ncs_charging
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

---

# 15.3 我不想安装 MySQL

使用：

```env
DB_BACKEND=sqlite
NCS_DATABASE=data/ncs.db
```

然后：

```powershell
.\.venv\Scripts\python.exe app.py
```

即可运行完整 Web App。

---

# 15.4 AI Agent 可以回答，但不是 GLM

检查：

```env
NCS_LLM_ENABLED=1
```

以及：

```env
BIGMODEL_API_KEY=YOUR_REAL_KEY
```

然后重启 Python。

如果 GLM 调用失败，系统会自动切换：

```text
Local Agent
```

所以页面仍然可以正常工作。

---

# 15.5 修改 `.env` 没有效果

`.env` 是应用启动时读取。

先：

```text
Ctrl+C
```

然后：

```powershell
.\.venv\Scripts\python.exe app.py
```

---

# 15.6 `ModuleNotFoundError`

通常表示：

* requirements 没安装
* 用错 Python
* VS Code interpreter 不正确

重新：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

然后：

```powershell
.\.venv\Scripts\python.exe app.py
```

---

# 15.7 `openai` module 找不到

运行：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

或者：

```powershell
.\.venv\Scripts\python.exe -m pip install openai
```

---

# 15.8 `dbutils` 找不到

运行：

```powershell
.\.venv\Scripts\python.exe -m pip install DBUtils
```

通常直接重新安装：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

即可。

---

# 15.9 Port 5000 被占用

PowerShell：

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

# 15.10 SQLite 想完全重置

停止程序。

删除：

```text
data/ncs.db
```

然后重新启动：

```powershell
.\.venv\Scripts\python.exe app.py
```

系统会重新生成 demo data。

> 如果里面有需要保留的数据，不要删除。

---

# 15.11 MySQL 想完全重置

警告：下面操作会删除当前数据库数据。

可以：

```sql
DROP DATABASE ncs_charging;
```

然后：

```sql
CREATE DATABASE ncs_charging
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

重新启动 NCS 后会重新初始化。

---

# 15.12 手机无法访问，但电脑可以

多数情况是：

```text
Windows Firewall
```

或者：

```text
Wi-Fi Client Isolation
```

尤其校园网 / 公共 Wi-Fi 很常见。

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
├─ Procfile
│
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
│  ├─ agent.py
│  ├─ llm_agent.py
│  ├─ preferences.py
│  ├─ avatars.py
│  ├─ expansion.py
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
│  └─ test_workflows.py
│
└─ data/
   └─ ncs.db
```

其中：

```text
data/
```

不会提交到 Git。

---

# 重要文件说明

| 文件                        | 作用                           |
| ------------------------- | ---------------------------- |
| `app.py`                  | 启动 Flask + Waitress          |
| `requirements.txt`        | Python dependencies          |
| `.env.example`            | 环境变量模板                       |
| `ncs/__init__.py`         | Flask 配置、CSRF、数据库初始化         |
| `ncs/db.py`               | SQLite / MySQL、连接池、Seed Data |
| `ncs/mysql_schema.py`     | MySQL Schema                 |
| `ncs/routes.py`           | API Routes                   |
| `ncs/services.py`         | 预约、充电、结算等核心业务                |
| `ncs/agent.py`            | Local AI Agent               |
| `ncs/llm_agent.py`        | GLM + Local fallback Agent   |
| `static/app.js`           | 前端逻辑                         |
| `static/style.css`        | 前端 UI / Realtime / Agent 样式  |
| `tests/test_workflows.py` | 核心业务 Regression Tests        |
| `performance_test.py`     | 性能测试                         |
| `prepare_l1_loadtest.py`  | L1 测试数据准备                    |

---

# 17. 团队开发建议

不要直接长期在：

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
完成开发
↓
测试
↓
merge 回 dev
```

---

## 开始开发前

```powershell
git checkout dev
git pull origin dev
```

---

## 创建个人 branch

例如：

```powershell
git checkout -b features/rey
```

或者：

```powershell
git checkout -b features/jiaqi
```

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
git grep -n -E "^(<<<<<<<|=======|>>>>>>>)"
```

检查：

```powershell
git status
```

---

## Commit

```powershell
git add .
```

```powershell
git commit -m "feat: describe your feature"
```

---

## Push

```powershell
git push -u origin features/your-name
```

然后：

* Pull Request
* 或交给 Integration branch 合并

---

# 不要提交这些文件

不要提交：

```text
.env
```

```text
.venv/
```

```text
data/
```

```text
*.db
```

```text
backups/
```

以及：

```text
API Key
MySQL Password
Secret Key
```

这些大部分已经在 `.gitignore` 中，但仍应该在 commit 前检查：

```powershell
git status
```

---

# 推荐第一次配置顺序

如果你刚拿到这个项目，可以直接按下面执行。

## Step 1

安装：

```text
Git
Python 3.11+
VS Code
```

---

## Step 2

Clone：

```powershell
git clone https://github.com/a1re135/NCS_Charging.git
cd NCS_Charging
git checkout dev
```

---

## Step 3

Virtual Environment：

```powershell
py -3 -m venv .venv
```

---

## Step 4

Dependencies：

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

---

## Step 5

复制 `.env`：

```powershell
Copy-Item .env.example .env
```

---

## Step 6

如果想最快运行：

```env
DB_BACKEND=sqlite
NCS_LLM_ENABLED=0
```

---

## Step 7

运行：

```powershell
.\.venv\Scripts\python.exe app.py
```

---

## Step 8

打开：

```text
http://127.0.0.1:5000
```

---

## Step 9

登录：

```text
admin
Admin123456
```

或者：

```text
13800138000
User123456
```

---

## Step 10

确认基本功能正常后，再切换：

```text
SQLite
↓
MySQL
```

以及：

```text
Local Agent
↓
GLM Agent
```

---

# 最快运行方案

如果只是要最快看到系统：

`.env`：

```env
DB_BACKEND=sqlite

NCS_LLM_ENABLED=0

NCS_SECRET_KEY=local-development-secret

NCS_THREADS=16
```

然后：

```powershell
.\.venv\Scripts\python.exe app.py
```

即可。

不需要：

* MySQL
* BigModel Key
* Docker
* Node.js

---

# 完整演示推荐配置

最终 Demo 推荐：

```text
Python 3.12
+
MySQL 8
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

DB_BACKEND=mysql

MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=ncs_charging
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

# 相关文档

项目中还有：

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

---

# 安全说明

本项目是：

```text
课程项目 / Demo System
```

不应直接作为真实商业充电系统上线。

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
* 生产环境 Key Management

---

# NCS Smart Charging

```text
A LITTLE ENERGY.
A BETTER DAY.
```

Smart Charging Management Platform
Course Project / Demonstration System
