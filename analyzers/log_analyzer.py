#!/usr/bin/env python3
"""
# DAG Log Analyzer AI Agent - CloudWatch version
# This script analyzes Airflow DAG logs from AWS CloudWatch,
# leveraging a Llama 3.2 model (via Ollama) to identify errors and suggest fixes.
# It outputs structured JSON for programmatic consumption and a visual HTML report.
"""

import os
import json
import re
import argparse
from pathlib import Path
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
import requests
import boto3
from dataclasses import dataclass, asdict
from collections import defaultdict
import html
from concurrent.futures import ThreadPoolExecutor, as_completed

# Assuming these are local utility modules
from .dag_utils import extract_info_from_log_stream


@dataclass
class LogError:
    """
    # LogError Data Class
    # Standardized structure to hold parsed information about a single log error.
    # Enables easy serialization and passing between components.
    """
    dag_name: str
    task_name: str
    execution: str
    file_name: str
    error_line: str
    line_number: int
    error_type: str
    context_lines: List[str]


@dataclass
class ErrorAnalysis:
    """
    # ErrorAnalysis Data Class
    # Encapsulates the AI's analysis for a specific `LogError`.
    # Designed for structured storage and reporting of AI insights.
    """
    error: LogError
    category: str
    severity: str # e.g., "HIGH", "MEDIUM", "LOW"
    suggestion: str
    code_fix: Optional[str] = None
    documentation_links: Optional[List[str]] = None


class OllamaClient:
    """
    # OllamaClient
    # Manages communication with a locally running Ollama server for LLM inference.
    # Handles model availability checks and robust request handling.
    """
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2"):
        self.base_url = base_url
        self.model = model
        self.session = requests.Session()
    
    def is_available(self) -> bool:
        """
        # Checks Ollama server and specified model availability.
        # Crucial pre-flight check before attempting LLM analysis.
        """
        try:
            response = self.session.get(f"{self.base_url}/api/tags")
            if response.status_code == 200:
                models = response.json().get('models', [])
                return any(model['name'].startswith(self.model) for model in models)
            return False
        except requests.exceptions.RequestException:
            return False
    
    def generate(self, prompt: str, system_prompt: str = "") -> str:
        """
        # Sends a generation request to the Ollama model.
        # Specifies `format: "json"` to encourage structured output from the LLM,
        # which is vital for parsing AI responses programmatically.
        """
        try:
            payload = {
                "model": self.model, "prompt": prompt, "system": system_prompt,
                "stream": False, "format": "json", # Request JSON output directly
                "options": {"temperature": 0.1, "top_p": 0.9, "num_predict": 2048} # Tuned for structured, deterministic output
            }
            response = self.session.post(f"{self.base_url}/api/generate", json=payload, timeout=120)
            if response.status_code == 200:
                # Ollama's API wraps JSON in a 'response' field when stream=False
                return response.json().get('response', '')
            else:
                return f"Error: HTTP {response.status_code}"
        except requests.exceptions.RequestException as e:
            return f"Error connecting to Ollama: {str(e)}"


class DAGLogAnalyzer:
    """
    # DAGLogAnalyzer
    # Core class for extracting, classifying, and analyzing DAG errors.
    # Integrates with AWS CloudWatch and the OllamaClient for AI-driven insights.
    """
    def __init__(self, ollama_client: OllamaClient):
        self.ollama = ollama_client
        # Pre-defined common error patterns for initial classification.
        # This provides a baseline classification before detailed AI analysis.
        self.common_error_patterns = {
            r"ModuleNotFoundError": "IMPORT_ERROR", r"ImportError": "IMPORT_ERROR", r"ConnectionError": "CONNECTION_ERROR",
            r"TimeoutError": "TIMEOUT_ERROR", r"FileNotFoundError": "FILE_ERROR", r"PermissionError": "PERMISSION_ERROR",
            r"KeyError": "DATA_ERROR", r"ValueError": "DATA_ERROR", r"TypeError": "TYPE_ERROR", r"AttributeError": "ATTRIBUTE_ERROR",
            r"SyntaxError": "SYNTAX_ERROR", r"IndentationError": "SYNTAX_ERROR", r"NameError": "NAME_ERROR",
            r"UnboundLocalError": "NAME_ERROR", r"IndexError": "INDEX_ERROR", r"ZeroDivisionError": "MATH_ERROR",
            r"MemoryError": "RESOURCE_ERROR", r"DiskSpaceError": "RESOURCE_ERROR", r"DatabaseError": "DATABASE_ERROR",
            r"SQLAlchemy": "DATABASE_ERROR", r"psycopg2": "DATABASE_ERROR", r"Task failed": "TASK_FAILURE",
            r"Dag.*failed": "DAG_FAILURE", r"Broken DAG": "DAG_BROKEN", r"Missing.*dependency": "DEPENDENCY_ERROR"
        }
    
    def extract_errors_from_cloudwatch(
        self,
        log_group_name: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        max_events: int = 1000,
        filter_pattern: str = "ERROR"
    ) -> List[LogError]:
        """
        # Fetches error logs from AWS CloudWatch.
        # Iteratively queries logs, applies filters, and parses essential info like DAG/task/execution.
        # Scalable to large volumes of logs using pagination and event limits.
        """
        client = boto3.client("logs")
        if not start_time: start_time = datetime.now(timezone.utc) - timedelta(days=1)
        if not end_time: end_time = datetime.now(timezone.utc)
        start_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)
        
        print(f"⏳ Querying CloudWatch logs from '{log_group_name}' between {start_time} and {end_time}...")
        next_token, events, fetched = None, [], 0
        while True:
            kwargs = {
                "logGroupName": log_group_name, "startTime": start_ms, "endTime": end_ms,
                "limit": min(10000, max_events - fetched), "filterPattern": filter_pattern
            }
            if next_token: kwargs["nextToken"] = next_token
            response = client.filter_log_events(**kwargs)
            batch = response.get("events", [])
            events.extend(batch)
            fetched += len(batch)
            print(f"  -> {fetched} log events fetched...")
            next_token = response.get("nextToken")
            if not next_token or fetched >= max_events: break
        print(f"  => Found {len(events)} error log events with pattern '{filter_pattern}'.")

        errors: List[LogError] = []
        error_pattern = re.compile(r"\bERROR\b")

        for event in events:
            message = event["message"]
            log_stream = event.get("logStreamName", "")
            
            # Use utility for consistent parsing of log stream names
            dag_name, task_name, execution = extract_info_from_log_stream(log_stream)
            file_name = log_stream.split('/')[-1] if '/' in log_stream else log_stream
            
            lines = message.splitlines()
            for i, line in enumerate(lines):
                if error_pattern.search(line):
                    context = lines[max(0, i-2):i+3] # Capture surrounding lines for context
                    error_type = self._classify_error(line) # Initial classification
                    errors.append(
                        LogError(
                            dag_name=dag_name, task_name=task_name, execution=str(execution),
                            file_name=file_name, error_line=line, line_number=i+1,
                            error_type=error_type, context_lines=context
                        )
                    )
        return errors
    
    def _classify_error(self, error_line: str) -> str:
        """
        # Classifies error based on common regex patterns.
        # Provides a preliminary error type before LLM analysis.
        """
        for pattern, error_type in self.common_error_patterns.items():
            if re.search(pattern, error_line, re.IGNORECASE):
                return error_type
        return "GENERAL_ERROR"
    
    def analyze_error_with_ai(self, error: LogError) -> ErrorAnalysis:
        """
        # Sends a specific error (with context) to the LLM for detailed analysis.
        # Crafts a precise prompt to elicit structured JSON output, covering:
        # - Category, Severity, Root Cause, Solution Steps, Code Fix, Prevention Tips.
        # Implements robust parsing of LLM response, including Markdown JSON extraction.
        """
        system_prompt = """You are an expert Apache Airflow and Python developer specializing in debugging DAG errors. 
        Analyze the provided error and context. Your response MUST be a single, valid JSON object and nothing else.
        The JSON should contain: a root cause analysis, a list of solution steps, an optional code fix, and a list of prevention tips."""
        
        context_str = "\n".join([f"Line {i}: {line}" for i, line in enumerate(error.context_lines, start=max(1, error.line_number - 2))])
        
        prompt = f"""
        Analyze the following Airflow DAG error and provide a structured JSON response.

        DAG: {error.dag_name}
        Task: {error.task_name}
        Execution: {error.execution}
        Error Type: {error.error_type}
        Error Line: {error.error_line}
        
        Context:
        {context_str}
        
        Provide your analysis as a single, valid JSON object with ONLY the following keys:
        - "category": A brief error category (e.g., "Import Error", "Database Connection").
        - "severity": "HIGH", "MEDIUM", or "LOW".
        - "root_cause": A concise, one-sentence explanation of the primary problem.
        - "solution_steps": A list of actionable step-by-step strings to fix the issue.
        - "code_fix": A small, relevant code snippet showing the fix. Use null if not applicable.
        - "prevention_tips": A list of best practice strings to prevent this issue.
        """
        
        response_text = self.ollama.generate(prompt, system_prompt)
        
        ai_analysis = {}
        # Default suggestion if AI analysis fails or is malformed
        suggestion_text = f"AI analysis failed to generate a structured response. Raw output:\n\n{response_text}"
        code_fix_text, category, severity = None, error.error_type, 'MEDIUM'

        try:
            ai_analysis = json.loads(response_text)
        except json.JSONDecodeError:
            # Attempt to extract JSON from a markdown code block if direct parsing fails.
            print(f"⚠️ Failed to parse JSON directly for DAG {error.dag_name}. Attempting to extract from markdown.")
            match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
            if match:
                try: ai_analysis = json.loads(match.group(1))
                except json.JSONDecodeError: print(f"❌ Failed to parse extracted JSON for DAG {error.dag_name}")
            else: print(f"❌ Could not find a JSON block in the response for DAG {error.dag_name}")

        if ai_analysis:
            # Extract fields from parsed AI response
            category = ai_analysis.get('category', error.error_type)
            severity = ai_analysis.get('severity', 'MEDIUM')
            code_fix_text = ai_analysis.get('code_fix')
            
            # Format suggestion text for human readability in reports
            parts = []
            if 'root_cause' in ai_analysis and ai_analysis['root_cause']: parts.append(f"**Root Cause:** {ai_analysis['root_cause']}")
            if ai_analysis.get('solution_steps'): parts.append(f"**Recommended Solution:**\n" + "\n".join(f"  - {step}" for step in ai_analysis['solution_steps']))
            if ai_analysis.get('prevention_tips'): parts.append(f"**Prevention Tips:**\n" + "\n".join(f"  - {tip}" for tip in ai_analysis['prevention_tips']))
            
            if parts: suggestion_text = "\n\n".join(parts)
            else: suggestion_text = f"AI analysis provided a partial response. Raw JSON:\n{json.dumps(ai_analysis, indent=2)}"

        return ErrorAnalysis(error=error, category=category, severity=severity, suggestion=suggestion_text, code_fix=code_fix_text)
    
    def analyze_all_errors(self, errors: List[LogError], max_workers: int = 5) -> List[ErrorAnalysis]:
        """
        # Analyzes multiple errors in parallel using a ThreadPoolExecutor.
        # Improves performance significantly by concurrently calling the LLM API.
        # Critical for processing large batches of errors efficiently.
        """
        print(f"Analyzing {len(errors)} errors with AI (parallelized with {max_workers} workers)...")
        analyses = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_error = {executor.submit(self.analyze_error_with_ai, error): error for error in errors}
            for i, future in enumerate(as_completed(future_to_error), 1):
                error = future_to_error[future]
                try:
                    analysis = future.result()
                    analyses.append(analysis)
                    print(f"✅ [{i}/{len(errors)}] {error.dag_name}.{error.task_name} analyzed")
                except Exception as e:
                    print(f"❌ Error analyzing {error.dag_name}.{error.task_name}: {e}")
        return analyses

    def generate_summary_report(self, analyses: List[ErrorAnalysis]) -> str:
        """
        # Generates a high-level summary of all analyzed errors using the LLM.
        # Provides an executive overview, prioritizing recommendations and identifying systemic issues.
        # This is very useful for management or lead data scientists to get a quick health check.
        """
        if not analyses: return "No errors found to analyze."
        error_summary = defaultdict(list)
        dag_errors = defaultdict(int)
        for analysis in analyses:
            error_summary[analysis.category].append(analysis)
            dag_errors[analysis.error.dag_name] += 1
        
        summary_data = {
            "total_errors": len(analyses),
            "error_categories": {cat: len(errs) for cat, errs in error_summary.items()},
            "dags_with_errors": dict(dag_errors),
            "high_severity_count": sum(1 for a in analyses if a.severity == 'HIGH')
        }
        
        system_prompt = "You are an expert Airflow consultant. Analyze the error summary data and provide: 1. Overall assessment of the DAG health 2. Priority recommendations 3. Common patterns and systemic issues 4. Action plan for fixing errors. Be concise but insightful."
        prompt = f"Analyze this DAG error summary:\n\nTotal Errors: {summary_data['total_errors']}\nHigh Severity Errors: {summary_data['high_severity_count']}\n\nError Categories:\n{json.dumps(summary_data['error_categories'], indent=2)}\n\nDAGs with Errors:\n{json.dumps(summary_data['dags_with_errors'], indent=2)}\n\nProvide an executive summary with key insights and recommendations."
        return self.ollama.generate(prompt, system_prompt)

def save_analyses_as_json(analyses: List[ErrorAnalysis], output_file: str):
    """
    # Saves the detailed `ErrorAnalysis` objects to a JSON file.
    # Output is designed to be machine-readable for downstream automation or dashboarding.
    """
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    analyses_as_dict = [asdict(analysis) for analysis in analyses] # Convert dataclasses to dicts for JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(analyses_as_dict, f, indent=2)
    print(f"💾 Structured analysis data saved to: {output_path}")

def generate_analysis_html_report(analyses: List[ErrorAnalysis], summary: str, output_file: str):
    """
    # Generates a comprehensive HTML report with both the executive summary and
    # detailed analysis for each error. Designed for human readability and quick insights.
    """
    html_content = f"""<html><head><title>AI DAG Log Analysis Report</title>
    <style>
    body {{ font-family: Arial, sans-serif; padding: 20px; background: #f4f7f6; color: #333; }}
    h1, h2, h3 {{ color: #2c3e50; }}
    .summary-section {{ background: #e8f5e9; border-left: 5px solid #4CAF50; padding: 15px; margin-bottom: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
    .error-card {{ background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }}
    .error-card.severity-HIGH {{ border-left: 5px solid #e74c3c; }} /* Red */
    .error-card.severity-MEDIUM {{ border-left: 5px solid #f39c12; }} /* Orange */
    .error-card.severity-LOW {{ border-left: 5px solid #2ecc71; }} /* Green */
    pre {{ background: #ecf0f1; padding: 10px; border-radius: 5px; overflow-x: auto; white-space: pre-wrap; word-wrap: break-word; font-family: 'Courier New', monospace; font-size: 0.9em; }}
    .meta-data {{ font-size: 0.9em; color: #666; margin-bottom: 10px; }}
    .section-title {{ font-weight: bold; margin-top: 15px; margin-bottom: 5px; color: #34495e; }}
    ul {{ list-style-type: disc; margin-left: 20px; }}
    </style></head><body>
    <h1>🧠 AI DAG Log Analysis Report</h1>

    <div class="summary-section">
        <h2>Executive Summary</h2>
        <pre>{html.escape(summary)}</pre>
    </div>

    <h2>Detailed Error Analysis ({len(analyses)} Errors)</h2>
    """

    for analysis in analyses:
        error = analysis.error
        # Sanitize all potentially user-controlled or LLM-generated strings for HTML safety
        dag_name = html.escape(error.dag_name)
        task_name = html.escape(error.task_name)
        execution = html.escape(error.execution)
        file_name = html.escape(error.file_name)
        error_line = html.escape(error.error_line)
        error_type = html.escape(error.error_type)
        line_number = error.line_number
        context_lines_html = "<pre>" + html.escape("\n".join(error.context_lines)) + "</pre>"
        
        category = html.escape(analysis.category)
        severity = html.escape(analysis.severity)
        suggestion = html.escape(analysis.suggestion) # LLM output needs careful escaping
        
        code_fix_html = ""
        if analysis.code_fix:
            code_fix_html = f"<div class='section-title'>Suggested Code Fix:</div><pre>{html.escape(analysis.code_fix)}</pre>"

        html_content += f"""
        <div class="error-card severity-{severity}">
            <h3>🚨 {category} in {dag_name}.{task_name}</h3>
            <div class="meta-data">
                <strong>Severity:</strong> {severity} | 
                <strong>File:</strong> {file_name} | 
                <strong>Execution:</strong> {execution}
            </div>
            
            <div class="section-title">Error Details:</div>
            <pre>Line {line_number}: {error_line}</pre>
            
            <div class="section-title">Context Lines:</div>
            {context_lines_html}
            
            <div class="section-title">AI Analysis & Suggestions:</div>
            <pre>{suggestion}</pre>
            
            {code_fix_html}
        </div>
        """

    html_content += "</body></html>"

    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    # Using 'surrogateescape' for robust handling of any non-UTF-8 characters.
    Path(output_file).write_text(html_content.encode('utf-8', errors='surrogateescape').decode('utf-8'))
    print(f"🎨 HTML report generated: {output_file}")


def main():
    """
    # Main execution function for the DAG Log Analyzer.
    # Parses command-line arguments, initializes services,
    # and orchestrates the log extraction, AI analysis, and report generation.
    """
    parser = argparse.ArgumentParser(description="AI-powered DAG Log Analyzer")
    parser.add_argument("--log-group", "-g", default="airflow-Airflow-14-12-22-Task", help="CloudWatch log group name")
    parser.add_argument("--output", "-o", default="reports/log_analysis", help="Output file base name (will create .html and .json)")
    parser.add_argument("--model", "-m", default="llama3.2", help="Ollama model to use")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama server URL")
    parser.add_argument("--max-errors", type=int, default=200, help="Maximum errors to analyze")
    parser.add_argument("--hours", type=int, default=24, help="How many hours to look back in logs")
    parser.add_argument("--max-events", type=int, default=1000, help="Max CloudWatch log events to fetch")
    args = parser.parse_args()

    output_base = Path(args.output)
    html_output_file = output_base.with_suffix('.html')
    json_output_file = output_base.with_suffix('.json')

    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=args.hours)

    ollama = OllamaClient(args.ollama_url, args.model)
    print("🔍 Checking Ollama availability...")
    if not ollama.is_available():
        print(f"❌ Error: Ollama is not running or model '{args.model}' is not available.")
        return 1
    print("✅ Ollama is ready!")

    analyzer = DAGLogAnalyzer(ollama)
    print(f"📊 Extracting errors from CloudWatch log group '{args.log_group}'...")
    errors = analyzer.extract_errors_from_cloudwatch(
        log_group_name=args.log_group, start_time=start_time, end_time=end_time, max_events=args.max_events
    )

    if not errors:
        print("✅ No errors found in logs!")
        return 0
    print(f"Found {len(errors)} errors")

    if len(errors) > args.max_errors:
        print(f"⚠️ Limiting analysis to {args.max_errors} errors")
        errors = errors[:args.max_errors]

    analyses = analyzer.analyze_all_errors(errors)
    summary = analyzer.generate_summary_report(analyses)

    print("💾 Saving analysis results...")
    save_analyses_as_json(analyses, str(json_output_file))
    generate_analysis_html_report(analyses, summary, str(html_output_file))

    print(f"✅ Analysis complete! Data saved to: {json_output_file} and {html_output_file}")
    return 0

if __name__ == "__main__":
    exit(main())