# NCS 云端部署与性能验收方案

## 1. 推荐交付形态

本项目申报 **L1 基础业务级**。L1 的课程目标为：10,000 注册用户、1,000 日活、10 个充电站、100 台充电设备、100 同时在线用户，以及登录 20 QPS、站点查询 50 QPS、设备查看 30 QPS、开始/结束充电各 10 QPS、Agent 咨询 5 QPS。

推荐线上结构：

```text
公网
  ↓
云负载入口 / Nginx / HTTPS
  ↓
Waitress + Flask
  ↓
SQLite WAL + 持久化磁盘
```

对于课程项目，SQLite + 持久化卷足以用于 L1 演示；如果以后提升到更高等级，可把数据库替换为 PostgreSQL/MySQL，并加入 Redis、消息队列、独立设备数据接入服务等。

## 2. Docker 本地验收

```bash
docker compose up -d --build
curl http://127.0.0.1:5000/api/health
```

健康检查应包含：

```json
{"ok":true,"service":"ncs-charging","capacity_level":"L1","database":"ok"}
```

浏览器访问：

```text
http://127.0.0.1:5000
```

## 3. 云服务器部署

准备一台 Linux 云服务器并安装 Docker + Compose。把项目上传后：

```bash
cp .env.example .env
# 编辑 .env，设置 NCS_SECRET_KEY
docker compose -f docker-compose.prod.yml up -d --build
```

推荐使用云厂商的 HTTPS/反向代理把公网 443 转发到服务器 80；Nginx 容器负责反向代理到 Flask。

## 4. 数据持久化

SQLite 数据位于 `/app/data`。`ncs-data` volume 用于让容器重建后保留数据库。生产环境不要把数据库放在临时文件系统；云平台若提供 persistent disk，应挂载到 `/app/data`。

## 5. 上线检查清单

```text
[ ] /api/health 正常
[ ] 首页公网可访问
[ ] 用户可以登录
[ ] 管理员可以登录
[ ] 站点查询正常
[ ] 开始/结束充电正常
[ ] 订单生成与结算正常
[ ] 数据在容器重启后仍存在
[ ] HTTPS 正常
[ ] performance_test.py 对公网地址执行
[ ] 写入性能测试完成后执行 cleanup
```

## 6. L1 性能验收

先准备专用测试数据：

```bash
python prepare_l1_loadtest.py --prepare
```

只读压测（推荐先运行）：

```bash
python performance_test.py --base-url http://127.0.0.1:5000 --duration 60 --workers 60
```

云端只读压测：

```bash
python performance_test.py --base-url https://你的域名 --duration 60 --workers 80
```

真实订单写链路压测：

```bash
python performance_test.py --base-url https://你的域名 --duration 30 --workers 40 --write-test
```

写链路会真实调用 `/api/orders` 与 `/api/orders/<id>/finish`，覆盖订单创建、状态更新、结算、余额扣减和电桩释放。不要对真实生产用户数据运行写压测。

完成后：

```bash
python prepare_l1_loadtest.py --cleanup
```

报告会生成：

```text
performance_report.json
PERFORMANCE_REPORT.md
```

### 达标判定

每个场景满足：

```text
实测成功 QPS >= L1 目标 QPS
并且错误率 = 0
```

同时记录平均延迟、P95、P99。性能验收应保留命令行输出、报告文件和云端 URL 作为证据。

## 7. GitHub CI

仓库内置 `.github/workflows/ci.yml`，每次 push / pull request 自动执行：

```text
Python 3.12
→ requirements 安装
→ Python 编译检查
→ 12 条业务回归测试
→ Docker build
```

这样可以把“代码可重复验证”也作为软件工程交付证据。

### 8. 压力分级（加分项）

为了展示系统在目标附近的稳定区间，可增加五档压力阶段：25%、50%、75%、100%、125% 的并发工作线程。命令：

```bash
python performance_test.py --base-url https://你的域名 --duration 30 --workers 80 --stages
```

这样报告不仅给出“是否达到 L1”，还可以观察接近/超过目标时延迟和错误率如何变化。
