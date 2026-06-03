"""
Icon renderer - Draws clean vector-style icons using Pillow
Replaces all emoji usage with consistent, theme-matched icons
"""
from PIL import Image, ImageDraw, ImageFont
import os
import math

ICON_SIZE = 20

def _create_canvas(size=ICON_SIZE, color="#2271b1"):
    """Create a transparent canvas"""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    return img, draw

def _parse_color(color):
    """Parse hex color to RGB tuple"""
    if isinstance(color, str):
        color = color.lstrip('#')
        return tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
    return color

def draw_robot(size=ICON_SIZE, color="#2271b1"):
    """Robot/AI icon."""
    img, draw = _create_canvas(size, color)
    c = _parse_color(color)
    p = size / 20.0  # pixel unit
    # Head
    draw.rounded_rectangle([4*p, 5*p, 16*p, 14*p], radius=2*p, fill=c)
    # Eyes
    draw.ellipse([6*p, 8*p, 8*p, 10*p], fill=(255, 255, 255))
    draw.ellipse([12*p, 8*p, 14*p, 10*p], fill=(255, 255, 255))
    # Antenna
    draw.line([10*p, 5*p, 10*p, 2*p], fill=c, width=max(1, int(p)))
    draw.ellipse([9*p, 1*p, 11*p, 3*p], fill=c)
    return img

def draw_trophy(size=ICON_SIZE, color="#dba617"):
    """Trophy icon."""
    img, draw = _create_canvas(size, color)
    c = _parse_color(color)
    p = size / 20.0
    # Cup body
    draw.polygon([(4*p, 4*p), (16*p, 4*p), (14*p, 12*p), (6*p, 12*p)], fill=c)
    # Handles
    draw.arc([1*p, 4*p, 6*p, 10*p], 90, 270, fill=c, width=max(1, int(p*1.5)))
    draw.arc([14*p, 4*p, 19*p, 10*p], 270, 90, fill=c, width=max(1, int(p*1.5)))
    # Stem
    draw.rectangle([9*p, 12*p, 11*p, 16*p], fill=c)
    # Base
    draw.rectangle([6*p, 16*p, 14*p, 18*p], fill=c)
    return img

def draw_chart_bar(size=ICON_SIZE, color="#2271b1"):
    """Bar chart icon."""
    img, draw = _create_canvas(size, color)
    c = _parse_color(color)
    p = size / 20.0
    draw.rectangle([3*p, 12*p, 6*p, 18*p], fill=c)
    draw.rectangle([8*p, 6*p, 11*p, 18*p], fill=c)
    draw.rectangle([13*p, 9*p, 16*p, 18*p], fill=c)
    return img

def draw_compare(size=ICON_SIZE, color="#2271b1"):
    """Compare icon."""
    img, draw = _create_canvas(size, color)
    c = _parse_color(color)
    p = size / 20.0
    # Center post
    draw.rectangle([9*p, 3*p, 11*p, 17*p], fill=c)
    # Top bar
    draw.rectangle([3*p, 5*p, 17*p, 7*p], fill=c)
    # Left pan
    draw.arc([2*p, 7*p, 9*p, 13*p], 0, 180, fill=c, width=max(1, int(p*1.5)))
    # Right pan
    draw.arc([11*p, 7*p, 18*p, 13*p], 0, 180, fill=c, width=max(1, int(p*1.5)))
    # Base
    draw.rectangle([7*p, 17*p, 13*p, 19*p], fill=c)
    return img

def draw_chart_radar(size=ICON_SIZE, color="#2271b1"):
    """Radar chart icon."""
    img, draw = _create_canvas(size, color)
    c = _parse_color(color)
    p = size / 20.0
    cx, cy = 10*p, 11*p
    r = 7*p
    for i in range(3):
        ri = r * (i + 1) / 3
        pts = []
        for j in range(6):
            angle = math.radians(-90 + j * 60)
            pts.append((cx + ri * math.cos(angle), cy + ri * math.sin(angle)))
        draw.polygon(pts, outline=c, width=max(1, int(p*0.8)))
    # Spokes
    for j in range(6):
        angle = math.radians(-90 + j * 60)
        draw.line([(cx, cy), (cx + r * math.cos(angle), cy + r * math.sin(angle))],
                  fill=c, width=max(1, int(p*0.6)))
    return img

def draw_heatmap(size=ICON_SIZE, color="#2271b1"):
    """Heatmap icon."""
    img, draw = _create_canvas(size, color)
    c = _parse_color(color)
    light_c = tuple(min(255, int(x * 0.4 + 153)) for x in _parse_color(color))
    mid_c = tuple(min(255, int(x * 0.7 + 76)) for x in _parse_color(color))
    p = size / 20.0
    # Grid cells
    draw.rectangle([3*p, 4*p, 8*p, 9*p], fill=light_c)
    draw.rectangle([9*p, 4*p, 14*p, 9*p], fill=c)
    draw.rectangle([15*p, 4*p, 19*p, 9*p], fill=mid_c)
    draw.rectangle([3*p, 10*p, 8*p, 15*p], fill=c)
    draw.rectangle([9*p, 10*p, 14*p, 15*p], fill=mid_c)
    draw.rectangle([15*p, 10*p, 19*p, 15*p], fill=light_c)
    draw.rectangle([3*p, 16*p, 8*p, 19*p], fill=mid_c)
    draw.rectangle([9*p, 16*p, 14*p, 19*p], fill=light_c)
    draw.rectangle([15*p, 16*p, 19*p, 19*p], fill=c)
    return img

def draw_refresh(size=ICON_SIZE, color="#2271b1"):
    """Refresh icon."""
    img, draw = _create_canvas(size, color)
    c = _parse_color(color)
    p = size / 20.0
    cx, cy = 10*p, 10*p
    r = 6*p
    draw.arc([cx-r, cy-r, cx+r, cy+r], 45, 300, fill=c, width=max(2, int(p*1.5)))
    # Arrow head
    ax = cx + r * math.cos(math.radians(300))
    ay = cy + r * math.sin(math.radians(300))
    draw.polygon([(ax, ay), (ax+3*p, ay-2*p), (ax+1*p, ay+3*p)], fill=c)
    return img

def draw_upload(size=ICON_SIZE, color="#2271b1"):
    """Upload icon."""
    img, draw = _create_canvas(size, color)
    c = _parse_color(color)
    p = size / 20.0
    # Arrow up
    draw.polygon([(10*p, 3*p), (5*p, 9*p), (8*p, 9*p), (8*p, 15*p), (12*p, 15*p), (12*p, 9*p), (15*p, 9*p)], fill=c)
    # Base line
    draw.rectangle([3*p, 16*p, 17*p, 18*p], fill=c)
    return img

def draw_download(size=ICON_SIZE, color="#2271b1"):
    """Download icon."""
    img, draw = _create_canvas(size, color)
    c = _parse_color(color)
    p = size / 20.0
    # Arrow down
    draw.polygon([(10*p, 17*p), (5*p, 11*p), (8*p, 11*p), (8*p, 5*p), (12*p, 5*p), (12*p, 11*p), (15*p, 11*p)], fill=c)
    # Base line
    draw.rectangle([3*p, 2*p, 17*p, 4*p], fill=c)
    return img

def draw_search(size=ICON_SIZE, color="#646970"):
    """Search icon."""
    img, draw = _create_canvas(size, color)
    c = _parse_color(color)
    p = size / 20.0
    cx, cy = 8*p, 8*p
    r = 5*p
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], outline=c, width=max(2, int(p*1.5)))
    # Handle
    hx = cx + r * math.cos(math.radians(45))
    hy = cy + r * math.sin(math.radians(45))
    draw.line([(hx, hy), (18*p, 18*p)], fill=c, width=max(2, int(p*1.5)))
    return img

def draw_database(size=ICON_SIZE, color="#2271b1"):
    """Database icon."""
    img, draw = _create_canvas(size, color)
    c = _parse_color(color)
    p = size / 20.0
    # Cylinder body
    draw.ellipse([3*p, 2*p, 17*p, 7*p], fill=c)
    draw.rectangle([3*p, 5*p, 17*p, 14*p], fill=c)
    draw.ellipse([3*p, 12*p, 17*p, 17*p], fill=c)
    # Middle line
    draw.ellipse([3*p, 7*p, 17*p, 10*p], outline=(255, 255, 255), width=max(1, int(p*0.8)))
    return img

def draw_star(size=ICON_SIZE, color="#dba617"):
    """Star icon"""
    img, draw = _create_canvas(size, color)
    c = _parse_color(color)
    p = size / 20.0
    cx, cy = 10*p, 10*p
    pts = []
    for i in range(10):
        angle = math.radians(-90 + i * 36)
        r = 8*p if i % 2 == 0 else 4*p
        pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(pts, fill=c)
    return img

def draw_nav_ranking(size=ICON_SIZE, color="#2271b1"):
    """Ranking nav icon"""
    return draw_trophy(size, color)

def draw_nav_analysis(size=ICON_SIZE, color="#2271b1"):
    """Analysis nav icon"""
    return draw_chart_radar(size, color)

def draw_nav_compare(size=ICON_SIZE, color="#2271b1"):
    """Compare nav icon"""
    return draw_compare(size, color)

def draw_nav_heatmap(size=ICON_SIZE, color="#2271b1"):
    """Heatmap nav icon"""
    return draw_heatmap(size, color)

# Icon registry
_ICONS = {
    'robot': draw_robot,
    'trophy': draw_trophy,
    'chart_bar': draw_chart_bar,
    'compare': draw_compare,
    'chart_radar': draw_chart_radar,
    'heatmap': draw_heatmap,
    'refresh': draw_refresh,
    'upload': draw_upload,
    'download': draw_download,
    'search': draw_search,
    'database': draw_database,
    'star': draw_star,
    'nav_ranking': draw_nav_ranking,
    'nav_analysis': draw_nav_analysis,
    'nav_compare': draw_nav_compare,
    'nav_heatmap': draw_nav_heatmap,
}

# Cache for rendered icons
_cache = {}

def get_icon(name, size=ICON_SIZE, color=None):
    """Get a rendered icon image. Returns a PIL Image."""
    cache_key = (name, size, color)
    if cache_key in _cache:
        return _cache[cache_key]
    
    drawer = _ICONS.get(name)
    if drawer is None:
        # Fallback to a simple circle
        img, draw = _create_canvas(size, color or "#2271b1")
        draw.ellipse([2, 2, size-2, size-2], fill=_parse_color(color or "#2271b1"))
        _cache[cache_key] = img
        return img
    
    img = drawer(size, color or "#2271b1")
    _cache[cache_key] = img
    return img

def get_icon_photo(name, size=ICON_SIZE, color=None):
    """Get a PhotoImage for use in tkinter widgets"""
    import tkinter as tk
    img = get_icon(name, size, color)
    # Scale up for retina if needed
    return img
