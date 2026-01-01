# -*- coding: utf-8 -*-
"""
雪球组合跟踪端 - XueQiuFollower

通过轮询目标组合的调仓历史，将权重变化转换为交易指令。
"""
import json
import os
import pickle
import queue
import re
import threading
import time
from datetime import datetime
from numbers import Number

import requests
import urllib3

# 禁用 HTTPS 证书验证警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from exceptions import TradeError, LoginError
from utils import logger, parse_cookies_str


class XueQiuFollower:
    """
    雪球组合跟踪类
    
    使用方法:
        follower = XueQiuFollower()
        follower.login(cookies="your_cookies")
        follower.follow(
            strategies=["ZH123456"],
            total_assets=100000,
            track_interval=10
        )
    """
    
    LOGIN_PAGE = "https://www.xueqiu.com"
    TRANSACTION_API = "https://xueqiu.com/cubes/rebalancing/history.json"
    PORTFOLIO_URL = "https://xueqiu.com/p/"
    WEB_REFERER = "https://www.xueqiu.com"
    CMD_CACHE_FILE = "cmd_cache.pk"
    
    def __init__(self):
        """初始化跟踪端"""
        self.trade_queue = queue.Queue()
        self.expired_cmds = set()
        
        self.session = requests.Session()
        self.session.verify = False
        
        self.slippage = 0.0
        self._users = None
        self._adjust_sell = False
    
    def _generate_headers(self) -> dict:
        """生成请求头"""
        return {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36",
            "Referer": self.WEB_REFERER,
            "X-Requested-With": "XMLHttpRequest",
        }
    
    def login(self, cookies: str):
        """
        雪球登录，通过 cookies 认证
        
        :param cookies: 雪球登录 cookies
        """
        if not cookies:
            raise LoginError("雪球登录需要设置 cookies")
        
        headers = self._generate_headers()
        self.session.headers.update(headers)
        
        # 初始化 cookie
        self.session.get(self.LOGIN_PAGE)
        
        # 设置 cookies
        cookie_dict = parse_cookies_str(cookies)
        self.session.cookies.update(cookie_dict)
        
        logger.info("登录成功")
    
    def follow(
        self,
        users=None,
        strategies=None,
        total_assets=10000,
        initial_assets=None,
        adjust_sell=False,
        track_interval=10,
        trade_cmd_expire_seconds=120,
        cmd_cache=True,
        slippage=0.0,
    ):
        """
        跟踪雪球组合
        
        :param users: easytrader 用户对象，用于执行实盘交易（可选）
        :param strategies: 雪球组合代码，如 "ZH123456" 或 ["ZH123456", "ZH654321"]
        :param total_assets: 组合对应的总资产
        :param initial_assets: 初始资产，用于通过净值计算总资产
        :param adjust_sell: 是否根据实际持仓调整卖出数量
        :param track_interval: 轮询间隔（秒）
        :param trade_cmd_expire_seconds: 交易指令过期时间（秒）
        :param cmd_cache: 是否使用指令缓存
        :param slippage: 滑点，0.0 表示无滑点
        """
        self.slippage = slippage
        self._adjust_sell = adjust_sell
        self._users = self._wrap_list(users) if users else []
        
        strategies = self._wrap_list(strategies)
        total_assets = self._wrap_list(total_assets)
        initial_assets = self._wrap_list(initial_assets)
        
        if cmd_cache:
            self._load_expired_cmd_cache()
        
        # 启动交易执行线程
        if self._users:
            self._start_trader_thread(self._users, trade_cmd_expire_seconds)
        
        # 为每个策略启动跟踪线程
        for strategy_url, strategy_total_assets, strategy_initial_assets in zip(
            strategies, total_assets, initial_assets
        ):
            assets = self._calculate_assets(
                strategy_url, strategy_total_assets, strategy_initial_assets
            )
            
            try:
                strategy_id = self._extract_strategy_id(strategy_url)
                strategy_name = self._extract_strategy_name(strategy_url)
            except Exception:
                logger.error("抽取策略ID和名称失败，无效组合代码: %s", strategy_url)
                raise
            
            strategy_worker = threading.Thread(
                target=self._track_strategy_worker,
                args=[strategy_id, strategy_name],
                kwargs={"interval": track_interval, "assets": assets},
            )
            strategy_worker.daemon = True
            strategy_worker.start()
            logger.info("开始跟踪策略: %s", strategy_name)
        
        # 保持主线程运行
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("跟踪程序已停止")
    
    def _calculate_assets(self, strategy_url, total_assets=None, initial_assets=None):
        """计算总资产"""
        if total_assets is None and initial_assets is not None:
            net_value = self._get_portfolio_net_value(strategy_url)
            total_assets = initial_assets * net_value
        
        if not isinstance(total_assets, Number):
            raise TypeError("资产必须是数字类型 (int, float)")
        if total_assets < 1e3:
            raise ValueError(f"雪球总资产不能小于1000元，当前预设值 {total_assets}")
        
        return total_assets
    
    @staticmethod
    def _wrap_list(value):
        """将单个值包装为列表"""
        if value is None:
            return [None]
        if not isinstance(value, list):
            return [value]
        return value
    
    @staticmethod
    def _extract_strategy_id(strategy_url):
        """提取策略ID"""
        return strategy_url
    
    def _extract_strategy_name(self, strategy_url):
        """提取策略名称"""
        base_url = "https://xueqiu.com/cubes/nav_daily/all.json?cube_symbol={}"
        url = base_url.format(strategy_url)
        resp = self.session.get(url)
        info = resp.json()
        if info and len(info) > 0:
            return info[0].get("name", strategy_url)
        return strategy_url
    
    def _get_portfolio_info(self, portfolio_code):
        """获取组合信息"""
        url = self.PORTFOLIO_URL + portfolio_code
        resp = self.session.get(url)
        match = re.search(r"(?<=SNB.cubeInfo = ).*(?=;\n)", resp.text)
        
        if match is None:
            raise TradeError(f"无法获取组合信息: {url}")
        
        try:
            return json.loads(match.group())
        except Exception as e:
            raise TradeError(f"解析组合信息失败: {e}")
    
    def _get_portfolio_net_value(self, portfolio_code):
        """获取组合净值"""
        portfolio_info = self._get_portfolio_info(portfolio_code)
        return portfolio_info.get("net_value", 1.0)
    
    def _track_strategy_worker(self, strategy, name, interval=10, **kwargs):
        """策略跟踪工作线程"""
        poll_count = 0
        while True:
            poll_count += 1
            logger.info("[%s] 轮询检查策略 %s... (第 %d 次)", 
                       datetime.now().strftime("%H:%M:%S"), name, poll_count)
            
            try:
                transactions = self._query_strategy_transaction(strategy, **kwargs)
            except Exception as e:
                logger.exception("无法获取策略 %s 调仓信息, 错误: %s", name, e)
                time.sleep(3)
                continue
            
            if not transactions:
                logger.info("  未检测到新的调仓指令")
            
            for transaction in transactions:
                trade_cmd = {
                    "strategy": strategy,
                    "strategy_name": name,
                    "action": transaction["action"],
                    "stock_code": transaction["stock_code"],
                    "amount": transaction["amount"],
                    "price": transaction["price"],
                    "datetime": transaction["datetime"],
                }
                
                if self._is_cmd_expired(trade_cmd):
                    continue
                
                logger.info(
                    "策略 [%s] 发送指令: 股票 %s %s %s股 价格 %.2f 时间 %s",
                    name,
                    trade_cmd["stock_code"],
                    "买入" if trade_cmd["action"] == "buy" else "卖出",
                    trade_cmd["amount"],
                    trade_cmd["price"],
                    trade_cmd["datetime"],
                )
                
                self.trade_queue.put(trade_cmd)
                self._add_cmd_to_expired(trade_cmd)
            
            logger.info("  等待 %d 秒后再次检查...", interval)
            try:
                time.sleep(interval)
            except KeyboardInterrupt:
                logger.info("程序退出")
                break
    
    def _query_strategy_transaction(self, strategy, **kwargs):
        """查询策略调仓记录"""
        params = {"cube_symbol": strategy, "page": 1, "count": 1}
        resp = self.session.get(self.TRANSACTION_API, params=params)
        history = resp.json()
        
        transactions = self._extract_transactions(history)
        self._project_transactions(transactions, **kwargs)
        return self._order_transactions_sell_first(transactions)
    
    def _extract_transactions(self, history):
        """提取调仓记录"""
        if history.get("count", 0) <= 0:
            return []
        
        raw_transactions = history["list"][0].get("rebalancing_histories", [])
        transactions = []
        
        for transaction in raw_transactions:
            if transaction.get("price") is None:
                logger.info("该笔交易无法获取价格，跳过: %s", transaction)
                continue
            transactions.append(transaction)
        
        return transactions
    
    def _project_transactions(self, transactions, assets=10000, **kwargs):
        """将权重变化转换为具体股数"""
        for transaction in transactions:
            weight = transaction.get("weight") or 0
            prev_weight = transaction.get("prev_weight") or 0
            weight_diff = weight - prev_weight
            
            # 计算交易数量
            initial_amount = abs(weight_diff) / 100 * assets / transaction["price"]
            
            # 转换时间戳
            transaction["datetime"] = datetime.fromtimestamp(
                transaction["created_at"] // 1000
            )
            
            # 标准化股票代码
            transaction["stock_code"] = transaction["stock_symbol"].lower()
            
            # 确定买卖方向
            transaction["action"] = "buy" if weight_diff > 0 else "sell"
            
            # 计算股数（取整到100）
            transaction["amount"] = int(round(initial_amount, -2))
            
            # 卖出调整
            if transaction["action"] == "sell" and self._adjust_sell and self._users:
                transaction["amount"] = self._adjust_sell_amount(
                    transaction["stock_code"], transaction["amount"]
                )
    
    def _adjust_sell_amount(self, stock_code, amount):
        """根据实际持仓调整卖出数量"""
        if not self._users:
            return amount
        
        stock_code = stock_code[-6:]
        user = self._users[0]
        
        try:
            position = user.position
            stock = next((s for s in position if s.get("证券代码") == stock_code), None)
        except:
            return amount
        
        if stock is None:
            logger.info("未持有股票 %s，不做调整", stock_code)
            return amount
        
        available = stock.get("可用余额", 0)
        if available >= amount:
            return amount
        
        adjusted = available // 100 * 100
        logger.info("股票 %s 可用 %s，指令 %s，调整为 %s", stock_code, available, amount, adjusted)
        return adjusted
    
    @staticmethod
    def _order_transactions_sell_first(transactions):
        """调整顺序为先卖后买"""
        sell_first = []
        for t in transactions:
            if t["action"] == "sell":
                sell_first.insert(0, t)
            else:
                sell_first.append(t)
        return sell_first
    
    def _load_expired_cmd_cache(self):
        """加载已执行指令缓存"""
        if os.path.exists(self.CMD_CACHE_FILE):
            try:
                with open(self.CMD_CACHE_FILE, "rb") as f:
                    self.expired_cmds = pickle.load(f)
                logger.info("已加载 %d 条历史指令缓存", len(self.expired_cmds))
            except Exception as e:
                logger.warning("加载指令缓存失败: %s", e)
    
    @staticmethod
    def _generate_cmd_key(cmd):
        """生成指令唯一键"""
        return f"{cmd['strategy_name']}_{cmd['stock_code']}_{cmd['action']}_{cmd['amount']}_{cmd['price']}_{cmd['datetime']}"
    
    def _is_cmd_expired(self, cmd):
        """检查指令是否已执行"""
        key = self._generate_cmd_key(cmd)
        return key in self.expired_cmds
    
    def _add_cmd_to_expired(self, cmd):
        """添加指令到已执行缓存"""
        key = self._generate_cmd_key(cmd)
        self.expired_cmds.add(key)
        
        try:
            with open(self.CMD_CACHE_FILE, "wb") as f:
                pickle.dump(self.expired_cmds, f)
        except Exception as e:
            logger.warning("保存指令缓存失败: %s", e)
    
    def _start_trader_thread(self, users, expire_seconds):
        """启动交易执行线程"""
        trader = threading.Thread(
            target=self._trade_worker,
            args=[users],
            kwargs={"expire_seconds": expire_seconds},
        )
        trader.daemon = True
        trader.start()
    
    def _trade_worker(self, users, expire_seconds=120):
        """交易执行工作线程"""
        while True:
            trade_cmd = self.trade_queue.get()
            self._execute_trade_cmd(trade_cmd, users, expire_seconds)
    
    def _execute_trade_cmd(self, trade_cmd, users, expire_seconds):
        """执行交易指令"""
        for user in users:
            now = datetime.now()
            expire = (now - trade_cmd["datetime"]).total_seconds()
            
            if expire > expire_seconds:
                logger.warning(
                    "指令超时被丢弃: %s %s %s股",
                    trade_cmd["stock_code"],
                    trade_cmd["action"],
                    trade_cmd["amount"],
                )
                continue
            
            if trade_cmd["amount"] <= 0:
                logger.warning("交易数量无效，跳过: %s", trade_cmd)
                continue
            
            # 考虑滑点
            price = trade_cmd["price"]
            if trade_cmd["action"] == "buy":
                price = price * (1 + self.slippage)
            else:
                price = price * (1 - self.slippage)
            
            try:
                action_func = getattr(user, trade_cmd["action"])
                result = action_func(
                    security=trade_cmd["stock_code"],
                    price=price,
                    amount=trade_cmd["amount"],
                )
                logger.info("交易执行成功: %s", result)
            except Exception as e:
                logger.error("交易执行失败: %s", e)
    
    def get_transactions(self, strategy: str, count: int = 10) -> list:
        """
        获取策略调仓记录（调试用）
        
        :param strategy: 组合代码
        :param count: 获取数量
        :return: 调仓记录列表
        """
        params = {"cube_symbol": strategy, "page": 1, "count": count}
        resp = self.session.get(self.TRANSACTION_API, params=params)
        return resp.json().get("list", [])
