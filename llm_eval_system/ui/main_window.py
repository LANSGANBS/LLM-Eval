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
        self.current_tab = 'ranking'
        self.content_container = None
        self._global_rank_map = {}
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
                padding=(10, 7, 34, 7),
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
                fieldbackground=THEME['bg_tertiary'],
                background=THEME['bg_tertiary'],
                bordercolor=THEME['border'],
                lightcolor=THEME['border'],
                darkcolor=THEME['border'],
                relief='flat',
                borderwidth=0,
                padding=(6, 7))
        style.map('Modern.TEntry',
              bordercolor=[('focus', THEME['border_focus'])],
              lightcolor=[('focus', THEME['border_focus'])],
              darkcolor=[('focus', THEME['border_focus'])])

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
                          highlightthickness=1, width=260)
        self.sidebar_outer.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 20))
        self.sidebar_outer.pack_propagate(False)

        # Canvas + scrollbar for sidebar scrolling
        self._sidebar_canvas = tk.Canvas(self.sidebar_outer, bg=THEME['bg_secondary'],
                                          highlightthickness=0, width=280)
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

    def _widget_contains_point(self, widget, x_root, y_root):
        if not widget or not widget.winfo_exists():
            return False
        left = widget.winfo_rootx()
        top = widget.winfo_rooty()
        right = left + widget.winfo_width()
        bottom = top + widget.winfo_height()
        return left <= x_root <= right and top <= y_root <= bottom

    def _install_scroll_handler(self):
        """Install a single root-level scroll handler that dispatches
        based on cursor position.  Replaces the old dual-bind_all approach."""
        for seq in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
            self.root.bind(seq, self._root_mousewheel, add='+')

    def _root_mousewheel(self, event):
        """Single scroll handler: check cursor position, scroll the
        correct canvas, bubble to outer canvas on boundary."""
        x = self.root.winfo_pointerx()
        y = self.root.winfo_pointery()
        units = self._delta_to_units(event)
        if units == 0:
            return None

        # If cursor is over a Treeview, let it scroll itself
        hovered = self.root.winfo_containing(x, y)
        if hovered is not None:
            cls = hovered.winfo_class()
            if cls == 'Treeview':
                return self._try_scroll_treeview(hovered, units)
            if cls in ('TCombobox', 'Listbox', 'Text'):
                return None

        # Try sidebar first, then content (bubble on boundary)
        if self._widget_contains_point(self.sidebar_outer, x, y):
            if self._try_scroll_canvas(self._sidebar_canvas, units):
                return 'break'
            return None

        if self._widget_contains_point(self.content_outer, x, y):
            if self._try_scroll_canvas(self._content_canvas, units):
                return 'break'
            return None

        return None

    def _delta_to_units(self, event):
        """Convert wheel event to scroll units (macOS trackpad aware)."""
        delta = getattr(event, 'delta', 0)
        if delta == 0 and getattr(event, 'num', None) in (4, 5):
            return -3 if event.num == 4 else 3
        if delta == 0:
            return 0
        # macOS trackpad sends small values (1, -3, etc.)
        if abs(delta) < 120:
            return int(-delta * 0.5) or (-1 if delta > 0 else 1)
        return int(-delta / 120) * 3

    def _try_scroll_canvas(self, canvas, units):
        """Try scrolling a canvas. Return True if scrolled (not at boundary)."""
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
        try:
            start, end = tree.yview()
        except Exception:
            return None
        if start <= 0.0 and end >= 1.0:
            return None
        if units < 0 and start <= 0.0:
            return None
        if units > 0 and end >= 1.0:
            return None
        tree.yview_scroll(units, 'units')
        return 'break'

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

        self._show_ranking()

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
        finally:
            self._render_pending = False

    # ==================== Data loading ====================

    def _load_data_async(self):
        """Load data: DB first (instant), then crawl in background for fresh data."""
        # Step 1: Try loading from local DB (instant)
        try:
            db_data = self.db.load_all_data()
            if db_data and len(db_data) >= 50:
                self.root.after(0, lambda: self._on_data_loaded(db_data, origin='database'))
                # Step 2: Crawl fresh data in background, update when ready
                def _refresh():
                    try:
                        crawled = get_latest_models(minimum_rows=100, fallback_to_simulated=False)
                        if len(crawled) >= 100:
                            self.root.after(0, lambda: self._on_data_loaded(crawled, origin='crawler'))
                    except Exception:
                        pass
                threading.Thread(target=_refresh, daemon=True).start()
                return
        except Exception:
            pass

        # Step 3: No DB data — crawl
        def _crawl():
            try:
                crawled = get_latest_models(minimum_rows=100, fallback_to_simulated=False)
                if len(crawled) >= 100:
                    self.root.after(0, lambda: self._on_data_loaded(crawled, origin='crawler'))
                    return
            except Exception:
                pass
            # Step 4: Crawl failed — use simulated
            fallback = get_simulated_data()
            self.root.after(0, lambda: self._on_data_loaded(fallback, origin='simulated'))

        threading.Thread(target=_crawl, daemon=True).start()

    def _on_data_loaded(self, data, origin='simulated'):
        if not data:
            data = get_simulated_data()
            origin = 'simulated'

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
            # Clear old data before saving new
            self.db.clear_all_data()
            for item in data:
                model_name = item.get('model', '')
                category = item.get('category', 'unknown')
                dimension = item.get('dimension', '')
                score = item.get('score', 0)
                source = item.get('source', '')

                # Store extra fields in metadata JSON
                metadata = {}
                for key in ('company', 'rating', 'votes', 'license', 'modelUrl',
                            'inputPricePerMillion', 'outputPricePerMillion',
                            'contextLength'):
                    if item.get(key) is not None:
                        metadata[key] = item[key]
                if not metadata:
                    metadata = None

                model_id = self.db.insert_or_update_model(
                    model_name, category, source=source, metadata=metadata)
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
        self._stat_labels['top_model'].config(text=top_model, wraplength=100, justify='left')
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

        filter_row = tk.Frame(controls, bg=THEME['bg_secondary'])
        filter_row.pack(fill=tk.X, pady=(14, 0))

        search_icon_img = get_icon('search', size=16, color=THEME['text_muted'])
        self._search_photo = ImageTk.PhotoImage(search_icon_img)

        search_container = tk.Frame(filter_row, bg=THEME['bg_secondary'],
                                    highlightbackground=THEME['border'],
                                    highlightthickness=1)
        search_container.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 12))

        tk.Label(search_container, image=self._search_photo,
                 bg=THEME['bg_secondary']).pack(side=tk.LEFT, padx=(12, 4))

        self.search_var = tk.StringVar(value='搜索模型...')
        search_entry = ttk.Entry(search_container, textvariable=self.search_var,
                     style='Modern.TEntry', font=(THEME['font_family'], 11))
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=8, pady=10)
        search_entry.bind('<FocusIn>', lambda e: search_entry.delete(0, tk.END)
                          if search_entry.get() == '搜索模型...' else None)
        search_entry.bind('<FocusOut>',
                          lambda e: self.search_var.set('搜索模型...')
                          if not search_entry.get().strip() else None)

        companies = ['全部公司'] + sorted({
            item.get('company', '') for item in self.raw_data
            if item.get('company') and item.get('company') != '未知'
        })
        categories = ['全部类别', '国内', '国际']
        sort_rules = [
            '综合分数：高到低',
            '综合分数：低到高',
            'Arena Score：高到低',
            'Votes：多到少',
            '代码生成：高到低',
            '模型名称：A-Z',
            '公司名称：A-Z',
        ]
        top_n_values = ['全部', '10', '25', '50', '100']

        self.company_filter_var = tk.StringVar(value='全部公司')
        self.category_filter_var = tk.StringVar(value='全部类别')
        self.sort_var = tk.StringVar(value='综合分数：高到低')
        self.top_n_var = tk.StringVar(value='全部')

        def _add_filter(label_text, variable, values, width):
            container = tk.Frame(filter_row, bg=THEME['bg_secondary'])
            container.pack(side=tk.LEFT, padx=(0, 10))
            tk.Label(container, text=label_text, bg=THEME['bg_secondary'],
                     fg=THEME['text_muted'], font=(THEME['font_family'], 10)).pack(anchor='w')
            combo = ttk.Combobox(container, textvariable=variable, values=values,
                                 state='readonly', width=width, style='Modern.TCombobox')
            combo.pack(pady=(6, 0))
            return combo

        _add_filter('类别', self.category_filter_var, categories, 8)
        _add_filter('公司', self.company_filter_var, companies, 12)
        _add_filter('排序', self.sort_var, sort_rules, 14)
        _add_filter('显示数量', self.top_n_var, top_n_values, 6)

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

        columns = ('rank', 'model', 'company_license', 'score', 'votes', 'price', 'context')
        self.ranking_tree = ttk.Treeview(table_frame, columns=columns,
                                          show='headings', style='Custom.Treeview')

        self.ranking_tree.heading('rank', text='排名')
        self.ranking_tree.heading('model', text='模型')
        self.ranking_tree.heading('company_license', text='公司 · License')
        self.ranking_tree.heading('score', text='Score')
        self.ranking_tree.heading('votes', text='Votes')
        self.ranking_tree.heading('price', text='Price $/M')
        self.ranking_tree.heading('context', text='Context')

        self.ranking_tree.column('rank', width=50, anchor='center')
        self.ranking_tree.column('model', width=180, anchor='w')
        self.ranking_tree.column('company_license', width=180, anchor='w')
        self.ranking_tree.column('score', width=70, anchor='center')
        self.ranking_tree.column('votes', width=70, anchor='center')
        self.ranking_tree.column('price', width=100, anchor='center')
        self.ranking_tree.column('context', width=80, anchor='center')

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
        model_data = self._get_model_dimension_scores()
        all_avgs = [sum(info['scores'].values()) / len(info['scores'])
                    for info in model_data.values() if info['scores']]

        # Extract extra fields per model from raw_data
        model_extras = {}
        for item in self.raw_data:
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

        rows = []
        for model, info in model_data.items():
            dimension_scores = info['scores']
            if not dimension_scores:
                continue

            avg = sum(dimension_scores.values()) / len(dimension_scores)
            extras = model_extras.get(model, {})
            category = extras.get('category', '')
            company = info['company']
            rows.append({
                'rank': self._global_rank_map.get(model, 0),
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
                'dimensions': len(dimension_scores),
                'code_score': dimension_scores.get('代码生成', 0),
                'dimension_scores': dimension_scores,
            })

        search = self.search_var.get().strip() if hasattr(self, 'search_var') else ''
        if search and search != '搜索模型...':
            rows = [row for row in rows if search.lower() in row['model'].lower()]

        company_filter = self.company_filter_var.get() if hasattr(self, 'company_filter_var') else '全部公司'
        if company_filter and company_filter != '全部公司':
            rows = [row for row in rows if row['company'] == company_filter]

        category_filter = self.category_filter_var.get() if hasattr(self, 'category_filter_var') else '全部类别'
        if category_filter == '国内':
            rows = [row for row in rows if row['category'] == 'domestic']
        elif category_filter == '国际':
            rows = [row for row in rows if row['category'] == 'international']

        sort_rule = self.sort_var.get() if hasattr(self, 'sort_var') else '综合分数：高到低'
        if sort_rule == '综合分数：低到高':
            rows.sort(key=lambda row: row['avg'])
        elif sort_rule == 'Arena Score：高到低':
            rows.sort(key=lambda row: row.get('rating', 0) or 0, reverse=True)
        elif sort_rule == 'Votes：多到少':
            rows.sort(key=lambda row: row.get('votes', 0) or 0, reverse=True)
        elif sort_rule == '代码生成：高到低':
            rows.sort(key=lambda row: row['code_score'], reverse=True)
        elif sort_rule == '模型名称：A-Z':
            rows.sort(key=lambda row: row['model'].lower())
        elif sort_rule == '公司名称：A-Z':
            rows.sort(key=lambda row: (row['company'].lower(), -row['avg']))
        else:
            rows.sort(key=lambda row: row['avg'], reverse=True)

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
            score_str = f"{row['rating']:.0f}" if row.get('rating') else f"{row['scaled']:.2f}"
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
            item_id = self.ranking_tree.insert('', tk.END,
                                               values=(f"#{row['rank']}", row['model'], company_license,
                                                       score_str, votes_str, price_str, context_str))
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

        url_text = row.get('modelUrl', '') or ''
        if url_text:
            _info_item(self._detail_right, 'Link', url_text, 4, fg=THEME['primary'])

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

        # Model A column
        col_a = tk.Frame(selector_container, bg=THEME['bg_secondary'])
        col_a.grid(row=0, column=0, sticky='ew', padx=(0, 6))
        tk.Label(col_a, text="模型 A", bg=THEME['bg_secondary'],
                 fg=THEME['text_muted'], font=(THEME['font_family'], 10)).pack(anchor='w', pady=(0, 4))
        cb1 = ttk.Combobox(col_a, textvariable=self.model1_var,
                   values=sorted_models, state='readonly', width=30,
                   style='Modern.TCombobox')
        cb1.pack(fill=tk.X)
        if sorted_models:
            cb1.current(0)

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
        cb2 = ttk.Combobox(col_b, textvariable=self.model2_var,
                   values=sorted_models, state='readonly', width=30,
                   style='Modern.TCombobox')
        cb2.pack(fill=tk.X)
        if len(sorted_models) > 1:
            cb2.current(1)

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

        dimension_grid = tk.Frame(inner, bg=THEME['bg_secondary'])
        dimension_grid.pack(fill=tk.X, pady=(10, 0))
        self._compare_dim_vars = {}
        for index, dimension in enumerate(EVALUATION_DIMENSIONS):
            var = tk.BooleanVar(value=(dimension == '代码生成'))
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

    def _do_compare(self):
        m1 = self.model1_var.get()
        m2 = self.model2_var.get()
        selected_dimensions = self._get_selected_compare_dimensions()

        if not m1 or not m2:
            messagebox.showwarning("提示", "请选择两个模型")
            return
        if m1 == m2:
            messagebox.showwarning("提示", "请选择不同的模型进行对比")
            return
        if not selected_dimensions:
            messagebox.showwarning("提示", "请至少选择一个对比维度")
            return

        if self._compare_rendering or not hasattr(self, 'compare_result') or not self.compare_result.winfo_exists():
            return

        self._compare_rendering = True

        try:
            for widget in self.compare_result.winfo_children():
                widget.destroy()

            m1_data = {d['dimension']: d['score'] for d in self.raw_data
                       if d['model'] == m1 and d['dimension'] in selected_dimensions}
            m2_data = {d['dimension']: d['score'] for d in self.raw_data
                       if d['model'] == m2 and d['dimension'] in selected_dimensions}

            if not m1_data or not m2_data:
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
        if hasattr(self, 'compare_result') and self.compare_result.winfo_exists() and self.model1_var.get() and self.model2_var.get():
            self._do_compare()

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
        if not self.raw_data:
            return

        companies = self._get_top_company_flagships(limit=5)

        # Title card
        title_card = self._create_card(self.content_container, padding=(20, 16))
        title_card.pack(fill=tk.X, pady=(0, 16))
        title_frame = title_card.content

        icon_img = get_icon('chart_radar', size=20, color=THEME['primary'])
        self._radar_tab_photo = ImageTk.PhotoImage(icon_img)
        tk.Label(title_frame, image=self._radar_tab_photo,
                 bg=THEME['bg_secondary']).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(title_frame, text="旗舰模型能力雷达图", bg=THEME['bg_secondary'],
                 fg=THEME['text'], font=(THEME['font_family'], 14, 'bold')).pack(side=tk.LEFT, padx=(0, 16))
        tk.Label(title_frame, text="各公司最高分模型的八维度能力对比",
                 bg=THEME['bg_secondary'], fg=THEME['text_muted'],
                 font=(THEME['font_family'], 10)).pack(side=tk.LEFT)

        # Two-column layout: radar left, model cards right
        content_row = tk.Frame(self.content_container, bg=THEME['bg'])
        content_row.pack(fill=tk.BOTH, expand=True)
        content_row.grid_columnconfigure(0, weight=3)
        content_row.grid_columnconfigure(1, weight=2)

        # Left: radar chart
        chart_card = self._create_card(content_row, padding=(0, 0), min_height=520)
        chart_card.grid(row=0, column=0, sticky='nsew', padx=(0, 12))
        self._draw_radar_chart(chart_card.content, companies, large=True)

        # Right: model info cards
        info_card = self._create_card(content_row, padding=(16, 16), min_height=520)
        info_card.grid(row=0, column=1, sticky='nsew')
        info_frame = info_card.content

        tk.Label(info_frame, text="旗舰模型一览", bg=THEME['bg_secondary'],
                 fg=THEME['text'], font=(THEME['font_family'], 12, 'bold')).pack(anchor='w', pady=(0, 12))

        colors = THEME['chart_colors']
        for i, (company, info) in enumerate(companies):
            color = colors[i % len(colors)]
            model = info['model']
            scores = info['scores']
            avg = sum(scores.values()) / len(scores) if scores else 0

            # Company + model row
            row_frame = tk.Frame(info_frame, bg=THEME['bg_secondary'])
            row_frame.pack(fill=tk.X, pady=(0, 10))

            # Color indicator dot
            dot_canvas = tk.Canvas(row_frame, width=10, height=10,
                                   bg=THEME['bg_secondary'], highlightthickness=0)
            dot_canvas.pack(side=tk.LEFT, padx=(0, 8), pady=(4, 0))
            dot_canvas.create_oval(1, 1, 9, 9, fill=color, outline='')

            text_col = tk.Frame(row_frame, bg=THEME['bg_secondary'])
            text_col.pack(side=tk.LEFT, fill=tk.X, expand=True)

            company_label = f"{company} · {model}" if company != model else model
            tk.Label(text_col, text=company_label, bg=THEME['bg_secondary'],
                     fg=THEME['text'], font=(THEME['font_family'], 10, 'bold'),
                     anchor='w', wraplength=250, justify='left').pack(anchor='w')
            tk.Label(text_col, text=f"均分 {avg:.1f}  ·  {len(scores)} 维度",
                     bg=THEME['bg_secondary'], fg=THEME['text_muted'],
                     font=(THEME['font_family'], 9), anchor='w').pack(anchor='w')

            # Mini dimension bar
            bar_frame = tk.Frame(text_col, bg=THEME['bg_secondary'])
            bar_frame.pack(fill=tk.X, pady=(4, 0))

            ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            for dim_name, dim_score in ordered[:4]:
                pct = min(100, max(0, dim_score))
                bar_container = tk.Frame(bar_frame, bg=THEME['border_light'], height=6, width=40)
                bar_container.pack(side=tk.LEFT, padx=(0, 6))
                bar_container.pack_propagate(False)
                fill_width = max(1, int(40 * pct / 100))
                bar_fill = tk.Frame(bar_container, bg=color, width=fill_width, height=6)
                bar_fill.place(x=0, y=0, relheight=1.0)

            # Separator (except last)
            if i < len(companies) - 1:
                sep = tk.Frame(info_frame, bg=THEME['border_light'], height=1)
                sep.pack(fill=tk.X, pady=(0, 10))

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

        # Build score matrix once
        matrix = np.zeros((len(sorted_models), len(EVALUATION_DIMENSIONS)))
        for i, model in enumerate(sorted_models):
            for j, dim in enumerate(EVALUATION_DIMENSIONS):
                for d in self.raw_data:
                    if d.get('model') == model and d.get('dimension') == dim:
                        matrix[i, j] = d.get('score', 0)
                        break

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
                1: lambda p: self._draw_heatmap_chart(p, sorted_models, matrix, large=True),
                2: lambda p: self._draw_confidence_chart(p, sorted_models, avg_scores, large=True),
                3: lambda p: self._draw_price_rating_scatter(p, large=True),
                4: lambda p: self._draw_ranking_bar_chart(p, sorted_models, matrix, large=True),
                5: lambda p: self._draw_license_comparison(p, large=True),
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

            # Chart 1: 能力热力图
            c1 = self._create_card(grid_frame, padding=(0, 0), min_height=340)
            c1.grid(row=0, column=0, sticky='nsew', padx=(0, 8), pady=(0, 8))
            self._draw_heatmap_chart(c1.content, sorted_models, matrix)

            # Chart 2: 置信区间图
            c2 = self._create_card(grid_frame, padding=(0, 0), min_height=340)
            c2.grid(row=0, column=1, sticky='nsew', padx=(8, 0), pady=(0, 8))
            self._draw_confidence_chart(c2.content, sorted_models, avg_scores)

            # Chart 3: 价格-评分散点图
            c3 = self._create_card(grid_frame, padding=(0, 0), min_height=340)
            c3.grid(row=1, column=0, sticky='nsew', padx=(0, 8), pady=(8, 0))
            self._draw_price_rating_scatter(c3.content)

            # Chart 4: 排名分布图
            c4 = self._create_card(grid_frame, padding=(0, 0), min_height=340)
            c4.grid(row=1, column=1, sticky='nsew', padx=(8, 0), pady=(8, 0))
            self._draw_ranking_bar_chart(c4.content, sorted_models, matrix)

            # Chart 5: 开源 vs 闭源对比
            c5 = self._create_card(grid_frame, padding=(0, 0), min_height=340)
            c5.grid(row=2, column=0, sticky='nsew', padx=(0, 8), pady=(8, 0))
            self._draw_license_comparison(c5.content)

            # Chart 6: 投票热度图
            c6 = self._create_card(grid_frame, padding=(0, 0), min_height=340)
            c6.grid(row=2, column=1, sticky='nsew', padx=(8, 0), pady=(8, 0))
            self._draw_votes_chart(c6.content)

            # Click to zoom in
            for idx, card in enumerate([c1, c2, c3, c4, c5, c6], start=1):
                card.frame.bind('<Button-1>', lambda e, i=idx: self._heatmap_zoom_in(i))
                card.canvas.bind('<Button-1>', lambda e, i=idx: self._heatmap_zoom_in(i))
                card.content.bind('<Button-1>', lambda e, i=idx: self._heatmap_zoom_in(i))
                self._bind_click_recursive(card.content, lambda e, i=idx: self._heatmap_zoom_in(i))
                # Show hand cursor on hover
                card.frame.bind('<Enter>', lambda e: card.frame.configure(cursor='hand2'))
                card.frame.bind('<Leave>', lambda e: card.frame.configure(cursor=''))

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

    def _draw_heatmap_chart(self, parent, sorted_models, matrix, large=False):
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
        ax.set_xticks(range(len(EVALUATION_DIMENSIONS)))
        ax.set_xticklabels(EVALUATION_DIMENSIONS, rotation=45, ha='right', fontsize=lbl_fs, color=THEME['text_secondary'])
        ax.set_yticks(range(len(sorted_models)))
        ax.set_yticklabels([m[:name_len] for m in sorted_models], fontsize=ytick_fs, color=THEME['text_secondary'])
        for i in range(len(sorted_models)):
            for j in range(len(EVALUATION_DIMENSIONS)):
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
            dims = [d.get('score', 0) for d in self.raw_data if d.get('model') == m]
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

        n = len(EVALUATION_DIMENSIONS)
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
            values = [info['scores'].get(dim, min_range) for dim in EVALUATION_DIMENSIONS]
            values += values[:1]

            color = colors[i % len(colors)]
            ax.plot(angles, values, 'o-', linewidth=2,
                label=f"{company} · {info['model']}",
                    color=color, markersize=marker_sz)
            ax.fill(angles, values, alpha=0.1, color=color)

        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(EVALUATION_DIMENSIONS, fontsize=lbl_fs, color=THEME['text_secondary'])
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

    def _draw_ranking_bar_chart(self, parent, sorted_models, matrix, large=False):
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
        for j in range(len(EVALUATION_DIMENSIONS)):
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
        for item in self.raw_data:
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

    def _draw_license_comparison(self, parent, large=False):
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
        open_scores = {dim: [] for dim in EVALUATION_DIMENSIONS}
        closed_scores = {dim: [] for dim in EVALUATION_DIMENSIONS}
        for item in self.raw_data:
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
                    for d in EVALUATION_DIMENSIONS]
        closed_avg = [sum(closed_scores[d]) / len(closed_scores[d]) if closed_scores[d] else 0
                      for d in EVALUATION_DIMENSIONS]

        x = np.arange(len(EVALUATION_DIMENSIONS))
        width = 0.35

        bars1 = ax.bar(x - width / 2, open_avg, width, label='Open Source',
                       color=THEME['chart_colors'][2], alpha=0.85)
        bars2 = ax.bar(x + width / 2, closed_avg, width, label='Proprietary',
                       color=THEME['chart_colors'][0], alpha=0.85)

        ax.set_xticks(x)
        ax.set_xticklabels(EVALUATION_DIMENSIONS, rotation=45, ha='right',
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
        for item in self.raw_data:
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
        """Force refresh: crawl fresh data from the web."""
        def _crawl():
            try:
                crawled = get_latest_models(minimum_rows=100, fallback_to_simulated=False)
                if len(crawled) >= 100:
                    self.root.after(0, lambda: self._on_data_loaded(crawled, origin='crawler'))
                    return
            except Exception:
                pass
            fallback = get_simulated_data()
            self.root.after(0, lambda: self._on_data_loaded(fallback, origin='simulated'))
        threading.Thread(target=_crawl, daemon=True).start()

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
