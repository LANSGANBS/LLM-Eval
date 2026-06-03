"""
主窗口模块 - 清新浅色GUI应用
参考WordPress Dashboard风格，统一圆角、等距留白
修复：按钮点击区域、鼠标光标、雷达图区间、侧边栏滚动、编码、日志量
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import matplotlib
matplotlib.use('TkAgg')
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import matplotlib
import numpy as np
from PIL import ImageTk
import threading
import logging
import sys
import os
import json
import csv
from datetime import datetime
from typing import List, Dict, Optional
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm_eval_system.core.theme import THEME
from llm_eval_system.core.config import EVALUATION_DIMENSIONS
from llm_eval_system.data.db_manager import DatabaseManager
from llm_eval_system.spider.crawler import get_latest_models, get_simulated_data
from llm_eval_system.utils.file_handler import FileHandler
from llm_eval_system.utils.thread_manager import ThreadManager
from llm_eval_system.utils.exceptions import handle_exception
from llm_eval_system.ui.components import StyledButton, SidebarButton, LoadingSpinner, ToastNotification
from llm_eval_system.ui.icons import get_icon

# Reduce logging - only errors by default for the desktop app.
logging.basicConfig(level=logging.ERROR, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

# Fix matplotlib Chinese font
matplotlib.rcParams['font.sans-serif'] = ['PingFang SC', 'Heiti SC', 'STHeiti',
    'Microsoft YaHei', 'SimHei', 'Arial Unicode MS', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False


def scale_score(score, all_scores=None):
    """将分数映射到当前数据带宽内，放大细微差距但不脱离真实区间。"""
    if all_scores is None or len(all_scores) < 2:
        return score
    min_s = min(all_scores)
    max_s = max(all_scores)
    if max_s - min_s < 1:
        return round(score, 1)
    lower, upper = get_score_range(all_scores, padding_ratio=0.08, minimum_padding=1.2)
    scaled = lower + (score - min_s) / (max_s - min_s) * (upper - lower)
    return round(scaled, 1)


def get_score_range(scores, padding_ratio=0.15, minimum_padding=2.0):
    """Get a good display range for radar chart based on actual data range.
    Returns (min_val, max_val) that is slightly wider than the data range."""
    if not scores:
        return 0, 100
    min_s = min(scores)
    max_s = max(scores)
    spread = max(max_s - min_s, 0.5)
    padding = max(minimum_padding, spread * padding_ratio)
    lower = max(0, min_s - padding)
    upper = min(100, max_s + padding)
    if upper - lower < 6:
        midpoint = (upper + lower) / 2
        lower = max(0, midpoint - 3)
        upper = min(100, midpoint + 3)
    # Round to nice numbers
    lower = math.floor(lower / 2) * 2
    upper = math.ceil(upper / 2) * 2
    return lower, upper


class ModernApp:
    """主窗口类 - 清新浅色风格"""

    def __init__(self, root):
        self.root = root
        self.root.title("LLM评测分析系统")
        self.root.geometry("1600x950")
        self.root.configure(bg=THEME['bg'])
        self.root.minsize(1200, 700)

        self.raw_data = []
        self.filtered_data = []
        self.models = []
        self.current_tab = 'ranking'
        self.content_container = None
        self._global_rank_map = {}
        self._is_loading = False
        self._photo_refs = []  # Keep references to PhotoImage objects

        self.db = DatabaseManager()
        self.file_handler = FileHandler()
        self.thread_manager = ThreadManager(max_workers=3)
        self.thread_manager.start_workers()

        self._loading_frame = None
        self._loading_spinner = None

        self._setup_styles()
        self._build_ui()
        self._load_data_async()

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')

        style.configure('Custom.Treeview',
                        background=THEME['bg_secondary'],
                        foreground=THEME['text'],
                        rowheight=40,
                        font=(THEME['font_family'], 11),
                        fieldbackground=THEME['bg_secondary'])
        style.configure('Custom.Treeview.Heading',
                        background=THEME['bg_tertiary'],
                        foreground=THEME['text'],
                        font=(THEME['font_family'], 11, 'bold'),
                        padding=10)
        style.map('Custom.Treeview',
                  background=[('selected', THEME['primary_light'])],
                  foreground=[('selected', THEME['primary'])])

        style.configure('TScrollbar',
                        background=THEME['bg_tertiary'],
                        troughcolor=THEME['bg_secondary'])

        style.configure('TCombobox',
                        fieldbackground=THEME['bg_secondary'],
                        background=THEME['bg_secondary'])

    def _build_ui(self):
        self._build_header()
        main_frame = tk.Frame(self.root, bg=THEME['bg'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=(0, 24))

        # Sidebar with scrollbar support
        sidebar_outer = tk.Frame(main_frame, bg=THEME['bg_secondary'],
                                  highlightbackground=THEME['border'],
                                  highlightthickness=1, width=300)
        sidebar_outer.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 20))
        sidebar_outer.pack_propagate(False)

        # Canvas + scrollbar for sidebar scrolling
        self._sidebar_canvas = tk.Canvas(sidebar_outer, bg=THEME['bg_secondary'],
                                          highlightthickness=0, width=280)
        sidebar_scroll = ttk.Scrollbar(sidebar_outer, orient=tk.VERTICAL,
                                        command=self._sidebar_canvas.yview)
        self._sidebar_canvas.configure(yscrollcommand=sidebar_scroll.set)

        sidebar_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._sidebar_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Inner frame inside canvas
        self.sidebar = tk.Frame(self._sidebar_canvas, bg=THEME['bg_secondary'])
        self._sidebar_window = self._sidebar_canvas.create_window(
            (0, 0), window=self.sidebar, anchor='nw')

        self.sidebar.bind('<Configure>',
                          lambda e: self._sidebar_canvas.configure(
                              scrollregion=self._sidebar_canvas.bbox('all')))
        self._sidebar_canvas.bind('<Configure>',
                                  lambda e: self._sidebar_canvas.itemconfig(
                                      self._sidebar_window, width=e.width))

        # Mouse wheel scrolling for sidebar
        def _on_sidebar_mousewheel(event):
            delta = event.delta
            if delta == 0 and getattr(event, 'num', None) in (4, 5):
                delta = 120 if event.num == 4 else -120
            self._sidebar_canvas.yview_scroll(int(-1 * (delta / 120)), 'units')
            return 'break'

        self._bind_mousewheel_recursive(self._sidebar_canvas, _on_sidebar_mousewheel)
        self._bind_mousewheel_recursive(self.sidebar, _on_sidebar_mousewheel)

        self._build_sidebar()

        # Content area
        self.content = tk.Frame(main_frame, bg=THEME['bg'])
        self.content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._build_content()

    def _build_header(self):
        header = tk.Frame(self.root, bg=THEME['bg_secondary'], height=64)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        logo_frame = tk.Frame(header, bg=THEME['bg_secondary'])
        logo_frame.pack(side=tk.LEFT, padx=24)

        # Robot icon instead of emoji
        icon_img = get_icon('robot', size=28, color=THEME['primary'])
        self._logo_photo = ImageTk.PhotoImage(icon_img)
        logo_label = tk.Label(logo_frame, image=self._logo_photo,
                              bg=THEME['bg_secondary'])
        logo_label.pack(side=tk.LEFT, padx=(0, 10))

        tk.Label(logo_frame, text="LLM评测分析系统", bg=THEME['bg_secondary'],
                 fg=THEME['text'], font=(THEME['font_family'], 16, 'bold')).pack(side=tk.LEFT)

        # Right action buttons
        btn_frame = tk.Frame(header, bg=THEME['bg_secondary'])
        btn_frame.pack(side=tk.RIGHT, padx=24)

        self._refresh_btn = StyledButton(btn_frame, "刷新数据", self._refresh_data,
                                          icon_name='refresh', color_key='secondary',
                                          text_color=THEME['text_secondary'], font_size=10)
        self._refresh_btn.pack(side=tk.RIGHT, padx=(8, 0))

        self._upload_btn = StyledButton(btn_frame, "上传", self._upload_file,
                                         icon_name='upload', color_key='secondary',
                                         text_color=THEME['text_secondary'], font_size=10)
        self._upload_btn.pack(side=tk.RIGHT, padx=(8, 0))

        self._export_btn = StyledButton(btn_frame, "导出", self._export_data,
                                         icon_name='download', color_key='secondary',
                                         text_color=THEME['text_secondary'], font_size=10)
        self._export_btn.pack(side=tk.RIGHT, padx=(8, 0))

    def _build_sidebar(self):
        """构建侧边栏 - 可滚动"""
        # Navigation section
        nav_label = tk.Label(self.sidebar, text="导航", bg=THEME['bg_secondary'],
                             fg=THEME['text_muted'], font=(THEME['font_family'], 10),
                             anchor='w')
        nav_label.pack(fill=tk.X, padx=16, pady=(20, 8))

        nav_buttons = [
            ('ranking', '排行榜', 'nav_ranking'),
            ('analysis', '数据分析', 'nav_analysis'),
            ('compare', '模型对比', 'nav_compare'),
            ('heatmap', '热力图', 'nav_heatmap'),
        ]

        self._nav_buttons = {}
        for tab_id, label, icon_name in nav_buttons:
            btn = SidebarButton(self.sidebar, label,
                                lambda t=tab_id: self._switch_tab(t),
                                icon_name=icon_name,
                                is_active=(tab_id == self.current_tab))
            btn.pack(fill=tk.X, padx=8, pady=2)
            self._nav_buttons[tab_id] = btn

        # Separator
        sep = tk.Frame(self.sidebar, bg=THEME['border_light'], height=1)
        sep.pack(fill=tk.X, padx=16, pady=16)

        # Data overview section
        overview_label = tk.Label(self.sidebar, text="数据概览", bg=THEME['bg_secondary'],
                                   fg=THEME['text_muted'], font=(THEME['font_family'], 10),
                                   anchor='w')
        overview_label.pack(fill=tk.X, padx=16, pady=(0, 8))

        self._stat_labels = {}
        stats_data = [
            ('model_count', '模型总数', '0'),
            ('eval_count', '评测数据', '0'),
            ('domestic', '国内模型', '0'),
            ('international', '国际模型', '0'),
            ('avg_score', '平均分数', '0'),
            ('top_model', '最高分模型', '-'),
            ('top_score', '最高分', '0'),
            ('dimensions', '评测维度', str(len(EVALUATION_DIMENSIONS))),
        ]
        for key, label_text, default_val in stats_data:
            frame = tk.Frame(self.sidebar, bg=THEME['bg_secondary'])
            frame.pack(fill=tk.X, padx=16, pady=3)

            tk.Label(frame, text=label_text, bg=THEME['bg_secondary'],
                     fg=THEME['text_muted'], font=(THEME['font_family'], 10),
                     anchor='w').pack(side=tk.LEFT)

            val_label = tk.Label(frame, text=default_val, bg=THEME['bg_secondary'],
                                 fg=THEME['text'], font=(THEME['font_family'], 10, 'bold'),
                                 anchor='e')
            val_label.pack(side=tk.RIGHT)
            self._stat_labels[key] = val_label

        # Separator
        sep2 = tk.Frame(self.sidebar, bg=THEME['border_light'], height=1)
        sep2.pack(fill=tk.X, padx=16, pady=16)

        # Company ranking section
        company_label = tk.Label(self.sidebar, text="公司排名", bg=THEME['bg_secondary'],
                                  fg=THEME['text_muted'], font=(THEME['font_family'], 10),
                                  anchor='w')
        company_label.pack(fill=tk.X, padx=16, pady=(0, 8))

        self._company_frame = tk.Frame(self.sidebar, bg=THEME['bg_secondary'])
        self._company_frame.pack(fill=tk.X, padx=16, pady=(0, 16))

        # Ensure sidebar has enough space for scrolling
        self.sidebar.update_idletasks()

    def _bind_mousewheel_recursive(self, widget, handler):
        widget.bind('<MouseWheel>', handler, add='+')
        widget.bind('<Button-4>', handler, add='+')
        widget.bind('<Button-5>', handler, add='+')
        for child in widget.winfo_children():
            self._bind_mousewheel_recursive(child, handler)

    def _build_content(self):
        """构建内容区域"""
        self.content_container = tk.Frame(self.content, bg=THEME['bg'])
        self.content_container.pack(fill=tk.BOTH, expand=True)
        self._show_ranking()

    # ==================== Tab switching ====================

    def _switch_tab(self, tab_id):
        self.current_tab = tab_id
        for tid, btn in self._nav_buttons.items():
            btn.set_active(tid == tab_id)
        for widget in self.content_container.winfo_children():
            widget.destroy()

        tab_map = {
            'ranking': self._show_ranking,
            'analysis': self._show_analysis,
            'compare': self._show_compare,
            'heatmap': self._show_heatmap,
        }
        tab_map.get(tab_id, self._show_ranking)()

    # ==================== Data loading ====================

    def _load_data_async(self):
        def _load():
            data = get_latest_models()
            self.root.after(0, lambda: self._on_data_loaded(data))

        threading.Thread(target=_load, daemon=True).start()

    def _on_data_loaded(self, data):
        if not data:
            data = get_simulated_data()

        self.raw_data = data
        self.filtered_data = data

        # Build model list sorted by average score (descending)
        model_scores = {}
        for item in data:
            m = item.get('model', '')
            if m not in model_scores:
                model_scores[m] = []
            model_scores[m].append(item.get('score', 0))

        avg_scores = {m: sum(s) / len(s) for m, s in model_scores.items()}
        self.models = sorted(avg_scores.keys(), key=lambda m: avg_scores[m], reverse=True)

        # Build global rank map
        self._global_rank_map = {}
        for i, model in enumerate(self.models):
            self._global_rank_map[model] = i + 1

        # Save to database
        self._save_to_db(data)

        # Update sidebar stats
        self._update_stats(data, avg_scores)

        # Refresh current tab
        self._switch_tab(self.current_tab)

    def _save_to_db(self, data):
        try:
            for item in data:
                model_name = item.get('model', '')
                category = item.get('category', 'unknown')
                company = item.get('company', '')
                dimension = item.get('dimension', '')
                score = item.get('score', 0)

                model_id = self.db.insert_or_update_model(model_name, category, company)
                self.db.insert_evaluation(model_id, dimension, score)
        except Exception:
            pass  # Silently handle DB errors

    def _update_stats(self, data, avg_scores):
        if not data:
            return

        domestic = len([m for m in self.models
                        if any(d.get('model') == m and d.get('category') == 'domestic'
                               for d in data)])
        international = len(self.models) - domestic

        all_scores = [d.get('score', 0) for d in data]
        avg_score = sum(all_scores) / len(all_scores) if all_scores else 0

        if avg_scores:
            top_model = max(avg_scores, key=avg_scores.get)
            top_score = avg_scores[top_model]
        else:
            top_model = '-'
            top_score = 0

        self._stat_labels['model_count'].config(text=str(len(self.models)))
        self._stat_labels['eval_count'].config(text=str(len(data)))
        self._stat_labels['domestic'].config(text=str(domestic))
        self._stat_labels['international'].config(text=str(international))
        self._stat_labels['avg_score'].config(text=f"{avg_score:.1f}")
        self._stat_labels['top_model'].config(text=top_model[:12] if len(top_model) > 12 else top_model)
        self._stat_labels['top_score'].config(text=f"{top_score:.1f}")

        # Update company rankings in sidebar
        for w in self._company_frame.winfo_children():
            w.destroy()

        company_best = {}
        for item in data:
            company = item.get('company', '')
            model = item.get('model', '')
            score = item.get('score', 0)
            if company and company != '未知':
                if company not in company_best or avg_scores.get(model, 0) > company_best.get(company, {}).get('score', 0):
                    company_best[company] = {'score': avg_scores.get(model, 0), 'model': model}

        sorted_companies = sorted(company_best.items(), key=lambda x: x[1]['score'], reverse=True)[:8]
        for i, (company, info) in enumerate(sorted_companies):
            row = tk.Frame(self._company_frame, bg=THEME['bg_secondary'])
            row.pack(fill=tk.X, pady=2)

            # Rank number
            tk.Label(row, text=f"{i + 1}.", bg=THEME['bg_secondary'],
                     fg=THEME['text_muted'], font=(THEME['font_family'], 10),
                     width=3, anchor='w').pack(side=tk.LEFT)

            tk.Label(row, text=company, bg=THEME['bg_secondary'],
                     fg=THEME['text'], font=(THEME['font_family'], 10),
                     anchor='w').pack(side=tk.LEFT, fill=tk.X, expand=True)

            tk.Label(row, text=f"{info['score']:.1f}", bg=THEME['bg_secondary'],
                     fg=THEME['primary'], font=(THEME['font_family'], 10, 'bold'),
                     anchor='e').pack(side=tk.RIGHT)

    # ==================== Ranking Tab ====================

    def _show_ranking(self):
        # Search bar
        search_frame = tk.Frame(self.content_container, bg=THEME['bg'])
        search_frame.pack(fill=tk.X, pady=(0, 16))

        search_icon_img = get_icon('search', size=16, color=THEME['text_muted'])
        self._search_photo = ImageTk.PhotoImage(search_icon_img)

        search_container = tk.Frame(search_frame, bg=THEME['bg_secondary'],
                                     highlightbackground=THEME['border'],
                                     highlightthickness=1)
        search_container.pack(fill=tk.X)

        tk.Label(search_container, image=self._search_photo,
                 bg=THEME['bg_secondary']).pack(side=tk.LEFT, padx=(12, 4))

        self.search_var = tk.StringVar()
        search_entry = tk.Entry(search_container, textvariable=self.search_var,
                                bg=THEME['bg_secondary'], fg=THEME['text'],
                                font=(THEME['font_family'], 11),
                                relief='flat', bd=0,
                                insertbackground=THEME['primary'])
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8, pady=10)
        self.search_var.set("搜索模型...")
        self.search_var.trace_add('write', lambda *a: self._filter_ranking())
        search_entry.bind('<FocusIn>', lambda e: search_entry.delete(0, tk.END)
                          if search_entry.get() == "搜索模型..." else None)
        search_entry.bind('<FocusOut>',
                  lambda e: self.search_var.set("搜索模型...")
                  if not search_entry.get().strip() else None)

        tk.Label(search_frame,
             text="榜单分数已按当前样本区间放大显示，便于看出高分模型之间的细微差距。",
             bg=THEME['bg'], fg=THEME['text_muted'],
             font=(THEME['font_family'], 10)).pack(anchor='w', pady=(8, 0))

        # Table frame
        table_frame = tk.Frame(self.content_container, bg=THEME['bg_secondary'],
                                highlightbackground=THEME['border'], highlightthickness=1)
        table_frame.pack(fill=tk.BOTH, expand=True)

        columns = ('rank', 'model', 'company', 'category', 'avg_score', 'dimensions')
        self.ranking_tree = ttk.Treeview(table_frame, columns=columns,
                                          show='headings', style='Custom.Treeview')

        self.ranking_tree.heading('rank', text='排名')
        self.ranking_tree.heading('model', text='模型')
        self.ranking_tree.heading('company', text='公司')
        self.ranking_tree.heading('category', text='类别')
        self.ranking_tree.heading('avg_score', text='对比分')
        self.ranking_tree.heading('dimensions', text='维度数')

        self.ranking_tree.column('rank', width=60, anchor='center')
        self.ranking_tree.column('model', width=200, anchor='w')
        self.ranking_tree.column('company', width=120, anchor='w')
        self.ranking_tree.column('category', width=80, anchor='center')
        self.ranking_tree.column('avg_score', width=100, anchor='center')
        self.ranking_tree.column('dimensions', width=80, anchor='center')

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL,
                                   command=self.ranking_tree.yview)
        self.ranking_tree.configure(yscrollcommand=scrollbar.set)

        self.ranking_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._populate_ranking()

    def _populate_ranking(self):
        if not hasattr(self, 'ranking_tree') or not self.ranking_tree.winfo_exists():
            return
        for item in self.ranking_tree.get_children():
            self.ranking_tree.delete(item)

        # Collect all average scores for score scaling
        model_scores = {}
        for d in self.filtered_data:
            m = d.get('model', '')
            if m not in model_scores:
                model_scores[m] = []
            model_scores[m].append(d.get('score', 0))

        all_avgs = [sum(s) / len(s) for s in model_scores.values() if s]

        for model in self.models:
            scores = model_scores.get(model, [])
            if not scores:
                continue

            # Check search filter
            search = self.search_var.get() if hasattr(self, 'search_var') else ''
            if search and search != "搜索模型...":
                if search.lower() not in model.lower():
                    continue

            avg = sum(scores) / len(scores)
            company = next((d.get('company', '') for d in self.filtered_data
                           if d.get('model') == model), '')
            category = next((d.get('category', '') for d in self.filtered_data
                            if d.get('model') == model), '')

            rank = self._global_rank_map.get(model, 0)

            # Scale the score for display
            scaled = scale_score(avg, all_avgs)

            category_display = "国内" if category == 'domestic' else "国际" if category == 'international' else category

            self.ranking_tree.insert('', tk.END,
                                     values=(f"#{rank}", model, company,
                                 category_display, f"{scaled:.2f}",
                                             len(scores)))

    def _filter_ranking(self):
        self._populate_ranking()

    # ==================== Analysis Tab ====================

    def _show_analysis(self):
        if not self.raw_data:
            return

        sorted_companies = self._get_top_company_flagships(limit=5)

        # Chart frame
        chart_frame = tk.Frame(self.content_container, bg=THEME['bg_secondary'],
                                highlightbackground=THEME['border'], highlightthickness=1)
        chart_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_frame = tk.Frame(chart_frame, bg=THEME['bg_secondary'])
        title_frame.pack(fill=tk.X, padx=20, pady=16)

        icon_img = get_icon('chart_radar', size=20, color=THEME['primary'])
        self._analysis_photo = ImageTk.PhotoImage(icon_img)
        tk.Label(title_frame, image=self._analysis_photo,
                 bg=THEME['bg_secondary']).pack(side=tk.LEFT, padx=(0, 8))

        tk.Label(title_frame, text="旗舰模型能力雷达图", bg=THEME['bg_secondary'],
                 fg=THEME['text'], font=(THEME['font_family'], 14, 'bold')).pack(side=tk.LEFT)

        # Radar chart
        self._draw_radar_chart(chart_frame, sorted_companies)

    def _draw_radar_chart(self, parent, companies):
        """Draw radar chart with zoomed-in range based on actual data"""
        if not companies:
            return

        n = len(EVALUATION_DIMENSIONS)
        angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
        angles += angles[:1]

        fig, ax = plt.subplots(figsize=(8, 6), subplot_kw=dict(polar=True))
        fig.patch.set_facecolor(THEME['bg_secondary'])
        ax.set_facecolor(THEME['bg_secondary'])

        # Collect all scores to determine the display range
        all_scores = []
        for company, info in companies:
            all_scores.extend(info['scores'].values())

        # Determine the range - zoom into the actual data range
        min_range, max_range = get_score_range(all_scores)

        colors = THEME['chart_colors']

        for i, (company, info) in enumerate(companies):
            values = [info['scores'].get(dim, min_range) for dim in EVALUATION_DIMENSIONS]
            values += values[:1]

            color = colors[i % len(colors)]
            ax.plot(angles, values, 'o-', linewidth=2,
                label=f"{company} · {info['model']}",
                    color=color, markersize=5)
            ax.fill(angles, values, alpha=0.1, color=color)

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(EVALUATION_DIMENSIONS, fontsize=9, color=THEME['text'])
        ax.set_ylim(min_range, max_range)

        # Set y-axis ticks to be readable
        tick_count = 5
        step = (max_range - min_range) / tick_count
        ax.set_yticks([min_range + step * i for i in range(tick_count + 1)])
        ax.set_yticklabels([f"{min_range + step * i:.0f}" for i in range(tick_count + 1)],
                           fontsize=8, color=THEME['text_muted'])

        ax.set_rlabel_position(30)
        ax.spines['polar'].set_color(THEME['border'])
        ax.grid(color=THEME['border_light'], linestyle='--', linewidth=0.5)

        ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=9,
                  framealpha=0.9, edgecolor=THEME['border'])

        plt.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 16))
        plt.close(fig)

    # ==================== Compare Tab ====================

    def _show_compare(self):
        if not self.models:
            return

        # Selection frame
        sel_frame = tk.Frame(self.content_container, bg=THEME['bg_secondary'],
                              highlightbackground=THEME['border'], highlightthickness=1)
        sel_frame.pack(fill=tk.X, pady=(0, 16))

        inner = tk.Frame(sel_frame, bg=THEME['bg_secondary'])
        inner.pack(padx=20, pady=16)

        icon_img = get_icon('compare', size=20, color=THEME['primary'])
        self._compare_photo = ImageTk.PhotoImage(icon_img)
        tk.Label(inner, image=self._compare_photo,
                 bg=THEME['bg_secondary']).pack(side=tk.LEFT, padx=(0, 8))

        tk.Label(inner, text="模型对比", bg=THEME['bg_secondary'],
                 fg=THEME['text'], font=(THEME['font_family'], 14, 'bold')).pack(side=tk.LEFT, padx=(0, 24))

        # Sort models by score (descending) for the dropdown
        model_scores = {}
        for d in self.raw_data:
            m = d.get('model', '')
            if m not in model_scores:
                model_scores[m] = []
            model_scores[m].append(d.get('score', 0))
        avg_scores = {m: sum(s) / len(s) for m, s in model_scores.items() if s}
        sorted_models = sorted(self.models, key=lambda m: avg_scores.get(m, 0), reverse=True)[:30]

        self.model1_var = tk.StringVar()
        self.model2_var = tk.StringVar()

        # Model 1 selector
        tk.Label(inner, text="模型A:", bg=THEME['bg_secondary'],
                 fg=THEME['text_secondary'], font=(THEME['font_family'], 11)).pack(side=tk.LEFT, padx=(0, 4))
        cb1 = ttk.Combobox(inner, textvariable=self.model1_var,
                           values=sorted_models, state='readonly', width=24)
        cb1.pack(side=tk.LEFT, padx=(0, 16))
        if sorted_models:
            cb1.current(0)

        # Model 2 selector
        tk.Label(inner, text="模型B:", bg=THEME['bg_secondary'],
                 fg=THEME['text_secondary'], font=(THEME['font_family'], 11)).pack(side=tk.LEFT, padx=(0, 4))
        cb2 = ttk.Combobox(inner, textvariable=self.model2_var,
                           values=sorted_models, state='readonly', width=24)
        cb2.pack(side=tk.LEFT, padx=(0, 16))
        if len(sorted_models) > 1:
            cb2.current(1)

        # Compare button
        StyledButton(inner, "开始对比", self._do_compare,
                     font_size=11).pack(side=tk.LEFT)

        # Result area
        self.compare_result = tk.Frame(self.content_container, bg=THEME['bg'])
        self.compare_result.pack(fill=tk.BOTH, expand=True)

        if self.model1_var.get() and self.model2_var.get():
            self.content_container.after_idle(self._do_compare)

    def _do_compare(self):
        m1 = self.model1_var.get()
        m2 = self.model2_var.get()

        if not m1 or not m2:
            messagebox.showwarning("提示", "请选择两个模型")
            return
        if m1 == m2:
            messagebox.showwarning("提示", "请选择不同的模型进行对比")
            return

        for widget in self.compare_result.winfo_children():
            widget.destroy()

        m1_data = {d['dimension']: d['score'] for d in self.raw_data if d['model'] == m1}
        m2_data = {d['dimension']: d['score'] for d in self.raw_data if d['model'] == m2}

        if not m1_data or not m2_data:
            messagebox.showwarning("提示", "模型数据不足")
            return

        # Two-column layout: chart left, table right
        result_container = tk.Frame(self.compare_result, bg=THEME['bg'])
        result_container.pack(fill=tk.BOTH, expand=True)

        # Left: radar chart comparison
        chart_frame = tk.Frame(result_container, bg=THEME['bg_secondary'],
                                highlightbackground=THEME['border'], highlightthickness=1)
        chart_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 12))

        self._draw_compare_radar(chart_frame, m1, m2, m1_data, m2_data)

        # Right: comparison table
        table_frame = tk.Frame(result_container, bg=THEME['bg_secondary'],
                                highlightbackground=THEME['border'], highlightthickness=1)
        table_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(table_frame, text=f"{m1} vs {m2}", bg=THEME['bg_secondary'],
                 fg=THEME['primary'], font=(THEME['font_family'], 14, 'bold')).pack(pady=16)

        tree = ttk.Treeview(table_frame, columns=('dim', 'm1', 'm2', 'diff', 'winner'),
                            show='headings', height=10, style='Custom.Treeview')

        tree.heading('dim', text='维度')
        tree.heading('m1', text='模型A')
        tree.heading('m2', text='模型B')
        tree.heading('diff', text='分差')
        tree.heading('winner', text='胜出')

        tree.column('dim', width=88, anchor='w')
        tree.column('m1', width=78, anchor='center')
        tree.column('m2', width=78, anchor='center')
        tree.column('diff', width=68, anchor='center')
        tree.column('winner', width=78, anchor='center')

        for dim in EVALUATION_DIMENSIONS:
            s1 = m1_data.get(dim, 0)
            s2 = m2_data.get(dim, 0)
            diff = s1 - s2
            winner = "A胜" if s1 > s2 else "B胜" if s2 > s1 else "平局"
            tree.insert('', tk.END, values=(dim, f"{s1:.2f}", f"{s2:.2f}",
                                            f"{diff:+.2f}", winner))

        tree.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 16))

    def _draw_compare_radar(self, parent, m1, m2, m1_data, m2_data):
        """Draw comparison radar chart with zoomed range"""
        n = len(EVALUATION_DIMENSIONS)
        angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
        angles += angles[:1]

        fig, ax = plt.subplots(figsize=(6, 5), subplot_kw=dict(polar=True))
        fig.patch.set_facecolor(THEME['bg_secondary'])
        ax.set_facecolor(THEME['bg_secondary'])

        # Collect all scores for range
        all_scores = list(m1_data.values()) + list(m2_data.values())
        min_range, max_range = get_score_range(all_scores, padding_ratio=0.12, minimum_padding=1.2)

        v1 = [m1_data.get(dim, min_range) for dim in EVALUATION_DIMENSIONS] + [m1_data.get(EVALUATION_DIMENSIONS[0], min_range)]
        v2 = [m2_data.get(dim, min_range) for dim in EVALUATION_DIMENSIONS] + [m2_data.get(EVALUATION_DIMENSIONS[0], min_range)]

        ax.plot(angles, v1, 'o-', linewidth=2, label='模型A', color=THEME['chart_colors'][0], markersize=5)
        ax.fill(angles, v1, alpha=0.15, color=THEME['chart_colors'][0])
        ax.plot(angles, v2, 'o-', linewidth=2, label='模型B', color=THEME['chart_colors'][1], markersize=5)
        ax.fill(angles, v2, alpha=0.15, color=THEME['chart_colors'][1])

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(EVALUATION_DIMENSIONS, fontsize=9, color=THEME['text'])
        ax.set_ylim(min_range, max_range)

        tick_count = 5
        step = (max_range - min_range) / tick_count
        ax.set_yticks([min_range + step * i for i in range(tick_count + 1)])
        ax.set_yticklabels([f"{min_range + step * i:.0f}" for i in range(tick_count + 1)],
                           fontsize=8, color=THEME['text_muted'])

        ax.set_rlabel_position(30)
        ax.spines['polar'].set_color(THEME['border'])
        ax.grid(color=THEME['border_light'], linestyle='--', linewidth=0.5)
        ax.legend(loc='upper left', bbox_to_anchor=(0.02, 1.10), fontsize=9, ncol=2)

        plt.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=16, pady=16)
        plt.close(fig)

    # ==================== Heatmap Tab ====================

    def _show_heatmap(self):
        if not self.raw_data:
            return

        # Get top 15 models by average score
        model_scores = {}
        for d in self.raw_data:
            m = d.get('model', '')
            if m not in model_scores:
                model_scores[m] = []
            model_scores[m].append(d.get('score', 0))

        avg_scores = {m: sum(s) / len(s) for m, s in model_scores.items() if s}
        sorted_models = sorted(avg_scores.keys(), key=lambda m: avg_scores[m], reverse=True)[:15]

        # Chart frame
        chart_frame = tk.Frame(self.content_container, bg=THEME['bg_secondary'],
                                highlightbackground=THEME['border'], highlightthickness=1)
        chart_frame.pack(fill=tk.BOTH, expand=True)

        title_frame = tk.Frame(chart_frame, bg=THEME['bg_secondary'])
        title_frame.pack(fill=tk.X, padx=20, pady=16)

        icon_img = get_icon('heatmap', size=20, color=THEME['primary'])
        self._heatmap_photo = ImageTk.PhotoImage(icon_img)
        tk.Label(title_frame, image=self._heatmap_photo,
                 bg=THEME['bg_secondary']).pack(side=tk.LEFT, padx=(0, 8))

        tk.Label(title_frame, text="模型能力热力图 (Top 15)", bg=THEME['bg_secondary'],
                 fg=THEME['text'], font=(THEME['font_family'], 14, 'bold')).pack(side=tk.LEFT)

        # Build matrix
        matrix = np.zeros((len(sorted_models), len(EVALUATION_DIMENSIONS)))
        for i, model in enumerate(sorted_models):
            for j, dim in enumerate(EVALUATION_DIMENSIONS):
                for d in self.raw_data:
                    if d.get('model') == model and d.get('dimension') == dim:
                        matrix[i, j] = d.get('score', 0)
                        break

        fig, ax = plt.subplots(figsize=(12, 8))
        fig.patch.set_facecolor(THEME['bg_secondary'])
        ax.set_facecolor(THEME['bg_secondary'])

        im = ax.imshow(matrix, cmap='YlOrRd', aspect='auto')

        ax.set_xticks(range(len(EVALUATION_DIMENSIONS)))
        ax.set_xticklabels(EVALUATION_DIMENSIONS, rotation=45, ha='right',
                           color=THEME['text'], fontsize=10)
        ax.set_yticks(range(len(sorted_models)))
        ax.set_yticklabels(sorted_models, fontsize=9, color=THEME['text'])

        for i in range(len(sorted_models)):
            for j in range(len(EVALUATION_DIMENSIONS)):
                val = matrix[i, j]
                text_color = 'white' if val > np.mean(matrix) + np.std(matrix) else 'black'
                ax.text(j, i, f'{val:.0f}', ha='center', va='center',
                        fontsize=8, color=text_color)

        plt.colorbar(im, ax=ax, label='分数', shrink=0.8)
        plt.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=chart_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 16))
        plt.close(fig)

    def _get_model_dimension_scores(self):
        model_dimensions = {}
        for item in self.raw_data:
            model = item.get('model', '')
            dimension = item.get('dimension', '')
            if not model or not dimension:
                continue

            entry = model_dimensions.setdefault(model, {
                'company': item.get('company', '未知'),
                'scores': {}
            })
            entry['scores'][dimension] = item.get('score', 0)
        return model_dimensions

    def _get_top_company_flagships(self, limit=5):
        candidates = []
        for model, info in self._get_model_dimension_scores().items():
            values = list(info['scores'].values())
            if not values:
                continue
            candidates.append({
                'model': model,
                'company': info['company'],
                'avg': sum(values) / len(values),
                'scores': info['scores'],
            })

        candidates.sort(key=lambda item: item['avg'], reverse=True)

        selected = []
        seen_companies = set()
        for candidate in candidates:
            company = candidate['company']
            if not company or company == '未知' or company in seen_companies:
                continue
            seen_companies.add(company)
            selected.append((company, candidate))
            if len(selected) >= limit:
                break
        return selected

    # ==================== Button callbacks ====================

    def _refresh_data(self):
        self._load_data_async()

    def _upload_file(self):
        try:
            file_path = self.file_handler.upload_file(self.root)
            if file_path:
                messagebox.showinfo("成功", f"文件已上传: {file_path}")
        except Exception as e:
            messagebox.showerror("错误", f"文件上传失败: {e}")

    def _export_data(self):
        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV文件", "*.csv"), ("JSON文件", "*.json")]
            )
            if file_path:
                if file_path.endswith('.json'):
                    self.file_handler.export_to_json(self.filtered_data, file_path)
                else:
                    self.file_handler.export_to_csv(self.filtered_data, file_path)
                messagebox.showinfo("成功", f"数据已导出: {file_path}")
        except Exception as e:
            messagebox.showerror("错误", f"数据导出失败: {e}")


def main():
    root = tk.Tk()
    app = ModernApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
