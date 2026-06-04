"""主题配置 - 浅色亚克力风格 (Acrylic / Fluent inspired)

纯 Tkinter 无法做真模糊，这里用「半透明叠色 + 柔和描边 + 阴影感」模拟亚克力质感。
所有尺寸 / 圆角 / 间距 / 字号都集中在此，保证全局统一。
"""

THEME = {
    # ---------- 背景层级（浅色亚克力底） ----------
    'bg': '#eef1f7',            # 应用最底层（略带蓝灰，衬托卡片浮起感）
    'bg_secondary': '#ffffff',  # 卡片表面
    'bg_tertiary': '#f1f5fb',   # 输入框 / 次级填充
    'bg_hover': '#eaf1ff',      # 悬停态
    'bg_card': '#ffffff',
    'bg_active': '#dbe7ff',

    # 亚克力叠色（半透明感的近似纯色，用于卡片/侧栏制造层次）
    'acrylic': '#f7f9fdff',     # 主亚克力面（近白带微透感）
    'acrylic_soft': '#fbfcfeff',
    'acrylic_tint': '#eaf0fb',  # 带蓝色调的亚克力（侧栏/高亮区）
    'acrylic_border': '#e2e8f4',  # 亚克力描边（柔和）
    'shadow': '#d3dcec',        # 模拟投影的浅色（绘制在卡片下方偏移处）

    # ---------- 文字 ----------
    'text': '#0f172a',
    'text_secondary': '#3a4763',
    'text_muted': '#7a879e',
    'text_bright': '#000000',
    'text_white': '#ffffff',

    # ---------- 边框 ----------
    'border': '#e2e8f4',
    'border_light': '#eef2f9',
    'border_focus': '#3b82f6',

    # ---------- 主色调 ----------
    'primary': '#3b6ef5',
    'primary_hover': '#2f5de0',
    'primary_active': '#2349c0',
    'primary_light': '#e3ebff',
    'primary_soft': '#f0f4ff',

    # ---------- 强调色 ----------
    'accent': '#38bdf8',
    'accent2': '#22c55e',

    # ---------- 状态色 ----------
    'success': '#16a34a',
    'success_hover': '#15803d',
    'success_light': '#dcfce7',
    'warning': '#f59e0b',
    'warning_hover': '#d97706',
    'warning_light': '#fef3c7',
    'danger': '#ef4444',
    'danger_hover': '#dc2626',
    'danger_light': '#fee2e2',
    'info': '#0ea5e9',
    'info_hover': '#0284c7',
    'info_light': '#e0f2fe',

    # ---------- 图表配色 ----------
    'chart_colors': [
        '#3b6ef5', '#16a34a', '#f59e0b', '#ef4444',
        '#8b5cf6', '#06b6d4', '#ec4899', '#14b8a6',
        '#84cc16', '#f97316', '#6366f1', '#d946ef'
    ],

    # ---------- 字体 ----------
    'font_family': 'PingFang SC',
    'font_family_fallback': 'Helvetica Neue, Arial, sans-serif',
    'font_size_small': 10,
    'font_size_normal': 11,
    'font_size_medium': 13,
    'font_size_large': 16,
    'font_size_xl': 20,
    'font_size_xxl': 24,

    # ---------- 统一圆角（全局只用这三档） ----------
    'radius_small': 10,
    'radius_medium': 14,
    'radius_large': 18,
    'radius_pill': 999,

    # ---------- 统一间距（8pt 栅格） ----------
    'spacing_xs': 4,
    'spacing_sm': 8,
    'spacing_md': 12,
    'spacing_lg': 16,
    'spacing_xl': 20,
    'spacing_xxl': 24,

    # ---------- 统一控件尺寸规范 ----------
    'btn_height': 38,          # 标准按钮高度（全局统一）
    'btn_height_sm': 32,       # 小按钮
    'btn_padding_x': 18,       # 按钮左右内边距
    'btn_padding_x_sm': 14,
    'sidebar_item_height': 44,  # 侧边栏项高度
    'input_height': 38,        # 输入框 / 下拉框高度
    'card_padding': 20,        # 卡片标准内边距
}
