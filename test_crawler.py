#!/usr/bin/env python3
"""
测试爬虫 - 先探测网站实际结构
"""

import requests
from bs4 import BeautifulSoup
import json

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

def test_url(url, name):
    print(f"\n{'='*60}")
    print(f"测试: {name}")
    print(f"URL: {url}")
    print(f"{'='*60}")
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        print(f"状态码: {resp.status_code}")
        print(f"Content-Type: {resp.headers.get('Content-Type', 'N/A')}")
        print(f"内容长度: {len(resp.text)}")
        
        # 检查是否是JSON
        if 'application/json' in resp.headers.get('Content-Type', ''):
            data = resp.json()
            print(f"JSON Keys: {list(data.keys())[:5]}")
            return data
        else:
            # 解析HTML找表格
            soup = BeautifulSoup(resp.text, 'html.parser')
            tables = soup.find_all('table')
            print(f"找到表格数: {len(tables)}")
            if tables:
                for i, table in enumerate(tables[:2]):
                    rows = table.find_all('tr')
                    print(f"  表格{i}: {len(rows)} 行")
                    if rows and len(rows) > 0:
                        first_row = rows[0]
                        headers_list = [th.get_text(strip=True) for th in first_row.find_all(['th', 'td'])]
                        print(f"    表头: {headers_list}")
            return soup
    except Exception as e:
        print(f"错误: {e}")
    return None

# 测试各种可能的URL
urls = [
    # LMSYS
    ("https://lmarena.ai/leaderboard", "LMSYS Leaderboard"),
    ("https://chat.lmsys.org/", "LMSYS Chat"),
    ("https://lmsys.org/", "LMSYS Org"),
    
    # Artificial Analysis
    ("https://artificialanalysis.ai/", "Artificial Analysis"),
    ("https://artificialanalysis.ai/leaderboard", "Artificial Analysis Leaderboard"),
    ("https://artificialanalysis.ai/models", "Artificial Analysis Models"),
    
    # OpenCompass
    ("https://opencompass.org.cn/leaderboard-llm", "OpenCompass"),
    ("https://opencompass.org.cn/", "OpenCompass Home"),
    
    # HuggingFace
    ("https://huggingface.co/spaces/open-llm-leaderboard/open_llm_leaderboard", "HF Leaderboard"),
    
    # SuperCLUE
    ("https://www.superclue.ai/", "SuperCLUE"),
]

for url, name in urls:
    test_url(url, name)
