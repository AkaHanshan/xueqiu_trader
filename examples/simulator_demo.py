# -*- coding: utf-8 -*-
"""
雪球模拟仓交易示例
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
    
    print("=" * 50)
    print("雪球模拟仓交易示例")
    print("=" * 50)
    
    # 1. 获取模拟仓列表
    print("\n【1】模拟仓列表:")
    groups = simulator.get_trans_groups()
    for g in groups:
        print(f"  {g['name']} (gid={g['gid']})")
    
    # 2. 获取指定模拟仓的收益
    gid = config.get("simulator_gid", 6522325211190960)
    print(f"\n【2】模拟仓收益 (gid={gid}):")
    perf = simulator.get_performances(gid)
    if perf:
        print(f"  总资产: {perf.get('assets', 0):,.2f}")
        print(f"  本金: {perf.get('principal', 0):,.2f}")
        print(f"  现金: {perf.get('cash', 0):,.2f}")
        print(f"  市值: {perf.get('market_value', 0):,.2f}")
        print(f"  浮动盈亏: {perf.get('float_amount', 0):,.2f} ({perf.get('float_rate', 0)*100:.2f}%)")
        print(f"  累计盈亏: {perf.get('accum_amount', 0):,.2f} ({perf.get('accum_rate', 0)*100:.2f}%)")
    
    # 3. 获取持仓
    print(f"\n【3】模拟仓持仓:")
    holdings = simulator.get_holdings(gid)
    if holdings:
        for h in holdings:
            print(f"  {h.get('name', 'N/A')} ({h.get('symbol', 'N/A')}): {h.get('shares', 0)} 股, 当前价 {h.get('current', 0)}")
    else:
        print("  暂无持仓")
    
    # 4. 获取目标组合持仓
    target_code = config.get("target_portfolio_code", "ZH1783962")
    print(f"\n【4】目标组合持仓 ({target_code}):")
    target_holdings, cash_weight = simulator.get_portfolio_holdings(target_code)
    print(f"  现金比例: {cash_weight:.2f}%")
    for h in target_holdings:
        print(f"  {h['name']} ({h['symbol']}): {h['weight']}%")
    
    # 5. 查询最近交易记录
    print(f"\n【5】最近交易记录:")
    transactions = simulator.get_transactions(gid, row=5)
    if transactions:
        for t in transactions[:5]:
            action = "买入" if t.get("type") == 1 else "卖出"
            print(f"  {action} {t.get('name')} ({t.get('symbol')}): {t.get('shares')} 股 @ {t.get('price')}")
    else:
        print("  暂无交易记录")
    
    print("\n" + "=" * 50)
    
    # 询问是否执行同步
    user_input = input("\n是否执行同步调仓? (输入 y 确认，其他跳过): ")
    if user_input.lower() == 'y':
        print("\n开始执行同步调仓...")
        result = simulator.sync_from_portfolio(gid=gid, portfolio_code=target_code)
        
        print("\n" + "=" * 50)
        print("调仓结果汇总:")
        print("=" * 50)
        
        if "summary" in result:
            print(f"  总资产: {result['summary']['total_assets']:,.2f}")
            print(f"  买入笔数: {result['summary']['buy_count']}")
            print(f"  卖出笔数: {result['summary']['sell_count']}")
            print(f"  错误笔数: {result['summary']['error_count']}")
        
        if result.get("errors"):
            print("\n  错误:")
            for e in result["errors"]:
                print(f"    - {e}")
        
        print("\n  最近交易记录:")
        for t in result.get("recent_transactions", [])[:5]:
            action = "买入" if t.get("type") == 1 else "卖出"
            print(f"    {action} {t.get('name')}: {t.get('shares')} 股 @ {t.get('price')}")
    else:
        print("跳过同步调仓")


if __name__ == "__main__":
    main()

