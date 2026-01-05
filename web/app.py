# -*- coding: utf-8 -*-
"""
雪球交易系统 - Web管理后台

功能:
- 配置管理 (SQLite 数据库)
- 脚本启停控制
- 实时日志显示 (SSE)
- 日志持久化
- 用户登录认证
"""
import json
import os
import subprocess
import sys
import threading
import time
import queue
import secrets
from datetime import datetime
from flask import Flask, render_template, jsonify, request, Response, redirect, url_for, stream_with_context
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from collections import deque

# 获取项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "user_config.json")
EXAMPLES_DIR = os.path.join(BASE_DIR, "examples")
DATA_DIR = os.path.join(BASE_DIR, "data")

# 确保数据目录存在
os.makedirs(DATA_DIR, exist_ok=True)

app = Flask(__name__)

# SQLite 数据库配置
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(DATA_DIR, "xueqiu_trader.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Flask-Login 配置
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or secrets.token_hex(32)

# 确保可以导入 web 模块
sys.path.insert(0, BASE_DIR)

# 初始化数据库
from models import db, init_db, SystemLog, UserConfig, User
init_db(app)

# 初始化 Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = '请先登录'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.before_request
def require_login():
    """保护所有 /api 路由（登录接口除外）"""
    exempt_routes = ['login', 'static']
    if request.endpoint and request.endpoint not in exempt_routes:
        if request.path.startswith('/api') and not current_user.is_authenticated:
            return jsonify({"success": False, "error": "请先登录"}), 401

# 存储运行中的进程
running_processes = {}

# 日志缓存 (最多保存500条)
log_buffer = deque(maxlen=500)
log_lock = threading.Lock()

# SSE 订阅者队列列表
sse_subscribers = []
sse_lock = threading.Lock()

# 可运行的脚本列表
AVAILABLE_SCRIPTS = {
    "auto_track": {
        "name": "自动跟踪同步",
        "file": "auto_track_demo.py",
        "description": "监控目标组合变化，自动同步到模拟仓"
    },
    "simulator": {
        "name": "模拟仓操作",
        "file": "simulator_demo.py",
        "description": "模拟仓交易演示"
    },
    "follower": {
        "name": "组合跟踪",
        "file": "follower_demo.py",
        "description": "跟踪雪球组合调仓信号"
    },
    "trader": {
        "name": "交易演示",
        "file": "trader_demo.py",
        "description": "组合调仓交易演示"
    }
}


def add_log(level: str, message: str, script: str = "system"):
    """添加日志到缓存、数据库并广播给SSE订阅者（双通道）"""
    # 强制清理消息中的非法字符，确保 JSON 序列化安全
    safe_message = str(message).replace('\x00', '').strip()
    
    log_entry = {
        "type": "log",
        "time": datetime.now().strftime("%H:%M:%S"),
        "level": level,
        "script": script,
        "message": safe_message
    }
    
    with log_lock:
        log_buffer.append(log_entry)
    
    # 持久化到数据库（线程安全）
    try:
        with app.app_context():
            SystemLog.add(level=level, message=safe_message, module=script)
    except Exception as e:
        print(f"日志写入数据库失败: {e}")
    
    # 广播给所有SSE订阅者
    broadcast_sse(log_entry)


def broadcast_script_status():
    """广播所有脚本状态给SSE订阅者"""
    scripts = []
    for script_id, info in AVAILABLE_SCRIPTS.items():
        scripts.append({
            "id": script_id,
            "name": info["name"],
            "running": script_id in running_processes
        })
    
    status_event = {
        "type": "script_status",
        "scripts": scripts
    }
    broadcast_sse(status_event)


def broadcast_sse(event_data):
    """广播事件给所有SSE订阅者"""
    with sse_lock:
        dead_subscribers = []
        for q in sse_subscribers:
            try:
                q.put_nowait(event_data)
            except:
                dead_subscribers.append(q)
        # 清理断开的订阅者
        for q in dead_subscribers:
            sse_subscribers.remove(q)


def read_process_output(process, script_id):
    """读取进程输出并添加到日志"""
    script_name = AVAILABLE_SCRIPTS.get(script_id, {}).get("name", script_id)
    
    try:
        for line in iter(process.stdout.readline, ''):
            if line:
                line = line.strip()
                level = "error" if "ERROR" in line.upper() else "info"
                add_log(level, line, script_name)
            if process.poll() is not None:
                break
    except Exception as e:
        add_log("error", f"读取输出失败: {e}", script_name)
    
    # 进程结束
    exit_code = process.poll()
    if exit_code != 0:
        add_log("error", f"进程异常退出，退出码: {exit_code}", script_name)
    else:
        add_log("info", "进程已停止", script_name)
    
    # 从运行列表中移除
    if script_id in running_processes:
        del running_processes[script_id]
    
    # 广播状态变化
    broadcast_script_status()


def generate_sse_stream():
    """生成SSE事件流 - Waitress 优化版"""
    import traceback
    q = queue.Queue()
    
    with sse_lock:
        sse_subscribers.append(q)
    
    try:
        # 1. 先发送历史日志
        with log_lock:
            for log in log_buffer:
                yield f"event: log\ndata: {json.dumps(log, ensure_ascii=False)}\n\n"
        
        # 2. 发送当前脚本状态
        scripts = []
        for script_id, info in AVAILABLE_SCRIPTS.items():
            scripts.append({
                "id": script_id,
                "name": info["name"],
                "running": script_id in running_processes
            })
        yield f"event: script_status\ndata: {json.dumps({'type': 'script_status', 'scripts': scripts}, ensure_ascii=False)}\n\n"
        
        # 3. 持续推送循环
        while True:
            try:
                # 将超时时间缩短到 15 秒，确保 Waitress 线程活跃
                event = q.get(timeout=15)
                event_type = event.get("type", "log")
                payload = json.dumps(event, ensure_ascii=False)
                yield f"event: {event_type}\ndata: {payload}\n\n"
            except queue.Empty:
                # 关键：发送心跳注释行，这是 SSE 标准，不会被前端解析但能保活连接
                yield ": heartbeat\n\n"
            except Exception as e:
                # 记录序列化错误但不跳出循环
                print(f"SSE 序列化异常: {e}")
                continue

    except GeneratorExit:
        # 正常连接关闭，不要抛出异常
        pass
    except Exception as e:
        print("\n!!! SSE 生成器运行时崩溃 !!!")
        traceback.print_exc()
    finally:
        with sse_lock:
            if q in sse_subscribers:
                sse_subscribers.remove(q)


@app.route("/api/logs/stream")
@login_required
def log_stream():
    """SSE日志流端点 - 修复 PEP 3333 协议冲突"""
    return Response(
        stream_with_context(generate_sse_stream()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            # Connection 是 hop-by-hop header，不能由 WSGI 应用设置 (PEP 3333)
            # Waitress 会自动处理连接保活
            'X-Accel-Buffering': 'no'  # 仅保留针对 Nginx 的优化头
        }
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    """登录页面"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user, remember=True)
            user.last_login = datetime.utcnow()
            db.session.commit()
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        
        return render_template("login.html", error="用户名或密码错误")
    
    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    """登出"""
    logout_user()
    return redirect(url_for('login'))


@app.route("/")
@login_required
def index():
    """主页"""
    return render_template("index.html")


@app.route("/api/config", methods=["GET"])
@login_required
def get_config():
    """获取配置"""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        # 隐藏敏感的 cookies 完整内容
        if "cookies" in config:
            cookies = config["cookies"]
            if len(cookies) > 50:
                config["cookies_preview"] = cookies[:30] + "..." + cookies[-20:]
            else:
                config["cookies_preview"] = cookies
        return jsonify({"success": True, "config": config})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/config", methods=["POST"])
def save_config():
    """保存配置"""
    try:
        data = request.json
        
        # 读取现有配置
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        
        # 检查 cookies 是否变化（用于判断是否需要重启脚本）
        old_cookies = config.get("cookies", "")
        new_cookies = data.get("cookies", "")
        cookies_changed = old_cookies != new_cookies
        
        # 更新配置（不覆盖未提供的字段）
        for key, value in data.items():
            if key != "cookies_preview":  # 跳过预览字段
                config[key] = value
        
        # 保存到 JSON 文件
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
        
        # 同时保存到数据库
        try:
            with app.app_context():
                from models import UserConfig
                descriptions = {
                    "cookies": "雪球登录 Cookies",
                    "portfolio_code": "默认组合代码",
                    "target_portfolio_code": "目标跟踪组合代码",
                    "simulator_gid": "模拟仓 GID",
                    "my_portfolio_code": "我的组合代码列表",
                    "track_interval": "轮询间隔（秒）",
                    "initial_assets": "初始资产",
                    "portfolio_market": "组合市场（cn/us）"
                }
                for key, value in data.items():
                    if key != "cookies_preview":
                        UserConfig.set(
                            key=key,
                            value=value,
                            description=descriptions.get(key, f"配置项: {key}")
                        )
        except Exception as db_error:
            add_log("warning", f"配置保存到数据库失败（已保存到文件）: {db_error}")
        
        # 如果 cookies 变化，检查是否有运行中的脚本需要重启
        scripts_to_restart = []
        if cookies_changed:
            # 检查哪些脚本正在运行（这些脚本可能使用了旧的 cookies）
            for script_id in running_processes.keys():
                scripts_to_restart.append(script_id)
        
        add_log("info", "配置已保存到文件和数据库")
        
        response_data = {"success": True}
        if cookies_changed and scripts_to_restart:
            response_data["warning"] = f"Cookies 已更新，建议重启以下运行中的脚本: {', '.join(scripts_to_restart)}"
            response_data["scripts_to_restart"] = scripts_to_restart
        
        return jsonify(response_data)
    except Exception as e:
        add_log("error", f"保存配置失败: {e}")
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/scripts", methods=["GET"])
def get_scripts():
    """获取脚本列表及状态"""
    scripts = []
    for script_id, info in AVAILABLE_SCRIPTS.items():
        scripts.append({
            "id": script_id,
            "name": info["name"],
            "description": info["description"],
            "running": script_id in running_processes
        })
    return jsonify({"success": True, "scripts": scripts})


@app.route("/api/scripts/<script_id>/start", methods=["POST"])
def start_script(script_id):
    """启动脚本"""
    if script_id not in AVAILABLE_SCRIPTS:
        return jsonify({"success": False, "error": "脚本不存在"})
    
    if script_id in running_processes:
        return jsonify({"success": False, "error": "脚本已在运行中"})
    
    script_file = AVAILABLE_SCRIPTS[script_id]["file"]
    script_path = os.path.join(EXAMPLES_DIR, script_file)
    
    if not os.path.exists(script_path):
        return jsonify({"success": False, "error": f"脚本文件不存在: {script_file}"})
    
    try:
        # 启动子进程
        process = subprocess.Popen(
            [sys.executable, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            text=True,
            bufsize=1,
            cwd=BASE_DIR
        )
        
        running_processes[script_id] = process
        
        # 启动输出读取线程
        output_thread = threading.Thread(
            target=read_process_output,
            args=(process, script_id),
            daemon=True
        )
        output_thread.start()
        
        add_log("info", f"脚本已启动: {AVAILABLE_SCRIPTS[script_id]['name']}")
        broadcast_script_status()  # 广播状态变化
        return jsonify({"success": True})
    except Exception as e:
        add_log("error", f"启动脚本失败: {e}")
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/scripts/<script_id>/stop", methods=["POST"])
def stop_script(script_id):
    """停止脚本"""
    if script_id not in running_processes:
        return jsonify({"success": False, "error": "脚本未在运行"})
    
    try:
        process = running_processes[script_id]
        process.terminate()
        
        # 等待进程结束
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
        
        if script_id in running_processes:
            del running_processes[script_id]
        
        add_log("info", f"脚本已停止: {AVAILABLE_SCRIPTS[script_id]['name']}")
        broadcast_script_status()  # 广播状态变化
        return jsonify({"success": True})
    except Exception as e:
        add_log("error", f"停止脚本失败: {e}")
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/logs", methods=["GET"])
def get_logs():
    """获取日志"""
    since = request.args.get("since", "0")
    
    with log_lock:
        logs = list(log_buffer)
    
    return jsonify({
        "success": True,
        "logs": logs,
        "running": list(running_processes.keys())
    })


@app.route("/api/logs/clear", methods=["POST"])
def clear_logs():
    """清空日志"""
    with log_lock:
        log_buffer.clear()
    return jsonify({"success": True})


@app.route("/api/logs/history", methods=["GET"])
def get_logs_history():
    """获取历史日志（从数据库）"""
    limit = request.args.get("limit", 100, type=int)
    module = request.args.get("module")
    level = request.args.get("level")
    
    try:
        logs = SystemLog.get_recent(limit=limit, module=module, level=level)
        return jsonify({
            "success": True,
            "logs": [log.to_dict() for log in reversed(logs)]  # 按时间正序
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/portfolio/<portfolio_code>", methods=["GET"])
def get_portfolio_info(portfolio_code):
    """获取组合详细信息"""
    try:
        # 导入模拟器
        sys.path.insert(0, BASE_DIR)
        from xq_simulator import XueQiuSimulator
        
        simulator = XueQiuSimulator()
        simulator.login()
        
        # 获取组合持仓
        holdings, cash_weight = simulator.get_portfolio_holdings(portfolio_code)
        
        # 获取组合基本信息
        info = {
            "code": portfolio_code,
            "name": "",
            "cash_weight": cash_weight,
            "holdings": holdings,
            "total_weight": sum(h["weight"] for h in holdings) + cash_weight
        }
        
        # 尝试获取组合名称
        try:
            import requests
            url = f"https://xueqiu.com/cubes/nav_daily/all.json?cube_symbol={portfolio_code}"
            headers = simulator.session.headers.copy()
            resp = simulator.session.get(url)
            data = resp.json()
            if data and len(data) > 0:
                info["name"] = data[0].get("name", portfolio_code)
                info["net_value"] = data[0].get("value", 1.0)
                info["daily_gain"] = data[0].get("daily_gain", 0)
        except:
            info["name"] = portfolio_code
        
        return jsonify({"success": True, "portfolio": info})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/simulator/<int:gid>", methods=["GET"])
def get_simulator_info(gid):
    """获取模拟仓详细信息"""
    try:
        sys.path.insert(0, BASE_DIR)
        from xq_simulator import XueQiuSimulator
        
        simulator = XueQiuSimulator()
        simulator.login()
        
        # 获取模拟仓持仓和表现
        holdings = simulator.get_holdings(gid)
        perf = simulator.get_performances(gid)
        
        info = {
            "gid": gid,
            "total_assets": perf.get("assets", 0),
            "cash": perf.get("cash", 0),
            "market_value": perf.get("market_value", 0),
            "profit": perf.get("profit", 0),
            "profit_rate": perf.get("profit_rate", 0),
            "holdings": holdings
        }
        
        return jsonify({"success": True, "simulator": info})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


if __name__ == "__main__":
    add_log("info", "Web管理后台已启动")
    print("=" * 50)
    print("雪球交易系统 - Web管理后台")
    print("=" * 50)
    print("访问地址: http://127.0.0.1:5000")
    print("按 Ctrl+C 停止服务")
    print("=" * 50)
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
