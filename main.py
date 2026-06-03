"""主程序入口"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from llm_eval_system.ui.main_window import main

if __name__ == "__main__":
    main()
