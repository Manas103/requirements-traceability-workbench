"""Regenerate data/trace.db from scratch. Run:
    venv\\Scripts\\python.exe scripts\\build_db.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trace_workbench.seed import main

if __name__ == "__main__":
    main("data/trace.db")
