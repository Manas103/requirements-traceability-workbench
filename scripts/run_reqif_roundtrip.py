"""Export data/trace.db to ReqIF XML, reimport it into a fresh in-memory
db, and diff the two models. Run:
    venv\\Scripts\\python.exe scripts\\run_reqif_roundtrip.py
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trace_workbench.db import connect, SCHEMA
from trace_workbench.reqif_io import export_reqif, import_reqif, snapshot


def main():
    conn = connect("data/trace.db")
    Path("docs").mkdir(exist_ok=True)
    reqif_path = "docs/contrast_injector_requirements.reqif.xml"
    export_reqif(conn, reqif_path)

    reimport_conn = sqlite3.connect(":memory:")
    reimport_conn.row_factory = sqlite3.Row
    reimport_conn.executescript(SCHEMA)
    import_reqif(reqif_path, reimport_conn)

    original_snapshot = snapshot(conn)
    reimported_snapshot = snapshot(reimport_conn)

    lines = []

    def out(s=""):
        lines.append(s)
        print(s)

    size_bytes = Path(reqif_path).stat().st_size
    out(f"exported ReqIF file: {reqif_path} ({size_bytes} bytes)")

    lossless = original_snapshot == reimported_snapshot
    out(f"round trip lossless (original snapshot == reimported snapshot): {lossless}")

    if not lossless:
        for section in original_snapshot:
            if original_snapshot[section] != reimported_snapshot[section]:
                out(f"  MISMATCH in section: {section}")

    for section, data in original_snapshot.items():
        n = len(data) if hasattr(data, "__len__") else "?"
        out(f"  section '{section}': {n} items")

    Path("docs/reqif_roundtrip_output.txt").write_text("\n".join(lines), encoding="utf-8")
    conn.close()


if __name__ == "__main__":
    main()
