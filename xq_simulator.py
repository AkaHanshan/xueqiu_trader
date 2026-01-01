# -*- coding: utf-8 -*-
"""
雪球模拟仓交易模块 - XueQiuSimulator

实现模拟仓的交易操作，包括：
- 获取模拟仓列表
- 获取模拟仓持仓
- 获取模拟仓收益
- 买入/卖出股票
- 查询交易记录
- 跟踪组合进行调仓
"""
import json
import os
from datetime import datetime

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from exceptions import TradeError
from utils import logger, parse_cookies_str


class XueQiuSimulator:
    """
    雪球模拟仓交易类
    
    使用方法:
        simulator = XueQiuSimulator()
        simulator.login(cookies="your_cookies")
        
        # 获取模拟仓列表
        groups = simulator.get_trans_groups()
        
        # 获取持仓
        holdings = simulator.get_holdings(gid=6522325211190960)
        
        # 买入
        simulator.buy(gid=6522325211190960, symbol="SZ123091", price=127.21, shares=100)
        
        # 跟踪组合调仓
        simulator.sync_from_portfolio(gid=6522325211190960, portfolio_code="ZH1783962")
    """
    
    # API 端点
    BASE_URL = "https://tc.xueqiu.com/tc/snowx/MONI"
    STOCK_SEARCH_URL = "https://xueqiu.com/query/v1/search/stock.json"
    
    _HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Pragma": "no-cache",
        "Connection": "keep-alive",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Referer": "https://xueqiu.com/",
        "X-Requested-With": "XMLHttpRequest",
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update(self._HEADERS)
        self.config = self._load_user_config()
        
        # 默认税率和佣金率（千分位）
        self.tax_rate = 0.5
        self.commission_rate = 0.05
    
    def _load_user_config(self) -> dict:
        config_path = os.path.join(os.path.dirname(__file__), "config", "user_config.json")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    
    def login(self, cookies: str = None):
        """登录（设置 cookies）"""
        if cookies is None:
            cookies = self.config.get("cookies", "")
        if not cookies:
            raise TradeError("需要设置 cookies")
        
        cookie_dict = parse_cookies_str(cookies)
        self.session.cookies.update(cookie_dict)
        logger.info("模拟仓登录成功")
    
    def get_trans_groups(self) -> list:
        """
        获取模拟仓列表
        
        :return: 模拟仓列表，包含 gid, name, cash 等信息
        """
        url = f"{self.BASE_URL}/trans_group/list.json"
        resp = self.session.get(url)
        
        try:
            result = resp.json()
            if result.get("success"):
                return result.get("result_data", {}).get("trans_groups", [])
            else:
                logger.error("获取模拟仓列表失败: %s", result.get("msg"))
                return []
        except Exception as e:
            logger.error("获取模拟仓列表失败: %s", e)
            return []
    
    def get_holdings(self, gid: int, period: str = "1m") -> list:
        """
        获取模拟仓持仓（从 performances API 获取更详细持仓）
        
        :param gid: 模拟仓 ID
        :param period: 时间周期
        :return: 持仓列表
        """
        # 从 performances 获取更完整的持仓信息
        url = f"{self.BASE_URL}/performances.json"
        params = {"gid": gid}
        resp = self.session.get(url, params=params)
        
        try:
            result = resp.json()
            if result.get("success"):
                performances = result.get("result_data", {}).get("performances", [])
                holdings = []
                for perf in performances:
                    market_list = perf.get("list", [])
                    if isinstance(market_list, list):
                        for stock in market_list:
                            if stock.get("symbol"):
                                holdings.append({
                                    "symbol": stock.get("symbol"),
                                    "name": stock.get("name"),
                                    "shares": stock.get("shares", 0),
                                    "current": stock.get("current", 0),
                                    "market_value": stock.get("market_value", 0),
                                    "float_rate": stock.get("float_rate", 0),
                                    "cost": stock.get("hold_cost", 0),
                                })
                return holdings
            else:
                logger.error("获取持仓失败: %s", result.get("msg"))
                return []
        except Exception as e:
            logger.error("获取持仓失败: %s", e)
            return []
    
    def get_performances(self, gid: int) -> dict:
        """
        获取模拟仓收益
        
        :param gid: 模拟仓 ID
        :return: 收益信息
        """
        url = f"{self.BASE_URL}/performances.json"
        params = {"gid": gid}
        resp = self.session.get(url, params=params)
        
        try:
            result = resp.json()
            if result.get("success"):
                performances = result.get("result_data", {}).get("performances", [])
                # 返回全市场汇总
                for p in performances:
                    if p.get("market") == "ALL":
                        return p
                return performances[0] if performances else {}
            else:
                logger.error("获取收益失败: %s", result.get("msg"))
                return {}
        except Exception as e:
            logger.error("获取收益失败: %s", e)
            return {}
    
    def search_stock(self, code: str) -> dict:
        """
        搜索股票信息
        
        :param code: 股票代码，如 SZ123091
        :return: 股票信息
        """
        params = {"code": code, "size": 10}
        resp = self.session.get(self.STOCK_SEARCH_URL, params=params)
        
        try:
            result = resp.json()
            stocks = result.get("stocks", [])
            if stocks:
                return stocks[0]
            return {}
        except Exception as e:
            logger.error("搜索股票失败: %s", e)
            return {}
    
    def buy(self, gid: int, symbol: str, price: float, shares: int, 
            date: str = None, tax_rate: float = None, commission_rate: float = None) -> bool:
        """
        买入股票
        
        :param gid: 模拟仓 ID
        :param symbol: 股票代码
        :param price: 买入价格
        :param shares: 买入股数
        :param date: 交易日期 (YYYY-MM-DD)
        :param tax_rate: 税率（千分位）
        :param commission_rate: 佣金率（千分位）
        :return: 是否成功
        """
        return self._trade(gid, symbol, price, shares, trade_type=1, 
                          date=date, tax_rate=tax_rate, commission_rate=commission_rate)
    
    def sell(self, gid: int, symbol: str, price: float, shares: int,
             date: str = None, tax_rate: float = None, commission_rate: float = None) -> bool:
        """
        卖出股票
        
        :param gid: 模拟仓 ID
        :param symbol: 股票代码
        :param price: 卖出价格
        :param shares: 卖出股数
        :param date: 交易日期 (YYYY-MM-DD)
        :param tax_rate: 税率（千分位）
        :param commission_rate: 佣金率（千分位）
        :return: 是否成功
        """
        return self._trade(gid, symbol, price, shares, trade_type=2,
                          date=date, tax_rate=tax_rate, commission_rate=commission_rate)
    
    def _trade(self, gid: int, symbol: str, price: float, shares: int, trade_type: int,
               date: str = None, tax_rate: float = None, commission_rate: float = None) -> bool:
        """
        执行交易
        
        :param trade_type: 1=买入, 2=卖出
        """
        url = f"{self.BASE_URL}/transaction/add.json"
        
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        if tax_rate is None:
            tax_rate = self.tax_rate
        if commission_rate is None:
            commission_rate = self.commission_rate
        
        data = {
            "type": trade_type,
            "date": date,
            "gid": gid,
            "symbol": symbol,
            "price": price,
            "shares": shares,
            "tax_rate": tax_rate,
            "commission_rate": commission_rate,
        }
        
        resp = self.session.post(url, data=data)
        
        try:
            result = resp.json()
            if result.get("success"):
                action = "买入" if trade_type == 1 else "卖出"
                logger.info("%s成功: %s %d股 @ %.3f", action, symbol, shares, price)
                return True
            else:
                logger.error("交易失败: %s", result.get("msg"))
                return False
        except Exception as e:
            logger.error("交易失败: %s", e)
            return False
    
    def get_transactions(self, gid: int, row: int = 50) -> list:
        """
        获取交易记录
        
        :param gid: 模拟仓 ID
        :param row: 返回记录数
        :return: 交易记录列表
        """
        url = f"{self.BASE_URL}/transaction/list.json"
        params = {"gid": gid, "row": row}
        resp = self.session.get(url, params=params)
        
        try:
            result = resp.json()
            if result.get("success"):
                return result.get("result_data", {}).get("transactions", [])
            else:
                logger.error("获取交易记录失败: %s", result.get("msg"))
                return []
        except Exception as e:
            logger.error("获取交易记录失败: %s", e)
            return []
    
    def get_portfolio_holdings(self, portfolio_code: str) -> list:
        """
        获取组合持仓（用于跟踪）
        
        :param portfolio_code: 组合代码
        :return: (持仓列表, 现金比例)
        """
        url = "https://xueqiu.com/cubes/rebalancing/current.json"
        params = {"cube_symbol": portfolio_code}
        resp = self.session.get(url, params=params)
        
        try:
            result = resp.json()
            last_rb = result.get("last_rb", {})
            cash_weight = float(last_rb.get("cash", 0))
            holdings = last_rb.get("holdings", [])
            holdings_list = [{
                "symbol": h.get("stock_symbol"),
                "name": h.get("stock_name"),
                "weight": h.get("weight", 0),
            } for h in holdings]
            return holdings_list, cash_weight
        except Exception as e:
            logger.error("获取组合持仓失败: %s", e)
            return [], 0
    
    def sync_from_portfolio(self, gid: int, portfolio_code: str) -> dict:
        """
        根据组合持仓同步调仓模拟仓
        
        逻辑：
        1. 获取模拟仓当前总资产和持仓
        2. 获取目标组合的持仓比例
        3. 计算每只股票的目标市值 = 总资产 × 权重比例
        4. 计算目标股数 = 目标市值 / 当前股价（可转债取整到10张）
        5. 对比当前持仓，计算需要买入/卖出的股数
        6. 先卖后买，执行交易
        
        :param gid: 模拟仓 ID
        :param portfolio_code: 要跟踪的组合代码
        :return: 调仓结果
        """
        logger.info("=" * 50)
        logger.info("开始同步组合 %s 到模拟仓 %d", portfolio_code, gid)
        logger.info("=" * 50)
        
        # 1. 获取模拟仓当前资产和持仓
        perf = self.get_performances(gid)
        total_assets = perf.get("assets", 0)
        current_cash = perf.get("cash", 0)
        
        logger.info("模拟仓总资产: %.2f, 现金: %.2f", total_assets, current_cash)
        
        # 获取当前模拟仓持仓
        sim_holdings = self.get_holdings(gid)
        sim_holdings_map = {}
        for h in sim_holdings:
            if h.get("symbol"):
                sim_holdings_map[h["symbol"]] = {
                    "shares": float(h.get("shares", 0)),
                    "current": float(h.get("current", 0)),
                    "name": h.get("name", ""),
                }
        
        logger.info("当前模拟仓持仓: %s", list(sim_holdings_map.keys()) if sim_holdings_map else "空仓")
        
        # 2. 获取目标组合持仓和现金比例
        target_holdings, target_cash_weight = self.get_portfolio_holdings(portfolio_code)
        
        if not target_holdings:
            logger.error("目标组合无持仓数据")
            return {"error": "目标组合无持仓数据"}
        
        logger.info("目标组合现金比例: %.2f%%", target_cash_weight)
        logger.info("目标组合持仓:")
        for h in target_holdings:
            logger.info("  %s (%s): %.2f%%", h["name"], h["symbol"], h["weight"])
        
        # 3. 计算目标持仓
        results = {"buys": [], "sells": [], "errors": [], "skipped": []}
        target_map = {}
        
        for h in target_holdings:
            symbol = h["symbol"]
            weight = h["weight"] / 100.0  # 转换为小数
            target_value = total_assets * weight
            
            # 获取当前股价
            stock_info = self.search_stock(symbol)
            if not stock_info:
                results["errors"].append(f"找不到股票: {symbol}")
                continue
            
            current_price = float(stock_info.get("current", 0))
            if current_price <= 0:
                results["errors"].append(f"股票价格无效: {symbol}")
                continue
            
            # 可转债按10张整数买入（1张=10股面值）
            # 雪球模拟仓中可转债以"张"为单位，但接口用股数表示
            if "转债" in stock_info.get("name", ""):
                # 可转债：按张计算，1张 = 1股（在雪球中）
                target_shares = int(target_value / current_price / 10) * 10
            else:
                # 股票：按100股整数
                target_shares = int(target_value / current_price / 100) * 100
            
            target_map[symbol] = {
                "target_shares": target_shares,
                "target_value": target_value,
                "current_price": current_price,
                "name": stock_info.get("name", ""),
                "weight": h["weight"],
            }
            
            logger.info("  %s: 目标市值 %.2f, 目标股数 %d, 当前价 %.3f", 
                       symbol, target_value, target_shares, current_price)
        
        # 4. 先卖出：不在目标中的股票 或 需要减仓的股票
        logger.info("-" * 30)
        logger.info("执行卖出操作...")
        
        for symbol, holding in sim_holdings_map.items():
            current_shares = int(holding["shares"])
            
            if symbol not in target_map:
                # 股票不在目标中，全部卖出
                if current_shares > 0:
                    logger.info("卖出（清仓）: %s %d股 @ %.3f", symbol, current_shares, holding["current"])
                    success = self.sell(gid, symbol, holding["current"], current_shares)
                    results["sells"].append({
                        "symbol": symbol,
                        "name": holding["name"],
                        "shares": current_shares,
                        "price": holding["current"],
                        "success": success,
                        "reason": "不在目标组合中",
                    })
            else:
                # 股票在目标中，检查是否需要减仓
                target_shares = target_map[symbol]["target_shares"]
                diff = current_shares - target_shares
                
                if diff > 0:
                    logger.info("卖出（减仓）: %s %d股 @ %.3f", symbol, diff, holding["current"])
                    success = self.sell(gid, symbol, holding["current"], diff)
                    results["sells"].append({
                        "symbol": symbol,
                        "name": holding["name"],
                        "shares": diff,
                        "price": holding["current"],
                        "success": success,
                        "reason": "减仓",
                    })
        
        # 5. 再买入：新增或加仓的股票
        logger.info("-" * 30)
        logger.info("执行买入操作...")
        
        for symbol, target in target_map.items():
            current_shares = sim_holdings_map.get(symbol, {}).get("shares", 0)
            target_shares = target["target_shares"]
            diff = target_shares - int(current_shares)
            
            if diff > 0:
                logger.info("买入: %s %d股 @ %.3f (目标权重 %.2f%%)", 
                           symbol, diff, target["current_price"], target["weight"])
                success = self.buy(gid, symbol, target["current_price"], diff)
                results["buys"].append({
                    "symbol": symbol,
                    "name": target["name"],
                    "shares": diff,
                    "price": target["current_price"],
                    "success": success,
                    "target_weight": target["weight"],
                })
            elif diff == 0:
                results["skipped"].append({
                    "symbol": symbol,
                    "name": target["name"],
                    "reason": "持仓已达目标",
                })
        
        # 6. 查询交易记录确认
        logger.info("-" * 30)
        logger.info("调仓完成，查询最新交易记录...")
        transactions = self.get_transactions(gid, row=20)
        
        # 统计结果
        buy_count = sum(1 for b in results["buys"] if b["success"])
        sell_count = sum(1 for s in results["sells"] if s["success"])
        
        logger.info("=" * 50)
        logger.info("调仓完成！买入 %d 笔，卖出 %d 笔", buy_count, sell_count)
        logger.info("=" * 50)
        
        results["summary"] = {
            "total_assets": total_assets,
            "buy_count": buy_count,
            "sell_count": sell_count,
            "error_count": len(results["errors"]),
        }
        results["recent_transactions"] = transactions[:10]
        
        return results
    
    def get_portfolio_rebalance_history(self, portfolio_code: str, count: int = 5) -> list:
        """
        获取组合的调仓历史记录
        
        :param portfolio_code: 组合代码
        :param count: 获取记录数
        :return: 调仓历史列表
        """
        url = "https://xueqiu.com/cubes/rebalancing/history.json"
        params = {"cube_symbol": portfolio_code, "count": count, "page": 1}
        resp = self.session.get(url, params=params)
        
        try:
            result = resp.json()
            return result.get("list", [])
        except Exception as e:
            logger.error("获取调仓历史失败: %s", e)
            return []
    
    def auto_track_and_sync(self, gid: int, portfolio_code: str, 
                            interval: int = 60, max_iterations: int = None):
        """
        自动跟踪组合变化并同步到模拟仓
        
        监控目标组合的调仓记录，当检测到新的调仓时自动同步模拟仓
        
        :param gid: 模拟仓 ID
        :param portfolio_code: 要跟踪的组合代码
        :param interval: 轮询间隔（秒）
        :param max_iterations: 最大轮询次数（None表示无限循环）
        """
        import time
        
        logger.info("=" * 60)
        logger.info("启动自动跟踪同步")
        logger.info("  模拟仓 GID: %d", gid)
        logger.info("  跟踪组合: %s", portfolio_code)
        logger.info("  轮询间隔: %d 秒", interval)
        logger.info("=" * 60)
        
        # 记录上次调仓时间
        last_rebalance_id = None
        
        # 记录上次持仓快照
        last_holdings_snapshot = None
        
        # 首次同步
        logger.info("\n首次同步...")
        result = self.sync_from_portfolio(gid, portfolio_code)
        
        # 获取初始调仓记录ID
        history = self.get_portfolio_rebalance_history(portfolio_code, count=1)
        if history:
            last_rebalance_id = history[0].get("id")
            logger.info("初始调仓记录 ID: %s", last_rebalance_id)
        
        # 获取初始持仓快照
        target_holdings, _ = self.get_portfolio_holdings(portfolio_code)
        last_holdings_snapshot = {h["symbol"]: h["weight"] for h in target_holdings}
        
        iteration = 0
        try:
            while True:
                iteration += 1
                if max_iterations and iteration > max_iterations:
                    logger.info("达到最大轮询次数 %d，退出", max_iterations)
                    break
                
                logger.info("\n[%s] 轮询检查中... (第 %d 次)", 
                           datetime.now().strftime("%H:%M:%S"), iteration)
                
                # 方法1：检查调仓历史记录
                history = self.get_portfolio_rebalance_history(portfolio_code, count=1)
                new_rebalance = False
                
                if history:
                    current_rebalance_id = history[0].get("id")
                    if current_rebalance_id != last_rebalance_id:
                        logger.info("检测到新的调仓记录！ID: %s", current_rebalance_id)
                        new_rebalance = True
                        last_rebalance_id = current_rebalance_id
                
                # 方法2：检查持仓比例是否变化
                if not new_rebalance:
                    current_holdings, _ = self.get_portfolio_holdings(portfolio_code)
                    current_snapshot = {h["symbol"]: h["weight"] for h in current_holdings}
                    
                    # 比较持仓
                    if current_snapshot != last_holdings_snapshot:
                        logger.info("检测到持仓比例变化！")
                        
                        # 详细显示变化
                        for symbol in set(list(current_snapshot.keys()) + list(last_holdings_snapshot.keys())):
                            old_weight = last_holdings_snapshot.get(symbol, 0)
                            new_weight = current_snapshot.get(symbol, 0)
                            if old_weight != new_weight:
                                logger.info("  %s: %.2f%% -> %.2f%%", symbol, old_weight, new_weight)
                        
                        new_rebalance = True
                        last_holdings_snapshot = current_snapshot
                
                # 如果检测到变化，先判断是否真正需要调仓
                if new_rebalance:
                    logger.info("\n检测到目标组合变化，检查是否需要调仓...")
                    
                    need_sync, trade_info = self.check_need_sync(gid, portfolio_code)
                    
                    if need_sync:
                        logger.info("\n" + "=" * 50)
                        logger.info("需要调仓！开始自动同步...")
                        logger.info("=" * 50)
                        
                        result = self.sync_from_portfolio(gid, portfolio_code)
                        
                        if "summary" in result:
                            logger.info("\n同步完成: 买入 %d 笔, 卖出 %d 笔", 
                                       result["summary"]["buy_count"], 
                                       result["summary"]["sell_count"])
                    else:
                        logger.info("模拟仓已与目标一致，无需调仓")
                else:
                    logger.info("未检测到变化，继续等待...")
                
                # 等待下一次轮询
                logger.info("等待 %d 秒后再次检查...", interval)
                time.sleep(interval)
                
        except KeyboardInterrupt:
            logger.info("\n用户中断，停止跟踪")
        
        logger.info("自动跟踪同步已停止")
    
    def check_need_sync(self, gid: int, portfolio_code: str) -> tuple:
        """
        检查模拟仓是否需要与目标组合同步
        
        :param gid: 模拟仓 ID
        :param portfolio_code: 目标组合代码
        :return: (是否需要同步, 交易详情)
        """
        # 获取模拟仓当前持仓
        perf = self.get_performances(gid)
        total_assets = perf.get("assets", 0)
        
        sim_holdings = self.get_holdings(gid)
        sim_holdings_map = {}
        for h in sim_holdings:
            if h.get("symbol"):
                sim_holdings_map[h["symbol"]] = float(h.get("shares", 0))
        
        # 获取目标组合持仓
        target_holdings, _ = self.get_portfolio_holdings(portfolio_code)
        
        buys_needed = []
        sells_needed = []
        
        # 计算每只股票的目标股数
        target_map = {}
        for h in target_holdings:
            symbol = h["symbol"]
            weight = h["weight"] / 100.0
            target_value = total_assets * weight
            
            # 获取当前股价
            stock_info = self.search_stock(symbol)
            if not stock_info:
                continue
            
            current_price = float(stock_info.get("current", 0))
            if current_price <= 0:
                continue
            
            # 计算目标股数
            if "转债" in stock_info.get("name", ""):
                target_shares = int(target_value / current_price / 10) * 10
            else:
                target_shares = int(target_value / current_price / 100) * 100
            
            target_map[symbol] = target_shares
        
        # 比较：需要卖出的
        for symbol, current_shares in sim_holdings_map.items():
            current_shares = int(current_shares)
            if symbol not in target_map:
                if current_shares > 0:
                    sells_needed.append({"symbol": symbol, "shares": current_shares, "reason": "清仓"})
            else:
                target_shares = target_map[symbol]
                diff = current_shares - target_shares
                if diff > 0:
                    sells_needed.append({"symbol": symbol, "shares": diff, "reason": "减仓"})
        
        # 比较：需要买入的
        for symbol, target_shares in target_map.items():
            current_shares = int(sim_holdings_map.get(symbol, 0))
            diff = target_shares - current_shares
            if diff > 0:
                buys_needed.append({"symbol": symbol, "shares": diff})
        
        need_sync = len(buys_needed) > 0 or len(sells_needed) > 0
        
        if need_sync:
            logger.info("需要调仓:")
            for s in sells_needed:
                logger.info("  卖出 %s: %d 股 (%s)", s["symbol"], s["shares"], s["reason"])
            for b in buys_needed:
                logger.info("  买入 %s: %d 股", b["symbol"], b["shares"])
        
        return need_sync, {"buys": buys_needed, "sells": sells_needed}

