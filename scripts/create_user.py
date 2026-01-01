# -*- coding: utf-8 -*-
"""
创建管理员用户脚本

用法: python scripts/create_user.py
"""
import os
import sys
import getpass

# 添加项目根目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from flask import Flask
from web.models import db, User

DATA_DIR = os.path.join(BASE_DIR, "data")


def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(DATA_DIR, "xueqiu_trader.db")}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    return app


def main():
    print("=" * 50)
    print("雪球交易系统 - 创建用户")
    print("=" * 50)
    
    # 获取用户输入
    username = input("请输入用户名: ").strip()
    if not username:
        print("❌ 用户名不能为空")
        return
    
    password = getpass.getpass("请输入密码: ")
    if len(password) < 6:
        print("❌ 密码长度至少6位")
        return
    
    password_confirm = getpass.getpass("请确认密码: ")
    if password != password_confirm:
        print("❌ 两次密码不一致")
        return
    
    # 创建用户
    app = create_app()
    with app.app_context():
        db.create_all()
        
        # 检查用户是否已存在
        existing = User.query.filter_by(username=username).first()
        if existing:
            print(f"❌ 用户 {username} 已存在")
            return
        
        user = User.create_user(username=username, password=password, is_admin=True)
        print(f"\n✅ 管理员用户 '{username}' 创建成功!")
        print(f"   现在可以使用此账号登录 Web 管理后台")
    
    print("=" * 50)


if __name__ == "__main__":
    main()
