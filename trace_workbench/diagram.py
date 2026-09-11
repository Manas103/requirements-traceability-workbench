"""Graphviz traceability diagram for a representative slice of the tree.

Renders User Need -> Requirement -> (Test | Risk Control) for two user
need subtrees (air-column detection and occlusion detection) rather than
all 14, because a 14-need, 86-requirement, 75-test, 43-risk-control
graph in one image is not something a human reviewer could actually
read; a legible slice that shows every edge type (decomposition,
verification, risk-control implementation, and a suspect edge) is more
useful documentation than a technically-complete but illegible wall
graph. The full graph can be produced by passing include_all=True.
"""
from __future__ import annotations


def _esc(text: str) -> str:
    return text.replace('"', '\\"')


def build_dot(conn, user_need_keys=("un_air", "un_occlusion"), include_all=False) -> str:
    lines = ["digraph traceability {", '  rankdir=LR;', '  node [fontname="Helvetica"];']

    if include_all:
        un_rows = conn.execute("SELECT id, key, text FROM user_needs ORDER BY id").fetchall()
    else:
        placeholders = ",".join("?" * len(user_need_keys))
        un_rows = conn.execute(
            f"SELECT id, key, text FROM user_needs WHERE key IN ({placeholders}) ORDER BY id",
            list(user_need_keys),
        ).fetchall()

    for un in un_rows:
        lines.append(
            f'  "{un["key"]}" [shape=box, style=filled, fillcolor="#cfe8ff", '
            f'label="USER NEED\\n{_esc(un["text"][:60])}..."];'
        )
        reqs = conn.execute(
            "SELECT id, key, text, suspect FROM requirements WHERE user_need_id = ? ORDER BY id",
            (un["id"],),
        ).fetchall()
        for req in reqs:
            _emit_requirement_subtree(conn, lines, req, un["key"])

    lines.append("}")
    return "\n".join(lines)


def _emit_requirement_subtree(conn, lines, req, parent_dot_key):
    color = "#ffd6d6" if req["suspect"] else "#e8ffd6"
    lines.append(
        f'  "req_{req["key"]}" [shape=box, style=filled, fillcolor="{color}", '
        f'label="{req["key"]}\\n{_esc(req["text"][:50])}..."];'
    )
    edge_style = ' [color=red, style=dashed, label="suspect"]' if req["suspect"] else ""
    lines.append(f'  "{parent_dot_key}" -> "req_{req["key"]}"{edge_style};')

    for t in conn.execute(
        "SELECT t.key AS key, t.result AS result, rt.suspect AS suspect "
        "FROM requirement_tests rt JOIN tests t ON t.id = rt.test_id "
        "WHERE rt.requirement_id = ?",
        (req["id"],),
    ).fetchall():
        tcolor = "#ffd6d6" if t["suspect"] else ("#d6ffd6" if t["result"] == "pass" else "#ffb3b3")
        lines.append(
            f'  "test_{t["key"]}" [shape=ellipse, style=filled, fillcolor="{tcolor}", '
            f'label="TEST\\n{t["key"]}\\nresult={t["result"]}"];'
        )
        tstyle = ' [color=red, style=dashed]' if t["suspect"] else ""
        lines.append(f'  "req_{req["key"]}" -> "test_{t["key"]}"{tstyle};')

    for rc in conn.execute(
        "SELECT rc.key AS key, rrc.suspect AS suspect "
        "FROM requirement_risk_controls rrc JOIN risk_controls rc ON rc.id = rrc.risk_control_id "
        "WHERE rrc.requirement_id = ?",
        (req["id"],),
    ).fetchall():
        rcolor = "#ffd6d6" if rc["suspect"] else "#e8d6ff"
        lines.append(
            f'  "rc_{rc["key"]}" [shape=hexagon, style=filled, fillcolor="{rcolor}", '
            f'label="RISK CONTROL\\n{rc["key"]}"];'
        )
        rstyle = ' [color=red, style=dashed]' if rc["suspect"] else ""
        lines.append(f'  "req_{req["key"]}" -> "rc_{rc["key"]}"{rstyle};')

    children = conn.execute(
        "SELECT id, key, text, suspect FROM requirements WHERE parent_id = ? ORDER BY id",
        (req["id"],),
    ).fetchall()
    for child in children:
        _emit_requirement_subtree(conn, lines, child, f'req_{req["key"]}')
