#!/bin/bash
# 大语言模型评测分析系统启动脚本

set -e

cd "$(dirname "$0")"

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "正在创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
source venv/bin/activate

# 检查依赖
echo "检查依赖..."
pip install -q requests beautifulsoup4 matplotlib numpy 2>/dev/null || true

echo "启动系统..."
cd llm_eval_system
python app.py
