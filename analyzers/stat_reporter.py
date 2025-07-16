#!/usr/bin/env python3
"""
DAG Statistics Reporter (CloudWatch, Task-Logs Only)
Generates both a structured JSON data file and a visual HTML report.
"""

import argparse
import html
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
import json
import boto3

def find_task_log_groups(prefix: str):
    """Find only the log groups for task logs: names starting with prefix and ending with '-Task'"""
    logs = boto3.client("logs")
    paginator = logs.get_paginator("describe_log_groups")
    matched = []
    print(f"Detecting log groups with prefix: '{prefix}' and suffix '-Task'")
    for page in paginator.paginate(logGroupNamePrefix=prefix):
        for lg in page.get("logGroups", []):
            name = lg["logGroupName"]
            if name.startswith(prefix) and name.endswith("-Task"):
                matched.append(name)
    print(f"Auto-detected {len(matched)} TASK log groups.")
    return matched

def fetch_cloudwatch_events(log_groups, start_time, end_time, max_events=20000):
    logs = boto3.client("logs")
    all_events = []
    for lg in log_groups:
        print(f"→ Fetching from: {lg}")
        next_token, fetched = None, 0
        while True:
            kwargs = {
                "logGroupName": lg, "startTime": int(start_time.timestamp() * 1000),
                "endTime": int(end_time.timestamp() * 1000), "limit": min(10000, max_events - fetched),
            }
            if next_token: kwargs["nextToken"] = next_token
            resp = logs.filter_log_events(**kwargs)
            batch = resp.get("events", [])
            all_events.extend(batch)
            fetched += len(batch)
            next_token = resp.get("nextToken")
            if not next_token or fetched >= max_events:
                print(f"   ...fetched {fetched} events.")
                break
    return all_events

def parse_events(events):
    from .dag_utils import extract_info_from_log_stream
    stats = defaultdict(lambda: {
        "task_success": 0, "task_failed": 0, "task_attempts": 0,
        "tasks": defaultdict(lambda: {"success":0, "failed":0, "attempts":0, "durations":[], "errors":[]}),
        "first_run": None, "last_run": None,
    })

    task_ok_re = re.compile(r"Marking task as SUCCESS|Task exited with return code 0")
    task_fail_re = re.compile(r"Marking task as FAILED|Task exited with return code [^0]|Traceback")
    
    for ev in events:
        msg = ev["message"]
        ts = datetime.fromtimestamp(ev["timestamp"] / 1000)
        dag, task, _ = extract_info_from_log_stream(ev.get("logStreamName",""))
        if dag == "unknown": continue

        dag_stats = stats[dag]
        dag_stats["first_run"] = min(dag_stats["first_run"], ts) if dag_stats["first_run"] else ts
        dag_stats["last_run"] = max(dag_stats["last_run"], ts) if dag_stats["last_run"] else ts
        
        if task_ok_re.search(msg):
            dag_stats["task_success"] += 1
            dag_stats["tasks"][task]["success"] += 1
        elif task_fail_re.search(msg):
            dag_stats["task_failed"] += 1
            dag_stats["tasks"][task]["failed"] += 1
            dag_stats["tasks"][task]["errors"].append(msg.splitlines()[0])

    final = {}
    for dag, d in stats.items():
        total_runs = d["task_success"] + d["task_failed"]
        mft, mfc = "N/A", 0
        for t, v in d["tasks"].items():
            if v["failed"] > mfc: mft, mfc = t, v["failed"]
        
        final[dag] = {
            "DAG_ID": dag, "Total_Runs": total_runs,
            "Success_Rate": round((d["task_success"] / total_runs * 100), 2) if total_runs > 0 else 0.0,
            "Total_Failures": d["task_failed"], "P95_Duration": "N/A", # Placeholder
            "Last_Run": d["last_run"].strftime("%Y-%m-%d %H:%M") if d["last_run"] else "N/A",
            "Most_Failing_Task": mft,
        }
    return final

def save_stats_as_json(stats_data: dict, output_file: str):
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(stats_data, f, indent=2)
    print(f"💾 Structured stats data saved to: {output_path}")

def generate_html_report(stats_data: dict, output: Path):
    print(f"🎨 Writing HTML report to: {output}")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    headers = ["DAG_ID", "Total_Runs", "Success_Rate", "Total_Failures", "P95_Duration", "Last_Run", "Most_Failing_Task"]
    header_html = "".join(f"<th>{html.escape(h.replace('_', ' '))}</th>" for h in headers)
    rows_html = ""
    for row in sorted(stats_data.values(), key=lambda x: x["Total_Failures"], reverse=True):
        rows_html += "<tr>" + "".join(f"<td>{html.escape(str(row.get(h, 'N/A')))}</td>" for h in headers) + "</tr>\n"

    html_doc = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>DAG Stats Report</title>
<style>
  body {{ font-family:sans-serif; background:#f8f9fa; padding:20px; }} h1 {{ color:#212529; }}
  table {{ width:100%; border-collapse:collapse; margin-top:20px; }} th,td {{ padding:10px; border:1px solid #ddd; text-align:left; }}
  th {{ background:#333; color:#fff; }} tr:nth-child(even) {{ background:#eee; }}
</style></head><body>
  <h1>📊 DAG Stats from Task Logs</h1><p><strong>Generated:</strong> {now}</p>
  <table><thead><tr>{header_html}</tr></thead><tbody>{rows_html}</tbody></table>
</body></html>"""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(html_doc, encoding="utf-8")
    print(f"✅ HTML Report saved: {output.resolve()}")

def main():
    parser = argparse.ArgumentParser(description="DAG Stats Reporter (Task-Logs Only)")
    parser.add_argument("--log-group-prefix", "-p", default="airflow-", help="Prefix for log groups")
    parser.add_argument("--output", "-o", default="reports/dag_stats", help="Output file base name (creates .html and .json)")
    parser.add_argument("--hours", type=int, default=48, help="Look back hours")
    parser.add_argument("--max-events", type=int, default=20000, help="Max events per group")
    args = parser.parse_args()

    output_base = Path(args.output)
    html_output_file = output_base.with_suffix('.html')
    json_output_file = output_base.with_suffix('.json')
    
    groups = find_task_log_groups(args.log_group_prefix)
    if not groups:
        print(f"❌ No Task log groups found with prefix '{args.log_group_prefix}'.")
        return

    end, start = datetime.now(), datetime.now() - timedelta(hours=args.hours)
    events = fetch_cloudwatch_events(groups, start, end, args.max_events)
    print(f"🔎 Total events fetched: {len(events)}")
    stats = parse_events(events)
    if stats:
        save_stats_as_json(stats, str(json_output_file))
        generate_html_report(stats, html_output_file)
    else:
        print("⚠️ No task-log statistics to report.")

if __name__ == "__main__":
    main()