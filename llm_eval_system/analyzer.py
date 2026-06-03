"""
数据分析与评测模块
涉及：序列操作、函数、面向对象、数据分析
"""

import json
import logging
import statistics
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime

from config import EVALUATION_DIMENSIONS
from database import DatabaseManager

logger = logging.getLogger(__name__)


@dataclass
class EvaluationScore:
    """评测分数数据类"""
    model_name: str
    category: str  # 'domestic' 或 'international'
    dimension: str
    score: float
    timestamp: str = ""
    details: Dict = None
    
    def __post_init__(self):
        if self.details is None:
            self.details = {}


class LLMEvaluator:
    """LLM评测器 - 面向对象设计"""
    
    def __init__(self, db: DatabaseManager = None):
        self.db = db
        self.evaluation_data: List[EvaluationScore] = []
        
    def add_evaluation(self, model_name: str, category: str, 
                      dimension: str, score: float, 
                      details: Dict = None) -> EvaluationScore:
        """添加评测数据"""
        evaluation = EvaluationScore(
            model_name=model_name,
            category=category,
            dimension=dimension,
            score=score,
            timestamp=datetime.now().isoformat(),
            details=details
        )
        self.evaluation_data.append(evaluation)
        return evaluation
    
    def calculate_dimension_stats(self, dimension: str) -> Dict:
        """计算某个维度的统计信息"""
        scores = [e.score for e in self.evaluation_data 
                 if e.dimension == dimension]
        
        if not scores:
            return {}
        
        return {
            "dimension": dimension,
            "count": len(scores),
            "mean": round(statistics.mean(scores), 2),
            "median": round(statistics.median(scores), 2),
            "std": round(statistics.stdev(scores), 2) if len(scores) > 1 else 0,
            "min": min(scores),
            "max": max(scores)
        }
    
    def compare_models(self, model1: str, model2: str) -> Dict:
        """比较两个模型的表现"""
        model1_data = [e for e in self.evaluation_data 
                      if e.model_name == model1]
        model2_data = [e for e in self.evaluation_data 
                      if e.model_name == model2]
        
        comparison = {
            "model1": model1,
            "model2": model2,
            "dimensions": {}
        }
        
        for dim in EVALUATION_DIMENSIONS:
            m1_score = next((e.score for e in model1_data 
                           if e.dimension == dim), None)
            m2_score = next((e.score for e in model2_data 
                           if e.dimension == dim), None)
            
            if m1_score and m2_score:
                comparison["dimensions"][dim] = {
                    "model1_score": m1_score,
                    "model2_score": m2_score,
                    "difference": round(m1_score - m2_score, 2),
                    "winner": model1 if m1_score > m2_score else model2
                }
        
        return comparison
    
    def get_category_comparison(self) -> Dict:
        """获取国内外模型分类对比"""
        domestic_scores = [e.score for e in self.evaluation_data 
                          if e.category == 'domestic']
        international_scores = [e.score for e in self.evaluation_data 
                                 if e.category == 'international']
        
        return {
            "domestic": {
                "count": len(domestic_scores),
                "mean": round(statistics.mean(domestic_scores), 2) if domestic_scores else 0,
                "median": round(statistics.median(domestic_scores), 2) if domestic_scores else 0
            },
            "international": {
                "count": len(international_scores),
                "mean": round(statistics.mean(international_scores), 2) if international_scores else 0,
                "median": round(statistics.median(international_scores), 2) if international_scores else 0
            }
        }
    
    def get_top_models(self, dimension: str = None, 
                      limit: int = 5) -> List[Dict]:
        """获取排名前几的模型"""
        if dimension:
            data = [e for e in self.evaluation_data 
                   if e.dimension == dimension]
        else:
            # 计算每个模型的平均分
            model_scores = {}
            for e in self.evaluation_data:
                if e.model_name not in model_scores:
                    model_scores[e.model_name] = []
                model_scores[e.model_name].append(e.score)
            
            result = []
            for model, scores in model_scores.items():
                result.append({
                    "model": model,
                    "score": round(statistics.mean(scores), 2)
                })
            
            result.sort(key=lambda x: x["score"], reverse=True)
            return result[:limit]
        
        data.sort(key=lambda x: x.score, reverse=True)
        return [{"model": e.model_name, "score": e.score} 
                for e in data[:limit]]
    
    def get_model_dimensions(self, model_name: str) -> Dict[str, float]:
        """获取某个模型各维度的分数"""
        return {e.dimension: e.score for e in self.evaluation_data 
                if e.model_name == model_name}
    
    def get_models_by_category(self, category: str) -> List[str]:
        """获取某个分类下的所有模型"""
        return list(set(e.model_name for e in self.evaluation_data 
                       if e.category == category))
    
    def get_dimension_ranking(self, dimension: str) -> List[Dict]:
        """获取某个维度的排名"""
        data = [e for e in self.evaluation_data if e.dimension == dimension]
        data.sort(key=lambda x: x.score, reverse=True)
        return [{"model": e.model_name, "category": e.category, "score": e.score} 
                for e in data]
    
    def generate_evaluation_report(self) -> str:
        """生成评测报告"""
        report = []
        report.append("=" * 60)
        report.append("大语言模型评测分析报告")
        report.append(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("=" * 60)
        
        # 总体统计
        report.append("\n【总体统计】")
        report.append(f"评测模型数: {len(set(e.model_name for e in self.evaluation_data))}")
        report.append(f"评测维度数: {len(set(e.dimension for e in self.evaluation_data))}")
        report.append(f"总评测次数: {len(self.evaluation_data)}")
        
        # 各维度统计
        report.append("\n【各维度统计】")
        for dim in EVALUATION_DIMENSIONS:
            stats = self.calculate_dimension_stats(dim)
            if stats:
                report.append(f"\n{dim}:")
                report.append(f"  平均分: {stats['mean']}")
                report.append(f"  中位数: {stats['median']}")
                report.append(f"  标准差: {stats['std']}")
        
        # 分类对比
        report.append("\n【国内外对比】")
        category_stats = self.get_category_comparison()
        report.append(f"国内模型平均分: {category_stats['domestic']['mean']}")
        report.append(f"国际模型平均分: {category_stats['international']['mean']}")
        
        # Top模型
        report.append("\n【Top 5 模型】")
        top_models = self.get_top_models(limit=5)
        for i, model in enumerate(top_models, 1):
            report.append(f"{i}. {model['model']}: {model['score']}")
        
        report.append("\n" + "=" * 60)
        
        return "\n".join(report)
    
    def load_from_database(self):
        """从数据库加载评测数据"""
        try:
            if not self.db:
                logger.warning("数据库未初始化，跳过加载")
                return
            evaluations = self.db.get_all_evaluations_with_models()
            for eval_data in evaluations:
                self.add_evaluation(
                    model_name=eval_data['model_name'],
                    category=eval_data['category'],
                    dimension=eval_data['dimension'],
                    score=eval_data['score']
                )
            logger.info(f"从数据库加载了 {len(evaluations)} 条评测数据")
        except Exception as e:
            logger.error(f"从数据库加载数据失败: {e}")
            raise
    
    def save_to_database(self):
        """保存评测数据到数据库"""
        try:
            if not self.db:
                logger.warning("数据库未初始化，跳过保存")
                return
            for eval_score in self.evaluation_data:
                self.db.insert_evaluation(
                    model_id=0,  # 简化处理
                    dimension=eval_score.dimension,
                    score=eval_score.score,
                    test_data=eval_score.details
                )
            logger.info("评测数据已保存到数据库")
        except Exception as e:
            logger.error(f"保存数据到数据库失败: {e}")
            raise


class DataProcessor:
    """数据处理工具类"""
    
    @staticmethod
    def normalize_scores(scores: List[float], 
                        method: str = "minmax") -> List[float]:
        """分数归一化"""
        if not scores:
            return []
        
        if method == "minmax":
            min_val, max_val = min(scores), max(scores)
            if max_val == min_val:
                return [0.5] * len(scores)
            return [(s - min_val) / (max_val - min_val) * 100 
                   for s in scores]
        
        elif method == "zscore":
            mean = statistics.mean(scores)
            std = statistics.stdev(scores) if len(scores) > 1 else 1
            return [(s - mean) / std for s in scores]
        
        return scores
    
    @staticmethod
    def filter_outliers(scores: List[float], 
                       threshold: float = 2.0) -> List[float]:
        """过滤异常值"""
        if len(scores) < 3:
            return scores
        
        mean = statistics.mean(scores)
        std = statistics.stdev(scores)
        
        return [s for s in scores 
                if abs(s - mean) <= threshold * std]
    
    @staticmethod
    def calculate_percentile(scores: List[float], 
                            value: float) -> float:
        """计算百分位数"""
        if not scores:
            return 0.0
        
        sorted_scores = sorted(scores)
        count = len(sorted_scores)
        
        # 找到第一个大于等于value的位置
        for i, score in enumerate(sorted_scores):
            if score >= value:
                return (i / count) * 100
        
        return 100.0
