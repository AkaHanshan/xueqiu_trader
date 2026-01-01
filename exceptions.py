# -*- coding: utf-8 -*-
"""
异常定义
"""


class TradeError(Exception):
    """交易相关异常"""
    pass


class LoginError(Exception):
    """登录相关异常"""
    pass


class ConfigError(Exception):
    """配置相关异常"""
    pass
