"""配置文件 - 全局常量与配置项"""
import os

# 数据库路径
DATABASE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "llm_evaluation.db")

# 评测维度
EVALUATION_DIMENSIONS = [
    "语言理解", "逻辑推理", "知识问答", "代码生成",
    "文本生成", "数学能力", "多语言能力", "安全性"
]

# 窗口配置
WINDOW_TITLE = "LLM评测分析系统"
WINDOW_SIZE = "1600x950"

# 文件上传配置
UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
ALLOWED_EXTENSIONS = {'.csv', '.json', '.txt', '.xlsx'}
