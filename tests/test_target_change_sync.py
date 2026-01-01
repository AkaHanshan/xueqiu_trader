# -*- coding: utf-8 -*-
"""
模拟目标组合调仓测试

场景：
1. 使用用户自己的组合 (ZH3562685) 作为目标组合
2. 通过 XueQiuTrader 对目标组合进行调仓（改变权重）
3. 检测到目标组合变化
4. 自动同步到模拟仓
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from xq_simulator import XueQiuSimulator
from xqtrader import XueQiuTrader
from utils import logger


def load_config():
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "user_config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    config = load_config()
    
    # 模拟仓
    simulator = XueQiuSimulator()
    simulator.login()
    
    # 目标组合调仓器（用于修改目标组合）
    trader = XueQiuTrader(initial_assets=config.get("initial_assets", 1000000))
    trader.prepare_account(
        cookies=config["cookies"],
        portfolio_code=config.get("my_portfolio_code", ["ZH3562685"])[0],  # 使用用户自己的组合
        portfolio_market=config.get("portfolio_market", "cn")
    )
    
    gid = config.get("simulator_gid", 6522325211190960)
    # 使用用户自己的组合作为目标（这样我们可以修改它来模拟调仓）
    my_portfolios = config.get("my_portfolio_code", ["ZH3562685"])
    target_code = my_portfolios[0] if my_portfolios else "ZH3562685"
    
    print("=" * 60)
    print("模拟目标组合调仓 -> 自动同步测试")
    print("=" * 60)
    print(f"  目标组合: {target_code}")
    print(f"  模拟仓 GID: {gid}")
    print("=" * 60)
    
    # 1. 获取当前目标组合持仓（作为"旧状态"）
    print("\n【1】当前目标组合持仓 (变更前):")
    old_holdings, old_cash = simulator.get_portfolio_holdings(target_code)
    print(f"  现金比例: {old_cash:.2f}%")
    for h in old_holdings:
        print(f"  {h['name']} ({h['symbol']}): {h['weight']:.2f}%")
    
    if not old_holdings:
        print("\n  目标组合为空，先添加一只股票...")
        # 买入一只可转债
        result = trader.adjust_weight("SZ123091", 50)  # 长海转债 50%
        if result:
            print(f"  添加失败: {result}")
        else:
            print("  添加成功！")
        time.sleep(1)
        old_holdings, old_cash = simulator.get_portfolio_holdings(target_code)
    
    # 记录旧状态快照
    old_snapshot = {h["symbol"]: h["weight"] for h in old_holdings}
    
    # 2. 获取当前模拟仓持仓
    print("\n【2】当前模拟仓持仓:")
    sim_holdings = simulator.get_holdings(gid)
    perf = simulator.get_performances(gid)
    print(f"  总资产: {perf.get('assets', 0):,.2f}")
    print(f"  现金: {perf.get('cash', 0):,.2f}")
    for h in sim_holdings:
        print(f"  {h.get('name')} ({h.get('symbol')}): {h.get('shares')} 股")
    
    # 3. 对目标组合进行调仓（模拟目标组合变化）
    print("\n【3】对目标组合进行调仓（模拟调仓变化）...")
    print("-" * 40)
    
    if old_holdings:
        # 选择第一只股票，改变其权重
        first_stock = old_holdings[0]
        old_weight = first_stock["weight"]
        # 如果权重大于30%就减少，否则增加
        new_weight = old_weight - 10 if old_weight > 30 else old_weight + 10
        new_weight = max(0, min(100, new_weight))  # 确保在0-100之间
        
        print(f"  调整 {first_stock['name']} ({first_stock['symbol']}):")
        print(f"    {old_weight:.2f}% -> {new_weight:.2f}%")
        
        # 执行调仓
        result = trader.adjust_weight(first_stock["symbol"], new_weight)
        if result:
            print(f"  调仓失败: {result}")
            return
        else:
            print("  ✓ 目标组合调仓成功！")
    else:
        print("  目标组合为空，无法调仓")
        return
    
    # 等待API更新
    print("\n  等待2秒让API更新...")
    time.sleep(2)
    
    # 4. 获取调仓后的目标组合持仓
    print("\n【4】调仓后的目标组合持仓 (变更后):")
    new_holdings, new_cash = simulator.get_portfolio_holdings(target_code)
    print(f"  现金比例: {new_cash:.2f}%")
    for h in new_holdings:
        old_w = old_snapshot.get(h["symbol"], 0)
        change = ""
        if h["weight"] != old_w:
            change = f" (变化: {old_w:.2f}% -> {h['weight']:.2f}%)"
        print(f"  {h['name']} ({h['symbol']}): {h['weight']:.2f}%{change}")
    
    # 5. 检测变化
    print("\n【5】检测目标组合变化:")
    print("-" * 40)
    
    new_snapshot = {h["symbol"]: h["weight"] for h in new_holdings}
    changes_detected = []
    
    # 比较变化
    all_symbols = set(list(old_snapshot.keys()) + list(new_snapshot.keys()))
    for symbol in all_symbols:
        old_w = old_snapshot.get(symbol, 0)
        new_w = new_snapshot.get(symbol, 0)
        if abs(old_w - new_w) > 0.01:  # 超过0.01%的变化
            changes_detected.append({
                "symbol": symbol,
                "old_weight": old_w,
                "new_weight": new_w,
            })
    
    if changes_detected:
        print("  ✓ 检测到持仓变化！")
        for c in changes_detected:
            print(f"    {c['symbol']}: {c['old_weight']:.2f}% -> {c['new_weight']:.2f}%")
    else:
        print("  未检测到变化")
        return
    
    # 6. 触发同步到模拟仓
    print("\n【6】触发自动同步到模拟仓...")
    print("=" * 60)
    
    result = simulator.sync_from_portfolio(gid, target_code)
    
    # 7. 显示同步结果
    print("\n【7】同步结果汇总:")
    print("=" * 60)
    
    if "summary" in result:
        print(f"  总资产: {result['summary']['total_assets']:,.2f}")
        print(f"  买入笔数: {result['summary']['buy_count']}")
        print(f"  卖出笔数: {result['summary']['sell_count']}")
        print(f"  错误笔数: {result['summary']['error_count']}")
    
    if result.get("buys"):
        print("\n  买入操作:")
        for b in result["buys"]:
            status = "✓" if b["success"] else "✗"
            print(f"    {status} {b['name']} ({b['symbol']}): {b['shares']} 股 @ {b['price']:.3f}")
    
    if result.get("sells"):
        print("\n  卖出操作:")
        for s in result["sells"]:
            status = "✓" if s["success"] else "✗"
            print(f"    {status} {s['name']} ({s['symbol']}): {s['shares']} 股")
    
    # 8. 验证最终持仓
    print("\n【8】同步后的模拟仓持仓:")
    print("-" * 40)
    holdings_final = simulator.get_holdings(gid)
    perf_final = simulator.get_performances(gid)
    print(f"  总资产: {perf_final.get('assets', 0):,.2f}")
    print(f"  现金: {perf_final.get('cash', 0):,.2f}")
    for h in holdings_final:
        print(f"  {h.get('name')} ({h.get('symbol')}): {h.get('shares')} 股")
    
    print("\n" + "=" * 60)
    print("测试完成！成功模拟了目标组合调仓触发模拟仓同步的流程：")
    print("  1. 记录目标组合原始状态")
    print("  2. 对目标组合进行调仓（改变权重）")
    print("  3. 检测到目标组合变化")
    print("  4. 自动同步到模拟仓")
    print("=" * 60)


if __name__ == "__main__":
    main()
