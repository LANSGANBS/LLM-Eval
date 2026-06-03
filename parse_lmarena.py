#!/usr/bin/env python3
"""解析 LMSYS Arena 排行榜"""

import requests
from bs4 import BeautifulSoup
import re

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

print("正在获取 LMSYS Arena 排行榜...")
resp = requests.get("https://lmarena.ai/leaderboard", headers=headers, timeout=30)
soup = BeautifulSoup(resp.text, 'html.parser')

table = soup.find('table')
rows = table.find_all('tr')
print(f"总行数: {len(rows)}\n")

data = []
for row in rows[1:]:  # 跳过表头
    cells = row.find_all(['td', 'th'])
    if len(cells) >= 3:
        model_name = cells[0].get_text(strip=True)
        overall_rank = cells[1].get_text(strip=True)
        expert_rank = cells[2].get_text(strip=True) if len(cells) > 2 else ''
        data.append({
            'model': model_name,
            'overall_rank': overall_rank,
            'expert_rank': expert_rank
        })

print(f"成功解析 {len(data)} 条数据\n")
print("前20个模型:")
for i, item in enumerate(data[:20]):
    print(f"  {i+1}. {item['model'][:50]}...")
