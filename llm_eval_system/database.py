"""
数据库模块 - 支持动态模型存储的SQLite数据库
涉及：数据库连接、CRUD操作、异常处理、动态模型管理
"""

import sqlite3
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional
from contextlib import contextmanager
import threading

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DatabaseManager:
    """数据库管理类 - 面向对象设计，支持动态模型存储"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, db_path: str = "llm_evaluation.db"):
        """单例模式确保只有一个数据库连接实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, db_path: str = "llm_evaluation.db"):
        if self._initialized:
            return
        self.db_path = db_path
        self._local = threading.local()
        self._init_database()
        self._initialized = True
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取线程本地连接"""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection
    
    def _init_database(self):
        """初始化数据库表结构"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 创建模型信息表 - 支持动态模型
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS models (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    category TEXT NOT NULL,  -- 'domestic' 或 'international'
                    source TEXT,             -- 数据来源
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active INTEGER DEFAULT 1,
                    metadata TEXT            -- JSON格式存储额外信息
                )
            ''')
            
            # 创建评测结果表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS evaluations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_id INTEGER NOT NULL,
                    dimension TEXT NOT NULL,
                    score REAL NOT NULL,
                    test_data TEXT,  -- JSON格式存储详细测试数据
                    source TEXT,     -- 数据来源
                    evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (model_id) REFERENCES models(id)
                )
            ''')
            
            # 创建评测任务表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS evaluation_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_name TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    models TEXT,
                    dimensions TEXT,
                    results TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                )
            ''')
            
            # 创建爬虫数据表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS crawler_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    url TEXT NOT NULL,
                    content TEXT,
                    data_type TEXT,
                    crawled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            logger.info("数据库初始化完成")
            
        except sqlite3.Error as e:
            logger.error(f"数据库初始化失败: {e}")
            raise
        finally:
            conn.close()
    
    def insert_or_update_model(self, name: str, category: str, 
                               source: str = "", metadata: dict = None) -> int:
        """插入或更新模型信息"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # 检查模型是否已存在
            cursor.execute('SELECT id FROM models WHERE name = ?', (name,))
            result = cursor.fetchone()
            
            if result:
                # 更新现有模型
                cursor.execute('''
                    UPDATE models 
                    SET category = ?, source = ?, last_updated = CURRENT_TIMESTAMP,
                        metadata = ?, is_active = 1
                    WHERE id = ?
                ''', (category, source, json.dumps(metadata) if metadata else None, result[0]))
                model_id = result[0]
            else:
                # 插入新模型
                cursor.execute('''
                    INSERT INTO models (name, category, source, metadata)
                    VALUES (?, ?, ?, ?)
                ''', (name, category, source, json.dumps(metadata) if metadata else None))
                model_id = cursor.lastrowid
            
            conn.commit()
            return model_id
            
        except sqlite3.Error as e:
            logger.error(f"插入/更新模型失败: {e}")
            raise
    
    def get_active_models(self, category: str = None) -> List[Dict]:
        """获取活跃的模型列表"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if category:
                cursor.execute('''
                    SELECT * FROM models 
                    WHERE is_active = 1 AND category = ?
                    ORDER BY last_updated DESC
                ''', (category,))
            else:
                cursor.execute('''
                    SELECT * FROM models 
                    WHERE is_active = 1
                    ORDER BY last_updated DESC
                ''')
            
            return [dict(row) for row in cursor.fetchall()]
            
        except sqlite3.Error as e:
            logger.error(f"获取模型列表失败: {e}")
            raise
    
    def deactivate_old_models(self, days: int = 30):
        """停用长时间未更新的模型"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE models 
                SET is_active = 0
                WHERE last_updated < datetime('now', '-{} days')
            '''.format(days))
            conn.commit()
            logger.info(f"已停用 {days} 天未更新的模型")
        except sqlite3.Error as e:
            logger.error(f"停用旧模型失败: {e}")
            raise
    
    def insert_evaluation(self, model_id: int, dimension: str, score: float, 
                          source: str = "", test_data: dict = None) -> int:
        """插入评测结果"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            test_data_json = json.dumps(test_data) if test_data else None
            cursor.execute('''
                INSERT INTO evaluations (model_id, dimension, score, source, test_data)
                VALUES (?, ?, ?, ?, ?)
            ''', (model_id, dimension, score, source, test_data_json))
            conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"插入评测结果失败: {e}")
            raise
    
    def get_evaluations(self, model_id: int = None, dimension: str = None) -> List[Dict]:
        """获取评测结果"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            query = '''
                SELECT e.*, m.name as model_name, m.category 
                FROM evaluations e 
                JOIN models m ON e.model_id = m.id 
                WHERE 1=1
            '''
            params = []
            if model_id:
                query += ' AND e.model_id = ?'
                params.append(model_id)
            if dimension:
                query += ' AND e.dimension = ?'
                params.append(dimension)
            
            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"获取评测结果失败: {e}")
            raise
    
    def get_all_evaluations_with_models(self) -> List[Dict]:
        """获取所有评测结果（包含模型信息）"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT e.id, e.dimension, e.score, e.evaluated_at,
                       m.id as model_id, m.name as model_name, m.category
                FROM evaluations e
                JOIN models m ON e.model_id = m.id
                ORDER BY e.evaluated_at DESC
            ''')
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"获取评测数据失败: {e}")
            raise
    
    def insert_crawler_data(self, source: str, url: str, content: str, 
                           data_type: str = "benchmark") -> int:
        """插入爬虫数据"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO crawler_data (source, url, content, data_type)
                VALUES (?, ?, ?, ?)
            ''', (source, url, content, data_type))
            conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"插入爬虫数据失败: {e}")
            raise
    
    def get_latest_crawler_data(self, limit: int = 10) -> List[Dict]:
        """获取最新的爬虫数据"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM crawler_data 
                ORDER BY crawled_at DESC 
                LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"获取爬虫数据失败: {e}")
            raise
    
    def clear_evaluations(self):
        """清空评测数据"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM evaluations')
            conn.commit()
            logger.info("评测数据已清空")
        except sqlite3.Error as e:
            logger.error(f"清空数据失败: {e}")
            raise


def init_database_with_sample_data(db: DatabaseManager):
    """初始化示例数据 - 动态生成，不硬编码"""
    try:
        # 插入一些示例模型数据（用于演示）
        sample_models = [
            ("示例模型-国内A", "domestic", "https://example.com"),
            ("示例模型-国内B", "domestic", "https://example.com"),
            ("示例模型-国际A", "international", "https://example.com"),
            ("示例模型-国际B", "international", "https://example.com"),
        ]
        
        for name, cat, url in sample_models:
            db.insert_or_update_model(name, cat, url)
        
        logger.info("示例数据初始化完成")
        
    except Exception as e:
        logger.error(f"初始化示例数据失败: {e}")
        raise
