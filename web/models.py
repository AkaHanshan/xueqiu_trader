# -*- coding: utf-8 -*-
"""
雪球交易系统 - 数据库模型

使用 Flask-SQLAlchemy 实现持久化存储
"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
import json
import threading

db = SQLAlchemy()

# 线程安全锁（用于日志写入）
_log_lock = threading.Lock()


class UserConfig(db.Model):
    """用户配置表 - 替代 user_config.json"""
    __tablename__ = 'user_config'
    
    key = db.Column(db.String(50), primary_key=True)
    value = db.Column(db.Text)
    description = db.Column(db.String(200))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<UserConfig {self.key}>'
    
    @classmethod
    def get(cls, key, default=None):
        """获取配置值"""
        config = cls.query.get(key)
        if config is None:
            return default
        # 尝试 JSON 解析
        try:
            return json.loads(config.value)
        except (json.JSONDecodeError, TypeError):
            return config.value
    
    @classmethod
    def set(cls, key, value, description=None):
        """设置配置值"""
        config = cls.query.get(key)
        if config is None:
            config = cls(key=key)
        
        # 序列化为 JSON
        if isinstance(value, (dict, list)):
            config.value = json.dumps(value, ensure_ascii=False)
        else:
            config.value = str(value)
        
        if description:
            config.description = description
        
        db.session.add(config)
        db.session.commit()
        return config
    
    @classmethod
    def get_all(cls):
        """获取所有配置为字典"""
        configs = {}
        for config in cls.query.all():
            try:
                configs[config.key] = json.loads(config.value)
            except (json.JSONDecodeError, TypeError):
                configs[config.key] = config.value
        return configs


class Portfolio(db.Model):
    """组合信息表"""
    __tablename__ = 'portfolio'
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(100))
    type = db.Column(db.String(20), default='simulation')  # 'simulation' | 'real'
    is_tracking = db.Column(db.Boolean, default=False)
    gid = db.Column(db.BigInteger)  # 模拟仓 GID
    extra_data_json = db.Column(db.Text)  # 额外元数据 JSON
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<Portfolio {self.code}>'
    
    @property
    def extra_data(self):
        """获取额外数据字典"""
        if self.extra_data_json:
            try:
                return json.loads(self.extra_data_json)
            except json.JSONDecodeError:
                return {}
        return {}
    
    @extra_data.setter
    def extra_data(self, value):
        """设置额外数据"""
        self.extra_data_json = json.dumps(value, ensure_ascii=False)


class SystemLog(db.Model):
    """系统日志表 - 持久化日志记录"""
    __tablename__ = 'system_log'
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    level = db.Column(db.String(10), index=True)  # info, warning, error
    module = db.Column(db.String(50), index=True)  # 脚本/模块名称
    message = db.Column(db.Text)
    
    def __repr__(self):
        return f'<SystemLog {self.id} [{self.level}]>'
    
    @classmethod
    def add(cls, level, message, module='system'):
        """线程安全地添加日志"""
        with _log_lock:
            log = cls(level=level, message=message, module=module)
            db.session.add(log)
            db.session.commit()
            return log
    
    @classmethod
    def get_recent(cls, limit=100, module=None, level=None):
        """获取最近的日志"""
        query = cls.query.order_by(cls.timestamp.desc())
        
        if module:
            query = query.filter_by(module=module)
        if level:
            query = query.filter_by(level=level)
        
        return query.limit(limit).all()
    
    def to_dict(self):
        """转换为字典（用于 API 响应）"""
        return {
            'id': self.id,
            'time': self.timestamp.strftime('%H:%M:%S'),
            'level': self.level,
            'script': self.module,
            'message': self.message
        }


def init_db(app):
    """初始化数据库"""
    db.init_app(app)
    with app.app_context():
        db.create_all()
