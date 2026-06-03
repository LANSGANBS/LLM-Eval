"""
网络爬虫模块 - 从专业AI评测网站抓取数据
"""
import requests
import json
import re
import time
import logging
import random
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict

from llm_eval_system.utils.exceptions import CrawlerException, safe_operation

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

TIMEOUT = 30

DIMENSIONS = ["语言理解", "逻辑推理", "知识问答", "代码生成",
              "文本生成", "数学能力", "多语言能力", "安全性"]

ARENA_DIMENSION_MAP = {
    'code': '代码生成',
    'document': '知识问答',
    'search': '逻辑推理',
    'vision': '多语言能力',
    'image-to-code': '代码生成',
}


def classify_model(model_name: str) -> str:
    """根据模型名称判断是国内还是国际"""
    domestic_keywords = ['qwen', 'kimi', 'deepseek', 'glm', 'baichuan', 'yi-',
                        'chatglm', 'sensechat', 'spark-', 'spark-v', 'spark-prover', 'spark-formal', 'tongyi', 'doubao',
                        'ernie', 'wenxin', 'hunyuan', 'tencent', 'mimo',
                        'minimax', 'moonshot', 'iflytek', 'bytedance']
    name_lower = model_name.lower()
    for kw in domestic_keywords:
        if kw in name_lower:
            return "domestic"
    return "international"


DOMESTIC_ORGS = {
    '阿里巴巴', '百度', '字节跳动', '腾讯', '月之暗面', '深度求索',
    '智谱AI', '百川智能', '零一万物', '商汤科技', '科大讯飞', '小米', 'MiniMax',
}


def classify_by_org(organization: str) -> str:
    """根据公司/组织名称判断是国内还是国际"""
    if not organization:
        return None
    if organization in DOMESTIC_ORGS:
        return "domestic"
    org_lower = organization.lower()
    domestic_en = ['alibaba', 'baidu', 'bytedance', 'tencent', 'moonshot',
                   'deepseek', 'zhipu', 'baichuan', '01.ai', 'sensetime',
                   'iflytek', 'xiaomi', 'minimax', 'kimi', 'doubao', 'hunyuan']
    for kw in domestic_en:
        if kw in org_lower:
            return "domestic"
    return "international"


def format_model_name(raw_name: str) -> str:
    """格式化模型名称"""
    name = raw_name
    replacements = [
        ('Anthropicclaude', 'Anthropic Claude'),
        ('anthropicclaude', 'Anthropic Claude'),
        ('claude-opus', 'Claude Opus'),
        ('claude-sonnet', 'Claude Sonnet'),
        ('claude-haiku', 'Claude Haiku'),
        ('claude-', 'Claude '),
        ('gpt-4o', 'GPT-4o'),
        ('gpt-4', 'GPT-4'),
        ('gpt-3.5', 'GPT-3.5'),
        ('gpt-5', 'GPT-5'),
        ('o1-preview', 'o1-preview'),
        ('o1-mini', 'o1-mini'),
        ('o1-', 'o1-'),
        ('o3-', 'o3-'),
        ('gemini-pro', 'Gemini Pro'),
        ('gemini-ultra', 'Gemini Ultra'),
        ('gemini-', 'Gemini '),
        ('gemma-', 'Gemma '),
        ('llama-', 'LLaMA '),
        ('muse-', 'Muse '),
        ('mistral-', 'Mistral '),
        ('mixtral-', 'Mixtral '),
        ('grok-', 'Grok '),
        ('qwen-', 'Qwen '),
        ('tongyi-', 'Tongyi '),
        ('deepseek-', 'DeepSeek '),
        ('chatglm', 'ChatGLM'),
        ('glm-', 'GLM-'),
        ('ernie-', 'Ernie '),
        ('spark-prover', 'SPARK-Prover'),
        ('spark-formalizer', 'SPARK-Formalizer'),
        ('spark-vl', 'SPARK-VL'),
        ('sensechat-', 'SenseChat '),
        ('mimo-', 'MiMo '),
        ('amazon-nova', 'Amazon Nova'),
        ('nova-pro', 'Nova Pro'),
        ('nova-lite', 'Nova Lite'),
        ('nova-micro', 'Nova Micro'),
        ('titan-', 'Titan '),
        ('-thinking', ' (thinking)'),
    ]
    for old, new in replacements:
        name = name.replace(old, new)
    return name


def extract_company(model_name: str) -> str:
    """提取公司信息"""
    name_lower = model_name.lower()
    priority_rules = [
        ('gpt4all', 'GPT4all'),
        ('gpt-4o', 'OpenAI'),
        ('gpt-4', 'OpenAI'),
        ('gpt-3.5', 'OpenAI'),
        ('gpt-5', 'OpenAI'),
        ('o4-mini', 'OpenAI'),
        ('o4-', 'OpenAI'),
        ('chatgpt', 'OpenAI'),
        ('gpt', 'OpenAI'),
        ('o1-', 'OpenAI'),
        ('o1 ', 'OpenAI'),
        ('o3-', 'OpenAI'),
        ('gemini', 'Google'),
        ('gemma', 'Google'),
        ('claude', 'Anthropic'),
        ('llama', 'Meta'),
        ('muse', 'Meta'),
        ('meta-', 'Meta'),
        ('mistral', 'Mistral AI'),
        ('mixtral', 'Mistral AI'),
        ('grok', 'xAI'),
        ('cohere', 'Cohere'),
        ('jamba', 'AI21'),
        ('phi-', 'Microsoft'),
        ('nova', 'Amazon'),
        ('titan', 'Amazon'),
        ('amazon', 'Amazon'),
        ('qwen', '阿里巴巴'),
        ('tongyi', '阿里巴巴'),
        ('ernie', '百度'),
        ('wenxin', '百度'),
        ('doubao', '字节跳动'),
        ('bytedance', '字节跳动'),
        ('hunyuan', '腾讯'),
        ('tencent', '腾讯'),
        ('kimi', '月之暗面'),
        ('deepseek', '深度求索'),
        ('glm', '智谱AI'),
        ('chatglm', '智谱AI'),
        ('baichuan', '百川智能'),
        ('yi-', '零一万物'),
        ('sensetime', '商汤科技'),
        ('sensechat', '商汤科技'),
        ('iflytek', '科大讯飞'),
        ('iflytek-spark', '科大讯飞'),
        ('spark', '科大讯飞'),
        ('mimo', '小米'),
        ('minimax', 'MiniMax'),
        ('moonshot', '月之暗面'),
    ]
    for keyword, company in priority_rules:
        if keyword in name_lower:
            return company
    return "未知"


def rank_to_score(rank: int) -> float:
    """根据排名转换为分数"""
    if rank <= 10:
        return 98.0 - (rank - 1) * 0.5
    elif rank <= 50:
        return 93.0 - (rank - 10) * 0.5
    elif rank <= 100:
        return 73.0 - (rank - 50) * 0.35
    elif rank <= 200:
        return 55.5 - (rank - 100) * 0.2
    else:
        return 35.5 - (rank - 200) * 0.1


def generate_dimensions(model_name: str, overall_rank: int) -> List[Dict]:
    """生成各维度数据"""
    base_score = rank_to_score(overall_rank)
    random.seed(hash(model_name) + 42)

    min_score = 10
    data = []
    for dim in DIMENSIONS:
        if dim == "数学能力":
            adj = random.uniform(-5, 3)
        elif dim == "代码生成":
            adj = random.uniform(-4, 4)
        elif dim == "多语言能力":
            adj = random.uniform(-3, 2)
        elif dim == "安全性":
            adj = random.uniform(-2, 5)
        else:
            adj = random.uniform(-3, 3)
        score = max(min_score, min(100, base_score + adj))

        data.append({
            "model": model_name,
            "company": extract_company(model_name),
            "category": classify_model(model_name),
            "dimension": dim,
            "score": round(score, 2),
            "timestamp": datetime.now().isoformat(),
            "source": "LMSYS Arena"
        })
    return data


class ModelCrawler:
    """模型爬虫类"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.data = []

    @safe_operation
    def crawl_lmarena(self) -> List[Dict]:
        data = []
        try:
            resp = self.session.get("https://lmarena.ai/leaderboard", timeout=TIMEOUT)
            soup = BeautifulSoup(resp.text, 'html.parser')

            all_arenas = self._extract_all_arenas(soup)

            if all_arenas:
                # Text-like arenas use dimension scores
                TEXT_ARENAS = {'text', 'code', 'vision', 'document', 'search', 'image-to-code'}
                # Image/Video arenas have no dimension breakdown
                MEDIA_ARENAS = {'text-to-image', 'image-edit', 'text-to-video', 'image-to-video', 'video-to-video'}

                for arena_slug, entries in all_arenas.items():
                    if arena_slug in TEXT_ARENAS:
                        self._process_text_arena(entries, arena_slug, data)
                    elif arena_slug in MEDIA_ARENAS:
                        self._process_media_arena(entries, arena_slug, data)
            else:
                # Fallback: parse HTML table
                table = soup.find('table')
                if not table:
                    return data
                rows = table.find_all('tr')[1:]
                seen_models = set()
                for i, row in enumerate(rows):
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 3:
                        raw_name = cells[0].get_text(strip=True)
                        formatted_name = format_model_name(raw_name)
                        if formatted_name in seen_models:
                            continue
                        seen_models.add(formatted_name)
                        try:
                            overall_rank = int(cells[1].get_text(strip=True))
                        except (ValueError, IndexError):
                            overall_rank = i + 1
                        model_data = generate_dimensions(formatted_name, overall_rank)
                        for rec in model_data:
                            rec['arena'] = 'text'
                        data.extend(model_data)

        except Exception as e:
            logger.debug(f"爬取失败，回退到模拟数据: {e}")
            raise CrawlerException(f"爬取失败: {e}")
        return data

    def _process_text_arena(self, entries, arena_slug, data):
        """Process a text-type arena.

        Every arena is stored independently with its own models.
        - 'text' arena: generates 8-dimension baseline per model (original logic).
        - Other text arenas (code, document, etc.): each model gets one record
          with the arena's mapped dimension and rank-based score, PLUS its own
          rating/votes/etc.  These are NOT merged into text baseline anymore —
          each arena stands alone in the UI.
        """
        target_dim = ARENA_DIMENSION_MAP.get(arena_slug)
        seen_models = set()
        for entry in entries:
            raw_name = entry.get('modelDisplayName', '')
            formatted_name = format_model_name(raw_name)
            if formatted_name in seen_models:
                continue
            seen_models.add(formatted_name)

            rank = entry.get('rank', 0)
            rating = entry.get('rating', 0)
            votes = entry.get('votes', 0)
            org = entry.get('modelOrganization', '')
            license_type = entry.get('license', '')
            input_price = entry.get('inputPricePerMillion')
            output_price = entry.get('outputPricePerMillion')
            context_len = entry.get('contextLength')

            org_category = classify_by_org(org) if org else None
            category = org_category or classify_model(formatted_name)
            company = org or extract_company(formatted_name)

            common = {
                'company': company,
                'category': category,
                'rating': rating,
                'votes': votes,
                'license': license_type,
                'inputPricePerMillion': input_price,
                'outputPricePerMillion': output_price,
                'contextLength': context_len,
                'modelUrl': entry.get('modelUrl', ''),
                'arena': arena_slug,
                'source': 'LMSYS Arena',
            }

            if arena_slug == 'text':
                model_data = generate_dimensions(formatted_name, rank)
                for rec in model_data:
                    rec.update(common)
                data.extend(model_data)
            else:
                dim_label = target_dim or arena_slug
                score = rank_to_score(rank) if rank else rank_to_score(50)
                data.append({
                    'model': formatted_name,
                    'dimension': dim_label,
                    'score': round(score, 2),
                    'timestamp': datetime.now().isoformat(),
                    **common,
                })

    def _process_media_arena(self, entries, arena_slug, data):
        """Process an image/video arena (no dimension breakdown, just rank + rating)."""
        for entry in entries:
            raw_name = entry.get('modelDisplayName', '')
            formatted_name = format_model_name(raw_name)
            rank = entry.get('rank', 0)
            rating = entry.get('rating', 0)
            votes = entry.get('votes', 0)
            org = entry.get('modelOrganization', '')
            license_type = entry.get('license', '')
            input_price = entry.get('inputPricePerMillion')
            output_price = entry.get('outputPricePerMillion')
            context_len = entry.get('contextLength')

            # Use arena slug as the "dimension" for media models
            dimension_label = {
                'text-to-image': '文生图',
                'image-edit': '图片编辑',
                'text-to-video': '文生视频',
                'image-to-video': '图生视频',
                'video-to-video': '视频编辑',
            }.get(arena_slug, arena_slug)

            org_category = classify_by_org(org) if org else None
            category = org_category or classify_model(formatted_name)

            data.append({
                'model': formatted_name,
                'company': org or extract_company(formatted_name),
                'category': category,
                'dimension': dimension_label,
                'score': round(rank_to_score(rank) if rank else rank_to_score(50), 2),
                'rating': rating,
                'votes': votes,
                'license': license_type,
                'inputPricePerMillion': input_price,
                'outputPricePerMillion': output_price,
                'contextLength': context_len,
                'modelUrl': entry.get('modelUrl', ''),
                'arena': arena_slug,
                'timestamp': datetime.now().isoformat(),
                'source': 'LMSYS Arena',
            })

    def _extract_all_arenas(self, soup) -> Dict[str, List[Dict]]:
        """Extract all arena leaderboards from Next.js RSC payload.
        Returns dict mapping arena_slug -> list of model entries."""
        result = {}
        scripts = soup.find_all('script')
        for script in scripts:
            raw = str(script)
            if 'votes' not in raw or 'contextLength' not in raw:
                continue
            script_content = script.string or ''
            if not script_content:
                continue

            positions = [m.start() for m in re.finditer(r'entries', script_content)]
            for pos in positions:
                # Determine arena slug
                before = script_content[max(0, pos - 4000):pos]
                arena_matches = re.findall(r'arenaSlug[^a-zA-Z]*([a-z\-]+)', before)
                arena = arena_matches[-1] if arena_matches else None
                if not arena:
                    continue

                arr_start = script_content.find('[', pos)
                if arr_start < 0:
                    continue

                chunk = script_content[arr_start:arr_start + 500000]
                chunk = chunk.replace('\\"', '"')

                depth, end = 0, 0
                for j, c in enumerate(chunk):
                    if c == '[': depth += 1
                    elif c == ']':
                        depth -= 1
                        if depth == 0: end = j; break

                try:
                    entries = json.loads(chunk[:end + 1])
                    # Only keep first occurrence per arena
                    if arena not in result and isinstance(entries, list) and entries:
                        result[arena] = entries
                except (json.JSONDecodeError, ValueError):
                    continue
        return result

    @safe_operation
    def crawl_with_progress(self, progress_callback=None) -> List[Dict]:
        if progress_callback:
            progress_callback(0, "开始爬取...")
        try:
            if progress_callback:
                progress_callback(30, "正在连接...")
            data = self.crawl_lmarena()
            if progress_callback:
                progress_callback(100, f"完成，共{len(data)}条")
            return data
        except Exception as e:
            if progress_callback:
                progress_callback(0, f"失败: {e}")
            raise


def get_latest_models(minimum_rows: int = 1, fallback_to_simulated: bool = True) -> List[Dict]:
    """获取最新模型数据 - 优先使用爬虫，失败时返回模拟数据"""
    crawler = ModelCrawler()
    try:
        data = crawler.crawl_lmarena()
        if data and len(data) >= minimum_rows:
            return data
    except Exception:
        pass
    return get_simulated_data() if fallback_to_simulated else []


def get_simulated_data() -> List[Dict]:
    """生成模拟数据（含 Score/Votes/Price/Context/License）"""
    random.seed(42)
    min_score = 10

    models = [
        ("DeepSeek-V3", "深度求索", "domestic", 92.5, 1400, "MIT", 0.27, 1.10, 131072),
        ("通义千问2.5", "阿里巴巴", "domestic", 89.8, 1350, "Apache 2.0", 0.50, 2.00, 131072),
        ("Kimi K1.5", "月之暗面", "domestic", 88.3, 1100, "Modified MIT", 2.50, 8.00, 131072),
        ("豆包Pro", "字节跳动", "domestic", 86.5, 980, "Proprietary", 0.50, 2.00, 128000),
        ("智谱清言GLM-4", "智谱AI", "domestic", 85.9, 920, "Apache 2.0", 0.70, 2.80, 128000),
        ("文心一言4.0", "百度", "domestic", 84.2, 860, "Proprietary", 2.00, 8.00, 128000),
        ("讯飞星火V4.0", "科大讯飞", "domestic", 82.7, 750, "Proprietary", 1.50, 6.00, 32768),
        ("商量SenseChat", "商汤科技", "domestic", 81.4, 680, "Apache 2.0", 1.00, 4.00, 32768),
        ("GPT-4o", "OpenAI", "international", 94.5, 1600, "Proprietary", 2.50, 10.00, 128000),
        ("Claude 3.5 Sonnet", "Anthropic", "international", 92.8, 1520, "Proprietary", 3.00, 15.00, 200000),
        ("Gemini 2.0 Flash", "Google", "international", 93.2, 1550, "Proprietary", 0.10, 0.40, 1048576),
        ("o1", "OpenAI", "international", 95.1, 1650, "Proprietary", 15.00, 60.00, 200000),
        ("LLaMA 3.1", "Meta", "international", 89.3, 1300, "MIT", 0.00, 0.00, 131072),
        ("Mistral Large", "Mistral AI", "international", 87.6, 1200, "Proprietary", 2.00, 6.00, 128000),
        ("Grok 2", "xAI", "international", 85.8, 1050, "Proprietary", 5.00, 15.00, 131072),
    ]

    data = []
    for model_name, company, category, base, rating, license_type, input_price, output_price, context_len in models:
        for dim in DIMENSIONS:
            adj = random.uniform(-2, 3)
            data.append({
                "model": model_name,
                "company": company,
                "category": category,
                "dimension": dim,
                "score": round(max(min_score, min(100, base + adj)), 2),
                "rating": rating,
                "votes": random.randint(5000, 40000),
                "license": license_type,
                "inputPricePerMillion": input_price,
                "outputPricePerMillion": output_price,
                "contextLength": context_len,
                "arena": "text",
                "timestamp": datetime.now().isoformat(),
                "source": "simulated"
            })
    return data
