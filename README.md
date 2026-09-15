> **新增中英文切换与深色模式**：升级、设置入口和本次验证范围请先阅读 [UPGRADE_I18N_DARK.md](UPGRADE_I18N_DARK.md)。保留现有 `.env` 和数据库，打开包含 `app.py` / `requirements.txt` 的项目文件夹启动。

## 1. Windows + VS Code 启动（先看这里）

1. 安装 Python 3.11 或更新版本（建议使用 3.12），安装时勾选 **Add python.exe to PATH**。
2. 把整个压缩包解压，例如 `D:\Projects\NCS_Charging_Python`。不要直接在压缩包内部运行。
3. 在 VS Code 选择“文件 → 打开文件夹”，选中包含 `app.py` 的文件夹。
4. 安装 Microsoft 的 **Python** 和 **Python Debugger** 扩展。
5. 打开“终端 → 新建终端”，依次执行下面三条命令。

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

这里直接使用虚拟环境中的 Python，不需要执行 Activate.ps1，也不需要调整 PowerShell 执行策略。电脑没有 `py` 命令、但 `python --version` 正常时，第一条改为 `python -m venv .venv`。

6. 保持终端运行，在 Edge 或 Chrome 打开 **http://127.0.0.1:5000**。(先在终端输入ipconfig查看自己的ip然后改成http://ip：5000)
7. 在 VS Code 按 `Ctrl+Shift+P` → `Python: Select Interpreter` → 选择 `.venv\Scripts\python.exe`。此后可以按 F5，选择 `NCS Python - Windows` 调试。
8. 停止系统：在运行终端按 `Ctrl+C`。

也可以直接双击 `start_windows.bat`：它创建虚拟环境、安装依赖，然后启动程序。第一次需要联网下载依赖；后续可使用第三条命令直接启动，无需再安装。

**下次运行只需要：**

```powershell
.\.venv\Scripts\python.exe app.py
```

## 2. 演示账号

| 身份 | 登录账号 | 密码 |
| --- | --- | --- |
| 用户 | 13800138000 | User123456 |
| 另一位用户 | 13900139000 | User123456 |
| 管理员 | admin | Admin123456 |

登录页可点击演示账号自动填入。也可注册自己的手机号、昵称和密码；新账号余额为 0。手机号只做格式验证，不发送短信。示例用户“小林”初始余额 288 元，数据库初始化时生成 5 个电站、30 个电桩及近 28 天的示例历史订单，方便展示图表；其中部分电桩预置为故障、维修中、离线状态，用户“小明”预置一笔昨日未补缴订单欠费，便于演示管理端“欠费”状态。

用户和管理员在同一个登录页面登录，系统按数据库角色展示对应菜单；用户请求管理接口会被后端拒绝。若想同时打开两个身份，请使用普通窗口和无痕窗口，它们的登录会话互相独立。

## 3. 功能

### 用户端

- 总览：欢迎插画、充电统计、最近 7 天趋势、钱包余额、电桩状态、最近订单。
- 附近电站：区域预置位置、浏览器定位、站名/地址搜索；支持按充电状态（有空闲/故障/维修中/离线）筛选，并按距离或充电次数排序。
- 电站详情：快慢充、功率、状态、累计次数；可按电桩状态、类型筛选并按充电次数排序；空闲桩可预约或直接充电。
- 预约：保留 15 分钟；可开始、取消或过期释放。
- 我的充电：按 60 倍时间模拟电量与金额，每 3 秒刷新；页面关闭再打开后可恢复。
- 结束结算：冻结计费参数，扣减余额、记录欠费、释放电桩、保存小票。
- 我的订单：状态筛选、搜索、详情、浏览器打印小票、补缴欠费；支持按创建日期（起止年月日）筛选，含今天/近 7 天/近 30 天快捷按钮。
- 我的钱包：模拟充值、流水、欠费汇总。
- 个人中心：昵称、四种头像主题、修改密码、退出登录；重新登录后保留资料。
- 路线导航：可选驾车/步行/公交，在浏览器打开腾讯地图路线链接。

### 管理端

- 运营总览、实时设备状态、累计营收及最近 7 天实收趋势。
- 电站新增、编辑、删除；电站有电桩时禁止删除。
- 电桩新增、编辑、所属电站下拉筛选、类型（快充/慢充）筛选、状态筛选，按编号或充电次数（高到低/低到高）排序，故障/维修中/离线切换、恢复、软件模拟重启、删除。
- 有未完成订单的电桩禁止管理操作；有历史订单的电桩禁止删除或迁移电站。
- 用户查看：状态分正常/欠费/冻结三态（欠费=存在未补缴订单欠费）；支持按状态筛选、按注册时间起止日期区间筛选，按最新/最早注册排序；冻结/启用；冻结用户仍可取消预约、结束已有充电和补缴欠费。
- 全部订单查看、按创建日期筛选、CSV 导出（导出同步应用日期筛选范围）；导出 UTF-8 BOM，方便 Windows Excel 打开中文。
- 近 28 天同小时均值的负荷参考预测，展示未来 12 小时结果。
- 电站、电桩和用户状态操作日志。

## 4. 与原 Qt 项目的关系和边界

| 原项目模块 | 新版实现 | 说明 |
| --- | --- | --- |
| client_user/LoginWindow | 登录页 + /api/login、/api/register | 改为手机号 + 密码；未接短信 |
| PersonalHomePage / UserService | 个人中心、钱包 + profile、wallet 接口 | 资料和余额写入 SQLite；头像使用主题首字母，未迁移相机拍照/图片上传 |
| MainWindow / StationService | 电站列表与详情 + stations 接口 | 保留预置坐标、定位和距离排序；未接地址文字地理编码 |
| NavigationDialog / WebEngine | 外部腾讯地图路线链接 | 不需要 QtWebEngine；外部地图服务需联网，当前环境未完成外部路线服务联通验证 |
| ChargeService / OrderSettlementDialog | services.py 事务与状态机 + 我的充电 | 保留预约、未完成订单拦截、模拟计费、结算、欠费 |
| OrdersHistoryDialog | 我的订单、详情、打印小票 | 使用浏览器打印 |
| client_admin | 按角色展示的管理端页面与 /api/admin 接口 | 电站、电桩、用户、订单、营收、操作日志 |
| PredictionService | 历史小时均值预测 | 是可解释的基础版重写，未逐行移植原 C++ 预测算法 |
| charger_simulator / TCP RESTART | 管理端“软件模拟重启” | 未移植独立 TCP 模拟器；不会控制真实设备 |
| core/database | ncs/db.py + data/ncs.db | 新 schema，金额使用整数分；不能直接用旧 charge_platform.db 覆盖 |

**这不是全部原功能逐项等价迁移。** 首版优先实现可演示的用户和管理闭环。真实短信、真实支付、内嵌地图/地址地理编码、摄像头头像、独立 TCP 设备模拟器及原预测算法精确迁移，均不包含在本次版本内。

上传压缩包未包含运行时 SQLite 数据库，因此本项目不会包含旧电脑上的真实用户、余额或订单；演示数据在首次运行时生成。原 Qt 源码和配置没有放入新包，也没有复制原来的地图密钥。

## 5. 推荐演示顺序

1. 用 `13800138000` 登录，在个人中心修改昵称和头像主题，然后退出再登录，检查保留。
2. 我的钱包 → 充值 1 元，检查余额增加 1.00 元。
3. 附近电站 → 切换海淀区/朝阳区，观察排序变化。
4. 电站详情 → 选空闲桩 → 预约，查看 15 分钟到期时间。
5. 再去另一电站选桩，系统会拦截并跳回已有订单。
6. 我的充电 → 开始充电。等待约 10 秒，观察电量增长。
7. 结束充电并结算 → 查看小票、钱包扣款、电桩恢复空闲。
8. 管理员登录 → 查看订单/营收 → 新增电站和电桩 → 故障/恢复 → 查看日志。
9. 负荷预测 → 选择电站，展示未来 12 小时基础预测。

模拟计算：`电量 = 功率(kW) × 真实经过秒数 × 60 ÷ 3600`。例如 60 kW 快充在真实 10 秒内模拟约 10 kWh；1.60 元/度时约 16 元。结束瞬间的最终计费时间可能比页面上次刷新晚几秒。

同一用户只能有一个预约中或充电中的订单，同一个桩也只能有一个有效订单。服务层使用 `BEGIN IMMEDIATE` 事务与部分唯一索引防止并发重复占用。金额使用整数“分”，结束结算整体提交，避免重复扣款。预约过期在收到已登录 API 请求时检查；没有访问时不运行后台计时器，下次访问会先释放过期预约。

## 6. 文件结构和学习入口

| 文件 | 用途 |
| --- | --- |
| app.py | 启动 Flask 应用与 Waitress 本地服务器 |
| ncs/__init__.py | 应用配置、会话、CSRF 校验、错误处理 |
| ncs/db.py | 数据表、数据库连接、示例数据初始化 |
| ncs/services.py | 预约、充电、结算、欠费、金额校验、距离计算 |
| ncs/routes.py | 页面向 Python 发起的 API；登录、资料、用户和管理操作 |
| templates/index.html | 网页骨架 |
| static/style.css | 淡紫/蓝粉配色、侧栏、卡片、响应式布局 |
| static/app.js | 浏览器交互、页面渲染、调用 Python 接口 |
| static/hero.svg | 本地人物协作矢量插画，无需联网加载 |
| tests/test_workflows.py | 15 项核心业务回归测试 |
| backup_data.py | 使用 SQLite backup API 生成一致性备份 |
| start_windows.bat | Windows 启动脚本 |
| .vscode/ | VS Code 调试与测试配置 |

如果老师问“怎么做到改昵称下次登录还在”：前端提交 `/api/profile` → Python 执行 `UPDATE users` → SQLite 写入 `data/ncs.db` → 下次 `/api/login` 和 `/api/session` 重新读取该用户 → 页面展示数据库中的昵称。

如果问“Python 和网页怎么连接”：浏览器 JavaScript 用 `fetch('/api/...')` 请求；Flask routes.py 接收 JSON、验证身份，调用 services.py 操作数据库，返回 JSON；浏览器更新卡片和表格。类似 Qt 的按钮触发槽函数，只是这里经过 HTTP 请求。

## 7. 数据保存、换电脑和备份

首次启动生成 `data/ncs.db` 和随机会话密钥 `data/secret.key`。日常保留整个 `data` 文件夹；不要把它提交到公开仓库。

生成备份：

```powershell
.\.venv\Scripts\python.exe backup_data.py
```

备份保存到 `backups`。迁移到另一台电脑：先停止目标系统，备份目标现有数据库，再把生成的备份复制成目标 `data/ncs.db`。关闭后的旧 `ncs.db-wal`、`ncs.db-shm` 也需一起移走，防止新旧混用。目标的 `secret.key` 可保留，登录会话需重新建立。

每台电脑独立运行时使用各自的 SQLite 数据库，同一个手机号不会跨电脑自动同步。要跨设备同步，需要以后部署一个统一后端并让各设备访问同一服务；当前仅监听 `127.0.0.1`，供本机使用。

## 8. 常见问题

- **ModuleNotFoundError: flask / waitress**：使用 `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`，并在 VS Code 选择相同解释器。
- **浏览器打不开**：确认终端仍在运行，地址是 `http://127.0.0.1:5000`；不要直接双击 index.html，也不要用 Live Server 运行。
- **端口占用**：先停止旧进程，或 PowerShell 执行 `$env:NCS_PORT="5001"` 再启动；浏览器访问 `http://127.0.0.1:5001`。
- **画面没变化**：确认打开了正确文件夹；Python 改动需停止并重启服务，CSS/JS 改动后按 `Ctrl+F5` 强制刷新。
- **初次 pip 下载失败**：检查电脑网络和 Python 版本；本项目依赖只有 Flask、Waitress 及其自动安装的小型依赖。
- **地图定位失败**：允许浏览器定位，或选预置区域。浏览器定位可能不精确；路线使用外部服务，坐标/模式会带入 URL。
- **管理员删除电桩失败**：有历史订单的电桩受外键保护；可标记故障，保留历史记录。
- **待付款/欠费**：先充值足额，再进入订单详情点“补缴欠费”。
- **数据想从头开始**：先备份，再停止系统并把整个 `data` 文件夹移到其他位置；下次启动重新生成演示数据。不要在运行中删除数据库。

## 9. 测试与验证范围

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

已在提供的 Linux 执行环境通过 Python 3.12 + Flask + SQLite 的 12 项回归测试，并在 Windows/Python 3.11 环境补充通过新增 4 项（维修/离线状态、电站筛选、订单日期筛选、用户状态筛选排序）共 16 项。业务测试用独立临时数据库，不修改实际数据。已使用 Chromium 检查页面和主要交互；具体结果见 `VALIDATION.md`。

Windows 批处理、VS Code 配置已提供并检查内容，但本环境不是 Windows，未实际运行 Windows 批处理或 VS Code GUI。请按第 1 节在你的电脑运行；如报错，把完整终端文字发来即可进一步定位。

依赖与虚拟环境用法参考：[Flask 官方安装文档](https://flask.palletsprojects.com/en/stable/installation/)。本项目用例、界面和验证结果来自本次实现。

## 10. L1 容量等级、性能测试与云端部署

本版本已按课程要求申报 **L1 基础业务级**，目标规模为 10,000 注册用户、1,000 日活用户、10 个充电站、100 台充电设备、100 个同时在线用户。L1 峰值目标为：登录 20 QPS、查询充电站 50 QPS、查看设备 30 QPS、开始充电 10 QPS、结束充电 10 QPS、Agent 咨询 5 QPS。

容量目标集中定义在 `ncs/capacity.py`，后台管理员登录后可在 **容量等级** 页面查看。

### 性能测试

先启动服务：

```powershell
.\.venv\Scripts\python.exe app.py
```

再在另一个终端执行：

```powershell
.\.venv\Scripts\python.exe performance_test.py --base-url http://127.0.0.1:5000 --duration 15 --concurrency 20
```

测试结束后会生成：

- `performance_report.json`
- `PERFORMANCE_REPORT.md`

脚本会统计 QPS、平均延迟、P95、P99 和错误率，并与 L1 目标进行对照。

### 云端部署

项目已提供：

- `Dockerfile`
- `docker-compose.yml`
- `Procfile`
- `deploy.md`

Docker 运行：

```bash
docker compose up -d --build
```

程序监听 `PORT` 环境变量，也兼容本地 `NCS_PORT`。生产环境建议设置随机的 `NCS_SECRET_KEY`，并将 `/app/data` 挂载到持久化磁盘/卷，以保存 SQLite 数据。

部署后可以访问：

```text
/api/health
```

确认返回 `capacity_level: L1` 后，再从公网打开首页。

## L1 容量等级、性能测试与云端交付（新增）

本版本把课程要求明确落到可执行的工程流程：

1. **容量等级：L1 基础业务级**
   - 目标：10,000 注册用户、1,000 DAU、10 个电站、100 台电桩、100 同时在线用户。
   - QPS：登录 20、查询电站 50、查看设备 30、开始/结束充电 10/10、Agent 5。
   - 运行后进入管理员 → “容量等级”查看申报目标与当前数据规模。

2. **性能测试**
   - `performance_test.py` 支持登录、站点查询、设备查看等只读压测。
   - `--write-test` 使用真实订单创建与结算链路验证开始/结束充电，并记录 QPS、错误率、平均延迟、P95、P99。
   - 测试前执行 `python prepare_l1_loadtest.py --prepare`；测试结束执行 `python prepare_l1_loadtest.py --cleanup`。

3. **云端部署**
   - `Dockerfile`、`docker-compose.yml`、`docker-compose.prod.yml`、`nginx.conf` 已准备好。
   - Flask/Waitress 使用 `PORT`，反向代理识别 `X-Forwarded-*`，SQLite 使用持久化 volume。
   - `/api/health` 同时检查服务与数据库连通性。

4. **持续集成**
   - `.github/workflows/ci.yml` 自动进行依赖安装、Python 编译检查、业务回归测试和 Docker 构建。


## RBAC / 角色权限增强

系统提供四种业务角色，并将权限持久化到 `roles`、`permissions`、`role_permissions` 三张表。关键管理 API 在服务端进行权限校验，前端导航仅作为用户体验层的可见性控制。

| 角色 | 示例账号 | 主要权限 |
|---|---|---|
| 普通用户 | `13800138000 / User123456` | 附近电站、充电、个人订单 |
| 运营人员 | `operator / Operator123456` | 电站、电桩、订单、价格、运营分析 |
| 运维人员 | `tech / Tech123456` | 电桩、设备维护、故障处理 |
| 系统管理员 | `admin / Admin123456` | 全部权限、用户与角色管理 |

管理员可以在后台的 **角色与权限** 页面查看 RBAC 矩阵，并在 **用户管理** 中即时调整角色。关键 API 会返回 `403` 拒绝越权请求。

## 支付状态与用户统计

订单接口现在会返回计算后的 `payment_status`：`已支付`、`待补缴`、`部分支付`、`支付失败`、`待结算`、`无需支付`。其中正常充电结束后会自动扣除余额并显示 `已支付`；余额不足则形成真实的欠费状态 `待补缴`，而不是虚构的“支付中”。

运营总览增加注册用户总数、活跃用户数及近 7 日新增用户数量，用户数量统计来源于数据库实时聚合。
