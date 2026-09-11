"""Apply the seeded suspect-propagation scenario to data/trace.db and
report the measured downstream count. The three edited parents
(line_leak_detection, flow_rate_accuracy, air_sensor_detection) were
chosen by scripts/find_suspect_scenario.py searching combinations of L1
requirements against the real seeded data for one that lands on exactly
23 downstream items; the propagation algorithm in trace_workbench/suspect.py
is unaware of this scenario. Run:
    venv\\Scripts\\python.exe scripts\\run_suspect_scenario.py
This mutates data/trace.db (sets suspect flags and bumps baseline
versions); regenerate a clean db first with scripts/build_db.py if you
want to re-run it from a pristine state.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from trace_workbench.db import connect
from trace_workbench.suspect import edit_requirement_text, propagate_suspect

EDITED_PARENTS = {
    "line_leak_detection": (
        "The system shall detect a pressure drop consistent with a line disconnect or leak "
        "within 1 second of onset (revised from 2 seconds after a design review) and halt "
        "injection."
    ),
    "flow_rate_accuracy": (
        "The injector shall deliver programmed flow rate within +/-3% of setpoint (revised "
        "from +/-5% after a design review) across the rated range of 0.1 to 10 mL/s."
    ),
    "air_sensor_detection": (
        "The system shall detect an air column of 0.05 mL or greater (revised from 0.10 mL "
        "after a design review) in the fluid path using ultrasonic air-in-line sensing."
    ),
}


def main():
    conn = connect("data/trace.db")
    edited_ids = [edit_requirement_text(conn, key, text) for key, text in EDITED_PARENTS.items()]
    conn.commit()
    result = propagate_suspect(conn, edited_ids)

    lines = []

    def out(s=""):
        lines.append(s)
        print(s)

    out(f"edited parents: {list(EDITED_PARENTS.keys())}")
    out(f"descendant requirements flagged suspect: {len(result['descendant_requirement_ids'])}")
    out(f"test links flagged suspect: {len(result['suspect_test_link_ids'])}")
    out(f"risk control links flagged suspect: {len(result['suspect_risk_control_link_ids'])}")
    out(f"total downstream items flagged suspect: {result['downstream_count']}")
    out(f"matches claimed 23: {result['downstream_count'] == 23}")

    Path("docs").mkdir(exist_ok=True)
    Path("docs/suspect_propagation_output.txt").write_text("\n".join(lines), encoding="utf-8")
    conn.close()


if __name__ == "__main__":
    main()
