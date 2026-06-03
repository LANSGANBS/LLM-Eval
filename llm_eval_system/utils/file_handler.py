"""文件处理模块 - 支持文件上传与处理"""
import os
import csv
import json
import logging
from datetime import datetime
from tkinter import filedialog

logger = logging.getLogger(__name__)


class FileHandler:
    """文件处理器 - 面向对象设计"""
    
    ALLOWED_EXTENSIONS = {'.csv', '.json', '.txt'}
    
    def __init__(self, upload_dir='uploads'):
        self.upload_dir = upload_dir
        os.makedirs(upload_dir, exist_ok=True)
    
    def upload_file(self, parent_window=None):
        """上传文件并返回文件路径"""
        file_path = filedialog.askopenfilename(
            parent=parent_window,
            title="选择文件",
            filetypes=[
                ("CSV文件", "*.csv"),
                ("JSON文件", "*.json"),
                ("文本文件", "*.txt"),
                ("所有文件", "*.*")
            ]
        )
        if file_path:
            return self._process_uploaded_file(file_path)
        return None
    
    def _process_uploaded_file(self, file_path):
        """处理上传的文件"""
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            raise ValueError(f"不支持的文件格式: {ext}")
        
        # 复制到上传目录
        filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.path.basename(file_path)}"
        dest_path = os.path.join(self.upload_dir, filename)
        
        with open(file_path, 'rb') as src, open(dest_path, 'wb') as dst:
            dst.write(src.read())
        
        logger.debug(f"文件已上传: {dest_path}")
        return dest_path
    
    def parse_csv(self, file_path):
        """解析CSV文件"""
        data = []
        with open(file_path, 'r', encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            for row in reader:
                data.append(dict(row))
        return data
    
    def parse_json(self, file_path):
        """解析JSON文件"""
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            return json.load(f)
    
    def export_to_csv(self, data, file_path):
        """导出数据到CSV"""
        if not data:
            return
        keys = data[0].keys()
        with open(file_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(data)
        logger.debug(f"数据已导出: {file_path}")
    
    def export_to_json(self, data, file_path):
        """导出数据到JSON"""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.debug(f"数据已导出: {file_path}")
