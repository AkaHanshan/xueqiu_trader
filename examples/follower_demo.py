# -*- coding: utf-8 -*-
"""
雪球跟单示例

使用方法:
1. 编辑 config/user_config.json，填入您的 cookies
2. 修改 STRATEGY_CODE 为您要跟踪的组合代码
3. 运行此脚本

注意:
- 此示例仅打印跟踪信号，不执行实盘交易
- 如需实盘交易，需要配合 easytrader 使用
"""
import json
import os
import sys

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from xq_follower import XueQiuFollower


def load_config():
    """加载用户配置"""
    config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "config",
        "user_config.json"
    )
    
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    # 加载配置
    config = load_config()
    
    # 检查 cookies 是否已配置
    if "请在此处粘贴" in config["cookies"]:
        print("请先在 config/user_config.json 中配置您的 cookies!")
        print("获取方法: 登录 xueqiu.com -> F12 -> Network -> 复制 Cookie")
        return
    
    # 要跟踪的组合代码（可以修改为任意公开组合）
    STRATEGY_CODE = config.get("portfolio_code", "ZH123456")
    TOTAL_ASSETS = config.get("initial_assets", 100000)
    TRACK_INTERVAL = config.get("track_interval", 10)
    
    print("=" * 50)
    print("雪球组合跟踪示例")
    print("=" * 50)
    print(f"跟踪组合: {STRATEGY_CODE}")
    print(f"虚拟资产: {TOTAL_ASSETS}")
    print(f"轮询间隔: {TRACK_INTERVAL} 秒")
    print("=" * 50)
    
    # 初始化跟踪端
    follower = XueQiuFollower()
    
    # 登录
    follower.login(cookies=config["cookies"])
    
    # 先获取一些调仓记录看看
    print("\n【最近调仓记录】")
    try:
        transactions = follower.get_transactions(STRATEGY_CODE, count=5)
        if transactions:
            for t in transactions[:3]:
                status = t.get("status", "N/A")
                holdings = t.get("rebalancing_histories", [])
                print(f"\n  状态: {status}")
                for h in holdings[:2]:
                    name = h.get("stock_name", "未知")
                    prev = h.get("prev_weight", 0) or 0
                    target = h.get("target_weight", 0) or 0
                    print(f"    {name}: {prev:.2f}% -> {target:.2f}%")
        else:
            print("  暂无调仓记录")
    except Exception as e:
        print(f"  获取失败: {e}")
    
    print("\n" + "=" * 50)
    print("开始跟踪（按 Ctrl+C 停止）...")
    print("=" * 50)
    
    # 开始跟踪
    # 注意：这里没有传入 users 参数，所以只会打印信号，不会执行交易
    try:
        follower.follow(
            strategies=[STRATEGY_CODE],
            total_assets=TOTAL_ASSETS,
            track_interval=TRACK_INTERVAL,
            cmd_cache=True,  # 使用缓存避免重复执行
        )
    except KeyboardInterrupt:
        print("\n跟踪已停止")


if __name__ == "__main__":
    main()
