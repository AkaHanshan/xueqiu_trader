# XueQiu Trader - 雪球组合交易与跟踪系统

基于 [easytrader](https://github.com/shidenggui/easytrader) 实现的雪球组合调仓、跟踪和模拟交易功能。

## ✨ 功能特性

### 核心模块

| 模块 | 功能 | 说明 |
|------|------|------|
| **XueQiuTrader** | 组合调仓 | Cookie认证、按权重/金额/股数调仓 |
| **XueQiuFollower** | 组合跟踪 | 轮询调仓历史、权重变化转信号、指令缓存 |
| **XueQiuSimulator** | 模拟仓交易 | 模拟账户买卖、同步目标组合、自动跟踪 |

### Web 管理后台 🆕

- **可视化配置管理** - 在线编辑 `user_config.json`
- **脚本控制** - 一键启停各类演示脚本
- **实时日志 (SSE)** - 零轮询，服务端推送日志流
- **组合详情弹窗** - 点击查看持仓、净值、收益率
- **脚本状态实时推送** - 启动/停止状态瞬间反馈

## 📁 项目结构

```
xueqiu_trader/
├── config/
│   ├── xq.json              # API 配置
│   └── user_config.json     # 用户配置
├── utils/
│   ├── log.py               # 日志模块
│   └── misc.py              # 工具函数
├── xqtrader.py              # 调仓模块
├── xq_follower.py           # 跟踪模块
├── xq_simulator.py          # 模拟仓模块 🆕
├── exceptions.py            # 异常定义
├── examples/                # 演示脚本
│   ├── trader_demo.py       # 调仓示例
│   ├── follower_demo.py     # 跟踪示例
│   ├── simulator_demo.py    # 模拟仓示例 🆕
│   └── auto_track_demo.py   # 自动跟踪示例 🆕
├── tests/                   # 测试脚本 🆕
│   ├── test_real_sync.py
│   ├── test_rebalance_sync.py
│   └── test_target_change_sync.py
└── web/                     # Web管理后台 🆕
    ├── app.py               # Flask 后端
    ├── templates/
    │   └── index.html       # 页面模板
    └── static/
        ├── css/style.css    # 样式
        └── js/app.js        # 前端逻辑
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 Cookies

编辑 `config/user_config.json`:

```json
{
    "cookies": "your_xueqiu_cookies_here",
    "portfolio_code": "ZH123456",
    "target_portfolio_code": "ZH654321",
    "simulator_gid": 1234567890,
    "my_portfolio_code": ["ZH123456"],
    "track_interval": 30,
    "initial_assets": 1000000
}
```

**获取 Cookies:**
1. 登录 https://xueqiu.com
2. F12 打开开发者工具 → Network
3. 刷新页面，复制请求头中的 Cookie

### 3. 启动 Web 管理后台

```bash
python web/app.py
```

访问 http://127.0.0.1:5000

### 4. 运行演示脚本

```bash
python examples/trader_demo.py      # 调仓演示
python examples/follower_demo.py    # 跟踪演示
python examples/simulator_demo.py   # 模拟仓演示
python examples/auto_track_demo.py  # 自动跟踪
```

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

# 自动跟踪（持续监控并同步）
simulator.auto_track_and_sync(
    gid=1234567890,
    target_code="ZH654321",
    interval=30
)
```

### 组合跟踪

```python
from xq_follower import XueQiuFollower

follower = XueQiuFollower()
follower.login(cookies="your_cookies")

follower.follow(
    strategies=["ZH123456"],
    total_assets=100000,
    track_interval=10
)
```

## 🌐 Web API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/config` | GET/POST | 配置管理 |
| `/api/scripts` | GET | 脚本列表和状态 |
| `/api/scripts/<id>/start` | POST | 启动脚本 |
| `/api/scripts/<id>/stop` | POST | 停止脚本 |
| `/api/logs/stream` | GET | SSE 日志流 |
| `/api/portfolio/<code>` | GET | 组合详情 |
| `/api/simulator/<gid>` | GET | 模拟仓详情 |

## ⚠️ 注意事项

- 本项目仅供学习研究使用
- 雪球 API 可能随时变更
- 请勿用于自动化实盘交易，风险自负

## 📜 License

MIT
