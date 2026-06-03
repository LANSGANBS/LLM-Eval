"""
UI组件库 - 可复用的现代化组件
遵循WordPress Dashboard风格，统一圆角、等距留白
"""
import tkinter as tk
from tkinter import ttk
from PIL import ImageTk

from llm_eval_system.core.theme import THEME
from llm_eval_system.ui.icons import get_icon


class RoundedCard:
    """通用圆角卡片容器。"""

    def __init__(self, parent, bg=None, border_color=None, radius=None,
                 padding=16, surface_bg=None, min_height=None):
        self.parent = parent
        self.bg = bg or THEME['bg_secondary']
        self.border_color = border_color or THEME['border']
        self.radius = radius or THEME['radius_large']
        self.surface_bg = surface_bg or (parent.cget('bg') if 'bg' in parent.keys() else THEME['bg'])
        self.min_height = min_height

        if isinstance(padding, tuple):
            if len(padding) == 2:
                self.padx, self.pady = padding
            else:
                self.padx, self.pady = padding[0], padding[1]
        else:
            self.padx = padding
            self.pady = padding

        self.frame = tk.Frame(self.parent, bg=self.surface_bg, highlightthickness=0, bd=0)
        self.canvas = tk.Canvas(self.frame, bg=self.surface_bg, highlightthickness=0, bd=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.content = tk.Frame(self.canvas, bg=self.bg, highlightthickness=0, bd=0)
        self._content_window = self.canvas.create_window(
            self.padx, self.pady, anchor='nw', window=self.content
        )

        self.canvas.bind('<Configure>', self._on_configure)
        self.content.bind('<Configure>', self._sync_size, add='+')

    def _draw_rounded_rect(self, canvas, x1, y1, x2, y2, r, **kwargs):
        points = [
            x1 + r, y1,
            x2 - r, y1,
            x2, y1,
            x2, y1 + r,
            x2, y2 - r,
            x2, y2,
            x2 - r, y2,
            x1 + r, y2,
            x1, y2,
            x1, y2 - r,
            x1, y1 + r,
            x1, y1,
        ]
        return canvas.create_polygon(points, smooth=True, **kwargs)

    def _sync_size(self, _event=None):
        req_height = self.content.winfo_reqheight() + self.pady * 2
        req_width = self.content.winfo_reqwidth() + self.padx * 2
        if self.min_height is not None:
            req_height = max(req_height, self.min_height)
        self.canvas.configure(height=req_height)
        self.canvas.configure(width=max(self.canvas.winfo_width(), req_width))
        self._redraw()

    def _on_configure(self, _event=None):
        self._redraw()

    def _redraw(self):
        width = max(self.canvas.winfo_width(), self.content.winfo_reqwidth() + self.padx * 2)
        height = max(self.canvas.winfo_height(), self.content.winfo_reqheight() + self.pady * 2)
        if self.min_height is not None:
            height = max(height, self.min_height)

        self.canvas.delete('card-bg')
        self._draw_rounded_rect(
            self.canvas,
            2,
            2,
            width - 2,
            height - 2,
            self.radius,
            fill=self.bg,
            outline=self.border_color,
            width=1,
            tags='card-bg',
        )
        self.canvas.tag_lower('card-bg')
        self.canvas.itemconfigure(self._content_window, width=max(width - self.padx * 2, 1))
        self.canvas.coords(self._content_window, self.padx, self.pady)

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def grid(self, **kwargs):
        self.frame.grid(**kwargs)

    def place(self, **kwargs):
        self.frame.place(**kwargs)


class StyledButton:
    """样式按钮 - 修复点击区域、光标、等距留白"""

    def __init__(self, parent, text, command, color_key='primary',
                 text_color='#ffffff', width=None, height=None,
                 font_size=11, bold=True, icon_name=None):
        self.parent = parent
        self.text = text
        self.command = command
        self.color_key = color_key
        self.text_color = text_color
        self.width = width
        self.height = height
        self.font_size = font_size
        self.bold = bold
        self.icon_name = icon_name

        self._get_colors()
        self._build()

    def _get_colors(self):
        colors = {
            'primary': (THEME['primary'], THEME['primary_hover'], THEME['primary_active']),
            'success': (THEME['success'], THEME['success_hover'], THEME['primary_active']),
            'warning': (THEME['warning'], THEME['warning_hover'], THEME['primary_active']),
            'danger': (THEME['danger'], THEME['danger_hover'], THEME['primary_active']),
            'info': (THEME['info'], THEME['info_hover'], THEME['primary_active']),
            'secondary': (THEME['bg_tertiary'], THEME['bg_hover'], THEME['border']),
        }
        self.normal_color, self.hover_color, self.active_color = colors.get(
            self.color_key, (THEME['primary'], THEME['primary_hover'], THEME['primary_active'])
        )

    def _build(self):
        """构建按钮 - 使用Canvas绘制圆角按钮，解决点击区域问题"""
        btn_height = self.height or 40
        padding_x = 18
        self._surface_bg = self.parent.cget('bg') if 'bg' in self.parent.keys() else THEME['bg']

        font_weight = 'bold' if self.bold else 'normal'
        font = (THEME['font_family'], self.font_size, font_weight)

        # Measure text width
        temp = tk.Label(text=self.text, font=font)
        text_width = temp.winfo_reqwidth()
        temp.destroy()

        # Calculate total width
        icon_space = 24 if self.icon_name else 0
        total_width = self.width or (text_width + padding_x * 2 + icon_space + 8)

        # Create the outer frame with no highlight
        self.frame = tk.Frame(self.parent, bg=self._surface_bg,
                                                            highlightthickness=0, bd=0, cursor='arrow')

        # Use a Canvas for the rounded-rect button - this ensures the ENTIRE
        # area is clickable, not just the edges
        self.canvas = tk.Canvas(self.frame, width=total_width, height=btn_height,
                    bg=self._surface_bg, highlightthickness=0, bd=0,
                                                                cursor='arrow', takefocus=1)
        self.canvas.pack()

        # Draw rounded rectangle background
        r = THEME['radius_medium']
        self._draw_rounded_rect(self.canvas, 0, 0, total_width, btn_height, r,
                                fill=self.normal_color, outline='')

        # Draw icon if present
        x_offset = padding_x
        if self.icon_name:
            icon_img = get_icon(self.icon_name, size=16, color=self.text_color)
            self._icon_photo = ImageTk.PhotoImage(icon_img)
            self.canvas.create_image(padding_x, btn_height // 2,
                                     image=self._icon_photo, anchor='w')
            x_offset = padding_x + icon_space + 4

        # Draw text
        self.canvas.create_text(x_offset, btn_height // 2,
                                text=self.text, fill=self.text_color,
                                font=font, anchor='w')

        # Bind events on both frame and canvas so the entire visual button stays interactive.
        self.frame.bind('<Button-1>', lambda e: self._on_click())
        self.frame.bind('<Enter>', lambda e: self._on_enter())
        self.frame.bind('<Leave>', lambda e: self._on_leave())
        self.canvas.bind('<Button-1>', lambda e: self._on_click())
        self.canvas.bind('<Enter>', lambda e: self._on_enter())
        self.canvas.bind('<Leave>', lambda e: self._on_leave())
        self.canvas.bind('<Return>', lambda e: self._on_click())
        self.canvas.bind('<space>', lambda e: self._on_click())

        # Store drawing params for redraw
        self._total_width = total_width
        self._btn_height = btn_height
        self._r = r
        self._font = font
        self._padding_x = padding_x
        self._icon_space = icon_space
        self._x_offset = x_offset

    def _draw_rounded_rect(self, canvas, x1, y1, x2, y2, r, **kwargs):
        """Draw a rounded rectangle on canvas"""
        points = [
            x1 + r, y1,
            x2 - r, y1,
            x2, y1,
            x2, y1 + r,
            x2, y2 - r,
            x2, y2,
            x2 - r, y2,
            x1 + r, y2,
            x1, y2,
            x1, y2 - r,
            x1, y1 + r,
            x1, y1,
        ]
        return canvas.create_polygon(points, smooth=True, **kwargs)

    def _redraw(self, color):
        """Redraw button with new color"""
        self.canvas.delete('all')
        self.canvas.config(bg=self._surface_bg)
        self._draw_rounded_rect(self.canvas, 0, 0,
                                self._total_width, self._btn_height,
                                self._r, fill=color, outline='')

        x_offset = self._x_offset
        if self.icon_name:
            self.canvas.create_image(self._padding_x, self._btn_height // 2,
                                     image=self._icon_photo, anchor='w')
        self.canvas.create_text(x_offset, self._btn_height // 2,
                                text=self.text, fill=self.text_color,
                                font=self._font, anchor='w')

    def _on_enter(self):
        self._redraw(self.hover_color)

    def _on_leave(self):
        self._redraw(self.normal_color)

    def _on_click(self):
        self._redraw(self.active_color)
        self.parent.after(120, lambda: self._on_leave())
        if self.command:
            self.command()

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def grid(self, **kwargs):
        self.frame.grid(**kwargs)


class SidebarButton:
    """侧边栏按钮 - 左侧导航专用"""

    def __init__(self, parent, text, command, icon_name=None, is_active=False):
        self.parent = parent
        self.text = text
        self.command = command
        self.icon_name = icon_name
        self.is_active = is_active

        self._build()

    def _build(self):
        """构建侧边栏按钮"""
        bg = THEME['primary_light'] if self.is_active else THEME['bg_secondary']
        fg = THEME['primary'] if self.is_active else THEME['text_secondary']
        icon_color = THEME['primary'] if self.is_active else THEME['text_muted']
        self._surface_bg = self.parent.cget('bg') if 'bg' in self.parent.keys() else THEME['bg_secondary']

        self.frame = tk.Frame(self.parent, bg=self._surface_bg, highlightthickness=0, bd=0,
                              cursor='arrow')

        # Use canvas for full-clickable area with consistent height
        self.canvas = tk.Canvas(self.frame, height=44, bg=bg,
                                highlightthickness=0, bd=0,
                                cursor='arrow', takefocus=1)
        self.canvas.pack(fill=tk.X)
        self.canvas.bind('<Configure>', lambda e: self._on_leave())

        # Bind events - entire surface remains clickable and keyboard accessible.
        self.frame.bind('<Button-1>', lambda e: self._on_click())
        self.frame.bind('<Enter>', lambda e: self._on_enter())
        self.frame.bind('<Leave>', lambda e: self._on_leave())
        self.canvas.bind('<Button-1>', lambda e: self._on_click())
        self.canvas.bind('<Enter>', lambda e: self._on_enter())
        self.canvas.bind('<Leave>', lambda e: self._on_leave())
        self.canvas.bind('<Return>', lambda e: self._on_click())
        self.canvas.bind('<space>', lambda e: self._on_click())

        # Store for redraw
        self._bg = bg
        self._fg = fg
        self._icon_color = icon_color
        self._icon_x_start = 20
        self._canvas_bg = self._surface_bg
        self._radius = THEME['radius_large']
        self._on_leave()

    def _draw_rounded_rect(self, canvas, x1, y1, x2, y2, r, **kwargs):
        points = [
            x1 + r, y1,
            x2 - r, y1,
            x2, y1,
            x2, y1 + r,
            x2, y2 - r,
            x2, y2,
            x2 - r, y2,
            x1 + r, y2,
            x1, y2,
            x1, y2 - r,
            x1, y1 + r,
            x1, y1,
        ]
        return canvas.create_polygon(points, smooth=True, **kwargs)

    def _redraw(self, bg, fg, icon_color):
        self.canvas.delete('all')
        self.canvas.config(bg=self._canvas_bg)
        self.frame.config(bg=self._surface_bg)

        width = max(self.canvas.winfo_width(), 160)
        height = max(self.canvas.winfo_height(), 44)
        self._draw_rounded_rect(self.canvas, 4, 4, width - 4, height - 4,
                                self._radius, fill=bg, outline='')

        if self.is_active:
            self.canvas.create_rectangle(10, 11, 14, height - 11,
                                         fill=THEME['primary'], outline='')

        icon_x = self._icon_x_start
        if self.icon_name:
            icon_img = get_icon(self.icon_name, size=16, color=icon_color)
            self._icon_photo = ImageTk.PhotoImage(icon_img)
            self.canvas.create_image(icon_x, height // 2, image=self._icon_photo, anchor='w')
            icon_x = 44

        font = (THEME['font_family'], 11)
        self.canvas.create_text(icon_x, height // 2, text=self.text, fill=fg,
                                font=font, anchor='w')

    def _on_enter(self):
        self._redraw(THEME['bg_hover'], THEME['primary'], THEME['primary'])

    def _on_leave(self):
        bg = THEME['primary_light'] if self.is_active else THEME['bg_secondary']
        fg = THEME['primary'] if self.is_active else THEME['text_secondary']
        icon_color = THEME['primary'] if self.is_active else THEME['text_muted']
        self._redraw(bg, fg, icon_color)

    def _on_click(self):
        if self.command:
            self.command()

    def pack(self, **kwargs):
        self.frame.pack(**kwargs)

    def set_active(self, active):
        self.is_active = active
        self._on_leave()


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
    """Toast通知组件"""

    def __init__(self, parent):
        self.parent = parent
        self.toast = None

    def show(self, message, type_='info', duration=3000):
        if self.toast and self.toast.winfo_exists():
            self.toast.destroy()

        colors = {
            'success': ('#d4edda', '#155724', THEME['success']),
            'error': ('#f8d7da', '#721c24', THEME['danger']),
            'warning': ('#fff3cd', '#856404', THEME['warning']),
            'info': ('#d1ecf1', '#0c5460', THEME['info']),
        }
        bg, fg, border = colors.get(type_, colors['info'])

        self.toast = tk.Frame(self.parent, bg=bg, highlightbackground=border,
                              highlightthickness=1)
        self.toast.place(relx=0.5, rely=0.05, anchor='n')

        label = tk.Label(self.toast, text=message, bg=bg, fg=fg,
                         font=(THEME['font_family'], 11))
        label.pack(padx=16, pady=8)

        self.parent.after(duration, lambda: self._hide())

    def _hide(self):
        if self.toast and self.toast.winfo_exists():
            self.toast.destroy()
