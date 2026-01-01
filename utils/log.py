# -*- coding: utf-8 -*-
"""
日志模块
"""
import logging
import sys

# 创建 logger
logger = logging.getLogger("xueqiu_trader")
logger.setLevel(logging.DEBUG)

# 控制台输出
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)

# 格式化
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
console_handler.setFormatter(formatter)

# 添加 handler
if not logger.handlers:
    logger.addHandler(console_handler)
