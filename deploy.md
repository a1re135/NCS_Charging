# NCS 云端部署与性能验收方案

## 1. 项目交付目标

NCS Charging 当前按照 **L1 基础业务级** 进行课程项目设计和性能验收。

L1 目标包括：

* 10,000 注册用户
* 1,000 日活用户
* 10 个充电站
* 100 台充电设备
* 100 同时在线用户

主要接口性能目标：

| 场景          |  L1 目标 |
| ----------- | -----: |
| 登录          | 20 QPS |
| 电站查询        | 50 QPS |
| 设备查看        | 30 QPS |
| 开始充电        | 10 QPS |
| 结束充电        | 10 QPS |
| AI Agent 咨询 |  5 QPS |

项目当前数据库统一使用：

```text
MySQL 8.x
```

不再使用其他本地文件数据库。

---

# 2. 推荐部署架构

推荐线上架构：

```text
Internet
   ↓
HTTPS / Reverse Proxy
   ↓
Nginx
   ↓
Waitress
   ↓
Flask
   ↓
DBUtils Connection Pool
   ↓
PyMySQL
   ↓
MySQL 8.x
```

其中：

* **Nginx**：公网入口、反向代理、HTTPS
* **Waitress**：Python Web Server
* **Flask**：业务 API
* **DBUtils**：MySQL Connection Pool
* **PyMySQL**：MySQL Driver
* **MySQL 8.x**：业务数据库

---

# 3. 本地运行方式

Docker 不是本项目本地运行的必需条件。

Windows 开发环境只需要：

```text
Python
+
MySQL
```

即可运行完整系统。

---

## 3.1 MySQL 配置

项目正常数据库：

```text
ncs_charging
```

自动测试数据库：

```text
ncs_charging_test
```

`.env` 示例：

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

NCS_LLM_ENABLED=0
NCS_LLM_PROVIDER=bigmodel

BIGMODEL_API_KEY=
BIGMODEL_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
BIGMODEL_MODEL=glm-4-flashx-250414

NCS_THREADS=48
```

---

## 3.2 启动服务

Windows：

```powershell
.\.venv\Scripts\python.exe app.py
```

正常情况下终端会显示类似：

```text
[Database] MySQL localhost:3306/ncs_charging

NCS Charging: http://127.0.0.1:5000
Waitress threads: 48
Press Ctrl+C to stop.
```

浏览器访问：

```text
http://127.0.0.1:5000
```

---

# 4. 健康检查

访问：

```text
http://127.0.0.1:5000/api/health
```

正常情况下应返回类似：

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

表示 Flask 已经能够正常访问 MySQL。

---

# 5. 数据持久化

所有主要业务数据均存储在：

```text
MySQL
```

包括：

* 用户
* 电站
* 电桩
* 订单
* 钱包
* 欠费
* 分时收费
* 故障记录
* 操作日志
* RBAC
* 用户偏好
* 用户头像
* 数据迁移记录

因此部署时必须确保 MySQL 数据目录具有持久化存储。

如果使用：

```text
MySQL Server
```

直接安装在服务器，则应正常备份 MySQL 数据目录和数据库。

如果使用：

```text
Docker MySQL
```

则应使用 Docker Volume，例如：

```text
mysql-data:/var/lib/mysql
```

不要把数据库存放在临时容器文件系统中。

---

# 6. MySQL 备份

项目提供：

```text
backup_mysql.ps1
```

用于 Windows 环境下进行 MySQL 备份。

MySQL 备份使用：

```text
mysqldump
```

生成：

```text
.sql
```

备份文件。

建议在以下情况执行备份：

* 演示前
* 数据库结构修改前
* 大规模数据操作前
* 重要功能合并前

备份文件应放在：

```text
backups/
```

目录。

不要把包含业务数据的数据库备份提交到 Git。

---

# 7. Windows 本地验收

启动项目：

```powershell
.\.venv\Scripts\python.exe app.py
```

然后检查：

```text
http://127.0.0.1:5000/api/health
```

接着完成基本业务验收：

```text
[ ] 用户登录正常
[ ] 管理员登录正常
[ ] 电站列表正常
[ ] 电站详情正常
[ ] 电桩状态正常
[ ] 预约正常
[ ] 开始充电正常
[ ] 结束充电正常
[ ] 订单结算正常
[ ] 钱包正常
[ ] 欠费与补缴正常
[ ] 管理端正常
[ ] RBAC 权限正常
[ ] AI Agent 正常
```

---

# 8. 云服务器部署

推荐使用 Linux 云服务器。

基本环境：

```text
Linux
Python 3.11+
MySQL 8.x
Nginx
Git
```

推荐 Python：

```text
Python 3.12
```

---

## 8.1 Clone 项目

```bash
git clone https://github.com/a1re135/NCS_Charging.git
cd NCS_Charging
git checkout dev
```

---

## 8.2 创建 Python 环境

```bash
python3 -m venv .venv
```

安装：

```bash
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/python -m pip install -r requirements.txt
```

---

## 8.3 配置 MySQL

创建数据库：

```sql
CREATE DATABASE ncs_charging
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;
```

创建项目用户：

```sql
CREATE USER 'ncs_app'@'localhost'
IDENTIFIED BY 'YOUR_STRONG_PASSWORD';
```

授权：

```sql
GRANT ALL PRIVILEGES
ON ncs_charging.*
TO 'ncs_app'@'localhost';

FLUSH PRIVILEGES;
```

---

## 8.4 创建 `.env`

```bash
cp .env.example .env
```

修改：

```env
NCS_SECRET_KEY=YOUR_LONG_RANDOM_SECRET
NCS_CAPACITY_LEVEL=L1

NCS_COOKIE_SECURE=1
NCS_TRUST_PROXY=1

MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=ncs_charging
MYSQL_USER=ncs_app
MYSQL_PASSWORD=YOUR_STRONG_PASSWORD

NCS_LLM_ENABLED=0

NCS_THREADS=48
```

如果启用 GLM：

```env
NCS_LLM_ENABLED=1
BIGMODEL_API_KEY=YOUR_API_KEY
```

---

## 8.5 启动测试

```bash
./.venv/bin/python app.py
```

检查：

```bash
curl http://127.0.0.1:5000/api/health
```

确认：

```json
"database": "ok"
```

之后再配置 Nginx 和后台服务管理。

---

# 9. Nginx

推荐公网请求流程：

```text
Client
↓
HTTPS
↓
Nginx
↓
127.0.0.1:5000
↓
Waitress
↓
Flask
```

Nginx 不应该直接连接数据库。

MySQL 只由 Flask 后端访问。

生产环境建议：

```text
80 → HTTPS redirect
443 → Nginx
Nginx → Flask:5000
```

并配置：

```env
NCS_TRUST_PROXY=1
NCS_COOKIE_SECURE=1
```

HTTPS 配置完成后再开启安全 Cookie。

---

# 10. Docker 部署

Docker 是可选部署方式。

如果本机没有 Docker，可以直接跳过本节。

项目包含：

```text
Dockerfile
docker-compose.yml
docker-compose.prod.yml
nginx.conf
```

推荐 Docker 架构：

```text
Nginx
↓
NCS Flask
↓
MySQL
```

MySQL 数据应通过：

```text
/var/lib/mysql
```

绑定持久化 Volume。

Flask Container 连接 MySQL Container 时：

```env
MYSQL_HOST=mysql
```

而不是：

```env
MYSQL_HOST=localhost
```

因为 Container 内的：

```text
localhost
```

代表当前 Container 本身。

---

## 10.1 Docker Compose

安装 Docker 后可以运行：

```bash
docker compose up -d --build
```

检查：

```bash
docker compose ps
```

检查健康状态：

```bash
curl http://127.0.0.1:5000/api/health
```

停止：

```bash
docker compose down
```

如果需要同时删除测试用 Docker Volume：

```bash
docker compose down -v
```

> `-v` 会删除 Volume 中的数据。
>
> 有需要保留的数据时不要使用该参数。

---

# 11. 上线检查清单

正式演示或部署前建议检查：

```text
[ ] MySQL Server 正常
[ ] /api/health 正常
[ ] database = ok
[ ] 首页正常访问
[ ] 用户登录正常
[ ] 管理员登录正常
[ ] 运营人员登录正常
[ ] 运维人员登录正常
[ ] 电站查询正常
[ ] 电桩查询正常
[ ] 预约正常
[ ] 开始充电正常
[ ] 结束充电正常
[ ] 订单结算正常
[ ] 钱包正常
[ ] 欠费补缴正常
[ ] RBAC 权限正常
[ ] 实时监控正常
[ ] 营收统计正常
[ ] 趋势图正常
[ ] AI Agent 正常
[ ] HTTPS 正常（公网环境）
[ ] 数据库备份正常
[ ] 自动测试通过
[ ] JavaScript 语法检查通过
[ ] Performance Test 完成
```

---

# 12. 自动测试

自动测试必须使用独立数据库：

```text
ncs_charging_test
```

本地 `.env`：

```env
MYSQL_DATABASE=ncs_charging
MYSQL_TEST_DATABASE=ncs_charging_test
```

禁止：

```env
MYSQL_DATABASE=ncs_charging
MYSQL_TEST_DATABASE=ncs_charging
```

测试代码包含安全检查，测试数据库名称还必须以：

```text
_test
```

结尾。

---

## 12.1 运行完整测试

Windows：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Linux：

```bash
./.venv/bin/python -m unittest discover -s tests -v
```

---

## 12.2 Python 编译检查

Windows：

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

---

## 12.3 JavaScript 检查

如果安装 Node.js：

```bash
node --check static/app.js
```

成功时没有输出。

---

# 13. L1 性能验收

首先启动服务：

```powershell
.\.venv\Scripts\python.exe app.py
```

---

## 13.1 准备测试数据

另开终端：

```powershell
.\.venv\Scripts\python.exe prepare_l1_loadtest.py --prepare
```

脚本会准备确定性的 L1 性能测试用户。

---

## 13.2 基础只读压力测试

推荐先运行：

```powershell
.\.venv\Scripts\python.exe performance_test.py `
    --base-url http://127.0.0.1:5000 `
    --duration 60 `
    --workers 60
```

单行形式：

```powershell
.\.venv\Scripts\python.exe performance_test.py --base-url http://127.0.0.1:5000 --duration 60 --workers 60
```

---

## 13.3 云端只读测试

```bash
python performance_test.py \
    --base-url https://你的域名 \
    --duration 60 \
    --workers 80
```

---

## 13.4 真实写链路压力测试

```bash
python performance_test.py \
    --base-url https://你的域名 \
    --duration 30 \
    --workers 40 \
    --write-test
```

该模式会调用真实业务接口，覆盖：

```text
订单创建
↓
开始充电
↓
状态更新
↓
结束充电
↓
结算
↓
余额处理
↓
电桩释放
```

不要对包含重要用户数据的正式数据库随意运行写压力测试。

---

## 13.5 压力分级

运行：

```bash
python performance_test.py \
    --base-url https://你的域名 \
    --duration 30 \
    --workers 80 \
    --stages
```

系统会测试：

```text
25%
50%
75%
100%
125%
```

五个压力等级。

---

## 13.6 AI Agent 性能测试

真实 GLM 性能测试：

```bash
python performance_test.py \
    --base-url https://你的域名 \
    --duration 30 \
    --workers 60 \
    --agent-test
```

> `--agent-test` 会调用真实远程 AI API，并可能消耗 API Credits。

---

# 14. 性能测试结果

测试会生成：

```text
performance_report.json
PERFORMANCE_REPORT.md
```

主要记录：

* 实测 QPS
* 目标 QPS
* 平均延迟
* P95
* P99
* Error Rate
* 是否达到 L1 目标

---

## 达标判定

单项建议使用：

```text
实际成功 QPS >= 目标 QPS
并且
Error Rate = 0
```

作为通过标准。

性能验收应保留：

* 命令行输出
* `performance_report.json`
* `PERFORMANCE_REPORT.md`
* 测试环境配置
* 测试时间
* 云端 URL（如果有）
* 截图或录屏

作为课程验收证据。

---

# 15. 清理性能测试数据

测试结束后：

```powershell
.\.venv\Scripts\python.exe prepare_l1_loadtest.py --cleanup
```

Linux：

```bash
./.venv/bin/python prepare_l1_loadtest.py --cleanup
```

建议性能测试结束后及时清理测试用户。

---

# 16. GitHub CI

仓库使用：

```text
.github/workflows/ci.yml
```

进行自动验证。

推荐流程：

```text
Push / Pull Request
↓
GitHub Actions
↓
Python 3.12
↓
MySQL 8.x Test Service
↓
Install requirements
↓
Python Compile Check
↓
MySQL Regression Tests
↓
Docker Build
```

CI 使用独立数据库：

```text
ncs_charging_test
```

CI 中使用的：

```text
MySQL Password
Secret Key
```

应该只是 CI 临时测试值，不应使用开发者真实密码。

---

# 17. MySQL 并发控制

NCS Charging 的核心订单逻辑使用 MySQL / InnoDB Transaction。

重要业务操作使用：

```sql
SELECT ... FOR UPDATE
```

进行 Row Lock。

用于保护例如：

* 多用户同时抢同一充电桩
* 同订单重复结算
* 电桩状态并发修改
* 预约超时释放
* 钱包余额修改

整体流程：

```text
HTTP Request
↓
Flask
↓
Transaction
↓
SELECT ... FOR UPDATE
↓
Business Logic
↓
COMMIT / ROLLBACK
```

这样可以提高并发业务一致性。

---

# 18. Connection Pool

数据库连接架构：

```text
Flask Request
↓
DBUtils PooledDB
↓
PyMySQL
↓
MySQL
```

项目不会为每个请求都永久创建新的 MySQL 连接。

连接池可以：

* 复用连接
* 减少连接创建开销
* 支持并发请求
* 改善 L1 性能测试表现

---

# 19. 生产环境安全建议

生产或公网演示环境至少应：

```text
[ ] 使用随机 NCS_SECRET_KEY
[ ] 不提交 .env
[ ] 不提交 MySQL Password
[ ] 不提交 API Key
[ ] 使用 HTTPS
[ ] 开启 NCS_COOKIE_SECURE=1
[ ] 开启 NCS_TRUST_PROXY=1（反向代理环境）
[ ] MySQL 不直接暴露公网
[ ] 不使用 root 账号运行应用
[ ] 定期执行数据库备份
[ ] 修改默认演示账号密码
```

---

# 20. 数据库网络安全

MySQL 推荐：

```text
Flask Server
↓
Private Network / localhost
↓
MySQL
```

不推荐：

```text
Internet
↓
3306
↓
MySQL
```

MySQL Port：

```text
3306
```

不应该为了 Web 用户访问而直接开放到公网。

用户只能通过：

```text
HTTP / HTTPS
↓
Flask API
```

访问业务数据。

---

# 21. 项目定位

NCS Charging 当前是：

```text
Course Project
+
Demonstration System
+
L1 Performance Validation
```

不是商业级真实充电平台。

当前包含：

* 模拟钱包
* 模拟充值
* 模拟设备状态
* 模拟充电过程
* 演示用户
* 演示订单

不包含：

* 真实银行支付
* 支付宝 / 微信支付
* 商业充电桩硬件协议
* 真实短信服务
* 商业级身份认证
* Production-grade Secret Management

---

# 22. 最终验收建议

最终课程演示建议准备：

```text
1. GitHub Repository
2. README.md
3. deploy.md
4. VALIDATION.md
5. PERFORMANCE_REPORT.md
6. 正常运行的 MySQL
7. 用户端 Demo
8. 管理端 Demo
9. AI Agent Demo
10. L1 Performance Test Result
11. GitHub CI Result
12. 项目录屏 / 演示视频
```

最终演示前建议执行：

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

然后：

```powershell
node --check static/app.js
```

再检查：

```powershell
git grep -n -E '^(<<<<<<<|=======|>>>>>>>)'
```

并确认：

```text
所有 Tests Passed
数据库正常
页面正常
没有 Merge Conflict
没有敏感信息被提交
```
