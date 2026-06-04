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
from llm_eval_system.ui.components import (
    StyledButton,
    SidebarButton,
    LoadingSpinner,
    ToastNotification,
    RoundedCard,
    StatCard,
    Badge,
    RoundedDropdown,
    draw_rounded_rect,
)
from llm_eval_system.ui.icons import get_icon

# Reduce logging - only errors by default for the desktop app.
logging.basicConfig(level=logging.ERROR, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)

# Fix matplotlib Chinese font
matplotlib.rcParams['font.sans-serif'] = ['PingFang SC', 'Heiti SC', 'STHeiti',
    'Microsoft YaHei', 'SimHei', 'Arial Unicode MS', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False
# 性能：适度降低 dpi、关闭自动布局开销、统一字号
matplotlib.rcParams['figure.dpi'] = 90
matplotlib.rcParams['figure.autolayout'] = False
matplotlib.rcParams['path.simplify'] = True
matplotlib.rcParams['path.simplify_threshold'] = 0.8
matplotlib.rcParams['agg.path.chunksize'] = 10000

TEXT_ARENA_SET = {'text', 'code', 'vision', 'document', 'search', 'image-to-code', ''}
IMAGE_ARENA_SET = {'text-to-image', 'image-edit'}
VIDEO_ARENA_SET = {'text-to-video', 'image-to-video', 'video-to-video'}

ARENA_CHOICES = [
    ('综合领域', 'text'),
    ('代码', 'code'),
    ('文档理解', 'document'),
    ('搜索', 'search'),
    ('视觉', 'vision'),
    ('文生图', 'text-to-image'),
    ('图片编辑', 'image-edit'),
    ('文生视频', 'text-to-video'),
]

ARENA_SLUG_TO_DIMS = {
    'text': None,
    'code': ['代码生成'],
    'document': ['知识问答'],
    'search': ['逻辑推理'],
    'vision': ['多语言能力'],
    'text-to-image': ['文生图'],
    'image-edit': ['图片编辑'],
    'text-to-video': ['文生视频'],
}


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
        self.root.geometry("1280x800")
        self.root.configure(bg=THEME['bg'])
        self.root.minsize(960, 600)

        self.raw_data = []
        self.filtered_data = []
        self.models = []
        self.data_origin = None
        self.data_loaded_at = None
        self.current_tab = 'ranking'
        self.current_arena = 'text'
        self._arena_data = {}
        self._arena_models = {}
        self._arena_rank_map = {}
        self.content_container = None
        self._is_loading = False
        self._render_pending = False
        self._photo_refs = []  # Keep references to PhotoImage objects
        self._card_refs = []
        self._ranking_row_map = {}
        self._compare_dim_vars = {}
        self._compare_rendering = False
        self._heatmap_zoom = None
        self.sidebar_outer = None
        self.content_outer = None
        self._content_canvas = None
        self._content_window = None

        self.db = DatabaseManager()
        self.file_handler = FileHandler()
        self.thread_manager = ThreadManager(max_workers=3)
        self.thread_manager.start_workers()

        self._loading_frame = None
        self._loading_spinner = None

        self._toast = ToastNotification(self.root)
        self._chart_cache = {}  # 图表渲染缓存（性能优化）

        self._setup_styles()
        self._build_ui()
        self._load_data_async()

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')

        style.configure('Custom.Treeview',
                        background=THEME['bg_secondary'],
                        foreground=THEME['text'],
                        rowheight=42,
                        font=(THEME['font_family'], 11),
                        borderwidth=0,
                        relief='flat',
                        fieldbackground=THEME['bg_secondary'])
        style.configure('Custom.Treeview.Heading',
                        background=THEME['acrylic_tint'],
                        foreground=THEME['text_secondary'],
                        font=(THEME['font_family'], 11, 'bold'),
                        relief='flat',
                        borderwidth=0,
                        padding=12)
        style.map('Custom.Treeview',
                  background=[('selected', THEME['primary_light'])],
                  foreground=[('selected', THEME['primary'])])
        style.map('Custom.Treeview.Heading',
                  background=[('active', THEME['bg_active'])])

        style.configure('Modern.Vertical.TScrollbar',
                background=THEME['primary_light'],
                troughcolor=THEME['bg_tertiary'],
                bordercolor=THEME['bg_tertiary'],
                darkcolor=THEME['primary_light'],
                lightcolor=THEME['primary_light'],
                arrowcolor=THEME['text_muted'],
                arrowsize=12,
                gripcount=0,
                width=12)
        style.map('Modern.Vertical.TScrollbar',
              background=[('active', THEME['primary'])],
              arrowcolor=[('active', THEME['text_white'])])

        style.configure('Modern.TCombobox',
                foreground=THEME['text'],
                fieldbackground=THEME['bg_secondary'],
                background=THEME['bg_secondary'],
                bordercolor=THEME['border'],
                lightcolor=THEME['border'],
                darkcolor=THEME['border'],
                arrowcolor=THEME['text_secondary'],
                relief='flat',
                borderwidth=1,
                padding=(12, 8, 32, 8),
                insertcolor=THEME['primary'])
        style.map('Modern.TCombobox',
              fieldbackground=[('readonly', THEME['bg_secondary'])],
              selectbackground=[('readonly', THEME['primary_light'])],
              selectforeground=[('readonly', THEME['text'])],
              bordercolor=[('focus', THEME['border_focus'])],
              lightcolor=[('focus', THEME['border_focus'])],
              darkcolor=[('focus', THEME['border_focus'])])

        style.configure('Modern.TEntry',
                foreground=THEME['text'],
                fieldbackground=THEME['bg_secondary'],
                background=THEME['bg_secondary'],
                bordercolor=THEME['bg_secondary'],
                lightcolor=THEME['bg_secondary'],
                darkcolor=THEME['bg_secondary'],
                relief='flat',
                borderwidth=0,
                padding=(4, 6))
        style.map('Modern.TEntry',
              fieldbackground=[('focus', THEME['bg_secondary'])],
              bordercolor=[('focus', THEME['bg_secondary'])],
              lightcolor=[('focus', THEME['bg_secondary'])],
              darkcolor=[('focus', THEME['bg_secondary'])])

        self.root.option_add('*TCombobox*Listbox.background', THEME['bg_secondary'])
        self.root.option_add('*TCombobox*Listbox.foreground', THEME['text'])
        self.root.option_add('*TCombobox*Listbox.selectBackground', THEME['primary_light'])
        self.root.option_add('*TCombobox*Listbox.selectForeground', THEME['text'])

    def _build_ui(self):
        self._build_header()
        main_frame = tk.Frame(self.root, bg=THEME['bg'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=(0, 24))

        # Sidebar with scrollbar support
        self.sidebar_outer = tk.Frame(main_frame, bg=THEME['bg_secondary'],
                          highlightbackground=THEME['border'],
                          highlightthickness=1, width=272)
        self.sidebar_outer.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 20))
        self.sidebar_outer.pack_propagate(False)

        # Canvas + scrollbar for sidebar scrolling
        self._sidebar_canvas = tk.Canvas(self.sidebar_outer, bg=THEME['bg_secondary'],
                                          highlightthickness=0, width=272)
        sidebar_scroll = ttk.Scrollbar(self.sidebar_outer, orient=tk.VERTICAL,
                        style='Modern.Vertical.TScrollbar',
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

        # scroll bindings moved to _build_content (single root handler)

        self._build_sidebar()

        # Content area
        self.content = tk.Frame(main_frame, bg=THEME['bg'])
        self.content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._build_content()

    def _build_header(self):
        header = tk.Frame(self.root, bg=THEME['bg_secondary'], height=68)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        # 底部细描边，与内容区分隔
        tk.Frame(self.root, bg=THEME['border'], height=1).pack(fill=tk.X)

        logo_frame = tk.Frame(header, bg=THEME['bg_secondary'])
        logo_frame.pack(side=tk.LEFT, padx=24)

        # logo 圆角底片
        chip = tk.Canvas(logo_frame, width=40, height=40, bg=THEME['bg_secondary'],
                         highlightthickness=0, bd=0)
        chip.pack(side=tk.LEFT, padx=(0, 12), pady=14)
        draw_rounded_rect(chip, 1, 1, 39, 39, 12, fill=THEME['primary_light'], outline='')
        icon_img = get_icon('robot', size=24, color=THEME['primary'])
        self._logo_photo = ImageTk.PhotoImage(icon_img)
        chip.create_image(20, 20, image=self._logo_photo)

        title_col = tk.Frame(logo_frame, bg=THEME['bg_secondary'])
        title_col.pack(side=tk.LEFT)
        tk.Label(title_col, text="LLM 评测分析系统", bg=THEME['bg_secondary'],
                 fg=THEME['text'], font=(THEME['font_family'], 16, 'bold')).pack(anchor='w')
        self._header_status = tk.Label(title_col, text="正在加载数据…",
                                       bg=THEME['bg_secondary'], fg=THEME['text_muted'],
                                       font=(THEME['font_family'], 10))
        self._header_status.pack(anchor='w')

        # Right action buttons - 统一尺寸
        btn_frame = tk.Frame(header, bg=THEME['bg_secondary'])
        btn_frame.pack(side=tk.RIGHT, padx=24)

        self._refresh_btn = StyledButton(btn_frame, "刷新数据", self._refresh_data,
                                          icon_name='refresh', color_key='primary',
                                          font_size=11)
        self._refresh_btn.pack(side=tk.RIGHT, padx=(10, 0))

        self._export_btn = StyledButton(btn_frame, "导出", self._export_data,
                                        icon_name='download', color_key='secondary',
                                        font_size=11)
        self._export_btn.pack(side=tk.RIGHT, padx=(10, 0))

        self._upload_btn = StyledButton(btn_frame, "上传", self._upload_file,
                                        icon_name='upload', color_key='secondary',
                                        font_size=11)
        self._upload_btn.pack(side=tk.RIGHT, padx=(10, 0))

    def _build_sidebar(self):
        """构建侧边栏 - 可滚动"""
        # Arena selector section
        arena_label = tk.Label(self.sidebar, text="评测领域", bg=THEME['bg_secondary'],
                               fg=THEME['text_muted'], font=(THEME['font_family'], 10),
                               anchor='w')
        arena_label.pack(fill=tk.X, padx=16, pady=(20, 8))

        arena_names = [label for label, _ in ARENA_CHOICES]
        self.arena_var = tk.StringVar(value='综合领域')
        arena_dd = RoundedDropdown(self.sidebar, self.arena_var, arena_names, width_px=240)
        arena_dd.pack(fill=tk.X, padx=16, pady=(0, 4))
        # 用变量 trace 替代 ComboboxSelected 事件
        self.arena_var.trace_add('write', lambda *a: self._on_arena_changed())

        # Navigation section
        nav_label = tk.Label(self.sidebar, text="导航", bg=THEME['bg_secondary'],
                             fg=THEME['text_muted'], font=(THEME['font_family'], 10),
                             anchor='w')
        nav_label.pack(fill=tk.X, padx=16, pady=(20, 8))

        nav_buttons = [
            ('ranking', '排行榜', 'nav_ranking'),
            ('compare', '模型对比', 'nav_compare'),
            ('radar', '雷达图', 'nav_chart_radar'),
            ('heatmap', '综合洞察', 'nav_heatmap'),
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

        # 关键指标用横向统计卡单列展示（侧栏较窄，单列可保证标签/数字均完整）
        stat_col = tk.Frame(self.sidebar, bg=THEME['bg_secondary'])
        stat_col.pack(fill=tk.X, padx=12, pady=(0, 6))

        self._stat_cards = {}
        card_defs = [
            ('model_count', '模型总数', '0', THEME['primary']),
            ('avg_score', '平均分数', '0', THEME['success']),
            ('domestic', '国内模型', '0', THEME['warning']),
            ('international', '国际模型', '0', THEME['info']),
        ]
        for key, label_text, default_val, accent in card_defs:
            sc = StatCard(stat_col, label_text, default_val, accent=accent, horizontal=True)
            sc.pack(fill=tk.X, pady=4)
            self._stat_cards[key] = sc

        # 文本型次要指标
        self._stat_labels = {}
        text_stats = [
            ('eval_count', '评测数据', '0'),
            ('top_model', '最高分模型', '-'),
            ('top_score', '最高分', '0'),
            ('dimensions', '评测维度', str(len(EVALUATION_DIMENSIONS))),
        ]
        for key, label_text, default_val in text_stats:
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

    def _on_arena_changed(self, _event=None):
        selected = self.arena_var.get()
        slug = dict(ARENA_CHOICES).get(selected, 'text')
        if slug == self.current_arena:
            return
        self.current_arena = slug
        self.models = self._arena_models.get(slug, [])

        # Update radar nav label based on arena
        if hasattr(self, '_nav_buttons') and 'radar' in self._nav_buttons:
            self._nav_buttons['radar'].update_text('雷达图' if slug == 'text' else '能力对比')

        arena_data = self._get_current_arena_data()
        avg_scores = {}
        for item in arena_data:
            m = item.get('model', '')
            if m not in avg_scores:
                avg_scores[m] = []
            avg_scores[m].append(item.get('score', 0))
        avg_scores = {m: sum(s) / len(s) for m, s in avg_scores.items() if s}
        self._update_stats(arena_data, avg_scores)

        self._switch_tab(self.current_tab)

    def _widget_contains_point(self, widget, x_root, y_root):
        if not widget or not widget.winfo_exists():
            return False
        left = widget.winfo_rootx()
        top = widget.winfo_rooty()
        right = left + widget.winfo_width()
        bottom = top + widget.winfo_height()
        return left <= x_root <= right and top <= y_root <= bottom

    def _install_scroll_handler(self):
        """安装滚轮处理。

        除了 bind_all 兜底外，更关键的是：直接给「内容区」与「侧边栏」两棵
        widget 子树递归绑定滚轮事件（在每次渲染后刷新绑定）。
        这样无论鼠标悬停在哪个子组件（卡片 / 图表 / 标签）上，事件都会被
        该组件的 binding 直接捕获并滚动它所属的容器 —— 这才是「指针在哪个
        区域就滚哪个区域」的可靠做法，不依赖 bind_all 的脆弱传播。
        """
        # bind_all 兜底（处理未被递归绑定到的空白区域）
        for seq in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
            self.root.bind_all(seq, self._root_mousewheel, add='+')

    def _scroll_content(self, event):
        """滚动主内容区；若鼠标恰在 Treeview 上则优先滚 Treeview。"""
        units = self._delta_to_units(event)
        if units == 0:
            return 'break'
        w = getattr(event, 'widget', None)
        try:
            if w is not None and w.winfo_class() == 'Treeview':
                if self._try_scroll_treeview(w, units):
                    return 'break'
        except Exception:
            pass
        self._try_scroll_canvas(self._content_canvas, units)
        return 'break'

    def _scroll_sidebar(self, event):
        """滚动侧边栏。"""
        units = self._delta_to_units(event)
        if units == 0:
            return 'break'
        self._try_scroll_canvas(self._sidebar_canvas, units)
        return 'break'

    def _bind_scroll_tree(self, widget, handler):
        """给 widget 及其所有后代递归绑定滚轮事件到指定 handler。"""
        for seq in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
            widget.bind(seq, handler, add='+')
        for child in widget.winfo_children():
            self._bind_scroll_tree(child, handler)

    def _refresh_content_scroll_bindings(self):
        """内容渲染后调用：把内容区整棵子树绑定到内容滚动。"""
        if self.content_container and self.content_container.winfo_exists():
            self._bind_scroll_tree(self.content_container, self._scroll_content)

    def _root_mousewheel(self, event):
        """bind_all 兜底：按光标位置滚动正确的容器（处理空白/未绑定区域）。"""
        units = self._delta_to_units(event)
        if units == 0:
            return None

        x = self.root.winfo_pointerx()
        y = self.root.winfo_pointery()

        hovered = self.root.winfo_containing(x, y)
        if hovered is not None:
            try:
                cls = hovered.winfo_class()
            except Exception:
                cls = ''
            if cls == 'Treeview':
                if self._try_scroll_treeview(hovered, units):
                    return 'break'
                if self._try_scroll_canvas(self._content_canvas, units):
                    return 'break'
                return 'break'
            if cls in ('TCombobox', 'Listbox', 'Text'):
                return None

        if self._widget_contains_point(self.sidebar_outer, x, y):
            self._try_scroll_canvas(self._sidebar_canvas, units)
            return 'break'

        if self._widget_contains_point(self.content_outer, x, y):
            self._try_scroll_canvas(self._content_canvas, units)
            return 'break'

        return None

    def _delta_to_units(self, event):
        """把滚轮事件转换为滚动单位（兼容 macOS 触摸板的小步长）。"""
        delta = getattr(event, 'delta', 0)
        if delta == 0 and getattr(event, 'num', None) in (4, 5):
            return -3 if event.num == 4 else 3
        if delta == 0:
            return 0
        # macOS 触摸板发送小数值 (1, -3, ...)，Windows/X11 是 120 的倍数
        if abs(delta) < 120:
            step = int(-delta)
            return step if step != 0 else (-1 if delta > 0 else 1)
        return int(-delta / 120) * 3

    def _try_scroll_canvas(self, canvas, units):
        """尝试滚动 canvas，已滚动返回 True，无可滚内容/到边界返回 False。"""
        if not canvas or not canvas.winfo_exists():
            return False
        bbox = canvas.bbox('all')
        if not bbox or (bbox[3] - bbox[1]) <= canvas.winfo_height() + 2:
            return False
        try:
            start, end = canvas.yview()
        except Exception:
            return False
        if units < 0 and start <= 0.0:
            return False
        if units > 0 and end >= 1.0:
            return False
        canvas.yview_scroll(units, 'units')
        return True

    def _try_scroll_treeview(self, tree, units):
        """尝试滚动 Treeview，已滚动返回 True。"""
        try:
            start, end = tree.yview()
        except Exception:
            return False
        if units < 0 and start <= 0.0:
            return False
        if units > 0 and end >= 1.0:
            return False
        tree.yview_scroll(units, 'units')
        return True

    def _create_card(self, parent, padding=(18, 16), min_height=None):
        card = RoundedCard(parent, padding=padding, min_height=min_height)
        self._card_refs.append(card)
        return card

    def _build_content(self):
        """构建内容区域"""
        self.content_outer = tk.Frame(self.content, bg=THEME['bg'])
        self.content_outer.pack(fill=tk.BOTH, expand=True)

        self._content_canvas = tk.Canvas(self.content_outer, bg=THEME['bg'], highlightthickness=0)
        content_scroll = ttk.Scrollbar(self.content_outer, orient=tk.VERTICAL,
                                       style='Modern.Vertical.TScrollbar',
                                       command=self._content_canvas.yview)
        self._content_canvas.configure(yscrollcommand=content_scroll.set)

        content_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._content_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.content_container = tk.Frame(self._content_canvas, bg=THEME['bg'])
        self._content_window = self._content_canvas.create_window(
            (0, 0), window=self.content_container, anchor='nw')

        self.content_container.bind(
            '<Configure>',
            lambda e: self._content_canvas.configure(scrollregion=self._content_canvas.bbox('all'))
        )
        self._content_canvas.bind(
            '<Configure>',
            lambda e: self._content_canvas.itemconfig(self._content_window, width=e.width)
        )

        # Single root-level scroll handler installed below
        self._install_scroll_handler()
        # 侧边栏整棵子树绑定到侧栏滚动
        if hasattr(self, 'sidebar') and self.sidebar:
            self._bind_scroll_tree(self.sidebar, self._scroll_sidebar)

        self._show_ranking()
        self.root.after_idle(self._refresh_content_scroll_bindings)

    # ==================== Tab switching ====================

    def _switch_tab(self, tab_id):
        if self._render_pending:
            return
        self._render_pending = True
        try:
            if tab_id != 'heatmap' and self.current_tab != tab_id:
                self._heatmap_zoom = None
            self.current_tab = tab_id
            for tid, btn in self._nav_buttons.items():
                btn.set_active(tid == tab_id)
            plt.close('all')
            for widget in self.content_container.winfo_children():
                widget.destroy()
            self._card_refs = []
            self._ranking_row_map = {}

            tab_map = {
                'ranking': self._show_ranking,
                'compare': self._show_compare,
                'radar': self._show_radar,
                'heatmap': self._show_heatmap,
            }
            tab_map.get(tab_id, self._show_ranking)()
            if self._content_canvas and self._content_canvas.winfo_exists():
                self.root.after_idle(lambda: self._content_canvas.yview_moveto(0))
            # 渲染后给整棵内容子树递归绑定滚轮（含延迟渲染的图表）
            self.root.after_idle(self._refresh_content_scroll_bindings)
            self.root.after(120, self._refresh_content_scroll_bindings)
        finally:
            self._render_pending = False

    # ==================== Data loading ====================

    # 本地数据有效的最小行数阈值
    _MIN_LOCAL_ROWS = 50
    _MIN_CRAWL_ROWS = 100

    def _load_data_async(self):
        """启动加载策略：
        1) 本地有数据 → 直接读本地并分析（不自动后台覆盖，避免闪烁/误判）。
        2) 本地无数据 → 自动抓取；抓取成功用抓取数据。
        3) 抓取也失败 → 使用写死的模拟数据。
        """
        # Step 1: 优先读本地（使用新的扁平表，保留完整 arena 字段）
        db_data = None
        try:
            db_data = self.db.load_records()
        except Exception:
            db_data = None

        if db_data and len(db_data) >= self._MIN_LOCAL_ROWS:
            self._on_data_loaded(db_data, origin='database', persist=False)
            return

        # Step 2/3: 本地无数据，后台抓取
        def _crawl():
            crawled = None
            try:
                crawled = get_latest_models(minimum_rows=self._MIN_CRAWL_ROWS,
                                            fallback_to_simulated=False)
            except Exception:
                crawled = None
            if crawled and len(crawled) >= self._MIN_CRAWL_ROWS:
                self.root.after(0, lambda: self._on_data_loaded(crawled, origin='crawler'))
            else:
                fallback = get_simulated_data()
                self.root.after(0, lambda: self._on_data_loaded(fallback, origin='simulated'))

        threading.Thread(target=_crawl, daemon=True).start()

    def _on_data_loaded(self, data, origin='simulated', persist=True):
        if not data:
            data = get_simulated_data()
            origin = 'simulated'

        self.raw_data = data
        self.filtered_data = data
        self.data_origin = origin
        self.data_loaded_at = datetime.now()

        # Group data by arena slug
        self._arena_data = {}
        for item in data:
            arena = item.get('arena', 'text') or 'text'
            self._arena_data.setdefault(arena, []).append(item)

        # Build per-arena model lists and rank maps (sorted by Arena Score / Elo rating)
        self._arena_models = {}
        self._arena_rank_map = {}
        for arena, items in self._arena_data.items():
            model_ratings = {}
            for item in items:
                m = item.get('model', '')
                r = item.get('rating', 0)
                if m not in model_ratings or r > model_ratings[m]:
                    model_ratings[m] = r
            sorted_models = sorted(model_ratings.keys(),
                                   key=lambda m: model_ratings[m], reverse=True)
            self._arena_models[arena] = sorted_models
            self._arena_rank_map[arena] = {m: i + 1 for i, m in enumerate(sorted_models)}

        # Default model list = current arena
        self.models = self._arena_models.get(self.current_arena, [])

        # 仅在抓取/导入的新数据时写库；读本地无需重复写
        if persist:
            self._save_to_db(data)

        # Update sidebar stats
        arena_data = self._get_current_arena_data()
        avg_scores = {}
        for item in arena_data:
            m = item.get('model', '')
            if m not in avg_scores:
                avg_scores[m] = []
            avg_scores[m].append(item.get('score', 0))
        avg_scores = {m: sum(s) / len(s) for m, s in avg_scores.items() if s}
        self._update_stats(arena_data, avg_scores)

        # 更新 header 数据来源状态
        self._update_header_status()

        # Refresh current tab
        self._switch_tab(self.current_tab)

    def _update_header_status(self):
        if not hasattr(self, '_header_status'):
            return
        origin_map = {
            'database': '本地缓存',
            'crawler': 'LMArena 实时抓取',
            'simulated': '内置示例数据',
            'upload': '导入文件',
        }
        origin_text = origin_map.get(self.data_origin, '未知来源')
        ts = self.data_loaded_at.strftime('%H:%M') if self.data_loaded_at else ''
        total = len(self.raw_data)
        self._header_status.config(text=f"数据来源：{origin_text} · {total} 条 · 更新于 {ts}")

    def _save_to_db(self, data):
        """原子地保存完整记录到本地（每条保留 arena/rating/价格等全部字段）。"""
        try:
            self.db.save_records(data)
        except Exception:
            pass  # 写库失败不影响当前内存数据的分析

    def _get_current_arena_data(self):
        return self._arena_data.get(self.current_arena, [])

    def _get_current_arena_models(self):
        return self._arena_models.get(self.current_arena, [])

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

        # 更新统计卡
        if hasattr(self, '_stat_cards'):
            self._stat_cards['model_count'].set_value(len(self.models))
            self._stat_cards['avg_score'].set_value(f"{avg_score:.1f}")
            self._stat_cards['domestic'].set_value(domestic)
            self._stat_cards['international'].set_value(international)

        # 更新文本指标
        self._stat_labels['eval_count'].config(text=str(len(data)))
        self._stat_labels['top_model'].config(text=top_model, wraplength=120, justify='left')
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

        sorted_companies = sorted(company_best.items(), key=lambda x: x[1]['score'], reverse=True)
        for i, (company, info) in enumerate(sorted_companies):
            row = tk.Frame(self._company_frame, bg=THEME['bg_secondary'])
            row.pack(fill=tk.X, pady=1)

            tk.Label(row, text=f"{i + 1}.", bg=THEME['bg_secondary'],
                     fg=THEME['text_muted'], font=(THEME['font_family'], 9),
                     width=3, anchor='w').pack(side=tk.LEFT)

            tk.Label(row, text=company, bg=THEME['bg_secondary'],
                     fg=THEME['text'], font=(THEME['font_family'], 9),
                     anchor='w').pack(side=tk.LEFT, fill=tk.X, expand=True)

            tk.Label(row, text=f"{info['score']:.1f}", bg=THEME['bg_secondary'],
                     fg=THEME['primary'], font=(THEME['font_family'], 9, 'bold'),
                     anchor='e').pack(side=tk.RIGHT)

    # ==================== Ranking Tab ====================

    def _build_rounded_search(self, parent, height, variable, placeholder,
                              grid_col=0, grid_padx=(0, 12), width_px=None):
        """苹果风格的胶囊圆角输入框（搜索 / 公司筛选通用）。

        用原生 tk.Entry（非 ttk）+ relief=flat + 无边框 + 白底，融入 canvas
        圆角背景；圆角半径取 height/2 形成胶囊形；带 placeholder（灰字占位）。
        返回 entry 控件。
        """
        h = height
        canvas = tk.Canvas(parent, height=h, bg=THEME['bg_secondary'],
                           highlightthickness=0, bd=0)
        if width_px:
            canvas.configure(width=width_px)
        canvas.grid(row=1, column=grid_col, sticky='ew', padx=grid_padx)

        icon_img = get_icon('search', size=15, color=THEME['text_muted'])
        icon_photo = ImageTk.PhotoImage(icon_img)
        # 防止被 GC：挂到实例
        if not hasattr(self, '_input_photos'):
            self._input_photos = []
        self._input_photos.append(icon_photo)

        variable.set(placeholder)
        entry = tk.Entry(
            canvas, textvariable=variable,
            font=(THEME['font_family'], 12),
            relief='flat', bd=0, highlightthickness=0,
            bg=THEME['bg_secondary'], fg=THEME['text_muted'],
            insertbackground=THEME['primary'],
            disabledbackground=THEME['bg_secondary'])

        radius = h // 2
        icon_x = 18
        entry_x = 42

        canvas.create_image(icon_x, h // 2, image=icon_photo, anchor='w')
        win = canvas.create_window(entry_x, h // 2, window=entry, anchor='w')

        def _draw_bg(focused=False):
            w = canvas.winfo_width()
            if w <= 1:
                return
            canvas.delete('bg')
            draw_rounded_rect(
                canvas, 2, 2, w - 3, h - 3, radius,
                fill=THEME['bg_secondary'],
                outline=THEME['border_focus'] if focused else THEME['border'],
                width=2 if focused else 1, tags='bg')
            canvas.tag_lower('bg')
            canvas.itemconfigure(win, width=max(w - entry_x - radius, 40))

        canvas.bind('<Configure>', lambda e: _draw_bg(False))

        def _on_focus_in(_e):
            if entry.get() == placeholder:
                entry.delete(0, tk.END)
                entry.config(fg=THEME['text'])
            _draw_bg(True)

        def _on_focus_out(_e):
            if not entry.get().strip():
                variable.set(placeholder)
                entry.config(fg=THEME['text_muted'])
            _draw_bg(False)

        def _on_key(_e):
            if entry.get() != placeholder:
                entry.config(fg=THEME['text'])

        entry.bind('<FocusIn>', _on_focus_in)
        entry.bind('<FocusOut>', _on_focus_out)
        entry.bind('<KeyRelease>', _on_key)
        canvas.bind('<Button-1>', lambda e: entry.focus_set())
        return entry

    def _show_ranking(self):
        controls_card = self._create_card(self.content_container, padding=(20, 18))
        controls_card.pack(fill=tk.X, pady=(0, 16))
        controls = controls_card.content

        title_row = tk.Frame(controls, bg=THEME['bg_secondary'])
        title_row.pack(fill=tk.X)

        tk.Label(title_row, text='排行榜筛选', bg=THEME['bg_secondary'],
                 fg=THEME['text'], font=(THEME['font_family'], 14, 'bold')).pack(side=tk.LEFT)
        self._ranking_status_label = tk.Label(
            title_row,
            text='等待加载榜单数据',
            bg=THEME['bg_secondary'],
            fg=THEME['text_muted'],
            font=(THEME['font_family'], 10),
        )
        self._ranking_status_label.pack(side=tk.RIGHT)

        # 筛选区用 grid：第 0 行全是标签，第 1 行全是控件，保证完美对齐基线
        filter_row = tk.Frame(controls, bg=THEME['bg_secondary'])
        filter_row.pack(fill=tk.X, pady=(16, 0))
        # 搜索列与公司列可伸缩，其余固定
        filter_row.grid_columnconfigure(0, weight=2)
        filter_row.grid_columnconfigure(2, weight=1)
        for col in (1, 3, 4):
            filter_row.grid_columnconfigure(col, weight=0)

        categories = ['全部类别', '国内', '国际']
        sort_rules = [
            'Arena Score：高到低',
            '综合均分：高到低',
            '综合均分：低到高',
            'Votes：多到少',
            '性价比：高到低',
            '上下文：长到短',
            '代码生成：高到低',
        ]
        top_n_values = ['全部', '10', '25', '50', '100']

        self.search_var = tk.StringVar()
        self.company_filter_var = tk.StringVar()
        self.category_filter_var = tk.StringVar(value='全部类别')
        self.sort_var = tk.StringVar(value='Arena Score：高到低')
        self.top_n_var = tk.StringVar(value='全部')
        self._search_placeholder = '搜索模型...'
        self._company_placeholder = '输入公司名…'

        INPUT_H = THEME['input_height']

        def _add_label(text, col, padx):
            tk.Label(filter_row, text=text, bg=THEME['bg_secondary'],
                     fg=THEME['text_muted'], font=(THEME['font_family'], 10),
                     anchor='w').grid(row=0, column=col, sticky='w', padx=padx, pady=(0, 6))

        def _add_combo(variable, values, col, width, padx):
            # 圆角下拉框，宽度按字符数估算（保持与界面圆角统一）
            dd = RoundedDropdown(filter_row, variable, values,
                                 width_px=max(width * 11 + 40, 96), height=INPUT_H)
            dd.grid(row=1, column=col, sticky='ew', padx=padx)
            return dd

        # --- 搜索模型（圆角输入框 + 模糊匹配） ---
        _add_label('搜索模型', 0, (0, 12))
        self._search_entry = self._build_rounded_search(
            filter_row, INPUT_H, self.search_var, self._search_placeholder,
            grid_col=0, grid_padx=(0, 12))

        # --- 类别（下拉） ---
        _add_label('类别', 1, (0, 12))
        _add_combo(self.category_filter_var, categories, 1, 9, (0, 12))

        # --- 公司（改为手动输入 + 模糊匹配，与搜索模型相同逻辑） ---
        _add_label('公司', 2, (0, 12))
        self._company_entry = self._build_rounded_search(
            filter_row, INPUT_H, self.company_filter_var, self._company_placeholder,
            grid_col=2, grid_padx=(0, 12))

        # --- 排序 / 显示数量（下拉） ---
        _add_label('排序', 3, (0, 12))
        _add_combo(self.sort_var, sort_rules, 3, 15, (0, 12))
        _add_label('显示数量', 4, (0, 0))
        _add_combo(self.top_n_var, top_n_values, 4, 7, (0, 0))

        for variable in (self.search_var, self.category_filter_var, self.company_filter_var,
                         self.sort_var, self.top_n_var):
            variable.trace_add('write', lambda *args: self._filter_ranking())

        tk.Label(controls,
                 text='榜单分数会按当前样本区间放大显示，更适合区分高分模型之间的细微差距。',
                 bg=THEME['bg_secondary'], fg=THEME['text_muted'],
                 font=(THEME['font_family'], 10)).pack(anchor='w', pady=(12, 0))

        table_card = self._create_card(self.content_container, padding=(14, 14), min_height=420)
        table_card.pack(fill=tk.BOTH, expand=True)
        table_frame = table_card.content

        columns = ('rank', 'model', 'company_license', 'score', 'votes', 'price', 'context', 'value')
        self.ranking_tree = ttk.Treeview(table_frame, columns=columns,
                                          show='headings', style='Custom.Treeview')

        self.ranking_tree.heading('rank', text='排名')
        self.ranking_tree.heading('model', text='模型')
        self.ranking_tree.heading('company_license', text='公司 · License')
        self.ranking_tree.heading('score', text='Score')
        self.ranking_tree.heading('votes', text='Votes')
        self.ranking_tree.heading('price', text='Price $/M')
        self.ranking_tree.heading('context', text='Context')
        self.ranking_tree.heading('value', text='性价比')

        self.ranking_tree.column('rank', width=56, anchor='center')
        self.ranking_tree.column('model', width=180, anchor='w')
        self.ranking_tree.column('company_license', width=180, anchor='w')
        self.ranking_tree.column('score', width=70, anchor='center')
        self.ranking_tree.column('votes', width=72, anchor='center')
        self.ranking_tree.column('price', width=104, anchor='center')
        self.ranking_tree.column('context', width=78, anchor='center')
        self.ranking_tree.column('value', width=72, anchor='center')

        # 排名前三高亮 tag
        self.ranking_tree.tag_configure('rank1', foreground='#b8860b')
        self.ranking_tree.tag_configure('rank2', foreground='#7d8597')
        self.ranking_tree.tag_configure('rank3', foreground='#a0522d')

        scrollbar = ttk.Scrollbar(table_frame, orient=tk.VERTICAL,
                       style='Modern.Vertical.TScrollbar',
                       command=self.ranking_tree.yview)
        self.ranking_tree.configure(yscrollcommand=scrollbar.set)

        self.ranking_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        detail_card = self._create_card(self.content_container, padding=(20, 18), min_height=180)
        detail_card.pack(fill=tk.X, pady=(16, 0))
        detail_content = detail_card.content

        # Title row
        self._ranking_detail_title = tk.Label(detail_content, text='模型详情',
                                              bg=THEME['bg_secondary'], fg=THEME['text'],
                                              font=(THEME['font_family'], 14, 'bold'))
        self._ranking_detail_title.pack(anchor='w')

        # Info grid: two columns
        self._detail_info_frame = tk.Frame(detail_content, bg=THEME['bg_secondary'])
        self._detail_info_frame.pack(fill=tk.X, pady=(10, 0))
        self._detail_info_frame.grid_columnconfigure(0, weight=1)
        self._detail_info_frame.grid_columnconfigure(1, weight=1)

        self._detail_left = tk.Frame(self._detail_info_frame, bg=THEME['bg_secondary'])
        self._detail_left.grid(row=0, column=0, sticky='nw', padx=(0, 24))
        self._detail_right = tk.Frame(self._detail_info_frame, bg=THEME['bg_secondary'])
        self._detail_right.grid(row=0, column=1, sticky='nw')

        self._detail_labels = {}
        for key in ('company', 'license', 'category', 'rank', 'rating', 'votes',
                     'price', 'context', 'avg_score', 'model_url'):
            self._detail_labels[key] = None

        # Dimension breakdown
        self._ranking_detail_strength = tk.Label(detail_content, text='',
                                                 bg=THEME['bg_secondary'], fg=THEME['text_muted'],
                                                 font=(THEME['font_family'], 10), justify='left')
        self._ranking_detail_strength.pack(anchor='w', pady=(10, 0))
        self._ranking_detail_weakness = tk.Label(detail_content, text='',
                                                 bg=THEME['bg_secondary'], fg=THEME['text_muted'],
                                                 font=(THEME['font_family'], 10), justify='left')
        self._ranking_detail_weakness.pack(anchor='w', pady=(6, 0))
        self._ranking_detail_alldims = tk.Label(detail_content, text='',
                                                 bg=THEME['bg_secondary'], fg=THEME['text_muted'],
                                                 font=(THEME['font_family'], 10), justify='left')
        self._ranking_detail_alldims.pack(anchor='w', pady=(6, 0))

        self.ranking_tree.bind('<<TreeviewSelect>>', self._update_ranking_detail)

        self._populate_ranking()

    def _get_ranking_rows(self):
        arena_data = self._get_current_arena_data()
        rank_map = self._arena_rank_map.get(self.current_arena, {})

        model_data = {}
        for item in arena_data:
            model = item.get('model', '')
            dimension = item.get('dimension', '')
            if not model or not dimension:
                continue
            entry = model_data.setdefault(model, {
                'company': item.get('company', '未知'),
                'scores': {}
            })
            entry['scores'][dimension] = item.get('score', 0)

        all_avgs = [sum(info['scores'].values()) / len(info['scores'])
                    for info in model_data.values() if info['scores']]

        model_extras = {}
        for item in arena_data:
            model = item.get('model', '')
            if model not in model_extras:
                model_extras[model] = {
                    'category': item.get('category', ''),
                    'license': item.get('license', ''),
                    'rating': item.get('rating', 0),
                    'votes': item.get('votes', 0),
                    'inputPrice': item.get('inputPricePerMillion'),
                    'outputPrice': item.get('outputPricePerMillion'),
                    'contextLength': item.get('contextLength'),
                    'modelUrl': item.get('modelUrl', ''),
                }
            if item.get('rating', 0) > model_extras[model].get('rating', 0):
                model_extras[model]['rating'] = item['rating']
            if item.get('votes', 0) > model_extras[model].get('votes', 0):
                model_extras[model]['votes'] = item['votes']

        rows = []
        for model, info in model_data.items():
            dimension_scores = info['scores']
            if not dimension_scores:
                continue

            avg = sum(dimension_scores.values()) / len(dimension_scores)
            extras = model_extras.get(model, {})
            category = extras.get('category', '')
            company = info['company']
            # 性价比：Arena Score 相对输出价格（价格越低、分越高 → 越高）
            rating_val = extras.get('rating', 0) or 0
            out_price = extras.get('outputPrice')
            if rating_val and out_price is not None and out_price > 0:
                value_ratio = rating_val / out_price
            elif rating_val and out_price == 0:
                value_ratio = float('inf')  # 免费且有评分 → 极致性价比
            else:
                value_ratio = None
            rows.append({
                'rank': rank_map.get(model, 0),
                'model': model,
                'company': company,
                'license': extras.get('license', ''),
                'category': category,
                'category_display': '国内' if category == 'domestic' else '国际' if category == 'international' else category,
                'avg': avg,
                'scaled': scale_score(avg, all_avgs),
                'rating': extras.get('rating', 0),
                'votes': extras.get('votes', 0),
                'inputPrice': extras.get('inputPrice'),
                'outputPrice': extras.get('outputPrice'),
                'contextLength': extras.get('contextLength'),
                'modelUrl': extras.get('modelUrl', ''),
                'value_ratio': value_ratio,
                'dimensions': len(dimension_scores),
                'code_score': dimension_scores.get('代码生成', 0),
                'dimension_scores': dimension_scores,
            })

        search = self.search_var.get().strip() if hasattr(self, 'search_var') else ''
        if search and search != getattr(self, '_search_placeholder', '搜索模型...'):
            rows = [row for row in rows if search.lower() in row['model'].lower()]

        # 公司：手动输入 + 模糊匹配（与搜索模型相同逻辑，忽略占位符）
        company_filter = self.company_filter_var.get().strip() if hasattr(self, 'company_filter_var') else ''
        if company_filter and company_filter != getattr(self, '_company_placeholder', ''):
            rows = [row for row in rows
                    if company_filter.lower() in (row.get('company') or '').lower()]

        category_filter = self.category_filter_var.get() if hasattr(self, 'category_filter_var') else '全部类别'
        if category_filter == '国内':
            rows = [row for row in rows if row['category'] == 'domestic']
        elif category_filter == '国际':
            rows = [row for row in rows if row['category'] == 'international']

        sort_rule = self.sort_var.get() if hasattr(self, 'sort_var') else 'Arena Score：高到低'
        if sort_rule == '综合均分：高到低':
            rows.sort(key=lambda row: row['avg'], reverse=True)
        elif sort_rule == '综合均分：低到高':
            rows.sort(key=lambda row: row['avg'])
        elif sort_rule == 'Votes：多到少':
            rows.sort(key=lambda row: row.get('votes', 0) or 0, reverse=True)
        elif sort_rule == '性价比：高到低':
            rows.sort(key=lambda row: (row.get('value_ratio') if row.get('value_ratio') is not None else -1),
                      reverse=True)
        elif sort_rule == '上下文：长到短':
            rows.sort(key=lambda row: row.get('contextLength') or 0, reverse=True)
        elif sort_rule == '代码生成：高到低':
            rows.sort(key=lambda row: row['code_score'], reverse=True)
        else:
            rows.sort(key=lambda row: row.get('rating', 0) or 0, reverse=True)

        top_n = self.top_n_var.get() if hasattr(self, 'top_n_var') else '全部'
        if top_n.isdigit():
            rows = rows[:int(top_n)]

        return rows

    def _populate_ranking(self):
        if not hasattr(self, 'ranking_tree') or not self.ranking_tree.winfo_exists():
            return
        for item in self.ranking_tree.get_children():
            self.ranking_tree.delete(item)

        rows = self._get_ranking_rows()
        self._ranking_row_map = {}

        for row in rows:
            company_license = row['company']
            if row.get('license'):
                company_license = f"{row['company']} · {row['license']}"
            score_str = f"{row['rating']:.0f}" if row.get('rating') else '-'
            votes_str = f"{row['votes']:,}" if row.get('votes') else '-'
            price_str = '-'
            if row.get('inputPrice') is not None and row.get('outputPrice') is not None:
                price_str = f"${row['inputPrice']:.2f} / ${row['outputPrice']:.2f}"
            elif row.get('inputPrice') is not None:
                price_str = f"${row['inputPrice']:.2f}"
            context_str = '-'
            if row.get('contextLength'):
                cl = row['contextLength']
                if cl >= 1048576:
                    context_str = f"{cl // 1048576}M"
                elif cl >= 1024:
                    context_str = f"{cl // 1024}K"
                else:
                    context_str = str(cl)
            value_str = '-'
            vr = row.get('value_ratio')
            if vr == float('inf'):
                value_str = '免费'
            elif vr is not None:
                value_str = f"{vr:.0f}"

            rank = row['rank']
            tags = ()
            if rank == 1:
                tags = ('rank1',)
            elif rank == 2:
                tags = ('rank2',)
            elif rank == 3:
                tags = ('rank3',)
            medal = {1: '🥇', 2: '🥈', 3: '🥉'}.get(rank, '')
            rank_label = f"{medal} #{rank}" if medal else f"#{rank}"

            item_id = self.ranking_tree.insert('', tk.END,
                                               values=(rank_label, row['model'], company_license,
                                                       score_str, votes_str, price_str,
                                                       context_str, value_str),
                                               tags=tags)
            self._ranking_row_map[item_id] = row

        if hasattr(self, '_ranking_status_label'):
            self._ranking_status_label.config(
                text=f"当前显示 {len(rows)} 个模型 · {self.sort_var.get() if hasattr(self, 'sort_var') else '综合分数：高到低'}"
            )

        children = self.ranking_tree.get_children()
        if children:
            first_item = children[0]
            self.ranking_tree.selection_set(first_item)
            self.ranking_tree.focus(first_item)
            self._update_ranking_detail()
        else:
            self._ranking_detail_title.config(text='模型详情')
            for w in self._detail_left.winfo_children():
                w.destroy()
            for w in self._detail_right.winfo_children():
                w.destroy()
            self._ranking_detail_strength.config(text='')
            self._ranking_detail_weakness.config(text='')
            self._ranking_detail_alldims.config(text='')

    def _filter_ranking(self):
        self._populate_ranking()

    def _update_ranking_detail(self, _event=None):
        if not hasattr(self, 'ranking_tree'):
            return

        selection = self.ranking_tree.selection()
        if not selection:
            return

        row = self._ranking_row_map.get(selection[0])
        if not row:
            return

        self._ranking_detail_title.config(text=row['model'])

        # Build info items for left/right columns
        def _info_item(parent, label, value, row_idx, fg=None):
            fg_color = fg or THEME['text_secondary']
            f = tk.Frame(parent, bg=THEME['bg_secondary'])
            f.grid(row=row_idx, column=0, sticky='w', pady=2)
            tk.Label(f, text=label, bg=THEME['bg_secondary'],
                     fg=THEME['text_muted'], font=(THEME['font_family'], 10),
                     width=8, anchor='w').pack(side=tk.LEFT)
            tk.Label(f, text=value, bg=THEME['bg_secondary'],
                     fg=fg_color, font=(THEME['font_family'], 10, 'bold'),
                     anchor='w', wraplength=250, justify='left').pack(side=tk.LEFT)

        # Clear old labels
        for w in self._detail_left.winfo_children():
            w.destroy()
        for w in self._detail_right.winfo_children():
            w.destroy()

        # Left column
        _info_item(self._detail_left, '公司', row['company'], 0)
        license_text = row.get('license') or '-'
        _info_item(self._detail_left, 'License', license_text, 1)
        _info_item(self._detail_left, '类别', row['category_display'], 2)
        _info_item(self._detail_left, '排名', f"#{row['rank']}", 3, fg=THEME['primary'])
        _info_item(self._detail_left, '均分', f"{row['avg']:.2f}", 4)

        # Right column
        rating_text = f"{row['rating']:.0f}" if row.get('rating') else '-'
        _info_item(self._detail_right, 'Score', rating_text, 0, fg=THEME['primary'])
        votes_text = f"{row['votes']:,}" if row.get('votes') else '-'
        _info_item(self._detail_right, 'Votes', votes_text, 1)

        price_text = '-'
        if row.get('inputPrice') is not None and row.get('outputPrice') is not None:
            price_text = f"${row['inputPrice']:.2f} / ${row['outputPrice']:.2f}"
        elif row.get('inputPrice') is not None:
            price_text = f"${row['inputPrice']:.2f}"
        _info_item(self._detail_right, 'Price', price_text, 2, fg=THEME['warning'] if price_text != '-' else None)

        ctx_text = '-'
        if row.get('contextLength'):
            cl = row['contextLength']
            if cl >= 1048576:
                ctx_text = f"{cl // 1048576}M tokens"
            elif cl >= 1024:
                ctx_text = f"{cl // 1024}K tokens"
            else:
                ctx_text = f"{cl} tokens"
        _info_item(self._detail_right, 'Context', ctx_text, 3)

        vr = row.get('value_ratio')
        if vr == float('inf'):
            value_text = '免费 · 极致性价比'
        elif vr is not None:
            value_text = f"{vr:.0f} (分/美元)"
        else:
            value_text = '-'
        _info_item(self._detail_right, '性价比', value_text, 4,
                   fg=THEME['success'] if vr else None)

        url_text = row.get('modelUrl', '') or ''
        if url_text:
            _info_item(self._detail_right, 'Link', url_text, 5, fg=THEME['primary'])

        # Dimension breakdown
        ordered_dims = sorted(row['dimension_scores'].items(), key=lambda item: item[1], reverse=True)
        strongest = ' / '.join(f"{name} {score:.1f}" for name, score in ordered_dims[:3])
        weakest = ' / '.join(f"{name} {score:.1f}" for name, score in ordered_dims[-2:])
        all_dims = '  '.join(f"{name}:{score:.1f}" for name, score in ordered_dims)

        self._ranking_detail_strength.config(text=f"优势维度：{strongest}")
        self._ranking_detail_weakness.config(text=f"待观察维度：{weakest}")
        self._ranking_detail_alldims.config(text=f"全部维度：{all_dims}")

    # ==================== Compare Tab ====================

    def _show_compare(self):
        if not self.models:
            return

        controls_card = self._create_card(self.content_container, padding=(20, 18))
        controls_card.pack(fill=tk.X, pady=(0, 16))
        inner = controls_card.content

        # Title row
        top_row = tk.Frame(inner, bg=THEME['bg_secondary'])
        top_row.pack(fill=tk.X)

        icon_img = get_icon('compare', size=20, color=THEME['primary'])
        self._compare_photo = ImageTk.PhotoImage(icon_img)
        tk.Label(top_row, image=self._compare_photo,
                 bg=THEME['bg_secondary']).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(top_row, text="模型对比", bg=THEME['bg_secondary'],
                 fg=THEME['text'], font=(THEME['font_family'], 14, 'bold')).pack(side=tk.LEFT)

        # Model selector row - label above, combobox below for better alignment
        selector_container = tk.Frame(inner, bg=THEME['bg_secondary'])
        selector_container.pack(fill=tk.X, pady=(16, 0))
        selector_container.grid_columnconfigure(0, weight=1, uniform='model')
        selector_container.grid_columnconfigure(1, weight=0)
        selector_container.grid_columnconfigure(2, weight=1, uniform='model')

        # Sort models by score (descending) for the dropdown — current arena only
        arena_data = self._get_current_arena_data()
        model_scores = {}
        for d in arena_data:
            m = d.get('model', '')
            if m not in model_scores:
                model_scores[m] = []
            model_scores[m].append(d.get('score', 0))
        avg_scores = {m: sum(s) / len(s) for m, s in model_scores.items() if s}
        sorted_models = sorted(self._get_current_arena_models(),
                               key=lambda m: avg_scores.get(m, 0), reverse=True)[:30]

        self.model1_var = tk.StringVar()
        self.model2_var = tk.StringVar()
        # 选择模型后自动刷新对比（替代原 ComboboxSelected 事件）
        self.model1_var.trace_add('write', lambda *a: self._maybe_refresh_compare())
        self.model2_var.trace_add('write', lambda *a: self._maybe_refresh_compare())

        # 默认选中分数最高的两个模型
        if sorted_models:
            self.model1_var.set(sorted_models[0])
        if len(sorted_models) > 1:
            self.model2_var.set(sorted_models[1])

        # Model A column
        col_a = tk.Frame(selector_container, bg=THEME['bg_secondary'])
        col_a.grid(row=0, column=0, sticky='ew', padx=(0, 6))
        tk.Label(col_a, text="模型 A", bg=THEME['bg_secondary'],
                 fg=THEME['text_muted'], font=(THEME['font_family'], 10)).pack(anchor='w', pady=(0, 4))
        RoundedDropdown(col_a, self.model1_var, sorted_models, width_px=320).pack(fill=tk.X)

        # VS label centered
        vs_frame = tk.Frame(selector_container, bg=THEME['bg_secondary'])
        vs_frame.grid(row=0, column=1, padx=6)
        tk.Label(vs_frame, text="VS", bg=THEME['bg_secondary'],
                 fg=THEME['primary'], font=(THEME['font_family'], 16, 'bold')).pack(pady=(16, 0))

        # Model B column
        col_b = tk.Frame(selector_container, bg=THEME['bg_secondary'])
        col_b.grid(row=0, column=2, sticky='ew', padx=(6, 0))
        tk.Label(col_b, text="模型 B", bg=THEME['bg_secondary'],
                 fg=THEME['text_muted'], font=(THEME['font_family'], 10)).pack(anchor='w', pady=(0, 4))
        RoundedDropdown(col_b, self.model2_var, sorted_models, width_px=320).pack(fill=tk.X)

        # Action buttons row
        action_row = tk.Frame(inner, bg=THEME['bg_secondary'])
        action_row.pack(fill=tk.X, pady=(14, 0))
        StyledButton(action_row, "开始对比", self._do_compare,
                     font_size=11).pack(side=tk.LEFT)
        StyledButton(action_row, "交换模型", self._swap_compare_models,
                     font_size=11, color_key='secondary',
                     text_color=THEME['text_secondary']).pack(side=tk.LEFT, padx=(8, 0))

        # Dimension selection section
        dim_sep = tk.Frame(inner, bg=THEME['border_light'], height=1)
        dim_sep.pack(fill=tk.X, pady=(16, 0))

        dimension_header = tk.Frame(inner, bg=THEME['bg_secondary'])
        dimension_header.pack(fill=tk.X, pady=(12, 0))

        tk.Label(dimension_header, text='对比维度', bg=THEME['bg_secondary'],
                 fg=THEME['text'], font=(THEME['font_family'], 11, 'bold')).pack(side=tk.LEFT)

        dim_actions = tk.Frame(dimension_header, bg=THEME['bg_secondary'])
        dim_actions.pack(side=tk.RIGHT)
        StyledButton(dim_actions, '全选维度', self._select_all_compare_dimensions,
                     font_size=10, color_key='secondary',
                     text_color=THEME['text_secondary']).pack(side=tk.LEFT)
        StyledButton(dim_actions, '取消全选', self._deselect_all_compare_dimensions,
                     font_size=10, color_key='secondary',
                     text_color=THEME['text_secondary']).pack(side=tk.LEFT, padx=(8, 0))
        StyledButton(dim_actions, '仅代码生成', self._reset_compare_dimensions,
                     font_size=10, color_key='secondary',
                     text_color=THEME['text_secondary']).pack(side=tk.LEFT, padx=(8, 0))

        arena_data = self._get_current_arena_data()
        current_dims = sorted({d.get('dimension', '') for d in arena_data if d.get('dimension')})
        if not current_dims:
            current_dims = EVALUATION_DIMENSIONS

        dimension_grid = tk.Frame(inner, bg=THEME['bg_secondary'])
        dimension_grid.pack(fill=tk.X, pady=(10, 0))
        self._compare_dim_vars = {}
        for index, dimension in enumerate(current_dims):
            var = tk.BooleanVar(value=True)
            self._compare_dim_vars[dimension] = var
            checkbox = tk.Checkbutton(
                dimension_grid,
                text=dimension,
                variable=var,
                command=self._maybe_refresh_compare,
                bg=THEME['bg_secondary'],
                activebackground=THEME['bg_secondary'],
                selectcolor=THEME['bg_secondary'],
                fg=THEME['text_secondary'],
                font=(THEME['font_family'], 10),
                anchor='w',
                padx=0,
            )
            checkbox.grid(row=index // 4, column=index % 4, sticky='w', padx=(0, 18), pady=3)

        # Result area
        self.compare_result = tk.Frame(self.content_container, bg=THEME['bg'])
        self.compare_result.pack(fill=tk.BOTH, expand=True)

        if self.model1_var.get() and self.model2_var.get():
            self.content_container.after_idle(self._safe_auto_compare)

    def _safe_auto_compare(self):
        if hasattr(self, 'compare_result') and self.compare_result.winfo_exists():
            self._do_compare()

    def _clear_compare_result(self, hint=None):
        """清空对比结果区，可选显示一句居中提示。"""
        if not hasattr(self, 'compare_result') or not self.compare_result.winfo_exists():
            return
        for widget in self.compare_result.winfo_children():
            widget.destroy()
        if hint:
            tk.Label(self.compare_result, text=hint, bg=THEME['bg'],
                     fg=THEME['text_muted'],
                     font=(THEME['font_family'], 12)).pack(expand=True, pady=60)

    def _do_compare(self, silent=False):
        """执行对比。silent=True 时（自动刷新场景）不弹框，仅清空结果区。"""
        m1 = self.model1_var.get()
        m2 = self.model2_var.get()
        selected_dimensions = self._get_selected_compare_dimensions()

        # 校验失败：手动触发时提示，自动触发时静默清空
        if not m1 or not m2:
            if silent:
                self._clear_compare_result()
            else:
                messagebox.showwarning("提示", "请选择两个模型")
            return
        if m1 == m2:
            if silent:
                self._clear_compare_result('请选择两个不同的模型进行对比')
            else:
                messagebox.showwarning("提示", "请选择不同的模型进行对比")
            return
        if not selected_dimensions:
            # 什么维度都没选 —— 就真的不对比，清空结果区，绝不报错
            self._clear_compare_result('未选择任何对比维度')
            return

        if self._compare_rendering or not hasattr(self, 'compare_result') or not self.compare_result.winfo_exists():
            return

        self._compare_rendering = True

        try:
            for widget in self.compare_result.winfo_children():
                widget.destroy()

            arena_data = self._get_current_arena_data()
            m1_data = {d['dimension']: d['score'] for d in arena_data
                       if d['model'] == m1 and d['dimension'] in selected_dimensions}
            m2_data = {d['dimension']: d['score'] for d in arena_data
                       if d['model'] == m2 and d['dimension'] in selected_dimensions}

            if not m1_data or not m2_data:
                if silent:
                    self._clear_compare_result('所选维度下模型数据不足')
                else:
                    messagebox.showwarning("提示", "模型数据不足")
                return

            # Two-column layout: chart left, table right
            result_container = tk.Frame(self.compare_result, bg=THEME['bg'])
            result_container.pack(fill=tk.BOTH, expand=True)
            result_container.grid_columnconfigure(0, weight=1)
            result_container.grid_columnconfigure(1, weight=1)

            # Left: chart comparison
            chart_card = self._create_card(result_container, padding=(0, 0), min_height=520)
            chart_card.grid(row=0, column=0, sticky='nsew', padx=(0, 8))
            chart_frame = chart_card.content

            if len(selected_dimensions) <= 2:
                self._draw_compare_bar(chart_frame, m1, m2, m1_data, m2_data, selected_dimensions)
            else:
                self._draw_compare_radar(chart_frame, m1, m2, m1_data, m2_data, selected_dimensions)

            # Right: comparison table
            table_card = self._create_card(result_container, padding=(14, 14), min_height=520)
            table_card.grid(row=0, column=1, sticky='nsew', padx=(8, 0))
            table_frame = table_card.content

            # Header with model names
            header_row = tk.Frame(table_frame, bg=THEME['bg_secondary'])
            header_row.pack(fill=tk.X, padx=12, pady=(12, 8))

            tk.Label(header_row, text=m1, bg=THEME['bg_secondary'],
                     fg=THEME['chart_colors'][0], font=(THEME['font_family'], 12, 'bold'),
                     wraplength=180, justify='left').pack(side=tk.LEFT)
            tk.Label(header_row, text="VS", bg=THEME['bg_secondary'],
                     fg=THEME['text_muted'], font=(THEME['font_family'], 11, 'bold')).pack(side=tk.LEFT, padx=12)
            tk.Label(header_row, text=m2, bg=THEME['bg_secondary'],
                     fg=THEME['chart_colors'][1], font=(THEME['font_family'], 12, 'bold'),
                     wraplength=180, justify='right').pack(side=tk.LEFT)

            dim_label = tk.Frame(table_frame, bg=THEME['bg_secondary'])
            dim_label.pack(fill=tk.X, padx=12, pady=(0, 8))
            tk.Label(dim_label, text=f"维度：{'、'.join(selected_dimensions)}", bg=THEME['bg_secondary'],
                     fg=THEME['text_muted'], font=(THEME['font_family'], 9),
                     wraplength=400, justify='left').pack(side=tk.LEFT)

            # Summary stats
            m1_total = sum(m1_data.values())
            m2_total = sum(m2_data.values())
            m1_avg = m1_total / len(m1_data) if m1_data else 0
            m2_avg = m2_total / len(m2_data) if m2_data else 0
            wins_a = sum(1 for d in selected_dimensions if m1_data.get(d, 0) > m2_data.get(d, 0))
            wins_b = sum(1 for d in selected_dimensions if m2_data.get(d, 0) > m1_data.get(d, 0))

            summary_frame = tk.Frame(table_frame, bg=THEME['bg_secondary'])
            summary_frame.pack(fill=tk.X, padx=12, pady=(0, 10))
            summary_frame.grid_columnconfigure(0, weight=1)
            summary_frame.grid_columnconfigure(1, weight=1)
            summary_frame.grid_columnconfigure(2, weight=1)

            for col, (label_text, value, color) in enumerate([
                ('A 均分', f'{m1_avg:.2f}', THEME['chart_colors'][0]),
                ('B 均分', f'{m2_avg:.2f}', THEME['chart_colors'][1]),
                ('胜负', f'{wins_a} : {wins_b}', THEME['text']),
            ]):
                sf = tk.Frame(summary_frame, bg=THEME['bg_secondary'])
                sf.grid(row=0, column=col, sticky='ew', padx=4)
                tk.Label(sf, text=label_text, bg=THEME['bg_secondary'],
                         fg=THEME['text_muted'], font=(THEME['font_family'], 9)).pack()
                tk.Label(sf, text=value, bg=THEME['bg_secondary'],
                         fg=color, font=(THEME['font_family'], 14, 'bold')).pack()

            # Detail table
            tree = ttk.Treeview(table_frame, columns=('dim', 'm1', 'm2', 'diff', 'winner'),
                                show='headings', height=8, style='Custom.Treeview')

            tree.heading('dim', text='维度')
            tree.heading('m1', text='模型A')
            tree.heading('m2', text='模型B')
            tree.heading('diff', text='分差')
            tree.heading('winner', text='胜出')

            tree.column('dim', width=88, anchor='w')
            tree.column('m1', width=70, anchor='center')
            tree.column('m2', width=70, anchor='center')
            tree.column('diff', width=60, anchor='center')
            tree.column('winner', width=60, anchor='center')

            for dim in selected_dimensions:
                s1 = m1_data.get(dim, 0)
                s2 = m2_data.get(dim, 0)
                diff = s1 - s2
                winner = "A胜" if s1 > s2 else "B胜" if s2 > s1 else "平局"
                tree.insert('', tk.END, values=(dim, f"{s1:.2f}", f"{s2:.2f}",
                                                f"{diff:+.2f}", winner))

            tree.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        finally:
            self._compare_rendering = False
        self._heatmap_zoom = None

    def _draw_compare_radar(self, parent, m1, m2, m1_data, m2_data, selected_dimensions):
        """Draw comparison radar chart with zoomed range"""
        n = len(selected_dimensions)
        angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
        angles += angles[:1]

        fig, ax = plt.subplots(figsize=(6, 5), subplot_kw=dict(polar=True))
        fig.patch.set_facecolor(THEME['bg_secondary'])
        ax.set_facecolor(THEME['bg_secondary'])

        # Collect all scores for range
        all_scores = list(m1_data.values()) + list(m2_data.values())
        min_range, max_range = get_score_range(all_scores, padding_ratio=0.12, minimum_padding=1.2)

        v1 = [m1_data.get(dim, min_range) for dim in selected_dimensions] + [m1_data.get(selected_dimensions[0], min_range)]
        v2 = [m2_data.get(dim, min_range) for dim in selected_dimensions] + [m2_data.get(selected_dimensions[0], min_range)]

        ax.plot(angles, v1, 'o-', linewidth=2, label='模型A', color=THEME['chart_colors'][0], markersize=5)
        ax.fill(angles, v1, alpha=0.15, color=THEME['chart_colors'][0])
        ax.plot(angles, v2, 'o-', linewidth=2, label='模型B', color=THEME['chart_colors'][1], markersize=5)
        ax.fill(angles, v2, alpha=0.15, color=THEME['chart_colors'][1])

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(selected_dimensions, fontsize=9, color=THEME['text'])
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

    def _draw_compare_bar(self, parent, m1, m2, m1_data, m2_data, selected_dimensions):
        """Draw comparison bar chart for 1-2 dimensions (radar is a line with 2 axes)"""
        n_dims = len(selected_dimensions)
        all_scores = list(m1_data.values()) + list(m2_data.values())
        min_range, max_range = get_score_range(all_scores, padding_ratio=0.15, minimum_padding=1.5)

        fig, ax = plt.subplots(figsize=(6, 5))
        fig.patch.set_facecolor(THEME['bg_secondary'])
        ax.set_facecolor(THEME['bg_secondary'])

        x = np.arange(n_dims)
        bar_width = 0.35

        s1 = [m1_data.get(dim, 0) for dim in selected_dimensions]
        s2 = [m2_data.get(dim, 0) for dim in selected_dimensions]

        bars1 = ax.bar(x - bar_width / 2, s1, bar_width, label=m1,
                       color=THEME['chart_colors'][0], alpha=0.85)
        bars2 = ax.bar(x + bar_width / 2, s2, bar_width, label=m2,
                       color=THEME['chart_colors'][1], alpha=0.85)

        ax.set_ylim(min_range, max_range)
        ax.set_xticks(x)
        ax.set_xticklabels(selected_dimensions, fontsize=10, color=THEME['text'])
        ax.set_ylabel('得分', fontsize=10, color=THEME['text_secondary'])
        ax.legend(fontsize=9, framealpha=0.9, edgecolor=THEME['border'])
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color(THEME['border'])
        ax.spines['bottom'].set_color(THEME['border'])
        ax.tick_params(axis='y', colors=THEME['text_muted'])
        ax.grid(axis='y', color=THEME['border_light'], linestyle='--', linewidth=0.8)

        for bar, value in zip(bars1, s1):
            ax.text(bar.get_x() + bar.get_width() / 2, value + 0.15,
                    f'{value:.1f}', ha='center', va='bottom',
                    color=THEME['text'], fontsize=9)
        for bar, value in zip(bars2, s2):
            ax.text(bar.get_x() + bar.get_width() / 2, value + 0.15,
                    f'{value:.1f}', ha='center', va='bottom',
                    color=THEME['text'], fontsize=9)

        plt.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=16, pady=16)
        plt.close(fig)

    def _get_selected_compare_dimensions(self):
        return [dimension for dimension, var in self._compare_dim_vars.items() if var.get()]

    def _maybe_refresh_compare(self):
        if hasattr(self, 'compare_result') and self.compare_result.winfo_exists():
            self._do_compare(silent=True)

    def _swap_compare_models(self):
        model1 = self.model1_var.get()
        model2 = self.model2_var.get()
        if model1 and model2:
            self.model1_var.set(model2)
            self.model2_var.set(model1)
            self._do_compare()

    def _select_all_compare_dimensions(self):
        for var in self._compare_dim_vars.values():
            var.set(True)
        self._maybe_refresh_compare()

    def _deselect_all_compare_dimensions(self):
        for var in self._compare_dim_vars.values():
            var.set(False)
        self._maybe_refresh_compare()

    def _reset_compare_dimensions(self):
        for dimension, var in self._compare_dim_vars.items():
            var.set(dimension == '代码生成')
        self._maybe_refresh_compare()

    # ==================== Radar Tab ====================

    def _show_radar(self):
        if not self._get_current_arena_data():
            return

        companies = self._get_top_company_flagships(limit=5)
        arena_data = self._get_current_arena_data()
        current_dims = sorted({d.get('dimension', '') for d in arena_data if d.get('dimension')})
        n_dims = len(current_dims) if current_dims else len(EVALUATION_DIMENSIONS)

        chart_label = "能力雷达图" if n_dims >= 3 else "能力对比图"
        dim_desc = f"各公司最高分模型的{n_dims}维度能力对比" if n_dims >= 2 else "各公司最高分模型得分对比"

        # Title card
        title_card = self._create_card(self.content_container, padding=(20, 16))
        title_card.pack(fill=tk.X, pady=(0, 16))
        title_frame = title_card.content

        icon_img = get_icon('chart_radar', size=20, color=THEME['primary'])
        self._radar_tab_photo = ImageTk.PhotoImage(icon_img)
        tk.Label(title_frame, image=self._radar_tab_photo,
                 bg=THEME['bg_secondary']).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(title_frame, text=f"旗舰模型{chart_label}", bg=THEME['bg_secondary'],
                 fg=THEME['text'], font=(THEME['font_family'], 14, 'bold')).pack(side=tk.LEFT, padx=(0, 16))
        tk.Label(title_frame, text=dim_desc,
                 bg=THEME['bg_secondary'], fg=THEME['text_muted'],
                 font=(THEME['font_family'], 10)).pack(side=tk.LEFT)

        # Two-column layout: chart left, model cards right
        content_row = tk.Frame(self.content_container, bg=THEME['bg'])
        content_row.pack(fill=tk.BOTH, expand=True)
        content_row.grid_columnconfigure(0, weight=3)
        content_row.grid_columnconfigure(1, weight=2)

        # Left: chart
        chart_card = self._create_card(content_row, padding=(0, 0), min_height=520)
        chart_card.grid(row=0, column=0, sticky='nsew', padx=(0, 12))
        if n_dims >= 3:
            self._draw_radar_chart(chart_card.content, companies, large=True)
        else:
            self._draw_flagship_bar(chart_card.content, companies, current_dims)

        # Right: model info cards
        info_card = self._create_card(content_row, padding=(16, 16), min_height=520)
        info_card.grid(row=0, column=1, sticky='nsew')
        info_frame = info_card.content

        tk.Label(info_frame, text="旗舰模型一览", bg=THEME['bg_secondary'],
                 fg=THEME['text'], font=(THEME['font_family'], 12, 'bold')).pack(anchor='w', pady=(0, 12))

        # 计算全局维度区间，用于条长归一化（让条长真实反映强弱差异）
        all_dim_scores = [v for _, info in companies for v in info['scores'].values()]
        g_min = min(all_dim_scores) if all_dim_scores else 0
        g_max = max(all_dim_scores) if all_dim_scores else 100
        lo, hi = get_score_range([g_min, g_max], padding_ratio=0.05, minimum_padding=1.0)
        span = max(hi - lo, 1e-6)

        colors = THEME['chart_colors']
        for i, (company, info) in enumerate(companies):
            color = colors[i % len(colors)]
            model = info['model']
            scores = info['scores']
            avg = sum(scores.values()) / len(scores) if scores else 0

            # 标题行：色点 + 公司·模型 + 均分
            head = tk.Frame(info_frame, bg=THEME['bg_secondary'])
            head.pack(fill=tk.X, pady=(0, 6))
            dot_canvas = tk.Canvas(head, width=10, height=10,
                                   bg=THEME['bg_secondary'], highlightthickness=0)
            dot_canvas.pack(side=tk.LEFT, padx=(0, 8), pady=(5, 0))
            dot_canvas.create_oval(1, 1, 9, 9, fill=color, outline='')

            text_col = tk.Frame(head, bg=THEME['bg_secondary'])
            text_col.pack(side=tk.LEFT, fill=tk.X, expand=True)
            company_label = f"{company} · {model}" if company != model else model
            tk.Label(text_col, text=company_label, bg=THEME['bg_secondary'],
                     fg=THEME['text'], font=(THEME['font_family'], 10, 'bold'),
                     anchor='w', wraplength=250, justify='left').pack(anchor='w')
            tk.Label(text_col, text=f"均分 {avg:.1f}  ·  {len(scores)} 个维度",
                     bg=THEME['bg_secondary'], fg=THEME['text_muted'],
                     font=(THEME['font_family'], 9), anchor='w').pack(anchor='w')

            # 全维度水平进度条：维度名 + 条 + 分数（条长按数据区间归一化）
            ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            row_h = 20
            bars_canvas = tk.Canvas(text_col, height=row_h * len(ordered) + 4,
                                    bg=THEME['bg_secondary'], highlightthickness=0, bd=0)
            bars_canvas.pack(fill=tk.X, pady=(6, 0))

            def _draw_bars(cv=bars_canvas, ordered=ordered, color=color):
                cv.delete('all')
                w = cv.winfo_width()
                if w <= 1:
                    return
                name_w = 64       # 维度名宽度
                score_w = 34      # 分数宽度
                track_x0 = name_w
                track_x1 = w - score_w
                track_w = max(track_x1 - track_x0, 10)
                for r, (dim_name, dim_score) in enumerate(ordered):
                    cy = r * row_h + row_h // 2 + 2
                    cv.create_text(0, cy, text=dim_name, anchor='w',
                                   fill=THEME['text_secondary'],
                                   font=(THEME['font_family'], 9))
                    # 轨道
                    draw_rounded_rect(cv, track_x0, cy - 4, track_x1, cy + 4, 4,
                                      fill=THEME['border_light'], outline='')
                    # 填充
                    ratio = max(0.0, min(1.0, (dim_score - lo) / span))
                    fill_x1 = track_x0 + max(8, int(track_w * ratio))
                    draw_rounded_rect(cv, track_x0, cy - 4, fill_x1, cy + 4, 4,
                                      fill=color, outline='')
                    cv.create_text(w, cy, text=f"{dim_score:.1f}", anchor='e',
                                   fill=THEME['text'],
                                   font=(THEME['font_family'], 9, 'bold'))

            bars_canvas.bind('<Configure>', lambda e, fn=_draw_bars: fn())

            # 分隔线
            if i < len(companies) - 1:
                sep = tk.Frame(info_frame, bg=THEME['border_light'], height=1)
                sep.pack(fill=tk.X, pady=(10, 10))

    # ==================== Heatmap Tab ====================

    def _show_heatmap(self):
        if not self._get_current_arena_data():
            return

        arena_data = self._get_current_arena_data()

        # Get top 15 models by average score
        model_scores = {}
        for d in arena_data:
            m = d.get('model', '')
            if m not in model_scores:
                model_scores[m] = []
            model_scores[m].append(d.get('score', 0))

        avg_scores = {m: sum(s) / len(s) for m, s in model_scores.items() if s}
        sorted_models = sorted(avg_scores.keys(), key=lambda m: avg_scores[m], reverse=True)[:15]

        # Determine dimensions for current arena
        current_dims = sorted({d.get('dimension', '') for d in arena_data if d.get('dimension')})
        if not current_dims:
            current_dims = EVALUATION_DIMENSIONS

        # Build score matrix once（用字典查找，O(N) 替代三重循环）
        score_lookup = {}
        for d in arena_data:
            score_lookup[(d.get('model'), d.get('dimension'))] = d.get('score', 0)
        matrix = np.zeros((len(sorted_models), len(current_dims)))
        for i, model in enumerate(sorted_models):
            for j, dim in enumerate(current_dims):
                matrix[i, j] = score_lookup.get((model, dim), 0)

        companies = self._get_top_company_flagships(limit=5)

        zoom = self._heatmap_zoom  # None or 1-4

        # Title card
        title_card = self._create_card(self.content_container, padding=(20, 16))
        title_card.pack(fill=tk.X, pady=(0, 16))
        title_frame = title_card.content

        icon_img = get_icon('heatmap', size=20, color=THEME['primary'])
        self._heatmap_photo = ImageTk.PhotoImage(icon_img)
        tk.Label(title_frame, image=self._heatmap_photo,
                 bg=THEME['bg_secondary']).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(title_frame, text="模型综合洞察", bg=THEME['bg_secondary'],
                 fg=THEME['text'], font=(THEME['font_family'], 14, 'bold')).pack(side=tk.LEFT)

        if zoom:
            # Zoomed: single large chart
            large_card = self._create_card(self.content_container, padding=(0, 0), min_height=600)
            large_card.pack(fill=tk.BOTH, expand=True, pady=(0, 16))

            chart_methods = {
                1: lambda p: self._draw_heatmap_chart(p, sorted_models, matrix, current_dims, large=True),
                2: lambda p: self._draw_confidence_chart(p, sorted_models, avg_scores, large=True),
                3: lambda p: self._draw_price_rating_scatter(p, large=True),
                4: lambda p: self._draw_ranking_bar_chart(p, sorted_models, matrix, current_dims, large=True),
                5: lambda p: self._draw_license_comparison(p, current_dims, large=True),
                6: lambda p: self._draw_votes_chart(p, large=True),
            }
            chart_methods[zoom](large_card.content)

            # Click to zoom out
            large_card.frame.bind('<Button-1>', lambda e: self._heatmap_zoom_out())
            large_card.canvas.bind('<Button-1>', lambda e: self._heatmap_zoom_out())
            large_card.content.bind('<Button-1>', lambda e: self._heatmap_zoom_out())
            self._bind_click_recursive(large_card.content, lambda e: self._heatmap_zoom_out())

            # Hint label
            hint = tk.Label(large_card.content, text="点击任意位置返回缩略视图",
                            bg=THEME['bg_secondary'], fg=THEME['text_muted'],
                            font=(THEME['font_family'], 9))
            hint.pack(side=tk.BOTTOM, pady=(0, 8))
        else:
            # 3x2 grid of charts
            grid_frame = tk.Frame(self.content_container, bg=THEME['bg'])
            grid_frame.pack(fill=tk.BOTH, expand=True)
            grid_frame.grid_columnconfigure(0, weight=1)
            grid_frame.grid_columnconfigure(1, weight=1)
            grid_frame.grid_rowconfigure(0, weight=1)
            grid_frame.grid_rowconfigure(1, weight=1)
            grid_frame.grid_rowconfigure(2, weight=1)

            # 6 张图卡片骨架（先建好布局，绘制延迟以避免一次性阻塞 UI）
            positions = [
                (0, 0, (0, 8), (0, 8)), (0, 1, (8, 0), (0, 8)),
                (1, 0, (0, 8), (8, 0)), (1, 1, (8, 0), (8, 0)),
                (2, 0, (0, 8), (8, 0)), (2, 1, (8, 0), (8, 0)),
            ]
            cards = []
            for (r, col, px, py) in positions:
                card = self._create_card(grid_frame, padding=(0, 0), min_height=340)
                card.grid(row=r, column=col, sticky='nsew', padx=px, pady=py)
                cards.append(card)

            draw_funcs = [
                lambda p: self._draw_heatmap_chart(p, sorted_models, matrix, current_dims),
                lambda p: self._draw_confidence_chart(p, sorted_models, avg_scores),
                lambda p: self._draw_price_rating_scatter(p),
                lambda p: self._draw_ranking_bar_chart(p, sorted_models, matrix, current_dims),
                lambda p: self._draw_license_comparison(p, current_dims),
                lambda p: self._draw_votes_chart(p),
            ]

            def _render_one(i):
                if i >= len(cards):
                    return
                card = cards[i]
                if not card.content.winfo_exists() or self.current_tab != 'heatmap':
                    return
                draw_funcs[i](card.content)
                idx = i + 1
                # 绘制完成后绑定点击放大
                for w in (card.frame, card.canvas, card.content):
                    w.bind('<Button-1>', lambda e, k=idx: self._heatmap_zoom_in(k))
                self._bind_click_recursive(card.content, lambda e, k=idx: self._heatmap_zoom_in(k))
                card.frame.bind('<Enter>', lambda e, c=card: c.frame.configure(cursor='hand2'))
                card.frame.bind('<Leave>', lambda e, c=card: c.frame.configure(cursor=''))
                # 渲染下一张
                self.root.after(10, lambda: _render_one(i + 1))

            self.root.after_idle(lambda: _render_one(0))

    def _heatmap_zoom_in(self, chart_index):
        self._heatmap_zoom = chart_index
        self._switch_tab('heatmap')

    def _heatmap_zoom_out(self):
        self._heatmap_zoom = None
        self._switch_tab('heatmap')

    def _bind_click_recursive(self, widget, handler):
        """Bind click handler to a widget and all its children."""
        widget.bind('<Button-1>', handler)
        for child in widget.winfo_children():
            self._bind_click_recursive(child, handler)

    # ---------- heatmap sub-charts ----------

    def _draw_heatmap_chart(self, parent, sorted_models, matrix, dims, large=False):
        """Chart 1: 模型×维度能力热力图"""
        fs = (11, 8) if large else (5.5, 4)
        lbl_fs = 12 if large else 7
        ytick_fs = 9 if large else 6
        val_fs = 8 if large else 5
        name_len = 30 if large else 18

        header = tk.Frame(parent, bg=THEME['bg_secondary'])
        header.pack(fill=tk.X, padx=16, pady=(12, 4))
        tk.Label(header, text="能力热力图", bg=THEME['bg_secondary'],
                 fg=THEME['text'], font=(THEME['font_family'], 12, 'bold')).pack(side=tk.LEFT)

        fig, ax = plt.subplots(figsize=fs)
        fig.patch.set_facecolor(THEME['bg_secondary'])
        ax.set_facecolor(THEME['bg_secondary'])

        im = ax.imshow(matrix, cmap='YlOrRd', aspect='auto')
        ax.set_xticks(range(len(dims)))
        ax.set_xticklabels(dims, rotation=45, ha='right', fontsize=lbl_fs, color=THEME['text_secondary'])
        ax.set_yticks(range(len(sorted_models)))
        ax.set_yticklabels([m[:name_len] for m in sorted_models], fontsize=ytick_fs, color=THEME['text_secondary'])
        for i in range(len(sorted_models)):
            for j in range(len(dims)):
                val = matrix[i, j]
                tc = 'white' if val > np.mean(matrix) + np.std(matrix) else 'black'
                ax.text(j, i, f'{val:.0f}', ha='center', va='center', fontsize=val_fs, color=tc)
        plt.colorbar(im, ax=ax, shrink=0.6)
        plt.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        plt.close(fig)

    def _draw_confidence_chart(self, parent, sorted_models, avg_scores, large=False):
        """Chart 2: 各模型综合得分置信区间"""
        fs = (11, 8) if large else (5.5, 4)
        ytick_fs = 9 if large else 6
        xlabel_fs = 11 if large else 8
        name_len = 30 if large else 18

        header = tk.Frame(parent, bg=THEME['bg_secondary'])
        header.pack(fill=tk.X, padx=16, pady=(12, 4))
        tk.Label(header, text="得分置信区间", bg=THEME['bg_secondary'],
                 fg=THEME['text'], font=(THEME['font_family'], 12, 'bold')).pack(side=tk.LEFT)

        fig, ax = plt.subplots(figsize=fs)
        fig.patch.set_facecolor(THEME['bg_secondary'])
        ax.set_facecolor(THEME['bg_secondary'])

        models = sorted_models[:15]
        scores = [avg_scores.get(m, 0) for m in models]
        errors = []
        for m in models:
            dims = [d.get('score', 0) for d in self._get_current_arena_data() if d.get('model') == m]
            if len(dims) > 1:
                errors.append(np.std(dims))
            else:
                errors.append(2.0)

        colors = [THEME['chart_colors'][i % len(THEME['chart_colors'])] for i in range(len(models))]
        ax.barh(range(len(models)), scores, xerr=errors, color=colors, alpha=0.85, capsize=3)
        ax.set_yticks(range(len(models)))
        ax.set_yticklabels([m[:name_len] for m in models], fontsize=ytick_fs, color=THEME['text_secondary'])
        ax.set_xlabel('综合得分', fontsize=xlabel_fs, color=THEME['text_secondary'])
        ax.invert_yaxis()
        plt.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        plt.close(fig)

    def _draw_flagship_bar(self, parent, companies, dims):
        """Draw horizontal bar chart for 1-2 dimensions (radar is meaningless)."""
        if not companies:
            return

        header = tk.Frame(parent, bg=THEME['bg_secondary'])
        header.pack(fill=tk.X, padx=16, pady=(12, 4))
        tk.Label(header, text="旗舰模型得分对比", bg=THEME['bg_secondary'],
                 fg=THEME['text'], font=(THEME['font_family'], 12, 'bold')).pack(side=tk.LEFT)

        fig, ax = plt.subplots(figsize=(10, 7))
        fig.patch.set_facecolor(THEME['bg_secondary'])
        ax.set_facecolor(THEME['bg_secondary'])

        labels = [f"{company} · {info['model']}" for company, info in companies]
        colors = THEME['chart_colors']

        if len(dims) <= 1:
            dim_name = dims[0] if dims else 'Score'
            scores = [list(info['scores'].values())[0] if info['scores'] else 0
                      for _, info in companies]
            bar_colors = [colors[i % len(colors)] for i in range(len(companies))]
            y_pos = np.arange(len(companies))
            bars = ax.barh(y_pos, scores, height=0.6, color=bar_colors, alpha=0.85)
            ax.set_yticks(y_pos)
            ax.set_yticklabels(labels, fontsize=10, color=THEME['text_secondary'])
            ax.set_xlabel(dim_name, fontsize=11, color=THEME['text_secondary'])
            ax.invert_yaxis()
            for bar, val in zip(bars, scores):
                ax.text(val + 0.3, bar.get_y() + bar.get_height() / 2,
                        f'{val:.1f}', va='center', fontsize=10,
                        color=THEME['text'], fontweight='bold')
        else:
            x = np.arange(len(companies))
            width = 0.35
            for d_idx, dim_name in enumerate(dims[:2]):
                scores = [info['scores'].get(dim_name, 0) for _, info in companies]
                offset = (d_idx - 0.5) * width
                bar_color = colors[d_idx % len(colors)]
                bars = ax.barh(x + offset, scores, width, label=dim_name,
                               color=bar_color, alpha=0.85)
                for bar, val in zip(bars, scores):
                    ax.text(val + 0.3, bar.get_y() + bar.get_height() / 2,
                            f'{val:.1f}', va='center', fontsize=9,
                            color=THEME['text'])
            ax.set_yticks(x)
            ax.set_yticklabels(labels, fontsize=10, color=THEME['text_secondary'])
            ax.legend(fontsize=10, framealpha=0.8, edgecolor=THEME['border'])

        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color(THEME['border'])
        ax.spines['bottom'].set_color(THEME['border'])
        ax.tick_params(axis='x', colors=THEME['text_muted'])
        ax.grid(axis='x', color=THEME['border_light'], linestyle='--', linewidth=0.8)
        plt.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        plt.close(fig)

    def _draw_radar_chart(self, parent, companies, large=False):
        """Chart 3: 旗舰模型能力雷达图 (同数据分析逻辑)"""
        if not companies:
            return

        fs = (10, 7) if large else (5.5, 4)
        lbl_fs = 10 if large else 6
        ytick_fs = 9 if large else 6
        legend_fs = 9 if large else 6
        marker_sz = 6 if large else 5

        header = tk.Frame(parent, bg=THEME['bg_secondary'])
        header.pack(fill=tk.X, padx=16, pady=(12, 4))
        tk.Label(header, text="旗舰模型能力雷达图", bg=THEME['bg_secondary'],
                 fg=THEME['text'], font=(THEME['font_family'], 12, 'bold')).pack(side=tk.LEFT)

        # Determine dimensions from actual data
        dims = sorted({dim for _, info in companies for dim in info['scores']})
        if not dims:
            dims = EVALUATION_DIMENSIONS

        n = len(dims)
        angles = np.linspace(0, 2 * np.pi, n, endpoint=False).tolist()
        angles += angles[:1]

        fig, ax = plt.subplots(figsize=fs, subplot_kw=dict(polar=True))
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
            values = [info['scores'].get(dim, min_range) for dim in dims]
            values += values[:1]

            color = colors[i % len(colors)]
            ax.plot(angles, values, 'o-', linewidth=2,
                label=f"{company} · {info['model']}",
                    color=color, markersize=marker_sz)
            ax.fill(angles, values, alpha=0.1, color=color)

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(dims, fontsize=lbl_fs, color=THEME['text_secondary'])
        ax.set_ylim(min_range, max_range)

        # Set y-axis ticks to be readable
        tick_count = 5
        step = (max_range - min_range) / tick_count
        ax.set_yticks([min_range + step * i for i in range(tick_count + 1)])
        ax.set_yticklabels([f"{min_range + step * i:.0f}" for i in range(tick_count + 1)],
                           fontsize=ytick_fs, color=THEME['text_muted'])

        ax.set_rlabel_position(30)
        ax.spines['polar'].set_color(THEME['border'])
        ax.grid(color=THEME['border_light'], linestyle='--', linewidth=0.5)

        ax.legend(loc='upper right', bbox_to_anchor=(1.35, 1.15), fontsize=legend_fs,
                  framealpha=0.9, edgecolor=THEME['border'])

        plt.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        plt.close(fig)

    def _draw_ranking_bar_chart(self, parent, sorted_models, matrix, dims, large=False):
        """Chart 4: 各维度排名分布"""
        fs = (11, 8) if large else (5.5, 4)
        ytick_fs = 9 if large else 6
        xlabel_fs = 11 if large else 8
        legend_fs = 10 if large else 7
        name_len = 30 if large else 18

        header = tk.Frame(parent, bg=THEME['bg_secondary'])
        header.pack(fill=tk.X, padx=16, pady=(12, 4))
        tk.Label(header, text="维度排名分布", bg=THEME['bg_secondary'],
                 fg=THEME['text'], font=(THEME['font_family'], 12, 'bold')).pack(side=tk.LEFT)

        fig, ax = plt.subplots(figsize=fs)
        fig.patch.set_facecolor(THEME['bg_secondary'])
        ax.set_facecolor(THEME['bg_secondary'])

        # Average rank across dimensions for top 10 models
        top_n = min(10, len(sorted_models))
        dim_ranks = np.zeros_like(matrix[:top_n])
        for j in range(matrix.shape[1]):
            col = matrix[:top_n, j]
            order = col.argsort()[::-1]
            ranks = np.empty_like(order)
            ranks[order] = np.arange(1, len(col) + 1)
            dim_ranks[:, j] = ranks

        avg_ranks = dim_ranks.mean(axis=1)
        best_ranks = dim_ranks.min(axis=1)
        worst_ranks = dim_ranks.max(axis=1)

        y_pos = np.arange(top_n)
        ax.barh(y_pos, worst_ranks - best_ranks, left=best_ranks, height=0.6,
                color=THEME['accent'], alpha=0.3, label='排名区间')
        ax.scatter(avg_ranks, y_pos, color=THEME['primary'], s=30, zorder=5, label='平均排名')

        ax.set_yticks(y_pos)
        ax.set_yticklabels([sorted_models[i][:name_len] for i in range(top_n)],
                           fontsize=ytick_fs, color=THEME['text_secondary'])
        ax.set_xlabel('排名', fontsize=xlabel_fs, color=THEME['text_secondary'])
        ax.invert_yaxis()
        ax.legend(fontsize=legend_fs, framealpha=0.8)
        ax.grid(axis='x', color=THEME['border_light'], linewidth=0.5)
        plt.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        plt.close(fig)

    def _draw_price_rating_scatter(self, parent, large=False):
        """Chart 3: Price vs Arena Score scatter (value for money)"""
        fs = (11, 8) if large else (5.5, 4)
        dot_size = 60 if large else 30
        lbl_fs = 8 if large else 6
        name_len = 22 if large else 14

        header = tk.Frame(parent, bg=THEME['bg_secondary'])
        header.pack(fill=tk.X, padx=16, pady=(12, 4))
        tk.Label(header, text="性价比分布 (Price vs Score)", bg=THEME['bg_secondary'],
                 fg=THEME['text'], font=(THEME['font_family'], 12, 'bold')).pack(side=tk.LEFT)

        fig, ax = plt.subplots(figsize=fs)
        fig.patch.set_facecolor(THEME['bg_secondary'])
        ax.set_facecolor(THEME['bg_secondary'])

        # Collect data: average output price, rating, license for each model
        models_info = {}
        for item in self._get_current_arena_data():
            model = item.get('model', '')
            if model not in models_info:
                models_info[model] = {
                    'rating': item.get('rating', 0),
                    'outputPrice': item.get('outputPricePerMillion'),
                    'inputPrice': item.get('inputPricePerMillion'),
                    'license': item.get('license', ''),
                    'company': item.get('company', ''),
                }

        x_vals, y_vals, labels, colors_list, sizes = [], [], [], [], []
        for model, info in models_info.items():
            if info['rating'] and info['outputPrice'] is not None:
                x_vals.append(info['outputPrice'])
                y_vals.append(info['rating'])
                labels.append(model)
                is_open = info['license'] and info['license'].lower() not in ('proprietary', '')
                colors_list.append(THEME['chart_colors'][2] if is_open else THEME['chart_colors'][0])
                sizes.append(dot_size)

        if not x_vals:
            ax.text(0.5, 0.5, '暂无价格数据', ha='center', va='center',
                    transform=ax.transAxes, fontsize=12, color=THEME['text_muted'])
        else:
            ax.scatter(x_vals, y_vals, c=colors_list, s=sizes, alpha=0.7, edgecolors='white', linewidth=0.5)

            # Label top models
            top5_ratings = sorted(y_vals, reverse=True)[:5]
            cheapest5 = sorted(x_vals)[:5]
            for i, label in enumerate(labels):
                if y_vals[i] in top5_ratings or x_vals[i] in cheapest5:
                    ax.annotate(label[:name_len], (x_vals[i], y_vals[i]),
                                textcoords="offset points", xytext=(5, 5),
                                fontsize=lbl_fs, color=THEME['text_secondary'])

            # Legend for open vs proprietary
            from matplotlib.lines import Line2D
            legend_elements = [
                Line2D([0], [0], marker='o', color='w', markerfacecolor=THEME['chart_colors'][0],
                       markersize=8, label='Proprietary'),
                Line2D([0], [0], marker='o', color='w', markerfacecolor=THEME['chart_colors'][2],
                       markersize=8, label='Open Source'),
            ]
            ax.legend(handles=legend_elements, fontsize=8 if large else 7, framealpha=0.8,
                      edgecolor=THEME['border'])

        ax.set_xlabel('Output Price ($/M tokens)', fontsize=10 if large else 8,
                      color=THEME['text_secondary'])
        ax.set_ylabel('Arena Score', fontsize=10 if large else 8,
                      color=THEME['text_secondary'])
        ax.set_xscale('log')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color(THEME['border'])
        ax.spines['bottom'].set_color(THEME['border'])
        ax.tick_params(axis='both', colors=THEME['text_muted'])
        ax.grid(color=THEME['border_light'], linestyle='--', linewidth=0.5)

        plt.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        plt.close(fig)

    def _draw_license_comparison(self, parent, dims, large=False):
        """Chart 5: Open Source vs Proprietary score comparison by dimension"""
        fs = (11, 8) if large else (5.5, 4)
        lbl_fs = 10 if large else 7
        ytick_fs = 9 if large else 6
        legend_fs = 10 if large else 7

        header = tk.Frame(parent, bg=THEME['bg_secondary'])
        header.pack(fill=tk.X, padx=16, pady=(12, 4))
        tk.Label(header, text="开源 vs 闭源维度对比", bg=THEME['bg_secondary'],
                 fg=THEME['text'], font=(THEME['font_family'], 12, 'bold')).pack(side=tk.LEFT)

        fig, ax = plt.subplots(figsize=fs)
        fig.patch.set_facecolor(THEME['bg_secondary'])
        ax.set_facecolor(THEME['bg_secondary'])

        # Group models by license type
        open_scores = {dim: [] for dim in dims}
        closed_scores = {dim: [] for dim in dims}
        for item in self._get_current_arena_data():
            dim = item.get('dimension', '')
            score = item.get('score', 0)
            license_type = item.get('license', '')
            if not dim:
                continue
            if license_type and license_type.lower() not in ('proprietary', ''):
                open_scores[dim].append(score)
            else:
                closed_scores[dim].append(score)

        open_avg = [sum(open_scores[d]) / len(open_scores[d]) if open_scores[d] else 0
                    for d in dims]
        closed_avg = [sum(closed_scores[d]) / len(closed_scores[d]) if closed_scores[d] else 0
                      for d in dims]

        x = np.arange(len(dims))
        width = 0.35

        bars1 = ax.bar(x - width / 2, open_avg, width, label='Open Source',
                       color=THEME['chart_colors'][2], alpha=0.85)
        bars2 = ax.bar(x + width / 2, closed_avg, width, label='Proprietary',
                       color=THEME['chart_colors'][0], alpha=0.85)

        ax.set_xticks(x)
        ax.set_xticklabels(dims, rotation=45, ha='right',
                           fontsize=lbl_fs, color=THEME['text_secondary'])
        ax.set_ylabel('平均得分', fontsize=9 if large else 8, color=THEME['text_secondary'])
        ax.legend(fontsize=legend_fs, framealpha=0.8, edgecolor=THEME['border'])
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color(THEME['border'])
        ax.spines['bottom'].set_color(THEME['border'])
        ax.tick_params(axis='y', colors=THEME['text_muted'])
        ax.grid(axis='y', color=THEME['border_light'], linestyle='--', linewidth=0.5)
        plt.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        plt.close(fig)

    def _draw_votes_chart(self, parent, large=False):
        """Chart 6: Top models by vote count"""
        fs = (11, 8) if large else (5.5, 4)
        ytick_fs = 9 if large else 6
        name_len = 30 if large else 18

        header = tk.Frame(parent, bg=THEME['bg_secondary'])
        header.pack(fill=tk.X, padx=16, pady=(12, 4))
        tk.Label(header, text="投票热度排行 (Top 15)", bg=THEME['bg_secondary'],
                 fg=THEME['text'], font=(THEME['font_family'], 12, 'bold')).pack(side=tk.LEFT)

        fig, ax = plt.subplots(figsize=fs)
        fig.patch.set_facecolor(THEME['bg_secondary'])
        ax.set_facecolor(THEME['bg_secondary'])

        # Collect votes per model
        model_votes = {}
        for item in self._get_current_arena_data():
            model = item.get('model', '')
            votes = item.get('votes', 0)
            if model and votes:
                model_votes[model] = max(model_votes.get(model, 0), votes)

        sorted_by_votes = sorted(model_votes.items(), key=lambda x: x[1], reverse=True)[:15]
        if not sorted_by_votes:
            ax.text(0.5, 0.5, '暂无投票数据', ha='center', va='center',
                    transform=ax.transAxes, fontsize=12, color=THEME['text_muted'])
        else:
            models = [m[:name_len] for m, _ in sorted_by_votes]
            votes = [v for _, v in sorted_by_votes]
            colors = [THEME['chart_colors'][i % len(THEME['chart_colors'])] for i in range(len(models))]
            ax.barh(range(len(models)), votes, color=colors, alpha=0.85)
            ax.set_yticks(range(len(models)))
            ax.set_yticklabels(models, fontsize=ytick_fs, color=THEME['text_secondary'])
            ax.set_xlabel('Votes', fontsize=9 if large else 8, color=THEME['text_secondary'])
            ax.invert_yaxis()
            for i, v in enumerate(votes):
                ax.text(v + max(votes) * 0.01, i, f'{v:,}', va='center',
                        fontsize=ytick_fs, color=THEME['text_secondary'])
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            ax.spines['left'].set_color(THEME['border'])
            ax.spines['bottom'].set_color(THEME['border'])
            ax.tick_params(axis='x', colors=THEME['text_muted'])
            ax.grid(axis='x', color=THEME['border_light'], linestyle='--', linewidth=0.5)

        plt.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=parent)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        plt.close(fig)

    def _get_model_dimension_scores(self):
        model_dimensions = {}
        for item in self._get_current_arena_data():
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
        """点击刷新：主动抓取最新数据。

        - 抓取成功 → 更新并写库，Toast 成功提示。
        - 抓取失败 → 保留当前本地分析不变，Toast 错误提示。
        """
        if self._is_loading:
            return
        self._is_loading = True
        if hasattr(self, '_toast'):
            self._toast.show('正在抓取最新榜单数据…', type_='info', duration=8000)

        def _crawl():
            crawled = None
            err = None
            try:
                crawled = get_latest_models(minimum_rows=self._MIN_CRAWL_ROWS,
                                            fallback_to_simulated=False)
            except Exception as e:
                err = e
                crawled = None

            def _apply():
                self._is_loading = False
                if crawled and len(crawled) >= self._MIN_CRAWL_ROWS:
                    self._on_data_loaded(crawled, origin='crawler', persist=True)
                    if hasattr(self, '_toast'):
                        self._toast.show(f'刷新成功 · 已更新 {len(crawled)} 条数据',
                                         type_='success', duration=3000)
                else:
                    # 失败：保留本地数据分析不变
                    if hasattr(self, '_toast'):
                        self._toast.show('抓取失败，已保留本地数据分析',
                                         type_='error', duration=3500)
            self.root.after(0, _apply)

        threading.Thread(target=_crawl, daemon=True).start()

    def _upload_file(self):
        try:
            file_path = self.file_handler.upload_file(self.root)
            if file_path:
                messagebox.showinfo("成功", f"文件已上传: {file_path}")
        except Exception as e:
            messagebox.showerror("错误", f"文件上传失败: {e}")

    def _export_data(self):
        # 导出当前选中领域的数据；为空则提示
        export_data = self._get_current_arena_data() or self.raw_data
        if not export_data:
            if hasattr(self, '_toast'):
                self._toast.show('暂无可导出的数据', type_='warning')
            return
        try:
            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV文件", "*.csv"), ("JSON文件", "*.json")]
            )
            if file_path:
                if file_path.endswith('.json'):
                    self.file_handler.export_to_json(export_data, file_path)
                else:
                    self.file_handler.export_to_csv(export_data, file_path)
                if hasattr(self, '_toast'):
                    self._toast.show(f'已导出 {len(export_data)} 条数据', type_='success')
        except Exception as e:
            if hasattr(self, '_toast'):
                self._toast.show(f'导出失败：{e}', type_='error')


def main():
    root = tk.Tk()
    app = ModernApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
