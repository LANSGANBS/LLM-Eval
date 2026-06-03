"""全局异常处理模块"""
import logging
import traceback
from tkinter import messagebox

logger = logging.getLogger(__name__)


class AppException(Exception):
    """应用基础异常类"""
    def __init__(self, message, error_code=None):
        super().__init__(message)
        self.error_code = error_code
        self.message = message


class DatabaseException(AppException):
    """数据库操作异常"""
    pass


class CrawlerException(AppException):
    """爬虫操作异常"""
    pass


class FileUploadException(AppException):
    """文件上传异常"""
    pass


def handle_exception(func):
    """全局异常处理装饰器"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except AppException as e:
            logger.error(f"应用异常: {e.message}")
            messagebox.showerror("错误", f"操作失败: {e.message}")
        except Exception as e:
            logger.error(f"未预期异常: {str(e)}")
            logger.debug(traceback.format_exc())
            messagebox.showerror("错误", f"发生未预期错误: {str(e)}")
    return wrapper


def safe_operation(func):
    """安全操作装饰器 - 用于线程内"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.debug(f"线程内异常: {str(e)}")
            logger.debug(traceback.format_exc())
            return None
    return wrapper
