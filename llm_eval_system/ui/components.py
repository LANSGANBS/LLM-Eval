"""
UI组件库 - 浅色亚克力风格可复用组件
统一圆角、统一按钮尺寸、柔和描边 + 阴影感模拟亚克力质感。
"""
import tkinter as tk
from tkinter import ttk
from PIL import ImageTk

from llm_eval_system.core.theme import THEME
from llm_eval_system.ui.icons import get_icon


def _rounded_points(x1, y1, x2, y2, r):
    """生成圆角矩形的多边形点（用于 canvas smooth polygon）。"""
    return [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]


def draw_rounded_rect(canvas, x1, y1, x2, y2, r, **kwargs):
    """在 canvas 上绘制圆角矩形。"""
    return canvas.create_polygon(_rounded_points(x1, y1, x2, y2, r),
                                 smooth=True, **kwargs)


class RoundedCard:
    """亚克力圆角卡片容器。

    用 canvas 绘制：阴影层（柔和下偏移）+ 亚克力面 + 柔和描边。
    对外暴露 .frame / .canvas / .content，保持与旧版兼容。
    """

    SHADOW_OFFSET = 3  # 阴影向下偏移量

    def __init__(self, parent, bg=None, border_color=None, radius=None,
                 padding=None, surface_bg=None, min_height=None, shadow=True):
        self.parent = parent
        self.bg = bg or THEME['bg_secondary']
        self.border_color = border_color or THEME['acrylic_border']
        self.radius = radius if radius is not None else THEME['radius_large']
        self.surface_bg = surface_bg or (parent.cget('bg') if 'bg' in parent.keys() else THEME['bg'])
        self.min_height = min_height
        self.shadow = shadow

        if padding is None:
            padding = THEME['card_padding']
        if isinstance(padding, tuple):
            self.padx, self.pady = padding[0], padding[1]
        else:
            self.padx = self.pady = padding

        # 额外预留阴影空间
        self._pad_extra = self.SHADOW_OFFSET + 1 if shadow else 1

        self.frame = tk.Frame(self.parent, bg=self.surface_bg, highlightthickness=0, bd=0)
        self.canvas = tk.Canvas(self.frame, bg=self.surface_bg, highlightthickness=0, bd=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.content = tk.Frame(self.canvas, bg=self.bg, highlightthickness=0, bd=0)
        self._content_window = self.canvas.create_window(
            self.padx + 1, self.pady + 1, anchor='nw', window=self.content
        )

        self.canvas.bind('<Configure>', self._on_configure)
        self.content.bind('<Configure>', self._sync_size, add='+')

    def _sync_size(self, _event=None):
        req_height = self.content.winfo_reqheight() + self.pady * 2 + self._pad_extra
        if self.min_height is not None:
            req_height = max(req_height, self.min_height)
        self.canvas.configure(height=req_height)
        if self.canvas.winfo_width() <= 1:
            self.canvas.configure(width=self.content.winfo_reqwidth() + self.padx * 2 + self._pad_extra)
        self._redraw()

    def _on_configure(self, _event=None):
        self._redraw()

    def _redraw(self):
        width = self.canvas.winfo_width()
        if width <= 1:
            width = self.content.winfo_reqwidth() + self.padx * 2 + self._pad_extra
        height = max(self.canvas.winfo_height(),
                     self.content.winfo_reqheight() + self.pady * 2 + self._pad_extra)
        if self.min_height is not None:
            height = max(height, self.min_height)

        self.canvas.delete('card-bg')
        so = self.SHADOW_OFFSET

        # 柔和阴影（多层叠出渐隐感）
        if self.shadow:
            for i, sh in enumerate((THEME['shadow'], THEME['border_light'])):
                off = so - i
                draw_rounded_rect(
                    self.canvas, 3 + off, 3 + off, width - 3 + off, height - 3 + off,
                    self.radius, fill=sh, outline='', tags='card-bg')

        # 亚克力面
        draw_rounded_rect(
            self.canvas, 2, 2, width - 3 - so, height - 3 - so,
            self.radius, fill=self.bg, outline=self.border_color, width=1, tags='card-bg')

        self.canvas.tag_lower('card-bg')
        inner_w = max(width - self.padx * 2 - so - 2, 1)
        self.canvas.itemconfigure(self._content_window, width=inner_w)
        self.canvas.coords(self._content_window, self.padx + 1, self.pady + 1)

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def grid(self, **kwargs):
        self.frame.grid(**kwargs)

    def place(self, **kwargs):
        self.frame.place(**kwargs)


class StyledButton:
    """统一样式按钮 - 全局统一高度与圆角，整个区域可点击。"""

    def __init__(self, parent, text, command, color_key='primary',
                 text_color=None, width=None, height=None,
                 font_size=11, bold=True, icon_name=None, size='md'):
        self.parent = parent
        self.text = text
        self.command = command
        self.color_key = color_key
        self.size = size
        self.font_size = font_size
        self.bold = bold
        self.icon_name = icon_name

        # 统一高度（除非显式指定）
        if height is not None:
            self.height = height
        else:
            self.height = THEME['btn_height_sm'] if size == 'sm' else THEME['btn_height']
        self.width = width

        self._get_colors()
        # text color 自动：彩色按钮用白字，secondary 用深灰字
        if text_color is not None:
            self.text_color = text_color
        elif color_key in ('secondary', 'ghost'):
            self.text_color = THEME['text_secondary']
        else:
            self.text_color = THEME['text_white']

        self._build()

    def _get_colors(self):
        colors = {
            'primary': (THEME['primary'], THEME['primary_hover'], THEME['primary_active']),
            'success': (THEME['success'], THEME['success_hover'], THEME['primary_active']),
            'warning': (THEME['warning'], THEME['warning_hover'], THEME['primary_active']),
            'danger': (THEME['danger'], THEME['danger_hover'], THEME['primary_active']),
            'info': (THEME['info'], THEME['info_hover'], THEME['primary_active']),
            'secondary': (THEME['bg_tertiary'], THEME['bg_hover'], THEME['bg_active']),
            'ghost': (THEME['bg_secondary'], THEME['bg_hover'], THEME['bg_active']),
        }
        self.normal_color, self.hover_color, self.active_color = colors.get(
            self.color_key, colors['primary'])
        # secondary/ghost 需要描边
        self.outline = THEME['acrylic_border'] if self.color_key in ('secondary', 'ghost') else ''

    def _build(self):
        btn_height = self.height
        padding_x = THEME['btn_padding_x_sm'] if self.size == 'sm' else THEME['btn_padding_x']
        self._surface_bg = self.parent.cget('bg') if 'bg' in self.parent.keys() else THEME['bg']

        font_weight = 'bold' if self.bold else 'normal'
        font = (THEME['font_family'], self.font_size, font_weight)

        temp = tk.Label(text=self.text, font=font)
        text_width = temp.winfo_reqwidth()
        temp.destroy()

        icon_space = 22 if self.icon_name else 0
        total_width = self.width or (text_width + padding_x * 2 + icon_space + (6 if self.icon_name else 0))

        self.frame = tk.Frame(self.parent, bg=self._surface_bg, highlightthickness=0, bd=0, cursor='arrow')
        self.canvas = tk.Canvas(self.frame, width=total_width, height=btn_height,
                                bg=self._surface_bg, highlightthickness=0, bd=0,
                                cursor='arrow', takefocus=1)
        self.canvas.pack()

        self._total_width = total_width
        self._btn_height = btn_height
        self._r = THEME['radius_medium']
        self._font = font
        self._padding_x = padding_x
        self._icon_space = icon_space

        self._redraw(self.normal_color)

        for w in (self.frame, self.canvas):
            w.bind('<Button-1>', lambda e: self._on_click())
            w.bind('<Enter>', lambda e: self._on_enter())
            w.bind('<Leave>', lambda e: self._on_leave())
        self.canvas.bind('<Return>', lambda e: self._on_click())
        self.canvas.bind('<space>', lambda e: self._on_click())

    def _redraw(self, color):
        self.canvas.delete('all')
        self.canvas.config(bg=self._surface_bg)
        draw_rounded_rect(self.canvas, 1, 1, self._total_width - 1, self._btn_height - 1,
                          self._r, fill=color, outline=self.outline, width=1)

        x_offset = self._padding_x
        if self.icon_name:
            icon_img = get_icon(self.icon_name, size=16, color=self.text_color)
            self._icon_photo = ImageTk.PhotoImage(icon_img)
            self.canvas.create_image(self._padding_x, self._btn_height // 2,
                                     image=self._icon_photo, anchor='w')
            x_offset = self._padding_x + self._icon_space + 4

        self.canvas.create_text(x_offset, self._btn_height // 2,
                                text=self.text, fill=self.text_color,
                                font=self._font, anchor='w')

    def _on_enter(self):
        self._redraw(self.hover_color)

    def _on_leave(self):
        self._redraw(self.normal_color)

    def _on_click(self):
        self._redraw(self.active_color)
        self.parent.after(120, self._on_leave)
        if self.command:
            self.command()

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def grid(self, **kwargs):
        self.frame.grid(**kwargs)


class SidebarButton:
    """侧边栏导航按钮 - 统一高度，整面可点。"""

    def __init__(self, parent, text, command, icon_name=None, is_active=False):
        self.parent = parent
        self.text = text
        self.command = command
        self.icon_name = icon_name
        self.is_active = is_active
        self._build()

    def _build(self):
        self._surface_bg = self.parent.cget('bg') if 'bg' in self.parent.keys() else THEME['bg_secondary']
        self._radius = THEME['radius_medium']
        self._height = THEME['sidebar_item_height']

        self.frame = tk.Frame(self.parent, bg=self._surface_bg, highlightthickness=0, bd=0, cursor='arrow')
        self.canvas = tk.Canvas(self.frame, height=self._height, bg=self._surface_bg,
                                highlightthickness=0, bd=0, cursor='arrow', takefocus=1)
        self.canvas.pack(fill=tk.X)
        self.canvas.bind('<Configure>', lambda e: self._on_leave())

        for w in (self.frame, self.canvas):
            w.bind('<Button-1>', lambda e: self._on_click())
            w.bind('<Enter>', lambda e: self._on_enter())
            w.bind('<Leave>', lambda e: self._on_leave())
        self.canvas.bind('<Return>', lambda e: self._on_click())
        self.canvas.bind('<space>', lambda e: self._on_click())

        self._on_leave()

    def _redraw(self, bg, fg, icon_color, outline=''):
        self.canvas.delete('all')
        self.canvas.config(bg=self._surface_bg)
        self.frame.config(bg=self._surface_bg)

        width = max(self.canvas.winfo_width(), 180)
        height = max(self.canvas.winfo_height(), self._height)
        draw_rounded_rect(self.canvas, 3, 4, width - 3, height - 4,
                          self._radius, fill=bg, outline=outline, width=1)

        if self.is_active:
            # 左侧活动指示条
            draw_rounded_rect(self.canvas, 8, 13, 13, height - 13, 3,
                              fill=THEME['primary'], outline='')

        icon_x = 22
        if self.icon_name:
            icon_img = get_icon(self.icon_name, size=17, color=icon_color)
            self._icon_photo = ImageTk.PhotoImage(icon_img)
            self.canvas.create_image(icon_x, height // 2, image=self._icon_photo, anchor='w')
            icon_x = 48

        font = (THEME['font_family'], 11, 'bold' if self.is_active else 'normal')
        self.canvas.create_text(icon_x, height // 2, text=self.text, fill=fg,
                                font=font, anchor='w')

    def _on_enter(self):
        if self.is_active:
            self._redraw(THEME['primary_light'], THEME['primary'], THEME['primary'])
        else:
            self._redraw(THEME['bg_hover'], THEME['text'], THEME['primary'])

    def _on_leave(self):
        if self.is_active:
            self._redraw(THEME['primary_light'], THEME['primary'], THEME['primary'])
        else:
            self._redraw(THEME['bg_secondary'], THEME['text_secondary'], THEME['text_muted'])

    def _on_click(self):
        if self.command:
            self.command()

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def set_active(self, active):
        self.is_active = active
        self._on_leave()

    def update_text(self, new_text):
        self.text = new_text
        self._on_leave()


class Badge:
    """小徽章 - 用于显示标签（国内/国际/开源/数据来源等）。"""

    def __init__(self, parent, text, fg=None, bg=None, font_size=9):
        surface_bg = parent.cget('bg') if 'bg' in parent.keys() else THEME['bg_secondary']
        self.fg = fg or THEME['primary']
        self.bg = bg or THEME['primary_light']
        self.text = text
        self._font_size = font_size

        temp = tk.Label(text=text, font=(THEME['font_family'], font_size, 'bold'))
        tw = temp.winfo_reqwidth()
        temp.destroy()
        pad = 10
        w = tw + pad * 2
        h = font_size + 12

        self.canvas = tk.Canvas(parent, width=w, height=h, bg=surface_bg,
                                highlightthickness=0, bd=0)
        draw_rounded_rect(self.canvas, 1, 1, w - 1, h - 1, h // 2,
                          fill=self.bg, outline='')
        self.canvas.create_text(w // 2, h // 2, text=text, fill=self.fg,
                                font=(THEME['font_family'], font_size, 'bold'))

    def pack(self, **kwargs):
        self.canvas.pack(**kwargs)

    def grid(self, **kwargs):
        self.canvas.grid(**kwargs)


class RoundedDropdown:
    """苹果风格圆角下拉框 - 替代直角的 ttk.Combobox。

    外观：圆角 canvas 显示当前值 + 下拉箭头；点击弹出圆角浮层列表。
    通过 textvariable 与外部 StringVar 双向同步，trace 行为与 Combobox 一致。
    """

    def __init__(self, parent, textvariable, values, width_px=160, height=None):
        self.parent = parent
        self.var = textvariable
        self.values = list(values)
        self.width_px = width_px
        self.height = height or THEME['input_height']
        self._popup = None
        self._radius = THEME['radius_medium']

        self.canvas = tk.Canvas(parent, width=width_px, height=self.height,
                                bg=parent.cget('bg') if 'bg' in parent.keys() else THEME['bg_secondary'],
                                highlightthickness=0, bd=0, cursor='arrow')
        self._draw(focused=False)

        self.canvas.bind('<Button-1>', lambda e: self._toggle())
        self.canvas.bind('<Configure>', lambda e: self._draw(self._popup is not None))
        # 当外部变量变化时刷新显示
        self.var.trace_add('write', lambda *a: self._draw(self._popup is not None))

    def _draw(self, focused=False):
        cv = self.canvas
        cv.delete('all')
        w = cv.winfo_width()
        if w <= 1:
            w = self.width_px
        h = self.height
        draw_rounded_rect(cv, 2, 2, w - 3, h - 3, self._radius,
                          fill=THEME['bg_secondary'],
                          outline=THEME['border_focus'] if focused else THEME['border'],
                          width=2 if focused else 1)
        # 当前值文字（截断避免压箭头）
        text = self.var.get()
        cv.create_text(14, h // 2, text=text, anchor='w',
                       fill=THEME['text'], font=(THEME['font_family'], 11),
                       width=w - 38)
        # 下拉箭头（v 形）
        ax = w - 18
        ay = h // 2
        cv.create_line(ax - 4, ay - 2, ax, ay + 3, fill=THEME['text_muted'], width=2)
        cv.create_line(ax, ay + 3, ax + 4, ay - 2, fill=THEME['text_muted'], width=2)

    def _toggle(self):
        if self._popup is not None:
            self._close_popup()
        else:
            self._open_popup()

    def _open_popup(self):
        self._draw(focused=True)
        x = self.canvas.winfo_rootx()
        y = self.canvas.winfo_rooty() + self.height + 4
        w = self.canvas.winfo_width() or self.width_px

        row_h = 32
        pad = 6
        max_visible = min(len(self.values), 10)
        ph = row_h * max_visible + pad * 2

        popup = tk.Toplevel(self.canvas)
        popup.wm_overrideredirect(True)
        popup.wm_geometry(f"{w}x{ph}+{x}+{y}")
        popup.configure(bg=THEME['bg_secondary'])
        self._popup = popup

        # 圆角背景 canvas
        pcv = tk.Canvas(popup, width=w, height=ph, bg=THEME['bg'],
                        highlightthickness=0, bd=0)
        pcv.pack(fill=tk.BOTH, expand=True)
        draw_rounded_rect(pcv, 1, 1, w - 2, ph - 2, THEME['radius_medium'],
                          fill=THEME['bg_secondary'], outline=THEME['border'], width=1)

        # 可滚动列表（值多时）
        list_frame = tk.Frame(pcv, bg=THEME['bg_secondary'])
        pcv.create_window(pad, pad, window=list_frame, anchor='nw', width=w - pad * 2)

        self._row_items = []
        for val in self.values:
            row = tk.Frame(list_frame, bg=THEME['bg_secondary'], height=row_h)
            row.pack(fill=tk.X)
            row.pack_propagate(False)
            is_sel = (val == self.var.get())
            lbl = tk.Label(row, text=val, bg=THEME['primary_light'] if is_sel else THEME['bg_secondary'],
                           fg=THEME['primary'] if is_sel else THEME['text'],
                           font=(THEME['font_family'], 11, 'bold' if is_sel else 'normal'),
                           anchor='w', padx=10)
            lbl.pack(fill=tk.BOTH, expand=True, padx=2, pady=1)

            def _hover_in(e, l=lbl, s=is_sel):
                if not s:
                    l.config(bg=THEME['bg_hover'])

            def _hover_out(e, l=lbl, s=is_sel):
                if not s:
                    l.config(bg=THEME['bg_secondary'])

            def _select(e, v=val):
                self.var.set(v)
                self._close_popup()

            for wdg in (row, lbl):
                wdg.bind('<Enter>', _hover_in)
                wdg.bind('<Leave>', _hover_out)
                wdg.bind('<Button-1>', _select)

        # 点击外部关闭
        popup.bind('<FocusOut>', lambda e: self._close_popup())
        popup.focus_set()
        self._click_outside_id = self.canvas.winfo_toplevel().bind(
            '<Button-1>', self._maybe_close_on_root_click, add='+')

    def _maybe_close_on_root_click(self, event):
        # 点到下拉框本身或弹层之外则关闭
        if self._popup is None:
            return
        wx = event.x_root
        wy = event.y_root
        px, py = self._popup.winfo_rootx(), self._popup.winfo_rooty()
        pw, ph = self._popup.winfo_width(), self._popup.winfo_height()
        if not (px <= wx <= px + pw and py <= wy <= py + ph):
            cx, cy = self.canvas.winfo_rootx(), self.canvas.winfo_rooty()
            cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
            if not (cx <= wx <= cx + cw and cy <= wy <= cy + ch):
                self._close_popup()

    def _close_popup(self):
        if self._popup is not None:
            try:
                self._popup.destroy()
            except Exception:
                pass
            self._popup = None
        try:
            self.canvas.winfo_toplevel().unbind('<Button-1>', self._click_outside_id)
        except Exception:
            pass
        self._draw(focused=False)

    def set_values(self, values):
        self.values = list(values)

    def grid(self, **kwargs):
        self.canvas.grid(**kwargs)

    def pack(self, **kwargs):
        self.canvas.pack(**kwargs)


class StatCard:
    """统计指标卡 - 数字 + 标签 + 可选图标/趋势，用于数据概览区。"""

    def __init__(self, parent, label, value, icon_name=None,
                 accent=None, sub=None, horizontal=False):
        self.accent = accent or THEME['primary']
        self.card = RoundedCard(parent, padding=(14, 12), radius=THEME['radius_medium'])
        c = self.card.content

        if horizontal:
            # 横向：彩色竖条 + 标签（左）  数字（右）—— 宽度充足时最稳，文字不裁
            bar = tk.Canvas(c, width=4, height=22, bg=THEME['bg_secondary'],
                            highlightthickness=0, bd=0)
            bar.pack(side=tk.LEFT, padx=(0, 10))
            draw_rounded_rect(bar, 0, 0, 4, 22, 2, fill=self.accent, outline='')

            tk.Label(c, text=label, bg=THEME['bg_secondary'],
                     fg=THEME['text_muted'], font=(THEME['font_family'], 11),
                     anchor='w').pack(side=tk.LEFT, anchor='center')

            self._value_label = tk.Label(c, text=str(value), bg=THEME['bg_secondary'],
                                         fg=THEME['text'],
                                         font=(THEME['font_family'], 20, 'bold'),
                                         anchor='e')
            self._value_label.pack(side=tk.RIGHT, anchor='center')
        else:
            # 纵向：标签一行 → 大数字一行
            top = tk.Frame(c, bg=THEME['bg_secondary'])
            top.pack(fill=tk.X)
            accent_bar = tk.Canvas(top, width=4, height=14, bg=THEME['bg_secondary'],
                                   highlightthickness=0, bd=0)
            accent_bar.pack(side=tk.LEFT, padx=(0, 8), pady=(1, 0))
            draw_rounded_rect(accent_bar, 0, 0, 4, 14, 2, fill=self.accent, outline='')

            tk.Label(top, text=label, bg=THEME['bg_secondary'],
                     fg=THEME['text_muted'], font=(THEME['font_family'], 10),
                     anchor='w').pack(side=tk.LEFT, anchor='center')

            self._value_label = tk.Label(c, text=str(value), bg=THEME['bg_secondary'],
                                         fg=THEME['text'],
                                         font=(THEME['font_family'], 22, 'bold'),
                                         anchor='w')
            self._value_label.pack(anchor='w', fill=tk.X, pady=(6, 0))

            if sub:
                tk.Label(c, text=sub, bg=THEME['bg_secondary'], fg=THEME['text_muted'],
                         font=(THEME['font_family'], 9), anchor='w').pack(anchor='w', pady=(2, 0))

    def _tint(self, hexcolor):
        """生成图标底色的浅色版本。"""
        hexcolor = hexcolor.lstrip('#')
        r, g, b = (int(hexcolor[i:i+2], 16) for i in (0, 2, 4))
        r = int(r + (255 - r) * 0.85)
        g = int(g + (255 - g) * 0.85)
        b = int(b + (255 - b) * 0.85)
        return f'#{r:02x}{g:02x}{b:02x}'

    def set_value(self, value):
        self._value_label.config(text=str(value))

    def pack(self, **kwargs):
        self.card.pack(**kwargs)

    def grid(self, **kwargs):
        self.card.grid(**kwargs)


class LoadingSpinner:
    """加载动画组件"""

    def __init__(self, parent, size=40, color=None):
        self.parent = parent
        self.size = size
        self.color = color or THEME['primary']
        self.canvas = None
        self.angle = 0
        self.running = False
        self.after_id = None

    def _build(self):
        self.canvas = tk.Canvas(self.parent, width=self.size, height=self.size,
                                bg=THEME['bg'], highlightthickness=0)
        self.canvas.pack()

    def _draw(self):
        if not self.running or not self.canvas or not self.canvas.winfo_exists():
            return
        self.canvas.delete('all')
        cx, cy = self.size // 2, self.size // 2
        radius = self.size // 2 - 4
        import math
        for i in range(8):
            angle = math.radians(self.angle + i * 45)
            x = cx + radius * 0.6 * math.cos(angle)
            y = cy + radius * 0.6 * math.sin(angle)
            alpha = 1.0 - (i / 8.0) * 0.7
            r = int(int(self.color[1:3], 16) * alpha)
            g = int(int(self.color[3:5], 16) * alpha)
            b = int(int(self.color[5:7], 16) * alpha)
            color = f'#{r:02x}{g:02x}{b:02x}'
            dot_r = 3 + (i % 3)
            self.canvas.create_oval(x - dot_r, y - dot_r, x + dot_r, y + dot_r,
                                    fill=color, outline='')
        self.angle = (self.angle + 30) % 360
        self.after_id = self.parent.after(80, self._draw)

    def start(self):
        if not self.canvas:
            self._build()
        self.running = True
        self._draw()

    def stop(self):
        self.running = False
        if self.after_id:
            self.parent.after_cancel(self.after_id)
            self.after_id = None
        if self.canvas:
            self.canvas.pack_forget()


class ToastNotification:
    """Toast通知组件 - 圆角亚克力风格，淡入淡出。"""

    def __init__(self, parent):
        self.parent = parent
        self.toast = None
        self._after_id = None

    def show(self, message, type_='info', duration=3000):
        if self.toast and self.toast.winfo_exists():
            self.toast.destroy()
        if self._after_id:
            try:
                self.parent.after_cancel(self._after_id)
            except Exception:
                pass

        colors = {
            'success': (THEME['success_light'], THEME['success'], THEME['success']),
            'error': (THEME['danger_light'], THEME['danger_hover'], THEME['danger']),
            'warning': (THEME['warning_light'], THEME['warning_hover'], THEME['warning']),
            'info': (THEME['info_light'], THEME['info_hover'], THEME['info']),
        }
        bg, fg, border = colors.get(type_, colors['info'])

        host = self.parent
        self.toast = tk.Frame(host, bg=host.cget('bg') if 'bg' in host.keys() else THEME['bg'])
        self.toast.place(relx=0.5, rely=0.04, anchor='n')

        # 用 canvas 画圆角胶囊
        temp = tk.Label(text=message, font=(THEME['font_family'], 11, 'bold'))
        tw = temp.winfo_reqwidth()
        temp.destroy()
        w = tw + 52
        h = 42
        cv = tk.Canvas(self.toast, width=w, height=h,
                       bg=self.toast.cget('bg'), highlightthickness=0, bd=0)
        cv.pack()
        draw_rounded_rect(cv, 1, 1, w - 1, h - 1, h // 2, fill=bg, outline=border, width=1)
        # 左侧状态圆点
        cv.create_oval(16, h // 2 - 4, 24, h // 2 + 4, fill=border, outline='')
        cv.create_text(34, h // 2, text=message, fill=fg, anchor='w',
                       font=(THEME['font_family'], 11, 'bold'))

        self._after_id = self.parent.after(duration, self._hide)

    def _hide(self):
        if self.toast and self.toast.winfo_exists():
            self.toast.destroy()
