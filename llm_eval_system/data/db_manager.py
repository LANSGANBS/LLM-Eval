"""
数据库管理模块 - 支持动态模型存储的SQLite数据库
涉及：数据库连接、CRUD操作、异常处理、动态模型管理
"""
import sqlite3
import json
import logging
import os
from datetime import datetime
from typing import List, Dict, Optional
from contextlib import contextmanager
import threading

from llm_eval_system.core.config import DATABASE_PATH
from llm_eval_system.utils.exceptions import DatabaseException, handle_exception

logger = logging.getLogger(__name__)


class DatabaseManager:
    """数据库管理类 - 面向对象设计，支持动态模型存储"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, db_path: str = None):
        """单例模式确保只有一个数据库连接实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, db_path: str = None):
        if self._initialized:
            return
        self.db_path = db_path or DATABASE_PATH
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
                    category TEXT NOT NULL,
                    source TEXT,
                    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active INTEGER DEFAULT 1,
                    metadata TEXT
                )
            ''')
            
            # 创建评测结果表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS evaluations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    model_id INTEGER NOT NULL,
                    dimension TEXT NOT NULL,
                    score REAL NOT NULL,
                    test_data TEXT,
                    source TEXT,
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
            logger.debug("数据库初始化完成")
            
        except sqlite3.Error as e:
            logger.error(f"数据库初始化失败: {e}")
            raise DatabaseException(f"数据库初始化失败: {e}")
        finally:
            conn.close()
    
    @handle_exception
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
                    SET category = ?, source = ?, last_updated = CURRENT_TIMESTAMP
                    WHERE name = ?
                ''', (category, source, name))
                conn.commit()
                return result[0]
            else:
                # 插入新模型
                cursor.execute('''
                    INSERT INTO models (name, category, source, metadata)
                    VALUES (?, ?, ?, ?)
                ''', (name, category, source, json.dumps(metadata) if metadata else None))
                conn.commit()
                return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"插入/更新模型失败: {e}")
            raise DatabaseException(f"插入/更新模型失败: {e}")
    
    @handle_exception
    def get_all_models(self) -> List[Dict]:
        """获取所有模型"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM models WHERE is_active = 1')
            return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logger.error(f"获取模型失败: {e}")
            raise DatabaseException(f"获取模型失败: {e}")
    
    @handle_exception
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
            raise DatabaseException(f"插入评测结果失败: {e}")
    
    @handle_exception
    def get_all_evaluations(self) -> List[Dict]:
        """获取所有评测结果"""
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
            raise DatabaseException(f"获取评测数据失败: {e}")
    
    @handle_exception
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
            raise DatabaseException(f"获取评测结果失败: {e}")
    
    @handle_exception
    def load_all_data(self) -> List[Dict]:
        """从数据库加载全部评测数据（包含 metadata 中的额外字段）"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT m.name as model, m.category, m.metadata,
                       e.dimension, e.score, e.source
                FROM evaluations e
                JOIN models m ON e.model_id = m.id
                WHERE m.is_active = 1
                ORDER BY m.name, e.dimension
            ''')
            rows = cursor.fetchall()
            if not rows:
                return []
            result = []
            for row in rows:
                item = {
                    'model': row['model'],
                    'category': row['category'],
                    'dimension': row['dimension'],
                    'score': row['score'],
                    'source': row['source'] or 'database',
                }
                # Restore extra fields from metadata JSON
                metadata_str = row['metadata']
                if metadata_str:
                    try:
                        metadata = json.loads(metadata_str)
                        for key in ('company', 'rating', 'votes', 'license', 'modelUrl', 'arena',
                                    'inputPricePerMillion', 'outputPricePerMillion',
                                    'contextLength'):
                            if key in metadata:
                                item[key] = metadata[key]
                    except (json.JSONDecodeError, TypeError):
                        pass
                result.append(item)
            return result
        except sqlite3.Error as e:
            logger.error(f"加载数据库数据失败: {e}")
            return []

    @handle_exception
    def has_data(self) -> bool:
        """检查数据库是否有评测数据"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM evaluations')
            return cursor.fetchone()[0] > 0
        except sqlite3.Error:
            return False

    @handle_exception
    def clear_all_data(self):
        """清空所有评测和模型数据"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM evaluations')
            cursor.execute('DELETE FROM models')
            conn.commit()
        except sqlite3.Error as e:
            logger.error(f"清空数据失败: {e}")

    @handle_exception
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
            raise DatabaseException(f"获取评测数据失败: {e}")
    
    @handle_exception
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
            raise DatabaseException(f"插入爬虫数据失败: {e}")
    
    @handle_exception
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
            raise DatabaseException(f"获取爬虫数据失败: {e}")
    
    @handle_exception
    def clear_evaluations(self):
        """清空评测数据"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM evaluations')
            conn.commit()
            logger.debug("评测数据已清空")
        except sqlite3.Error as e:
            logger.error(f"清空数据失败: {e}")
            raise DatabaseException(f"清空数据失败: {e}")
    
    @handle_exception
    def get_stats(self) -> Dict:
        """获取数据库统计信息"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM models')
            model_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM evaluations')
            eval_count = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM crawler_data')
            crawler_count = cursor.fetchone()[0]
            
            return {
                'models': model_count,
                'evaluations': eval_count,
                'crawler_data': crawler_count
            }
        except sqlite3.Error as e:
            logger.error(f"获取统计信息失败: {e}")
            raise DatabaseException(f"获取统计信息失败: {e}")


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
        
        logger.debug("示例数据初始化完成")
        
    except Exception as e:
        logger.error(f"初始化示例数据失败: {e}")
        raise
