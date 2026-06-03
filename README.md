# LLM-Eval · 大语言模型评测分析系统

一款桌面端 LLM 评测数据采集与可视化分析工具，基于 Tkinter 构建，参考 WordPress Dashboard 风格的清新浅色 UI。

## 功能特性

- **数据采集** — 爬取 LMSYS Arena 等公开排行榜，自动解析模型排名与分数；爬取失败时回退至内置模拟数据
- **多维评测** — 8 大评测维度：语言理解、逻辑推理、知识问答、代码生成、文本生成、数学能力、多语言能力、安全性
- **国内/国际分类** — 自动识别模型归属（OpenAI、Google、Anthropic、阿里巴巴、深度求索、月之暗面等）
- **可视化分析**
  - 综合排行榜（国内 / 国际 / 全部）
  - 多模型雷达图对比
  - 模型能力热力图（Top 15）
  - 各维度柱状图
- **数据导入导出** — 支持 CSV / JSON 文件上传与导出
- **本地存储** — SQLite 数据库持久化，单例模式管理连接

## 项目结构

```
LLM-Eval/
├── main.py                          # 程序入口
├── start.sh                         # 快捷启动脚本
├── parse_lmarena.py                 # LMSYS Arena 排行榜解析脚本
├── test_crawler.py                  # 爬虫探测测试脚本
├── llm_eval_system/
│   ├── __init__.py
│   ├── core/
│   │   ├── config.py                # 全局配置（数据库路径、评测维度、窗口参数）
│   │   └── theme.py                 # UI 主题配色与排版常量
│   ├── ui/
│   │   ├── main_window.py           # 主窗口（侧边栏 + 5 个 Tab 页）
│   │   ├── components.py            # 可复用 UI 组件（RoundedCard、StyledButton 等）
│   │   └── icons/
│   │       ├── __init__.py
│   │       └── icon_renderer.py     # 图标渲染
│   ├── spider/
│   │   ├── __init__.py
│   │   └── crawler.py               # 网络爬虫（LMSYS Arena + 模拟数据）
│   ├── data/
│   │   ├── __init__.py
│   │   └── db_manager.py            # SQLite 数据库管理（单例、CRUD）
│   └── utils/
│       ├── __init__.py
│       ├── exceptions.py            # 全局异常处理与装饰器
│       ├── file_handler.py          # 文件上传 / 导入 / 导出
│       └── thread_manager.py        # 多线程任务队列
└── llm_evaluation.db                # SQLite 数据库文件（运行后生成）
```

## 技术栈

- Python 3.13
- Tkinter（GUI）
- Matplotlib（图表渲染）
- SQLite（数据持久化）
- BeautifulSoup4 + Requests（数据采集）
- Pillow（图标与图片处理）

## 快速开始

```bash
# 1. 克隆仓库
git clone <repo-url>
cd LLM-Eval

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# 3. 安装依赖
pip install matplotlib beautifulsoup4 requests pillow

# 4. 启动应用
python main.py
# 或
bash start.sh
```

## 评测维度说明

| 维度 | 说明 |
|------|------|
| 语言理解 | 自然语言语义理解与意图识别能力 |
| 逻辑推理 | 复杂逻辑推演与因果分析能力 |
| 知识问答 | 知识储备与事实性问答准确度 |
| 代码生成 | 编程语言代码生成与调试能力 |
| 文本生成 | 创意写作、摘要、翻译等生成质量 |
| 数学能力 | 数学运算与数学推理能力 |
| 多语言能力 | 跨语言理解与生成能力 |
| 安全性 | 内容安全与合规性表现 |

## 数据来源

- **LMSYS Arena** — 基于 Elo 评分的大模型众评排行榜（`https://lmarena.ai/leaderboard`）
- **模拟数据** — 爬取失败时的本地回退数据，涵盖 15 个主流国内外模型

## License

MIT
