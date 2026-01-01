# -*- coding: utf-8 -*-
"""
配置迁移脚本 - 从 JSON 迁移到 SQLite

用法: python scripts/migrate_config.py
"""
import os
import sys
import json

# 添加项目根目录到 Python 路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from flask import Flask
from web.models import db, UserConfig, Portfolio

# 配置文件路径
CONFIG_PATH = os.path.join(BASE_DIR, "config", "user_config.json")
DATA_DIR = os.path.join(BASE_DIR, "data")


def create_app():
    """创建 Flask 应用"""
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(DATA_DIR, "xueqiu_trader.db")}'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    return app


def migrate_config():
    """迁移配置文件到数据库"""
    print("=" * 50)
    print("配置迁移: user_config.json -> SQLite")
    print("=" * 50)
    
    # 检查配置文件是否存在
    if not os.path.exists(CONFIG_PATH):
        print(f"❌ 配置文件不存在: {CONFIG_PATH}")
        return False
    
    # 读取 JSON 配置
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)
    
    print(f"📄 读取配置文件: {CONFIG_PATH}")
    print(f"   包含 {len(config)} 个配置项")
    
    # 配置项描述
    descriptions = {
        "cookies": "雪球登录 Cookies",
        "portfolio_code": "默认组合代码",
        "target_portfolio_code": "目标跟踪组合代码",
        "simulator_gid": "模拟仓 GID",
        "my_portfolio_code": "我的组合代码列表",
        "track_interval": "轮询间隔（秒）",
        "initial_assets": "初始资产",
        "portfolio_market": "组合市场（cn/us）"
    }
    
    # 创建应用和迁移
    app = create_app()
    
    with app.app_context():
        # 创建表
        db.create_all()
        
        migrated = 0
        for key, value in config.items():
            desc = descriptions.get(key, "")
            UserConfig.set(key, value, desc)
            print(f"   ✅ {key}: {str(value)[:50]}...")
            migrated += 1
        
        # 如果有组合代码，创建 Portfolio 记录
        portfolio_codes = []
        if config.get("portfolio_code"):
            portfolio_codes.append(config["portfolio_code"])
        if config.get("target_portfolio_code"):
            portfolio_codes.append(config["target_portfolio_code"])
        if config.get("my_portfolio_code"):
            codes = config["my_portfolio_code"]
            if isinstance(codes, list):
                portfolio_codes.extend(codes)
            else:
                portfolio_codes.append(codes)
        
        for code in set(portfolio_codes):
            if code and not Portfolio.query.filter_by(code=code).first():
                portfolio = Portfolio(
                    code=code,
                    name=code,
                    type='real' if code.startswith('ZH') else 'simulation'
                )
                db.session.add(portfolio)
                print(f"   📊 创建组合记录: {code}")
        
        if config.get("simulator_gid"):
            gid = config["simulator_gid"]
            if not Portfolio.query.filter_by(gid=gid).first():
                portfolio = Portfolio(
                    code=f"SIM-{gid}",
                    name=f"模拟仓 {gid}",
                    type='simulation',
                    gid=gid
                )
                db.session.add(portfolio)
                print(f"   💰 创建模拟仓记录: GID={gid}")
        
        db.session.commit()
    
    print("=" * 50)
    print(f"✅ 迁移完成! 共迁移 {migrated} 个配置项")
    print(f"   数据库位置: {os.path.join(DATA_DIR, 'xueqiu_trader.db')}")
    print("=" * 50)
    return True


def verify_migration():
    """验证迁移结果"""
    print("\n验证迁移结果...")
    
    app = create_app()
    with app.app_context():
        configs = UserConfig.get_all()
        print(f"📋 数据库中有 {len(configs)} 个配置项:")
        for key, value in configs.items():
            print(f"   - {key}: {str(value)[:40]}...")
        
        portfolios = Portfolio.query.all()
        print(f"\n📊 组合记录: {len(portfolios)} 个")
        for p in portfolios:
            print(f"   - {p.code} ({p.type})")
    
    print("\n✅ 验证完成!")


if __name__ == "__main__":
    os.makedirs(DATA_DIR, exist_ok=True)
    if migrate_config():
        verify_migration()
