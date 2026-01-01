# -*- coding: utf-8 -*-
"""
模拟调仓变化测试

模拟场景：检测到跟踪组合发生调仓变化，自动同步到模拟仓
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from xq_simulator import XueQiuSimulator
from utils import logger


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
    
    print("=" * 60)
    print("模拟调仓变化检测测试")
    print("=" * 60)
    
    # 1. 获取当前模拟仓状态
    print("\n【1】当前模拟仓状态:")
    perf = simulator.get_performances(gid)
    print(f"  总资产: {perf.get('assets', 0):,.2f}")
    print(f"  现金: {perf.get('cash', 0):,.2f}")
    print(f"  市值: {perf.get('market_value', 0):,.2f}")
    
    holdings = simulator.get_holdings(gid)
    print("\n  当前持仓:")
    for h in holdings:
        print(f"    {h.get('name')} ({h.get('symbol')}): {h.get('shares')} 股")
    
    # 2. 获取目标组合当前持仓
    print(f"\n【2】目标组合持仓 ({target_code}):")
    current_holdings, cash_weight = simulator.get_portfolio_holdings(target_code)
    print(f"  现金比例: {cash_weight:.2f}%")
    for h in current_holdings:
        print(f"  {h['name']} ({h['symbol']}): {h['weight']:.2f}%")
    
    # 3. 模拟"之前的持仓快照"（假装有一只股票权重变化了）
    print("\n【3】模拟调仓变化检测:")
    print("-" * 40)
    
    # 创建一个"旧的"持仓快照，模拟某只股票的权重变化
    old_holdings_snapshot = {}
    for h in current_holdings:
        old_holdings_snapshot[h["symbol"]] = h["weight"]
    
    # 模拟：假设第一只股票之前的权重比现在少2%
    if current_holdings:
        first_symbol = current_holdings[0]["symbol"]
        old_weight = old_holdings_snapshot[first_symbol]
        simulated_old_weight = old_weight - 2.0  # 假设之前少2%
        
        print(f"  模拟场景: {first_symbol} 权重从 {simulated_old_weight:.2f}% 变为 {old_weight:.2f}%")
        print("  (实际检测时会比较历史调仓记录ID或持仓快照)")
    
    # 4. 检测到变化，触发同步
    print("\n【4】检测到调仓变化！触发自动同步...")
    print("=" * 60)
    
    # 执行同步
    result = simulator.sync_from_portfolio(gid, target_code)
    
    # 5. 显示同步结果
    print("\n【5】同步结果汇总:")
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
            print(f"    {status} {s['name']} ({s['symbol']}): {s['shares']} 股 @ {s['price']:.3f}")
    
    if result.get("skipped"):
        print("\n  跳过（已达目标）:")
        for sk in result["skipped"]:
            print(f"    - {sk['name']} ({sk['symbol']})")
    
    if result.get("errors"):
        print("\n  错误:")
        for e in result["errors"]:
            print(f"    - {e}")
    
    # 6. 验证：查询最新交易记录
    print("\n【6】最新交易记录（确认同步成功）:")
    print("-" * 40)
    transactions = simulator.get_transactions(gid, row=10)
    for t in transactions[:5]:
        action = "买入" if t.get("type") == 1 else "卖出"
        print(f"  {action} {t.get('name')} ({t.get('symbol')}): {t.get('shares')} 股 @ {t.get('price')}")
    
    # 7. 验证：查询最新持仓
    print("\n【7】同步后的模拟仓持仓:")
    print("-" * 40)
    perf_after = simulator.get_performances(gid)
    print(f"  总资产: {perf_after.get('assets', 0):,.2f}")
    print(f"  现金: {perf_after.get('cash', 0):,.2f}")
    
    holdings_after = simulator.get_holdings(gid)
    for h in holdings_after:
        print(f"  {h.get('name')} ({h.get('symbol')}): {h.get('shares')} 股, 市值 {h.get('market_value', 0):,.2f}")
    
    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
