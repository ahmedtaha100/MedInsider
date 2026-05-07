"""HTML chart renderer for clinician labeling.

Renders a scenario's patient state and action log as a self-contained HTML
page that clinician labelers can review in a browser. No external dependencies
— generates static HTML with inline CSS.
"""

import html
import json
from pathlib import Path
from typing import Any


def render_patient_state(state: dict[str, Any]) -> str:
    """Render patient state as an HTML section."""
    if not state:
        return "<p><em>No patient data available in chart.</em></p>"

    parts: list[str] = []

    demographics = state.get("demographics") or {}
    if demographics:
        parts.append("<h3>Demographics</h3><ul>")
        for k, v in sorted(demographics.items()):
            parts.append(f"<li><strong>{html.escape(str(k))}:</strong> {html.escape(str(v))}</li>")
        parts.append("</ul>")

    problems = state.get("problems") or {}
    if problems:
        parts.append("<h3>Active Problems</h3><ul>")
        for code, status in sorted(problems.items()):
            parts.append(f"<li><code>{html.escape(code)}</code>: {html.escape(str(status))}</li>")
        parts.append("</ul>")

    vital_signs = state.get("vital_signs") or {}
    if vital_signs:
        parts.append("<h3>Vital Signs</h3><ul>")
        for k, v in sorted(vital_signs.items()):
            parts.append(f"<li><strong>{html.escape(str(k))}:</strong> {html.escape(str(v))}</li>")
        parts.append("</ul>")

    labs = state.get("labs") or {}
    if labs:
        parts.append("<h3>Labs</h3><ul>")
        for k, v in sorted(labs.items()):
            parts.append(f"<li><strong>{html.escape(str(k))}:</strong> {html.escape(str(v))}</li>")
        parts.append("</ul>")

    notes = state.get("notes") or []
    if notes:
        parts.append("<h3>Existing Notes</h3>")
        for note in notes:
            note_id = html.escape(str(note.get("note_id", "")))
            section = html.escape(str(note.get("section", "")))
            text = html.escape(str(note.get("text", "")))
            parts.append(f'<div class="note"><strong>[{note_id}] {section}:</strong> {text}</div>')

    adverse_events = state.get("adverse_events") or []
    if adverse_events:
        parts.append("<h3>Adverse Events</h3><ul>")
        for event in adverse_events:
            eid = html.escape(str(event.get("event_id", "")))
            detail = html.escape(str(event.get("detail", "")))
            parts.append(f"<li><code>{eid}</code>: {detail}</li>")
        parts.append("</ul>")

    inbox_messages = state.get("inbox_messages") or []
    if inbox_messages:
        parts.append("<h3>Inbox Messages</h3>")
        for msg in inbox_messages:
            sender = html.escape(str(msg.get("from", "")))
            subject = html.escape(str(msg.get("subject", "")))
            body = html.escape(str(msg.get("body", "")))
            msg_type = html.escape(str(msg.get("type", "")))
            parts.append(
                f'<div class="note"><strong>[{msg_type}] From: {sender}</strong><br><em>{subject}</em><br>{body}</div>'
            )

    orders = state.get("orders") or []
    if orders:
        parts.append("<h3>Existing Orders</h3><ul>")
        for order in orders:
            parts.append(f"<li>{html.escape(json.dumps(order))}</li>")
        parts.append("</ul>")

    discharge_text = state.get("discharge_plan_text", "")
    if discharge_text:
        parts.append(f"<h3>Discharge Plan</h3><p>{html.escape(str(discharge_text))}</p>")

    return "\n".join(parts) if parts else "<p><em>No patient data available in chart.</em></p>"


def render_action_log(logs: list[dict[str, Any]]) -> str:
    """Render an action log as an HTML table."""
    if not logs:
        return "<p><em>No actions recorded.</em></p>"

    rows: list[str] = []
    rows.append("""
    <table>
    <thead><tr>
        <th>#</th><th>Tool</th><th>Params</th><th>OK</th><th>Result Summary</th>
    </tr></thead><tbody>""")

    for i, entry in enumerate(logs, 1):
        tool = html.escape(str(entry.get("tool_name", "")))
        params = html.escape(json.dumps(entry.get("params", {}), indent=2))
        result = entry.get("result") or {}
        ok = result.get("ok", False)
        ok_class = "ok" if ok else "fail"
        ok_text = "Yes" if ok else "No"

        result_summary = ""
        data = result.get("data") or {}
        if isinstance(data, dict):
            for key in ["text", "plan_text", "message", "metric", "code", "status"]:
                if key in data:
                    result_summary = html.escape(str(data[key]))
                    break
            if not result_summary and data:
                result_summary = html.escape(json.dumps(data, indent=2))
        if not result_summary and result.get("error"):
            result_summary = html.escape(str(result["error"]))

        rows.append(
            f"<tr><td>{i}</td><td><code>{tool}</code></td>"
            f"<td><details><summary>params</summary><pre>{params}</pre></details></td>"
            f'<td class="{ok_class}">{ok_text}</td>'
            f"<td><details><summary>result</summary><pre>{result_summary}</pre></details></td></tr>"
        )

    rows.append("</tbody></table>")
    return "\n".join(rows)


def render_scenario_html(
    scenario: dict[str, Any],
    logs: list[dict[str, Any]] | None = None,
    include_metadata: bool = False,
) -> str:
    """Render a complete scenario as a self-contained HTML page."""
    episode_id = html.escape(str(scenario.get("episode_id", "unknown")))
    family = html.escape(str(scenario.get("scenario_family", "")))
    condition = html.escape(str(scenario.get("condition", "")))

    state = scenario.get("patient_state") or {}
    state_html = render_patient_state(state)

    log_html = render_action_log(logs) if logs is not None else "<p><em>No action log provided.</em></p>"

    metadata_html = ""
    if include_metadata:
        meta = scenario.get("metadata") or {}
        metadata_html = f"""
        <div class="metadata">
        <h2>Scenario Metadata (Admin Only)</h2>
        <ul>
            <li><strong>Family:</strong> {family}</li>
            <li><strong>Condition:</strong> {condition}</li>
            <li><strong>Alignment:</strong> {html.escape(str(scenario.get("alignment_label", "")))}</li>
            <li><strong>Pair ID:</strong> {html.escape(str(meta.get("pair_id", "")))}</li>
            <li><strong>Twin Role:</strong> {html.escape(str(meta.get("twin_role", "")))}</li>
        </ul>
        </div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MedInsider Chart Review: {episode_id}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       max-width: 900px; margin: 0 auto; padding: 20px; color: #333; }}
h1 {{ color: #1a5276; border-bottom: 2px solid #1a5276; padding-bottom: 8px; }}
h2 {{ color: #2c3e50; margin-top: 24px; }}
h3 {{ color: #34495e; }}
code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }}
pre {{ white-space: pre-wrap; word-wrap: break-word; font-size: 0.85em; }}
table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; font-size: 0.85em;
          overflow-wrap: break-word; }}
th {{ background: #f8f9fa; font-weight: 600; }}
tr:nth-child(even) {{ background: #fafafa; }}
.ok {{ color: #27ae60; font-weight: bold; }}
.fail {{ color: #e74c3c; font-weight: bold; }}
.note {{ background: #fef9e7; border-left: 3px solid #f39c12; padding: 8px 12px; margin: 8px 0; }}
.metadata {{ background: #fdedec; border: 1px solid #e74c3c; padding: 12px; margin-top: 20px;
             border-radius: 4px; }}
.metadata h2 {{ color: #e74c3c; margin-top: 0; }}
ul {{ padding-left: 20px; }}
li {{ margin: 4px 0; }}
details {{ cursor: pointer; }}
summary {{ color: #2980b9; }}
</style>
</head>
<body>
<h1>Chart Review: {episode_id}</h1>

<h2>Patient Chart</h2>
{state_html}

<h2>Agent Actions</h2>
{log_html}

{metadata_html}

<footer style="margin-top: 40px; padding-top: 12px; border-top: 1px solid #ddd;
               color: #888; font-size: 0.8em;">
MedInsider Benchmark — Clinician Labeling Interface
</footer>
</body>
</html>"""


def render_scenario_to_file(
    scenario: dict[str, Any],
    output_path: str,
    logs: list[dict[str, Any]] | None = None,
    include_metadata: bool = False,
) -> None:
    """Render a scenario to an HTML file."""
    html_content = render_scenario_html(scenario, logs, include_metadata)
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html_content, encoding="utf-8")
