from __future__ import annotations

from pathlib import Path
import html
import duckdb
import pandas as pd
import plotly.express as px


def _read_gold(gold_paths: list[str]) -> pd.DataFrame:
    frames = []
    for path in gold_paths:
        source = Path(path)
        if not source.exists():
            raise FileNotFoundError(source)
        frames.append(pd.read_parquet(source))
    return pd.concat(frames, ignore_index=True, sort=False)


def _chart_sections(frame: pd.DataFrame) -> str:
    sections = []
    for column in frame.select_dtypes(include="number").columns:
        if column in {"record_id", "source_count"}:
            continue
        chart = px.histogram(frame, x=column, title=f"Distribution of {column}")
        sections.append(
            f"<section><h2>{html.escape(column.title())}</h2>"
            f"{chart.to_html(full_html=False, include_plotlyjs=False)}</section>"
        )
    return "".join(sections) or "<p>No numeric Gold measures were available for charting.</p>"


def create_report(gold_paths: list[str], output_path: str | Path, narrative: str = "") -> str:
    if not gold_paths:
        raise ValueError("No Gold inputs available for reporting")
    frame = _read_gold(gold_paths)
    conn = duckdb.connect()
    conn.register("gold_data", frame)
    summary = conn.execute(
        "SELECT COUNT(*) AS records, COUNT(DISTINCT record_id) AS distinct_records FROM gold_data"
    ).fetchone()
    numeric = [column for column in frame.select_dtypes(include="number").columns if column != "source_count"]
    metric_rows = []
    for column in numeric:
        identifier = '"' + column.replace('"', '""') + '"'
        metrics = conn.execute(
            f"SELECT SUM({identifier}), AVG({identifier}), MIN({identifier}), MAX({identifier}) FROM gold_data"
        ).fetchone()
        metric_rows.append(
            f"<tr><td>{html.escape(column)}</td><td>{metrics[0]}</td><td>{metrics[1]}</td>"
            f"<td>{metrics[2]}</td><td>{metrics[3]}</td></tr>"
        )
    metric_table = "".join(metric_rows) or "<tr><td colspan='5'>No numeric measures</td></tr>"
    chart_html = _chart_sections(frame)
    report = f"""<!doctype html>
<html><head><meta charset='utf-8'><title>Retail Executive Report</title>
<script src='https://cdn.plot.ly/plotly-2.35.2.min.js'></script></head>
<body><main><h1>Retail Executive Report</h1>
<p>{html.escape(narrative or 'Evidence-based summary generated from approved Gold data.')}</p>
<h2>Data coverage</h2><p>Approved Gold records: <strong>{int(summary[0])}</strong>; distinct records: <strong>{int(summary[1])}</strong></p>
<h2>Numeric evidence</h2><table><thead><tr><th>Measure</th><th>Total</th><th>Average</th><th>Minimum</th><th>Maximum</th></tr></thead>
<tbody>{metric_table}</tbody></table>{chart_html}</main></body></html>"""
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(report, encoding="utf-8")
    conn.close()
    return str(destination)
