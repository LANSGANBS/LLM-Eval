"""
数据可视化模块
使用matplotlib和seaborn进行数据可视化
"""

import matplotlib.pyplot as plt
import matplotlib
import seaborn as sns
import numpy as np
from typing import List, Dict, Optional
import logging

from config import EVALUATION_DIMENSIONS

logger = logging.getLogger(__name__)

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


class Visualizer:
    """数据可视化类 - 面向对象设计"""
    
    def __init__(self):
        self.color_palette = [
            '#e74c3c', '#3498db', '#2ecc71', '#f39c12', 
            '#9b59b6', '#1abc9c', '#e67e22', '#34495e'
        ]
        
    def plot_radar_chart(self, data: List[Dict], title: str = "模型能力雷达图"):
        """绘制雷达图"""
        try:
            fig, ax = plt.subplots(figsize=(10, 8), subplot_kw=dict(projection='polar'))
            
            dimensions = EVALUATION_DIMENSIONS
            num_vars = len(dimensions)
            angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
            angles += angles[:1]  # 闭合
            
            for i, model_data in enumerate(data[:5]):  # 最多显示5个模型
                values = [model_data.get(dim, 0) for dim in dimensions]
                values += values[:1]  # 闭合
                
                ax.plot(angles, values, 'o-', linewidth=2, 
                       label=model_data['model'], 
                       color=self.color_palette[i % len(self.color_palette)])
                ax.fill(angles, values, alpha=0.15,
                       color=self.color_palette[i % len(self.color_palette)])
            
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(dimensions, fontsize=10)
            ax.set_ylim(0, 100)
            ax.set_yticks([20, 40, 60, 80, 100])
            ax.set_yticklabels(['20', '40', '60', '80', '100'], fontsize=8)
            ax.grid(True)
            ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
            
            plt.title(title, fontsize=14, fontweight='bold', pad=20)
            plt.tight_layout()
            
            return fig
            
        except Exception as e:
            logger.error(f"绘制雷达图失败: {e}")
            raise
    
    def plot_bar_chart(self, data: List[Dict], title: str = "模型评分对比", 
                      xlabel: str = "模型", ylabel: str = "分数"):
        """绘制柱状图"""
        try:
            fig, ax = plt.subplots(figsize=(12, 6))
            
            models = [item['model'] for item in data]
            scores = [item['score'] for item in data]
            
            bars = ax.bar(models, scores, color=self.color_palette[:len(models)])
            
            # 添加数值标签
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:.1f}', ha='center', va='bottom')
            
            ax.set_xlabel(xlabel, fontsize=12)
            ax.set_ylabel(ylabel, fontsize=12)
            ax.set_title(title, fontsize=14, fontweight='bold')
            ax.set_ylim(0, 100)
            ax.grid(axis='y', alpha=0.3)
            
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()
            
            return fig
            
        except Exception as e:
            logger.error(f"绘制柱状图失败: {e}")
            raise
    
    def plot_heatmap(self, data: List[Dict], title: str = "模型能力热力图"):
        """绘制热力图"""
        try:
            # 构建数据矩阵
            models = list(set(item['model'] for item in data))
            dimensions = EVALUATION_DIMENSIONS
            
            matrix = np.zeros((len(models), len(dimensions)))
            for i, model in enumerate(models):
                for j, dim in enumerate(dimensions):
                    score_data = [item['score'] for item in data 
                                 if item['model'] == model and item['dimension'] == dim]
                    if score_data:
                        matrix[i, j] = score_data[0]
            
            fig, ax = plt.subplots(figsize=(12, 8))
            
            sns.heatmap(matrix, annot=True, fmt='.1f', 
                       xticklabels=dimensions, yticklabels=models,
                       cmap='YlOrRd', ax=ax, cbar_kws={'label': '分数'})
            
            ax.set_title(title, fontsize=14, fontweight='bold')
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()
            
            return fig
            
        except Exception as e:
            logger.error(f"绘制热力图失败: {e}")
            raise
    
    def plot_line_chart(self, data: List[Dict], title: str = "模型评分趋势"):
        """绘制折线图"""
        try:
            fig, ax = plt.subplots(figsize=(12, 6))
            
            # 按模型分组
            models = {}
            for item in data:
                model = item['model']
                if model not in models:
                    models[model] = []
                models[model].append(item)
            
            for i, (model, items) in enumerate(models.items()):
                items.sort(key=lambda x: x.get('timestamp', ''))
                x = range(len(items))
                y = [item['score'] for item in items]
                
                ax.plot(x, y, marker='o', linewidth=2, 
                       label=model, color=self.color_palette[i % len(self.color_palette)])
            
            ax.set_xlabel('评测次数', fontsize=12)
            ax.set_ylabel('分数', fontsize=12)
            ax.set_title(title, fontsize=14, fontweight='bold')
            ax.legend()
            ax.grid(True, alpha=0.3)
            
            plt.tight_layout()
            return fig
            
        except Exception as e:
            logger.error(f"绘制折线图失败: {e}")
            raise
    
    def plot_pie_chart(self, data: List[Dict], title: str = "模型分布"):
        """绘制饼图"""
        try:
            fig, ax = plt.subplots(figsize=(8, 8))
            
            models = [item['model'] for item in data]
            scores = [item['score'] for item in data]
            
            # 计算占比
            total = sum(scores)
            sizes = [score/total * 100 for score in scores]
            
            ax.pie(sizes, labels=models, autopct='%1.1f%%', 
                  colors=self.color_palette[:len(models)], startangle=90)
            ax.set_title(title, fontsize=14, fontweight='bold')
            
            plt.tight_layout()
            return fig
            
        except Exception as e:
            logger.error(f"绘制饼图失败: {e}")
            raise
    
    def plot_box_plot(self, data: List[Dict], title: str = "分数分布箱线图"):
        """绘制箱线图"""
        try:
            fig, ax = plt.subplots(figsize=(10, 6))
            
            # 按模型分组
            models = {}
            for item in data:
                model = item['model']
                if model not in models:
                    models[model] = []
                models[model].append(item['score'])
            
            # 准备数据
            box_data = [scores for scores in models.values()]
            labels = list(models.keys())
            
            ax.boxplot(box_data, labels=labels)
            ax.set_xlabel('模型', fontsize=12)
            ax.set_ylabel('分数', fontsize=12)
            ax.set_title(title, fontsize=14, fontweight='bold')
            ax.grid(axis='y', alpha=0.3)
            
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()
            return fig
            
        except Exception as e:
            logger.error(f"绘制箱线图失败: {e}")
            raise
    
    def plot_comparison_chart(self, domestic_data: List[Dict], 
                             international_data: List[Dict],
                             title: str = "国内外模型对比"):
        """绘制国内外对比图"""
        try:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
            
            # 国内模型
            if domestic_data:
                models_d = [item['model'] for item in domestic_data]
                scores_d = [item['score'] for item in domestic_data]
                ax1.bar(models_d, scores_d, color='#e74c3c')
                ax1.set_title('国内模型', fontsize=12, fontweight='bold')
                ax1.set_ylabel('分数')
                ax1.tick_params(axis='x', rotation=45)
                ax1.grid(axis='y', alpha=0.3)
            
            # 国际模型
            if international_data:
                models_i = [item['model'] for item in international_data]
                scores_i = [item['score'] for item in international_data]
                ax2.bar(models_i, scores_i, color='#3498db')
                ax2.set_title('国际模型', fontsize=12, fontweight='bold')
                ax2.set_ylabel('分数')
                ax2.tick_params(axis='x', rotation=45)
                ax2.grid(axis='y', alpha=0.3)
            
            plt.suptitle(title, fontsize=14, fontweight='bold')
            plt.tight_layout()
            return fig
            
        except Exception as e:
            logger.error(f"绘制对比图失败: {e}")
            raise
    
    def save_figure(self, fig, filename: str):
        """保存图表"""
        try:
            fig.savefig(filename, dpi=300, bbox_inches='tight')
            logger.info(f"图表已保存: {filename}")
        except Exception as e:
            logger.error(f"保存图表失败: {e}")
            raise
