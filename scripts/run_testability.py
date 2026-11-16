"""Run the untestable-phrasing detector against the real 86-requirement
texts (expect 0 flagged) and against the seeded 10-of-86 vague-rewrite
corpus (expect exactly the 10 seeded keys, 0 false positives). Run:
    venv\\Scripts\\python.exe scripts\\run_testability.py > docs\\testability_output.txt
Read-only: does not mutate data/trace.db or domain_data.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trace_workbench.testability import main

if __name__ == "__main__":
    main()
