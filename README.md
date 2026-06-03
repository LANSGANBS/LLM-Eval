# LLM评测分析系统

基于Python开发的现代化大语言模型评测分析平台。

## 项目结构

```
llm_eval_system/
├── core/              # 核心配置模块
│   ├── config.py      # 全局配置
│   └── theme.py       # 主题配色
├── data/              # 数据模块
│   └── db_manager.py  # 数据库管理
├── spider/            # 爬虫模块
│   └── crawler.py     # 网络爬虫
├── ui/                # 用户界面
│   └── main_window.py # 主窗口
└── utils/             # 工具模块
    ├── exceptions.py    # 异常处理
    ├── file_handler.py  # 文件处理
    └── thread_manager.py # 线程管理
```

## 功能特性

- **模型排行榜**: 基于综合评分的模型排名
- **数据可视化**: 柱状图、饼图、雷达图、热力图
- **模型对比**: 多维度模型对比分析
- **数据筛选**: 按维度、公司、分数筛选
- **文件上传**: 支持CSV/JSON/TXT格式
- **网络爬虫**: 自动抓取最新模型数据
- **多线程**: 异步任务处理与状态监控
- **异常处理**: 全局异常捕获与友好提示

## 技术栈

- Python 3.13
- tkinter (GUI)
- matplotlib (可视化)
- SQLite (数据库)
- requests + BeautifulSoup (爬虫)
- threading (多线程)

## 运行方式

```bash
./start.sh
```

或

```bash
python main.py
```
