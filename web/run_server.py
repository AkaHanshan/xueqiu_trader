# -*- coding: utf-8 -*-
"""
生产环境启动脚本 - 使用 Waitress WSGI 服务器
"""
import sys
import os

# 添加项目根目录到路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from waitress import serve
from app import app

if __name__ == "__main__":
    print("=" * 50)
    print("雪球交易系统 - Web管理后台 (Waitress 生产模式)")
    print("=" * 50)
    print("访问地址: http://127.0.0.1:5000")
    print("线程数: 50")
    print("按 Ctrl+C 停止服务")
    print("=" * 50)
    
    serve(app, host='0.0.0.0', port=5000, threads=50)
