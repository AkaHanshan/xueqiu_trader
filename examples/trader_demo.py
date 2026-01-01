# -*- coding: utf-8 -*-
"""
雪球调仓示例
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from xqtrader import XueQiuTrader


def load_config():
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "user_config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    config = load_config()
    
    if "请在此处粘贴" in config["cookies"]:
        print("请先在 config/user_config.json 中配置您的 cookies!")
        return
    
    trader = XueQiuTrader(initial_assets=config.get("initial_assets", 1000000))
    trader.prepare_account(
        cookies=config["cookies"],
        portfolio_code=config["portfolio_code"],
        portfolio_market=config.get("portfolio_market", "cn")
    )
    
    print("=" * 50)
    print("雪球组合调仓示例")
    print("=" * 50)
    
    # 1. 获取账户余额
    print("\n【1】获取账户资金:")
    try:
        balance = trader.get_balance()
        print(f"  总资产: {balance[0]['asset_balance']:.2f}")
        print(f"  可用资金: {balance[0]['current_balance']:.2f}")
        print(f"  市值: {balance[0]['market_value']:.2f}")
    except Exception as e:
        print(f"  获取失败: {e}")
    
    # 2. 获取当前持仓
    print("\n【2】获取当前持仓:")
    try:
        positions = trader.get_position()
        if positions:
            for pos in positions:
                print(f"  {pos['stock_name']} ({pos['stock_code']}): 权重 {pos['weight']:.2f}%")
        else:
            print("  暂无持仓")
    except Exception as e:
        print(f"  获取失败: {e}")
    
    # 3. 获取关注的组合列表
    print("\n【3】关注的组合 (portfolio_code):")
    try:
        followed = trader.get_followed_portfolios()
        if followed:
            for code in followed:
                print(f"  {code}")
        else:
            print("  暂无关注组合")
    except Exception as e:
        print(f"  获取失败: {e}")
    
    # 4. 获取我创建的组合
    print("\n【4】我创建的组合:")
    try:
        my_portfolios = trader.get_my_portfolios()
        if my_portfolios:
            for code in my_portfolios:
                print(f"  {code}")
        else:
            print("  暂无组合")
    except Exception as e:
        print(f"  获取失败: {e}")
    
    # 5. 获取我创建的组合的详细内容
    print("\n【5】我创建的组合详情:")
    try:
        my_portfolios = trader.get_my_portfolios()
        for code in my_portfolios:
            info = trader.get_public_portfolio(code)
            if info:
                print(f"\n  组合: {code}")
                print(f"  净值: {info.get('net_value', 0)}")
                print(f"  现金: {info.get('cash', 0)}%")
                print(f"  持仓:")
                for h in info.get("holdings", []):
                    print(f"    - {h['name']} ({h['symbol']}): {h['weight']}%")
    except Exception as e:
        print(f"  获取失败: {e}")
    
    print("\n" + "=" * 50)


if __name__ == "__main__":
    main()
