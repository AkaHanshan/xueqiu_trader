# -*- coding: utf-8 -*-
"""
自动跟踪同步示例

监控目标组合的调仓变化，自动同步到模拟仓
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from xq_simulator import XueQiuSimulator


def load_config():
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "user_config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    config = load_config()
    
    simulator = XueQiuSimulator()
    simulator.login()
    
    gid = config.get("simulator_gid", 6522325211190960)
    target_code = config.get("target_portfolio_code", "ZH1783962")
    interval = config.get("track_interval", 30)  # 默认30秒
    
    print("=" * 60)
    print("雪球自动跟踪同步")
    print("=" * 60)
    print(f"  模拟仓 GID: {gid}")
    print(f"  跟踪组合: {target_code}")
    print(f"  轮询间隔: {interval} 秒")
    print("=" * 60)
    print("\n按 Ctrl+C 可停止跟踪\n")
    
    # 启动自动跟踪同步
    # interval: 轮询间隔（秒）
    # max_iterations: 最大轮询次数，None 表示无限循环
    simulator.auto_track_and_sync(
        gid=gid,
        portfolio_code=target_code,
        interval=interval,
        max_iterations=None  # 无限循环，按 Ctrl+C 停止
    )


if __name__ == "__main__":
    main()
