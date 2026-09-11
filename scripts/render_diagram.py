"""Generate docs/traceability_slice.dot (and, if a `dot` binary is
reachable, docs/traceability_slice.png). Run:
    venv\\Scripts\\python.exe scripts\\render_diagram.py
"""
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trace_workbench.db import connect
from trace_workbench.diagram import build_dot


def main():
    conn = connect("data/trace.db")
    dot_source = build_dot(conn)
    Path("docs").mkdir(exist_ok=True)
    dot_path = Path("docs/traceability_slice.dot")
    dot_path.write_text(dot_source, encoding="utf-8")
    print(f"wrote {dot_path} ({len(dot_source)} bytes)")

    png_path = Path("docs/traceability_slice.png")
    if shutil.which("dot"):
        subprocess.run(["dot", "-Tpng", str(dot_path), "-o", str(png_path)], check=True)
        print(f"rendered {png_path}")
    else:
        # This Windows machine does not have a `dot` binary on PATH; the
        # committed .dot file is the deliverable and can be rendered with
        # any Graphviz install (or WSL2's, per this project's toolchain)
        # via: dot -Tpng docs/traceability_slice.dot -o docs/traceability_slice.png
        print("no `dot` binary on PATH; committing .dot source only, see README")
    conn.close()


if __name__ == "__main__":
    main()
