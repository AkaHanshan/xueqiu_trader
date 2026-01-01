# -*- coding: utf-8 -*-
"""
雪球组合交易端 - XueQiuTrader

通过模拟 HTTP 请求实现雪球组合的调仓操作。
"""
import json
import numbers
import os

import requests
import urllib3

# 禁用 HTTPS 证书验证警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from exceptions import TradeError, ConfigError
from utils import logger, parse_cookies_str


class XueQiuTrader:
    """
    雪球组合交易类
    """
    
    CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "xq.json")
    
    _HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Host": "xueqiu.com",
        "Pragma": "no-cache",
        "Connection": "keep-alive",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Cache-Control": "no-cache",
        "Referer": "https://xueqiu.com/P/ZH004612",
        "X-Requested-With": "XMLHttpRequest",
    }
    
    def __init__(self, initial_assets: int = 1000000):
        self.multiple = initial_assets
        if not isinstance(self.multiple, numbers.Number):
            raise TypeError("initial_assets 必须是数字类型")
        if self.multiple < 1e3:
            raise ValueError(f"雪球初始资产不能小于1000元")
        
        self.session = requests.Session()
        self.session.verify = False
        self.session.headers.update(self._HEADERS)
        self.account_config = None
        self.position_list = []
        self.config = self._load_config()
    
    def _load_config(self) -> dict:
        if not os.path.exists(self.CONFIG_PATH):
            raise ConfigError(f"配置文件不存在: {self.CONFIG_PATH}")
        with open(self.CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def prepare_account(self, cookies: str, portfolio_code: str, portfolio_market: str = "cn"):
        if not cookies:
            raise TradeError("雪球登录需要设置 cookies")
        if not portfolio_code:
            raise TradeError("需要设置 portfolio_code")
        
        self.account_config = {
            "cookies": cookies,
            "portfolio_code": portfolio_code,
            "portfolio_market": portfolio_market,
        }
        self._set_cookies(cookies)
        logger.info("账户准备完成，组合代码: %s", portfolio_code)
    
    def _set_cookies(self, cookies: str):
        cookie_dict = parse_cookies_str(cookies)
        self.session.cookies.update(cookie_dict)
    
    def _virtual_to_balance(self, virtual: float) -> float:
        return virtual * self.multiple
    
    def _search_stock_info(self, code: str) -> dict:
        params = {"code": str(code), "size": "300", "key": "47bce5c74f", "market": self.account_config["portfolio_market"]}
        resp = self.session.get(self.config["search_stock_url"], params=params)
        stocks = resp.json()
        if "stocks" in stocks and len(stocks["stocks"]) > 0:
            return stocks["stocks"][0]
        return None
    
    def _get_portfolio_info(self, portfolio_code: str) -> dict:
        params_rb = {"cube_symbol": portfolio_code}
        resp_rb = self.session.get(self.config["portfolio_url_new"], params=params_rb)
        params_qt = {"code": portfolio_code}
        resp_qt = self.session.get(self.config["portfolio_quote"], params=params_qt)
        try:
            rebalance_info = resp_rb.json()
            quote_info = resp_qt.json()
            net_value = quote_info[portfolio_code]["net_value"]
            portfolio_info = rebalance_info
            portfolio_info["net_value"] = net_value
        except Exception as e:
            raise TradeError(f"获取组合信息失败: {e}")
        return portfolio_info
    
    def get_balance(self) -> list:
        portfolio_code = self.account_config.get("portfolio_code")
        portfolio_info = self._get_portfolio_info(portfolio_code)
        asset_balance = self._virtual_to_balance(float(portfolio_info["net_value"]))
        position = portfolio_info["last_rb"]
        cash = asset_balance * float(position["cash"]) / 100
        market = asset_balance - cash
        return [{"asset_balance": asset_balance, "current_balance": cash, "enable_balance": cash, "market_value": market, "money_type": "人民币", "pre_interest": 0.25}]
    
    @property
    def cash_weight(self) -> float:
        portfolio_code = self.account_config.get("portfolio_code")
        portfolio_info = self._get_portfolio_info(portfolio_code)
        return float(portfolio_info["last_rb"]["cash"])
    
    def _get_position(self) -> list:
        portfolio_code = self.account_config["portfolio_code"]
        portfolio_info = self._get_portfolio_info(portfolio_code)
        return portfolio_info["last_rb"]["holdings"]
    
    def get_position(self) -> list:
        xq_positions = self._get_position()
        balance = self.get_balance()[0]
        position_list = []
        for pos in xq_positions:
            volume = pos["weight"] * balance["asset_balance"] / 100
            position_list.append({
                "stock_code": pos["stock_symbol"],
                "stock_name": pos["stock_name"],
                "weight": pos["weight"],
                "market_value": volume,
            })
        return position_list
    
    def adjust_weight(self, stock_code: str, weight: float, fetch_position: bool = True):
        stock = self._search_stock_info(stock_code)
        if stock is None:
            raise TradeError("没有查询到股票信息")
        if stock.get("flag") != 1:
            raise TradeError("股票无法操作")
        
        weight = round(weight, 2)
        if fetch_position:
            self.position_list = self._get_position()
        
        stock_exists = False
        for position in self.position_list:
            if position["stock_id"] == stock["stock_id"]:
                position["proactive"] = True
                position["weight"] = weight
                stock_exists = True
                break
        
        if not stock_exists and weight != 0:
            self.position_list.append({
                "code": stock["code"], "name": stock["name"], "flag": stock["flag"],
                "current": stock["current"], "chg": stock.get("chg", 0),
                "percent": str(stock.get("percent", 0)), "stock_id": stock["stock_id"],
                "ind_id": stock.get("ind_id"), "ind_name": stock.get("ind_name", ""),
                "ind_color": stock.get("ind_color", ""), "textname": stock["name"],
                "segment_name": stock.get("ind_name", ""), "weight": weight,
                "url": "/S/" + stock["code"], "proactive": True, "price": str(stock["current"]),
            })
        
        remain_weight = 100 - sum(i.get("weight", 0) for i in self.position_list)
        cash = round(remain_weight, 2)
        
        data = {"cash": cash, "holdings": json.dumps(self.position_list), "cube_symbol": str(self.account_config["portfolio_code"]), "segment": "true", "comment": ""}
        
        try:
            resp = self.session.post(self.config["rebalance_url"], data=data)
        except Exception as e:
            return {"error": str(e)}
        
        resp_json = resp.json()
        if "error_description" in resp_json and resp.status_code != 200:
            return {"error_no": resp_json.get("error_code"), "error_info": resp_json["error_description"]}
        
        logger.info("调仓成功 %s: %.2f%%", stock["name"], weight)
        return None
    
    def buy(self, stock_code: str, amount: int = 0, price: float = 0, volume: float = 0):
        return self._trade(stock_code, amount=amount, price=price, volume=volume, entrust_bs="buy")
    
    def sell(self, stock_code: str, amount: int = 0, price: float = 0, volume: float = 0):
        return self._trade(stock_code, amount=amount, price=price, volume=volume, entrust_bs="sell")
    
    def _trade(self, security: str, price: float = 0, amount: int = 0, volume: float = 0, entrust_bs: str = "buy"):
        stock = self._search_stock_info(security)
        balance = self.get_balance()[0]
        if stock is None:
            raise TradeError("没有查询到股票信息")
        if not volume:
            volume = int(float(price) * amount)
        if balance["current_balance"] < volume and entrust_bs == "buy":
            raise TradeError("现金不足")
        if stock.get("flag") != 1:
            raise TradeError("股票无法操作")
        if volume == 0:
            raise TradeError("金额不能为零")
        
        weight = volume / balance["asset_balance"] * 100
        weight = round(weight, 2)
        position_list = self._get_position()
        
        is_have = False
        for position in position_list:
            if position["stock_id"] == stock["stock_id"]:
                is_have = True
                position["proactive"] = True
                old_weight = position["weight"]
                if entrust_bs == "buy":
                    position["weight"] = round(weight + old_weight, 2)
                else:
                    if weight > old_weight:
                        raise TradeError("数量超过可卖")
                    position["weight"] = round(old_weight - weight, 2)
                break
        
        if not is_have:
            if entrust_bs == "buy":
                position_list.append({
                    "code": stock["code"], "name": stock["name"], "flag": stock["flag"],
                    "current": stock["current"], "chg": stock.get("chg", 0),
                    "percent": str(stock.get("percent", 0)), "stock_id": stock["stock_id"],
                    "ind_id": stock.get("ind_id"), "ind_name": stock.get("ind_name", ""),
                    "ind_color": stock.get("ind_color", ""), "textname": stock["name"],
                    "segment_name": stock.get("ind_name", ""), "weight": weight,
                    "url": "/S/" + stock["code"], "proactive": True, "price": str(stock["current"]),
                })
            else:
                raise TradeError("没有该股票")
        
        remain_weight = 100 - sum(i.get("weight", 0) for i in position_list)
        cash = round(remain_weight, 2)
        data = {"cash": cash, "holdings": json.dumps(position_list), "cube_symbol": str(self.account_config["portfolio_code"]), "segment": "true", "comment": ""}
        
        try:
            resp = self.session.post(self.config["rebalance_url"], data=data)
        except Exception as e:
            return {"error": str(e)}
        
        resp_json = resp.json()
        if "error_description" in resp_json and resp.status_code != 200:
            return {"error_no": resp_json.get("error_code"), "error_info": resp_json["error_description"]}
        
        logger.info("%s成功: %.2f", "买入" if entrust_bs == "buy" else "卖出", volume)
        return None
    
    def get_history(self, count: int = 20) -> list:
        params = {"cube_symbol": str(self.account_config["portfolio_code"]), "count": count, "page": 1}
        resp = self.session.get(self.config["history_url"], params=params)
        return resp.json().get("list", [])
    
    def get_followed_portfolios(self) -> list:
        """
        获取自选中关注的组合代码列表
        
        :return: 组合代码列表，如 ['ZH111175', 'SP1005282', ...]
        """
        url = "https://stock.xueqiu.com/v5/stock/portfolio/stock/list.json"
        params = {"size": 1000, "category": 3, "pid": -120}
        
        # stock.xueqiu.com 需要不同的 Host header
        headers = self.session.headers.copy()
        headers["Host"] = "stock.xueqiu.com"
        
        resp = self.session.get(url, params=params, headers=headers)
        try:
            result = resp.json()
            if result.get("error_code") != 0:
                logger.error("获取关注组合失败: %s", result.get("error_description", "未知错误"))
                return []
            stocks = result.get("data", {}).get("stocks", [])
            return [s.get("symbol") for s in stocks if s.get("symbol")]
        except Exception as e:
            logger.error("获取关注组合失败: %s, 响应: %s", e, resp.text[:200] if resp.text else "空")
            return []
    
    def get_my_portfolios(self) -> list:
        """
        获取我创建的组合代码列表（从配置文件读取）
        
        :return: 组合代码列表
        """
        # 从配置文件加载
        config_path = os.path.join(os.path.dirname(__file__), "config", "user_config.json")
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                user_config = json.load(f)
            my_portfolios = user_config.get("my_portfolio_code", [])
            # 兼容字符串格式
            if isinstance(my_portfolios, str):
                return [my_portfolios] if my_portfolios else []
            return my_portfolios if isinstance(my_portfolios, list) else []
        except Exception as e:
            logger.error("获取我的组合失败: %s", e)
            return []
    
    def get_public_portfolio(self, portfolio_code: str) -> dict:
        """获取任意公开组合的持仓信息"""
        try:
            params = {"cube_symbol": portfolio_code}
            resp = self.session.get(self.config["portfolio_url_new"], params=params)
            info = resp.json()
            params_qt = {"code": portfolio_code}
            resp_qt = self.session.get(self.config["portfolio_quote"], params=params_qt)
            quote = resp_qt.json()
            holdings = info.get("last_rb", {}).get("holdings", [])
            net_value = quote.get(portfolio_code, {}).get("net_value", 1.0)
            return {
                "portfolio_code": portfolio_code,
                "net_value": net_value,
                "cash": info.get("last_rb", {}).get("cash", 0),
                "holdings": [{"symbol": h.get("stock_symbol", ""), "name": h.get("stock_name", ""), "weight": h.get("weight", 0)} for h in holdings]
            }
        except Exception as e:
            logger.error("获取公开组合失败: %s", e)
            return {}
