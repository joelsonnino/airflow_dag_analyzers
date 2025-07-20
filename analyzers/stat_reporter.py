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
    """
    Finds CloudWatch log groups that match a given prefix and end with '-Task',
    which is a common naming convention for Airflow task logs.
    """
    logs = boto3.client("logs")
    paginator = logs.get_paginator("describe_log_groups")
    matched = []
    print(f"Detecting log groups with prefix: '{prefix}' and suffix '-Task'")
    # Iterate through paginated results to get all matching log groups
    for page in paginator.paginate(logGroupNamePrefix=prefix):
        for lg in page.get("logGroups", []):
            name = lg["logGroupName"]
            if name.startswith(prefix) and name.endswith("-Task"):
                matched.append(name)
    print(f"Auto-detected {len(matched)} TASK log groups.")
    return matched

def fetch_cloudwatch_events(log_groups, start_time, end_time, max_events=20000):
    """
    Fetches log events from specified CloudWatch log groups within a given time range.
    Uses pagination to handle large numbers of events efficiently.
    """
    logs = boto3.client("logs")
    all_events = []
    for lg in log_groups:
        print(f"→ Fetching from: {lg}")
        next_token, fetched = None, 0
        while True:
            # Prepare arguments for filter_log_events API call
            kwargs = {
                "logGroupName": lg,
                "startTime": int(start_time.timestamp() * 1000), # Convert datetime to milliseconds timestamp
                "endTime": int(end_time.timestamp() * 1000),     # Convert datetime to milliseconds timestamp
                "limit": min(10000, max_events - fetched),       # Max 10000 events per call, respect overall max_events
            }
            if next_token: kwargs["nextToken"] = next_token # Use next_token for pagination
            
            resp = logs.filter_log_events(**kwargs)
            batch = resp.get("events", [])
            all_events.extend(batch)
            fetched += len(batch)
            next_token = resp.get("nextToken")
            
            # Break loop if no more pages or max events limit reached
            if not next_token or fetched >= max_events:
                print(f"   ...fetched {fetched} events.")
                break
    return all_events

def parse_events(events):
    """
    Parses raw CloudWatch log events to extract DAG and task-level statistics.
    Identifies task success/failure based on log messages.
    """
    # Import dag_utils dynamically to avoid circular dependencies if this module is imported elsewhere
    from .dag_utils import extract_info_from_log_stream
    
    # Use defaultdict to easily initialize nested dictionaries for DAG and task stats
    stats = defaultdict(lambda: {
        "task_success": 0, "task_failed": 0, "task_attempts": 0,
        "tasks": defaultdict(lambda: {"success":0, "failed":0, "attempts":0, "durations":[], "errors":[]}),
        "first_run": None, "last_run": None,
    })

    # Regex patterns to identify success and failure messages in logs
    task_ok_re = re.compile(r"Marking task as SUCCESS|Task exited with return code 0")
    task_fail_re = re.compile(r"Marking task as FAILED|Task exited with return code [^0]|Traceback")
    
    for ev in events:
        msg = ev["message"]
        ts = datetime.fromtimestamp(ev["timestamp"] / 1000)
        # Extract DAG, task, and run IDs from the log stream name using a utility function
        dag, task, _ = extract_info_from_log_stream(ev.get("logStreamName",""))
        if dag == "unknown": continue # Skip events from unparsable log streams

        dag_stats = stats[dag]
        # Update first and last run timestamps for the DAG
        dag_stats["first_run"] = min(dag_stats["first_run"], ts) if dag_stats["first_run"] else ts
        dag_stats["last_run"] = max(dag_stats["last_run"], ts) if dag_stats["last_run"] else ts
        
        # Categorize event as success or failure based on regex
        if task_ok_re.search(msg):
            dag_stats["task_success"] += 1
            dag_stats["tasks"][task]["success"] += 1
        elif task_fail_re.search(msg):
            dag_stats["task_failed"] += 1
            dag_stats["tasks"][task]["failed"] += 1
            # Store the first line of the error message for context
            dag_stats["tasks"][task]["errors"].append(msg.splitlines()[0])

    # Final aggregation and calculation of derived metrics
    final = {}
    for dag, d in stats.items():
        total_runs = d["task_success"] + d["task_failed"]
        mft, mfc = "N/A", 0 # Most failing task and its failure count
        for t, v in d["tasks"].items():
            if v["failed"] > mfc: mft, mfc = t, v["failed"]
        
        final[dag] = {
            "DAG_ID": dag,
            "Total_Runs": total_runs,
            "Success_Rate": round((d["task_success"] / total_runs * 100), 2) if total_runs > 0 else 0.0,
            "Total_Failures": d["task_failed"],
            "P95_Duration": "N/A", # Placeholder for future duration calculation
            "Last_Run": d["last_run"].strftime("%Y-%m-%d %H:%M") if d["last_run"] else "N/A",
            "Most_Failing_Task": mft,
        }
    return final

def save_stats_as_json(stats_data: dict, output_file: str):
    """Saves the aggregated statistics data to a JSON file."""
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True) # Ensure output directory exists
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(stats_data, f, indent=2) # Pretty-print JSON for readability
    print(f"💾 Structured stats data saved to: {output_path}")

def generate_html_report(stats_data: dict, output: Path):
    """Generates a simple HTML report visualizing the DAG statistics."""
    print(f"🎨 Writing HTML report to: {output}")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Define headers for the HTML table, ensuring consistent order
    headers = ["DAG_ID", "Total_Runs", "Success_Rate", "Total_Failures", "P95_Duration", "Last_Run", "Most_Failing_Task"]
    header_html = "".join(f"<th>{html.escape(h.replace('_', ' '))}</th>" for h in headers)
    rows_html = ""
    # Sort DAGs by total failures in descending order for easier review
    for row in sorted(stats_data.values(), key=lambda x: x["Total_Failures"], reverse=True):
        rows_html += "<tr>" + "".join(f"<td>{html.escape(str(row.get(h, 'N/A')))}</td>" for h in headers) + "</tr>\n"

    # Construct the full HTML document
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
    output.parent.mkdir(parents=True, exist_ok=True) # Ensure output directory exists
    output.write_text(html_doc, encoding="utf-8")
    print(f"✅ HTML Report saved: {output.resolve()}")

def main():
    """Main function to run the DAG statistics reporter."""
    parser = argparse.ArgumentParser(description="DAG Stats Reporter (Task-Logs Only)")
    parser.add_argument("--log-group-prefix", "-p", default="airflow-", help="Prefix for CloudWatch log groups, e.g., 'airflow-prod-'")
    parser.add_argument("--output", "-o", default="reports/dag_stats", help="Output file base name (creates .html and .json)")
    parser.add_argument("--hours", type=int, default=48, help="Look back period for logs in hours")
    parser.add_argument("--max-events", type=int, default=20000, help="Maximum log events to fetch from CloudWatch per log group")
    args = parser.parse_args()

    output_base = Path(args.output)
    html_output_file = output_base.with_suffix('.html')
    json_output_file = output_base.with_suffix('.json')
    
    # Discover relevant CloudWatch log groups
    groups = find_task_log_groups(args.log_group_prefix)
    if not groups:
        print(f"❌ No Task log groups found with prefix '{args.log_group_prefix}'. Exiting.")
        return

    # Define the time window for fetching logs
    end, start = datetime.now(), datetime.now() - timedelta(hours=args.hours)
    
    # Fetch log events and parse them into structured statistics
    events = fetch_cloudwatch_events(groups, start, end, args.max_events)
    print(f"🔎 Total events fetched: {len(events)}")
    stats = parse_events(events)
    
    # Save statistics and generate HTML report if data is available
    if stats:
        save_stats_as_json(stats, str(json_output_file))
        generate_html_report(stats, html_output_file)
    else:
        print("⚠️ No task-log statistics to report.")

if __name__ == "__main__":
    main()