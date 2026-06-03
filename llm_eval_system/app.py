"""大语言模型评测分析系统 - 现代化GUI"""

import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'PingFang SC', 'Heiti SC', 'SimHei', 'STHeiti', 'WenQuanYi Micro Hei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
import threading
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import EVALUATION_DIMENSIONS
from crawler import get_latest_models, get_simulated_data
from database import DatabaseManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 现代化配色方案
BG = "#f8fafc"              # 浅灰背景
CARD_BG = "#ffffff"        # 卡片白色
SIDEBAR_BG = "#f1f5f9"     # 侧边栏
HEADER_BG = "#1e293b"      # 深蓝灰色顶部
HEADER_TEXT = "#f8fafc"    # 白色文字
PRIMARY = "#3b82f6"        # 明亮蓝色
PRIMARY_HOVER = "#2563eb"  # 悬停蓝色
SUCCESS = "#10b981"        # 绿色
SUCCESS_HOVER = "#059669"   # 悬停绿色
TEXT = "#1e293b"           # 深色文字
TEXT_MUTED = "#64748b"     # 灰色文字
BORDER = "#e2e8f0"        # 边框色
CHART_COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", 
                "#06b6d4", "#8b5cf6", "#f97316", "#14b8a6"]


class ModernApp:
    """现代化GUI应用"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("LLM评测分析系统")
        self.root.geometry("1400x900")
        self.root.configure(bg=BG)
        
        # 数据
        self.raw_data = []
        self.filtered_data = []
        self.models = []
        
        # 初始化
        self.db = DatabaseManager()
        self._setup_styles()
        self._build_ui()
        self._load_data()
    
    def _setup_styles(self):
        """设置现代化样式"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Treeview样式
        style.configure('Custom.Treeview', 
                       background=CARD_BG, 
                       foreground=TEXT, 
                       rowheight=32,
                       font=('Arial', 10),
                       fieldbackground=CARD_BG)
        style.configure('Custom.Treeview.Heading', 
                       background="#e2e8f0", 
                       foreground=TEXT,
                       font=('Arial', 10, 'bold'), 
                       padding=8)
        style.map('Custom.Treeview', 
                 background=[('selected', '#dbeafe')],
                 foreground=[('selected', TEXT)])
    
    def _build_ui(self):
        """构建UI"""
        self._build_header()
        
        main_frame = tk.Frame(self.root, bg=BG)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        
        # 左侧边栏
        self.sidebar = tk.Frame(main_frame, bg=SIDEBAR_BG, width=260, 
                               highlightbackground=BORDER, highlightthickness=1)
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 12))
        self.sidebar.pack_propagate(False)
        self._build_sidebar()
        
        # 右侧内容
        self.content = tk.Frame(main_frame, bg=BG)
        self.content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._build_content()
    
    def _build_header(self):
        """现代化顶部导航栏"""
        header = tk.Frame(self.root, bg=HEADER_BG, height=55)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        logo_frame = tk.Frame(header, bg=HEADER_BG)
        logo_frame.pack(side=tk.LEFT, padx=20)
        
        tk.Label(logo_frame, text="🤖", bg=HEADER_BG, fg=HEADER_TEXT,
                font=('Arial', 20)).pack(side=tk.LEFT, padx=(0, 10))
        tk.Label(logo_frame, text="LLM评测分析系统", bg=HEADER_BG, fg=HEADER_TEXT,
                font=('Arial', 16, 'bold')).pack(side=tk.LEFT)
        
        nav = tk.Frame(header, bg=HEADER_BG)
        nav.pack(side=tk.LEFT, padx=30)
        
        self._nav_btn(nav, "排行榜", self._show_ranking_tab)
        self._nav_btn(nav, "可视化", self._show_chart_tab)
        self._nav_btn(nav, "模型对比", self._show_compare_tab)
        self._nav_btn(nav, "原始数据", self._show_data_tab)
    
    def _nav_btn(self, parent, text, command):
        """用Label模拟按钮 - macOS上tk.Button的bg/fg不生效"""
        btn = tk.Label(parent, text=text,
                      bg="#334155", fg=HEADER_TEXT,
                      font=('Arial', 11), 
                      padx=18, pady=8,
                      cursor="hand2")
        btn.pack(side=tk.LEFT, padx=4, pady=10)
        
        def on_enter(e):
            btn.config(bg=PRIMARY, fg=HEADER_TEXT)
        def on_leave(e):
            btn.config(bg="#334155", fg=HEADER_TEXT)
        def on_click(e):
            command()
        
        btn.bind('<Enter>', on_enter)
        btn.bind('<Leave>', on_leave)
        btn.bind('<Button-1>', on_click)
        return btn
    
    def _build_sidebar(self):
        """构建现代化侧边栏"""
        # 标题
        tk.Label(self.sidebar, text="筛选条件", bg=SIDEBAR_BG, fg=TEXT,
                font=('Arial', 13, 'bold')).pack(anchor=tk.W, padx=15, pady=(15, 10))
        
        # 模型分类筛选
        filter_frame = tk.Frame(self.sidebar, bg=SIDEBAR_BG)
        filter_frame.pack(fill=tk.X, padx=15, pady=5)
        
        tk.Label(filter_frame, text="模型分类", bg=SIDEBAR_BG, fg=TEXT_MUTED,
                font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(0, 5))
        
        self.filter_var = tk.StringVar(value="all")
        for val, text in [("all", "全部模型"), ("domestic", "国内模型"), 
                          ("international", "国际模型")]:
            tk.Radiobutton(filter_frame, text=text, variable=self.filter_var, 
                          value=val, bg=SIDEBAR_BG, font=('Arial', 10),
                          command=self._apply_filter).pack(anchor=tk.W, pady=2)
        
        # 分割线
        tk.Frame(self.sidebar, bg=BORDER, height=1).pack(fill=tk.X, padx=15, pady=10)
        
        # 维度选择
        dim_frame = tk.Frame(self.sidebar, bg=SIDEBAR_BG)
        dim_frame.pack(fill=tk.X, padx=15, pady=5)
        
        tk.Label(dim_frame, text="评测维度", bg=SIDEBAR_BG, fg=TEXT_MUTED,
                font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(0, 5))
        
        self.dim_vars = {}
        for dim in EVALUATION_DIMENSIONS:
            var = tk.BooleanVar(value=True)
            self.dim_vars[dim] = var
            tk.Checkbutton(dim_frame, text=dim, variable=var, bg=SIDEBAR_BG,
                          font=('Arial', 10), command=self._apply_filter).pack(anchor=tk.W, pady=1)
        
        # 分割线
        tk.Frame(self.sidebar, bg=BORDER, height=1).pack(fill=tk.X, padx=15, pady=10)
        
        # 统计信息
        stats_frame = tk.Frame(self.sidebar, bg=SIDEBAR_BG)
        stats_frame.pack(fill=tk.X, padx=15, pady=5)
        
        tk.Label(stats_frame, text="统计信息", bg=SIDEBAR_BG, fg=TEXT_MUTED,
                font=('Arial', 10, 'bold')).pack(anchor=tk.W, pady=(0, 5))
        
        self.stats_labels = {}
        for key in ["模型数", "平均分数", "最高分数"]:
            row = tk.Frame(stats_frame, bg=SIDEBAR_BG)
            row.pack(fill=tk.X, pady=3)
            tk.Label(row, text=f"{key}:", bg=SIDEBAR_BG, fg=TEXT_MUTED, 
                    font=('Arial', 10)).pack(side=tk.LEFT)
            self.stats_labels[key] = tk.Label(row, text="-", bg=SIDEBAR_BG,
                                              fg=PRIMARY, font=('Arial', 10, 'bold'))
            self.stats_labels[key].pack(side=tk.RIGHT)
    
    def _build_content(self):
        """构建内容区"""
        self.rank_frame = tk.Frame(self.content, bg=BG)
        self.chart_frame = tk.Frame(self.content, bg=BG)
        self.compare_frame = tk.Frame(self.content, bg=BG)
        self.data_frame = tk.Frame(self.content, bg=BG)
        
        self._build_ranking(self.rank_frame)
        self._build_chart(self.chart_frame)
        self._build_compare(self.compare_frame)
        self._build_data(self.data_frame)
        
        self._show_ranking_tab()
    
    def _build_ranking(self, parent):
        """排行榜页面"""
        tk.Label(parent, text="模型排行榜", bg=BG, fg=TEXT,
                font=('Arial', 20, 'bold')).pack(anchor=tk.W, pady=(15, 10), padx=10)
        
        # 搜索和筛选区
        control_frame = tk.Frame(parent, bg=BG)
        control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 搜索框
        search_container = tk.Frame(control_frame, bg=BG)
        search_container.pack(side=tk.LEFT)
        
        tk.Label(search_container, text="🔍", bg=BG, font=('Arial', 12)).pack(side=tk.LEFT)
        self.search_var = tk.StringVar()
        self.search_var.trace_add('write', lambda *args: self._apply_filter())
        tk.Entry(search_container, textvariable=self.search_var, font=('Arial', 10), 
                width=25, bd=1, relief="solid").pack(side=tk.LEFT, padx=5)
        
        # 公司筛选
        tk.Label(control_frame, text="公司:", bg=BG, fg=TEXT,
                font=('Arial', 10)).pack(side=tk.LEFT, padx=(20, 5))
        self.company_filter_var = tk.StringVar(value="全部")
        self.company_combo = ttk.Combobox(control_frame, textvariable=self.company_filter_var, 
                                          width=15, state="readonly")
        self.company_combo.pack(side=tk.LEFT, padx=5)
        self.company_combo.bind('<<ComboboxSelected>>', lambda e: self._apply_filter())
        
        # 排序
        tk.Label(control_frame, text="排序:", bg=BG, fg=TEXT,
                font=('Arial', 10)).pack(side=tk.LEFT, padx=(20, 5))
        self.sort_var = tk.StringVar(value="总榜排名")
        sort_combo = ttk.Combobox(control_frame, textvariable=self.sort_var, 
                                  width=12, state="readonly")
        sort_combo['values'] = ["总榜排名", "评分降序", "评分升序", "名称A-Z", "名称Z-A"]
        sort_combo.pack(side=tk.LEFT, padx=5)
        sort_combo.bind('<<ComboboxSelected>>', lambda e: self._apply_filter())
        
        columns = ('rank', 'model', 'company', 'category', 'score')
        self.tree = ttk.Treeview(parent, columns=columns, show='headings',
                                style='Custom.Treeview', height=22)
        
        for col, text, width in [('rank', '排名', 80), ('model', '模型名称', 250), 
                                  ('company', '公司', 120), ('category', '分类', 80), 
                                  ('score', '评分', 80)]:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=width, anchor='center' if col in ('rank', 'score') else 'w')
        
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def _build_chart(self, parent):
        """图表页面"""
        tk.Label(parent, text="数据可视化", bg=BG, fg=TEXT,
                font=('Arial', 20, 'bold')).pack(anchor=tk.W, pady=(15, 10), padx=10)
        
        btn_frame = tk.Frame(parent, bg=BG)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # 现代化按钮
        for text, cmd in [("排名对比", self._show_bar_chart), 
                          ("能力雷达", self._show_radar_chart),
                          ("热力图", self._show_heatmap)]:
            btn = tk.Label(btn_frame, text=text,
                          bg=PRIMARY, fg="white",
                          font=('Arial', 10, 'bold'), 
                          padx=15, pady=8,
                          cursor="hand2")
            btn.pack(side=tk.LEFT, padx=5)
            
            def make_handlers(b, c):
                def on_enter(e):
                    b.config(bg=PRIMARY_HOVER)
                def on_leave(e):
                    b.config(bg=PRIMARY)
                def on_click(e):
                    c()
                return on_enter, on_leave, on_click
            enter_h, leave_h, click_h = make_handlers(btn, cmd)
            btn.bind('<Enter>', enter_h)
            btn.bind('<Leave>', leave_h)
            btn.bind('<Button-1>', click_h)
        
        self.chart_container = tk.Frame(parent, bg=BG)
        self.chart_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    def _build_compare(self, parent):
        """对比页面"""
        tk.Label(parent, text="模型对比", bg=BG, fg=TEXT,
                font=('Arial', 20, 'bold')).pack(anchor=tk.W, pady=(15, 10), padx=10)
        
        select_frame = tk.Frame(parent, bg=BG)
        select_frame.pack(fill=tk.X, padx=10, pady=10)
        
        tk.Label(select_frame, text="模型1:", bg=BG, fg=TEXT, font=('Arial', 11)).pack(side=tk.LEFT)
        self.model1_var = tk.StringVar()
        self.model1_combo = ttk.Combobox(select_frame, textvariable=self.model1_var, width=25)
        self.model1_combo.pack(side=tk.LEFT, padx=5)
        
        tk.Label(select_frame, text=" VS ", bg=BG, fg=PRIMARY, font=('Arial', 12, 'bold')).pack(side=tk.LEFT, padx=10)
        
        tk.Label(select_frame, text="模型2:", bg=BG, fg=TEXT, font=('Arial', 11)).pack(side=tk.LEFT)
        self.model2_var = tk.StringVar()
        self.model2_combo = ttk.Combobox(select_frame, textvariable=self.model2_var, width=25)
        self.model2_combo.pack(side=tk.LEFT, padx=5)
        
        compare_btn = tk.Label(select_frame, text="开始对比",
                              bg=SUCCESS, fg="white",
                              font=('Arial', 10, 'bold'), padx=20, pady=5,
                              cursor="hand2")
        compare_btn.pack(side=tk.LEFT, padx=20)
        
        def cb_enter(e):
            compare_btn.config(bg=SUCCESS_HOVER)
        def cb_leave(e):
            compare_btn.config(bg=SUCCESS)
        compare_btn.bind('<Enter>', cb_enter)
        compare_btn.bind('<Leave>', cb_leave)
        compare_btn.bind('<Button-1>', lambda e: self._do_compare())
        
        self.compare_result = tk.Frame(parent, bg=BG)
        self.compare_result.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    def _build_data(self, parent):
        """数据页面"""
        tk.Label(parent, text="原始数据", bg=BG, fg=TEXT,
                font=('Arial', 20, 'bold')).pack(anchor=tk.W, pady=(15, 10), padx=10)
        
        self.data_tree = ttk.Treeview(parent, columns=('model', 'company', 'cat', 'dim', 'score', 'source'),
                                      show='headings', style='Custom.Treeview', height=25)
        
        for col, text, w in [('model', '模型', 200), ('company', '公司', 100), ('cat', '分类', 60),
                             ('dim', '维度', 80), ('score', '分数', 60), ('source', '来源', 100)]:
            self.data_tree.heading(col, text=text)
            self.data_tree.column(col, width=w)
        
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.data_tree.yview)
        self.data_tree.configure(yscrollcommand=scrollbar.set)
        
        self.data_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    # ==================== 页面切换 ====================
    def _show_ranking_tab(self):
        self._hide_all()
        self.rank_frame.pack(fill=tk.BOTH, expand=True)
    
    def _show_chart_tab(self):
        self._hide_all()
        self.chart_frame.pack(fill=tk.BOTH, expand=True)
    
    def _show_compare_tab(self):
        self._hide_all()
        self.compare_frame.pack(fill=tk.BOTH, expand=True)
    
    def _show_data_tab(self):
        self._hide_all()
        self.data_frame.pack(fill=tk.BOTH, expand=True)
    
    def _hide_all(self):
        for frame in [self.rank_frame, self.chart_frame, self.compare_frame, self.data_frame]:
            frame.pack_forget()
    
    # ==================== 数据加载 ====================
    def _load_data(self):
        def load():
            try:
                self.raw_data = get_latest_models()
                if not self.raw_data:
                    self.raw_data = get_simulated_data()
                
                self.filtered_data = self.raw_data.copy()
                self.root.after(0, self._update_models_list)
                self.root.after(0, self._update_ui)
            except Exception as e:
                logger.error(f"加载数据失败: {e}")
                self.raw_data = get_simulated_data()
                self.filtered_data = self.raw_data.copy()
                self.root.after(0, self._update_models_list)
                self.root.after(0, self._update_ui)
        
        threading.Thread(target=load, daemon=True).start()
    
    def _update_models_list(self):
        model_scores = {}
        for d in self.raw_data:
            model = d['model']
            if model not in model_scores:
                model_scores[model] = []
            model_scores[model].append(d['score'])
        avg_scores = {m: sum(s)/len(s) for m, s in model_scores.items()}
        self.models = sorted(avg_scores.keys(), key=lambda m: avg_scores[m], reverse=True)
        self.model1_combo['values'] = self.models
        self.model2_combo['values'] = self.models
        if len(self.models) >= 2:
            self.model1_var.set(self.models[0])
            self.model2_var.set(self.models[1])
        
        # 更新公司筛选下拉框
        companies = set()
        for d in self.raw_data:
            if d.get('company'):
                companies.add(d['company'])
        company_list = sorted(companies)
        self.company_combo['values'] = ["全部"] + company_list
    
    def _apply_filter(self):
        category = self.filter_var.get()
        selected_dims = [d for d, v in self.dim_vars.items() if v.get()]
        
        self.filtered_data = []
        for d in self.raw_data:
            if category != "all" and d.get('category') != category:
                continue
            if d.get('dimension') in selected_dims:
                self.filtered_data.append(d)
        
        self._update_ui()
    
    def _update_ui(self):
        self._update_ranking()
        self._update_stats()
        self._update_data_tab()
    
    def _update_ranking(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        
        model_scores = {}
        model_info = {}
        for d in self.raw_data:
            model = d['model']
            if model not in model_scores:
                model_scores[model] = []
                model_info[model] = d
            model_scores[model].append(d['score'])
        
        ranked = []
        for model, scores in model_scores.items():
            avg = sum(scores) / len(scores)
            info = model_info[model]
            cat = '国内' if info.get('category') == 'domestic' else '国际'
            ranked.append({'model': model, 'company': info.get('company', ''), 
                          'category': cat, 'score': avg})
        
        ranked.sort(key=lambda x: x['score'], reverse=True)
        for i, r in enumerate(ranked, 1):
            r['global_rank'] = i
        
        filtered = ranked[:]
        
        search_term = self.search_var.get().lower().strip()
        if search_term:
            filtered = [r for r in filtered if search_term in r['model'].lower() 
                       or search_term in r['company'].lower()]
        
        company_filter = self.company_filter_var.get()
        if company_filter != "全部":
            filtered = [r for r in filtered if r['company'] == company_filter]
        
        category = self.filter_var.get()
        if category != "all":
            filtered = [r for r in filtered if r.get('category') == ('国内' if category == 'domestic' else '国际')]
        
        is_filtered = bool(search_term) or company_filter != "全部" or category != "all"
        
        sort_type = self.sort_var.get()
        if sort_type == "评分降序":
            filtered.sort(key=lambda x: x['score'], reverse=True)
        elif sort_type == "评分升序":
            filtered.sort(key=lambda x: x['score'])
        elif sort_type == "名称A-Z":
            filtered.sort(key=lambda x: x['model'].lower())
        elif sort_type == "名称Z-A":
            filtered.sort(key=lambda x: x['model'].lower(), reverse=True)
        elif sort_type == "总榜排名":
            filtered.sort(key=lambda x: x['global_rank'])
        
        for i, r in enumerate(filtered, 1):
            if is_filtered and i != r['global_rank']:
                rank_text = f"#{i}(#{r['global_rank']})"
            else:
                rank_text = f"#{i}"
            self.tree.insert('', tk.END, values=(
                rank_text, r['model'], r['company'], r['category'], f"{r['score']:.2f}"
            ))
    
    def _update_stats(self):
        if not self.filtered_data:
            return
        
        scores = [d['score'] for d in self.filtered_data]
        model_count = len(set(d['model'] for d in self.filtered_data))
        
        self.stats_labels["模型数"].config(text=str(model_count))
        self.stats_labels["平均分数"].config(text=f"{sum(scores)/len(scores):.2f}")
        self.stats_labels["最高分数"].config(text=f"{max(scores):.2f}")
    
    def _update_data_tab(self):
        for item in self.data_tree.get_children():
            self.data_tree.delete(item)
        
        for d in self.filtered_data[:100]:
            cat = '国内' if d.get('category') == 'domestic' else '国际'
            self.data_tree.insert('', tk.END, values=(
                d['model'], d.get('company', ''), cat,
                d.get('dimension', ''), f"{d['score']:.2f}", d.get('source', '')
            ))
    
    # ==================== 图表 ====================
    def _show_bar_chart(self):
        self._clear_chart()
        
        model_scores = {}
        for d in self.raw_data:
            model = d['model']
            if model not in model_scores:
                model_scores[model] = []
            model_scores[model].append(d['score'])
        
        avg_scores = {k: sum(v)/len(v) for k, v in model_scores.items()}
        top_10 = sorted(avg_scores.items(), key=lambda x: x[1], reverse=True)[:10]
        
        fig, ax = plt.subplots(figsize=(12, 7))
        models = [x[0] for x in top_10]
        scores = [x[1] for x in top_10]
        
        ax.barh(range(len(models)), scores, color=CHART_COLORS[:len(models)])
        ax.set_yticks(range(len(models)))
        ax.set_yticklabels(models, fontsize=9)
        ax.set_xlabel('综合评分')
        ax.set_title('Top 10 模型排名', fontsize=14, fontweight='bold')
        ax.invert_yaxis()
        
        for i, s in enumerate(scores):
            ax.text(s + 0.3, i, f'{s:.1f}', va='center', fontsize=8)
        
        plt.subplots_adjust(left=0.28, right=0.95, top=0.92, bottom=0.08)
        
        canvas = FigureCanvasTkAgg(fig, master=self.chart_container)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    def _show_radar_chart(self):
        """显示雷达图 - 选择主流公司的最强模型"""
        self._clear_chart()
        
        # 主流公司列表
        mainstream_companies = {
            'OpenAI', 'Anthropic', 'Google', 'Meta', 'Mistral AI', 'xAI',
            '阿里巴巴', '字节跳动', '月之暗面', '深度求索', '智谱AI', '百度', '腾讯', '小米'
        }
        
        # 按公司分组，选择每个主流公司的最高分模型
        company_models = {}
        for d in self.raw_data:
            company = d.get('company', '未知')
            if company not in mainstream_companies:
                continue
            model = d['model']
            if company not in company_models:
                company_models[company] = {'model': model, 'score': d['score']}
            elif d['score'] > company_models[company]['score']:
                company_models[company] = {'model': model, 'score': d['score']}
        
        # 选择Top5主流公司
        top_companies = sorted(company_models.items(), key=lambda x: x[1]['score'], reverse=True)[:5]
        
        model_scores = {}
        for company, info in top_companies:
            model = info['model']
            model_scores[model] = {}
            for d in self.raw_data:
                if d['model'] == model:
                    model_scores[model][d['dimension']] = d['score']
        
        fig = plt.figure(figsize=(10, 8))
        ax = fig.add_subplot(111, polar=True)
        
        angles = np.linspace(0, 2*np.pi, len(EVALUATION_DIMENSIONS), endpoint=False).tolist()
        angles += angles[:1]
        
        all_values = []
        for i, (company, info) in enumerate(top_companies):
            model = info['model']
            values = [model_scores[model].get(d, 0) for d in EVALUATION_DIMENSIONS]
            all_values.extend(values)
            values += values[:1]
            label = f"{company} ({model[:12]})"
            ax.plot(angles, values, 'o-', linewidth=2, label=label, color=CHART_COLORS[i])
            ax.fill(angles, values, alpha=0.15, color=CHART_COLORS[i])
        
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(EVALUATION_DIMENSIONS, fontsize=9)
        if all_values:
            y_min = max(0, min(all_values) - 5)
            y_max = min(100, max(all_values) + 5)
            if y_max - y_min < 10:
                y_min = max(0, y_min - 5)
                y_max = min(100, y_max + 5)
            ax.set_ylim(y_min, y_max)
        ax.legend(loc='upper right', bbox_to_anchor=(1.35, 1.0), fontsize=8)
        ax.set_title('主流公司最强模型能力雷达图', fontsize=14, fontweight='bold', pad=25)
        
        plt.subplots_adjust(right=0.72)
        
        canvas = FigureCanvasTkAgg(fig, master=self.chart_container)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    def _show_heatmap(self):
        """显示热力图 - Top10公司旗舰模型，按分数排序"""
        self._clear_chart()
        
        company_best = {}
        for d in self.raw_data:
            company = d.get('company', '未知')
            model = d['model']
            if company not in company_best:
                company_best[company] = {'model': model, 'scores': [d['score']]}
            else:
                company_best[company]['scores'].append(d['score'])
        
        company_avg = {}
        for company, info in company_best.items():
            avg = sum(info['scores']) / len(info['scores'])
            company_avg[company] = {'model': info['model'], 'avg': avg}
        
        top10 = sorted(company_avg.items(), key=lambda x: x[1]['avg'], reverse=True)[:10]
        models = [info['model'] for _, info in top10]
        
        matrix = np.zeros((len(models), len(EVALUATION_DIMENSIONS)))
        
        for i, model in enumerate(models):
            for j, dim in enumerate(EVALUATION_DIMENSIONS):
                scores = [d['score'] for d in self.raw_data if d['model'] == model and d['dimension'] == dim]
                matrix[i, j] = scores[0] if scores else 0
        
        fig, ax = plt.subplots(figsize=(12, 8))
        im = ax.imshow(matrix, cmap='YlOrRd', aspect='auto')
        
        ax.set_xticks(range(len(EVALUATION_DIMENSIONS)))
        ax.set_xticklabels(EVALUATION_DIMENSIONS, rotation=45, ha='right')
        ax.set_yticks(range(len(models)))
        display_names = []
        for idx, (company, info) in enumerate(top10):
            m = info['model']
            name = f"{company} | {m}"
            display_names.append(name)
        ax.set_yticklabels(display_names, fontsize=8)
        ax.set_title('Top 10 公司旗舰模型能力热力图', fontsize=14, fontweight='bold')
        
        for i in range(len(models)):
            for j in range(len(EVALUATION_DIMENSIONS)):
                val = matrix[i, j]
                text_color = 'white' if val > 80 else 'black'
                ax.text(j, i, f'{val:.0f}', ha='center', va='center', fontsize=7, color=text_color)
        
        plt.colorbar(im, ax=ax, label='分数')
        plt.subplots_adjust(left=0.30, right=0.92, top=0.93, bottom=0.10)
        
        canvas = FigureCanvasTkAgg(fig, master=self.chart_container)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    def _clear_chart(self):
        for widget in self.chart_container.winfo_children():
            widget.destroy()
    
    # ==================== 对比 ====================
    def _do_compare(self):
        m1 = self.model1_var.get()
        m2 = self.model2_var.get()
        
        if not m1 or not m2:
            messagebox.showwarning("提示", "请选择两个模型")
            return
        
        m1_data = [d for d in self.raw_data if d['model'] == m1]
        m2_data = [d for d in self.raw_data if d['model'] == m2]
        
        if not m1_data or not m2_data:
            messagebox.showwarning("提示", "模型数据不足")
            return
        
        for widget in self.compare_result.winfo_children():
            widget.destroy()
        
        result = tk.Frame(self.compare_result, bg=BG)
        result.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(result, text=f"{m1} vs {m2}", bg=BG, fg=PRIMARY,
                font=('Arial', 14, 'bold')).pack(pady=10)
        
        tree = ttk.Treeview(result, columns=('dim', 'm1', 'm2', 'winner'), show='headings', height=10)
        tree.heading('dim', text='维度')
        tree.heading('m1', text=m1)
        tree.heading('m2', text=m2)
        tree.heading('winner', text='胜者')
        
        for col in ['dim', 'm1', 'm2', 'winner']:
            tree.column(col, width=150, anchor='center')
        
        for dim in EVALUATION_DIMENSIONS:
            s1 = next((d['score'] for d in m1_data if d['dimension'] == dim), 0)
            s2 = next((d['score'] for d in m2_data if d['dimension'] == dim), 0)
            winner = m1 if s1 > s2 else m2
            tree.insert('', tk.END, values=(dim, f"{s1:.2f}", f"{s2:.2f}", winner))
        
        tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    


def main():
    root = tk.Tk()
    app = ModernApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
