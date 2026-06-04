# LLM-Eval · 大语言模型评测分析系统

一款桌面端 LLM 评测数据采集与可视化分析工具，基于 Tkinter 构建的**浅色亚克力风格** GUI 应用。

## 功能特性

- **多领域数据采集** — 爬取 LMSYS Arena 多个领域排行榜（综合、代码、文档理解、搜索、视觉、文生图、图片编辑、文生视频），每个领域独立排名
- **智能数据加载策略**
  - 本地有数据 → 优先读取本地缓存，秒开
  - 点击「刷新数据」→ 主动抓取最新榜单；成功更新，失败则**保留本地分析不变**并 Toast 提示
  - 本地无数据 → 自动抓取；抓取失败则回退到内置写死数据，保证始终可用
- **综合领域8维评测** — 语言理解、逻辑推理、知识问答、代码生成、文本生成、数学能力、多语言能力、安全性
- **国内/国际分类** — 自动识别模型归属（OpenAI、Google、Anthropic、阿里巴巴、深度求索、月之暗面等）
- **丰富字段展示与分析** — Arena Score、投票数、输入/输出价格、上下文长度、License、**性价比（分/美元）**，支持多维排序（性价比、上下文、投票、代码生成等）
- **可视化分析**
  - 排行榜 — 多维筛选/排序，前三名奖牌高亮，模型详情含全维度拆解
  - 模型对比 — 双模型维度柱状图/雷达图对比 + 胜负统计
  - 雷达图/能力对比 — 综合领域展示8维雷达图，单维度领域自动切换为柱状图
  - 综合洞察 — 能力热力图、置信区间、性价比散点图、排名分布、开源vs闭源、投票热度等6张图表（懒渲染，点击放大）
- **领域切换** — 侧边栏选择评测领域，排行榜/对比/图表联动刷新
- **数据导入导出** — 支持 CSV / JSON 文件上传与导出
- **本地存储** — SQLite 数据库持久化，单例模式管理连接

## UI 设计

- **浅色亚克力风格** — 半透明叠色卡片 + 柔和描边 + 阴影感，统一大圆角
- **统一设计系统** — 全局统一的圆角档位、8pt 间距栅格、按钮尺寸规范（集中在 `core/theme.py`）
- **顺滑滚动** — 鼠标滚轮 / 触摸板可在任意区域（含卡片、图表内部）滚动主内容区与侧边栏
- **统计卡概览** — 侧边栏关键指标以图标统计卡网格呈现

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
│   │   ├── main_window.py           # 主窗口（侧边栏 + 领域选择 + 4 个 Tab 页）
│   │   ├── components.py            # 可复用 UI 组件（RoundedCard、SidebarButton、StyledButton 等）
│   │   └── icons/
│   │       ├── __init__.py
│   │       └── icon_renderer.py     # 图标渲染
│   ├── spider/
│   │   ├── __init__.py
│   │   └── crawler.py               # 网络爬虫（多领域 LMSYS Arena + 模拟数据）
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

## 评测领域说明

| 领域 | 数据来源 | 说明 |
|------|----------|------|
| 综合领域 | Text Arena | 8维度综合评测，雷达图/热力图/开源闭源对比等完整分析 |
| 代码 | Code Arena | 代码生成能力排名 |
| 文档理解 | Document Arena | 文档理解与知识问答排名 |
| 搜索 | Search Arena | 搜索增强与逻辑推理排名 |
| 视觉 | Vision Arena | 多模态视觉理解排名 |
| 文生图 | Text-to-Image Arena | 图像生成模型排名 |
| 图片编辑 | Image Edit Arena | 图像编辑模型排名 |
| 文生视频 | Text-to-Video Arena | 视频生成模型排名 |

## 综合领域评测维度

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
