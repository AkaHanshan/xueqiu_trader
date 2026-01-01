# -*- coding: utf-8 -*-
"""
工具函数
"""


def parse_cookies_str(cookies_str: str) -> dict:
    """
    解析浏览器复制的 cookie 字符串为字典
    
    :param cookies_str: 浏览器复制的 cookie 字符串，格式如 "key1=value1; key2=value2"
    :return: cookie 字典
    """
    cookie_dict = {}
    if not cookies_str:
        return cookie_dict
    
    # 按分号分割
    for item in cookies_str.split(";"):
        item = item.strip()
        if not item:
            continue
        # 按第一个等号分割（value 中可能包含等号）
        if "=" in item:
            key, value = item.split("=", 1)
            cookie_dict[key.strip()] = value.strip()
    
    return cookie_dict
