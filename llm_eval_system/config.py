"""大语言模型评测分析系统 - 配置文件"""

DATABASE_PATH = "llm_evaluation.db"

EVALUATION_DIMENSIONS = [
    "语言理解", "逻辑推理", "知识问答", "代码生成",
    "文本生成", "数学能力", "多语言能力", "安全性"
]

# 配色方案 - 现代浅色主题
COLORS = {
    "bg": "#f8f9fa",
    "bg_card": "#ffffff",
    "bg_sidebar": "#f1f3f5",
    "text": "#212529",
    "text_muted": "#6c757d",
    "primary": "#0d6efd",
    "success": "#198754",
    "warning": "#ffc107",
    "danger": "#dc3545",
    "info": "#0dcaf0",
    "border": "#dee2e6",
    "chart_colors": [
        "#0d6efd", "#198754", "#ffc107", "#dc3545",
        "#0dcaf0", "#6f42c1", "#fd7e14", "#20c997"
    ]
}

WINDOW_TITLE = "LLM评测分析系统"
WINDOW_SIZE = "1400x900"
