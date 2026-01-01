# -*- coding: utf-8 -*-
"""
真实调仓同步测试

场景：
1. 先卖出模拟仓中一只转债，制造与目标组合的差异
2. 模拟检测到调仓变化
3. 触发同步，买回卖出的转债
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
    print("真实调仓同步测试")
    print("=" * 60)
    
    # 1. 获取当前模拟仓状态
    print("\n【1】当前模拟仓持仓:")
    holdings = simulator.get_holdings(gid)
    for h in holdings:
        print(f"  {h.get('name')} ({h.get('symbol')}): {h.get('shares')} 股")
    
    if not holdings:
        print("  模拟仓为空，请先运行 simulator_demo.py 同步一次")
        return
    
    # 2. 卖出第一只转债，制造与目标的差异
    print("\n【2】卖出第一只转债，制造差异:")
    print("-" * 40)
    
    # 获取第一只持仓
    first_holding = holdings[0]
    symbol_to_sell = first_holding["symbol"]
    shares_to_sell = int(first_holding["shares"])
    current_price = float(first_holding["current"])
    
    if shares_to_sell <= 0:
        print(f"  {symbol_to_sell} 持仓为0，跳过卖出")
        # 尝试找一个有持仓的
        for h in holdings:
            if float(h.get("shares", 0)) > 0:
                first_holding = h
                symbol_to_sell = h["symbol"]
                shares_to_sell = int(h["shares"])
                current_price = float(h["current"])
                break
    
    print(f"  准备卖出: {first_holding.get('name')} ({symbol_to_sell})")
    print(f"  卖出数量: {shares_to_sell} 股")
    print(f"  卖出价格: {current_price}")
    
    # 执行卖出
    sell_success = simulator.sell(gid, symbol_to_sell, current_price, shares_to_sell)
    if sell_success:
        print(f"  ✓ 卖出成功！")
    else:
        print(f"  ✗ 卖出失败")
        return
    
    # 3. 查看卖出后的持仓状态
    print("\n【3】卖出后的模拟仓持仓:")
    print("-" * 40)
    holdings_after_sell = simulator.get_holdings(gid)
    for h in holdings_after_sell:
        status = "(已清仓)" if h.get("symbol") == symbol_to_sell and float(h.get("shares", 0)) == 0 else ""
        print(f"  {h.get('name')} ({h.get('symbol')}): {h.get('shares')} 股 {status}")
    
    perf = simulator.get_performances(gid)
    print(f"\n  当前现金: {perf.get('cash', 0):,.2f}")
    
    # 4. 获取目标组合持仓
    print(f"\n【4】目标组合持仓 ({target_code}):")
    print("-" * 40)
    target_holdings, cash_weight = simulator.get_portfolio_holdings(target_code)
    print(f"  现金比例: {cash_weight:.2f}%")
    for h in target_holdings:
        flag = " <-- 需要买回" if h["symbol"] == symbol_to_sell else ""
        print(f"  {h['name']} ({h['symbol']}): {h['weight']:.2f}%{flag}")
    
    # 5. 模拟检测到调仓变化，触发同步
    print("\n【5】检测到差异！触发自动同步...")
    print("=" * 60)
    
    result = simulator.sync_from_portfolio(gid, target_code)
    
    # 6. 显示同步结果
    print("\n【6】同步结果汇总:")
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
    
    # 7. 验证最终持仓
    print("\n【7】同步后的最终持仓:")
    print("-" * 40)
    holdings_final = simulator.get_holdings(gid)
    for h in holdings_final:
        print(f"  {h.get('name')} ({h.get('symbol')}): {h.get('shares')} 股")
    
    perf_final = simulator.get_performances(gid)
    print(f"\n  总资产: {perf_final.get('assets', 0):,.2f}")
    print(f"  现金: {perf_final.get('cash', 0):,.2f}")
    
    # 8. 查询交易记录确认
    print("\n【8】最新交易记录（验证调仓）:")
    print("-" * 40)
    transactions = simulator.get_transactions(gid, row=5)
    for t in transactions[:5]:
        action = "买入" if t.get("type") == 1 else "卖出"
        print(f"  {action} {t.get('name')}: {t.get('shares')} 股 @ {t.get('price')}")
    
    print("\n" + "=" * 60)
    print("测试完成！成功模拟了调仓同步流程：")
    print("  1. 卖出一只转债制造差异")
    print("  2. 检测到与目标组合的差异")
    print("  3. 自动买回转债恢复目标持仓")
    print("=" * 60)


if __name__ == "__main__":
    main()
