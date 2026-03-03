    # XueQiu Trader - 雪球组合交易与跟踪系统

基于 [easytrader](https://github.com/shidenggui/easytrader) 实现的雪球组合调仓、跟踪和模拟交易功能。

## ✨ 功能特性

### 核心模块

| 模块 | 功能 | 说明 |
|------|------|------|
| **XueQiuTrader** | 组合调仓 | Cookie认证、按权重/金额/股数调仓 |
| **XueQiuFollower** | 组合跟踪 | 轮询调仓历史、权重变化转信号、指令缓存 |
| **XueQiuSimulator** | 模拟仓交易 | 模拟账户买卖、同步目标组合、自动跟踪 |

### Web 管理后台

- **🔐 用户登录认证** - Flask-Login，密码哈希存储
- **可视化配置管理** - 在线编辑配置
- **脚本控制** - 一键启停各类演示脚本
- **实时日志 (SSE)** - 零轮询，服务端推送日志流
- **日志持久化 (SQLite)** - 历史日志存档
- **组合详情弹窗** - 点击查看持仓、净值、收益率
- **脚本状态实时推送** - 启动/停止状态瞬间反馈

## 📁 项目结构

```
xueqiu_trader/
├── config/
│   ├── xq.json                   # API 配置
│   └── user_config.template.json # 用户配置模板
├── data/                         # 数据目录 (git ignored)
│   └── xueqiu_trader.db          # SQLite 数据库
├── scripts/                      # 工具脚本
│   ├── create_user.py            # 创建管理员用户
│   └── migrate_config.py         # 配置迁移脚本
├── utils/
│   ├── log.py                    # 日志模块
│   └── misc.py                   # 工具函数
├── xqtrader.py                   # 调仓模块
├── xq_follower.py                # 跟踪模块
├── xq_simulator.py               # 模拟仓模块
├── exceptions.py                 # 异常定义
├── examples/                     # 演示脚本
│   ├── trader_demo.py
│   ├── follower_demo.py
│   ├── simulator_demo.py
│   └── auto_track_demo.py
├── tests/                        # 测试脚本
└── web/                          # Web管理后台
    ├── app.py                    # Flask 后端
    ├── models.py                 # 数据库模型
    └── templates/
        ├── index.html            # 主页
        └── login.html            # 登录页
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 复制配置模板

```bash
cp config/user_config.template.json config/user_config.json
```

编辑 `config/user_config.json` 填入你的 Cookies 和组合代码。

**获取 Cookies:**
1. 登录 https://xueqiu.com
2. F12 打开开发者工具 → Network
3. 刷新页面，复制请求头中的 Cookie

### 3. 初始化数据库

```bash
python scripts/migrate_config.py
```

### 4. 创建管理员用户

```bash
python scripts/create_user.py
```
按提示输入用户名和密码（密码至少6位）

### 5. 启动 Web 管理后台

```bash
python web/app.py
```

访问 http://127.0.0.1:5000/login 登录

## 📖 使用示例

### 模拟仓操作

```python
from xq_simulator import XueQiuSimulator

simulator = XueQiuSimulator()
simulator.login()

# 获取模拟仓持仓
holdings = simulator.get_holdings(gid=1234567890)

# 同步到目标组合
simulator.sync_from_portfolio(gid=1234567890, target_code="ZH654321")

# 自动跟踪
simulator.auto_track_and_sync(gid=1234567890, target_code="ZH654321", interval=30)
```

### 组合跟踪

```python
from xq_follower import XueQiuFollower

follower = XueQiuFollower()
follower.login(cookies="your_cookies")
follower.follow(strategies=["ZH123456"], total_assets=100000, track_interval=10)
```

## 🌐 Web API

所有 API 需要登录认证（Cookie Session）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/login` | GET/POST | 登录页面 |
| `/logout` | GET | 登出 |
| `/api/config` | GET/POST | 配置管理 |
| `/api/scripts` | GET | 脚本列表和状态 |
| `/api/scripts/<id>/start` | POST | 启动脚本 |
| `/api/scripts/<id>/stop` | POST | 停止脚本 |
| `/api/logs/stream` | GET | SSE 日志流 |
| `/api/logs/history` | GET | 历史日志 |
| `/api/portfolio/<code>` | GET | 组合详情 |
| `/api/simulator/<gid>` | GET | 模拟仓详情 |

## 🔐 安全说明

- 所有 API 路由需要登录后访问
- 密码使用 `werkzeug.security` 哈希存储
- `config/user_config.json` 和 `data/` 已加入 `.gitignore`
- 公网部署建议使用 HTTPS

## ⚠️ 注意事项

- 本项目仅供学习研究使用
- 雪球 API 可能随时变更
- 请勿用于自动化实盘交易，风险自负

## 📜 License

MIT
