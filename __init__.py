# -*- coding: utf-8 -*-
"""
XueQiu Trader - 雪球组合交易与跟踪

基于 easytrader 实现的简化版雪球组合调仓和跟踪功能。
"""

from .xqtrader import XueQiuTrader
from .xq_follower import XueQiuFollower
from .exceptions import TradeError, LoginError, ConfigError

__version__ = "1.0.0"
__all__ = ["XueQiuTrader", "XueQiuFollower", "TradeError", "LoginError", "ConfigError"]
