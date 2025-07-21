# AI DAG Code Auditor
# Iterates on DAG Files in S3 and uses Llama 3.2 to identify possible problems.
# Generates both a structured JSON data file and a visual HTML report.

import os
import html
import json
import argparse
from pathlib import Path
from typing import List, Optional, Dict
import requests
from .data_reader import list_py_files, read_file
from .dag_utils import extract_dag_ids_from_code

DEFAULT_S3_DAGS_DIR = "s3://buff-analytics-dags/dags/"

class OllamaClient:
    """
    # OllamaClient
    # Facilitates interaction with a local or network-accessible Ollama instance for LLM inference.
    # Abstracts API calls and handles environment-based host detection (e.g., Docker).
    # Essential for integrating LLM capabilities into automated code review.
    """
    def __init__(self, model: str = "llama3.2", host: Optional[str] = None):
        """
        # Initializes the Ollama client. Auto-detects host for Docker or local setup.
        """
        if host is None:
            if "DOCKER_INTERNAL_HOST" in os.environ:
                host = "http://host.docker.internal:11434"
            else:
                host = "http://localhost:11434"
        self.model = model
        self.host = host
        print(f"🤖 Ollama client configured to connect to: {self.host}")

    def ask(self, prompt: str, system_prompt: str) -> dict:
        """
        # Sends a prompt to Ollama, expecting a JSON response.
        # Uses `format: "json"` to ensure structured output for programmatic parsing.
        # Includes robust error handling for LLM non-JSON responses.
        """
        response = requests.post(f"{self.host}/api/generate", json={
            "model": self.model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": False,
            "format": "json"
        }, timeout=300)
        try:
            response_data = response.json()
            return json.loads(response_data.get("response", "{}"))
        except (json.JSONDecodeError, AttributeError) as e:
            raw_text = response.text
            print(f"Error parsing AI response: {e}. Raw text: {raw_text[:500]}...")
            return {"error": "Unable to parse AI response", "raw": raw_text}

def analyze_dag_code(file_path: Path, code: str, client: OllamaClient, dag_id: str) -> dict:
    """
    # Orchestrates AI analysis for a single Airflow DAG.
    # Constructs a precise prompt to guide the LLM's output into a structured JSON format.
    # Ensures specific focus on one DAG_ID even if multiple are present in the file.
    """
    prompt = (
        "You are an expert in Apache Airflow and Python development.\n\n"
        f"Focus your analysis on the DAG with dag_id='{dag_id}'. "
        "If there are multiple DAGs in the file, analyze only this one.\n\n"
        "Carefully analyze the following DAG source code and provide:\n"
        "1. A clear summary of what the DAG does (max 5 lines).\n"
        "2. Identification of potential issues or bad practices (e.g. missing retries, hardcoded paths, improper scheduling, deprecated operators, lack of docstrings, etc.).\n"
        "3. A risk level: LOW, MEDIUM, or HIGH.\n"
        "4. Practical suggestions to improve the DAG, including a sample code fix if applicable.\n\n"
        "Return your answer strictly in the following JSON format:\n\n"
        "{\n"
        '  "dag_id": string or null,\n'
        '  "summary": string,\n'
        '  "problems": [list of strings],\n'
        '  "risk_level": "LOW" | "MEDIUM" | "HIGH",\n'
        '  "suggestion": string,\n'
        '  "code_fix": string or null\n'
        "}\n\n"
        f"Code to analyze:\n```python\n{code}\n```"
    )

    system_prompt = "You are an experienced code reviewer for Airflow DAGs. Be concise but accurate. Return only a valid JSON object."

    ai_result = client.ask(prompt, system_prompt)
    ai_result["dag_id"] = dag_id  # Force correct dag_id for data integrity.
    return ai_result

def save_results_as_json(results: List[Dict], output_file: str):
    """
    # Saves audit results to a JSON file.
    # Provides a machine-readable output for further automated processing or integration.
    """
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    print(f"💾 Structured audit data saved to: {output_path}")


def generate_html(results: List[dict], output_path: str):
    """
    # Generates a human-readable HTML report from audit results.
    # Includes basic styling for readability and visual risk level cues.
    # Critical for easy consumption by stakeholders without coding knowledge.
    """
    html_content = """<html><head><title>AI DAG Code Audit</title>
    <style>
    body { font-family: Arial; padding: 20px; background: #f9f9f9; }
    h1 { color: #333; }
    .dag { border: 1px solid #ccc; padding: 15px; margin: 10px 0; background: #fff; border-radius: 6px; }
    .risk-HIGH { border-left: 5px solid red; }
    .risk-MEDIUM { border-left: 5px solid orange; }
    .risk-LOW { border-left: 5px solid green; }
    .summary { font-style: italic; margin: 10px 0; color: #555; }
    .problems ul { padding-left: 20px; } .problems li { color: #d9534f; }
    .suggestion { color: #0275d8; margin-top: 10px; }
    pre { background: #eee; padding: 10px; border-radius: 4px; overflow-x: auto; white-space: pre-wrap; word-wrap: break-word; }
    </style></head><body>
    <h1>🧠 AI DAG Code Audit Report</h1>
    """

    for result in results:
        # Sanitize and format problems list for HTML.
        problems_list = result.get("problems", [])
        if not isinstance(problems_list, list): problems_list = []
        problems_html = "<ul>" + "".join(f"<li>{html.escape(p)}</li>" for p in problems_list) + "</ul>"

        # Handle various formats of 'code_fix' (str, list, dict) for robustness.
        code_fix_raw = result.get("code_fix")
        code_fix_text = "" 
        if isinstance(code_fix_raw, str): code_fix_text = code_fix_raw
        elif isinstance(code_fix_raw, list): code_fix_text = "\n".join(map(str, code_fix_raw))
        elif isinstance(code_fix_raw, dict): code_fix_text = json.dumps(code_fix_raw, indent=2)
        elif code_fix_raw is not None: code_fix_text = str(code_fix_raw)

        # Handle 'suggestion' which might also be a list or string.
        suggestion_val = result.get("suggestion", "")
        suggestion_text = "\n".join(suggestion_val) if isinstance(suggestion_val, list) else str(suggestion_val)
        
        fix_html = f"<pre>{html.escape(code_fix_text)}</pre>" if code_fix_text else ""

        # Construct and append HTML for each DAG's audit result.
        html_content += f"""
        <div class='dag risk-{result.get("risk_level", "UNKNOWN")}'>
            <h2>📄 {html.escape(result.get("filename", "unknown"))} (DAG ID: {html.escape(str(result.get("dag_id", "unknown")))})</h2>
            <div class='summary'><strong>🧠 Summary:</strong> {html.escape(result.get("summary", "No summary provided."))}</div>
            <div class='problems'><strong>Identified Problems:</strong>{problems_html}</div>
            <div class='suggestion'><strong>💡 Suggestion:</strong> {html.escape(suggestion_text)}</div>
            {fix_html}
        </div>"""

    html_content += "</body></html>"

    # Encode with surrogateescape for robust character handling.
    sanitized_html = html_content.encode('utf-8', errors='surrogateescape').decode('utf-8')
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(sanitized_html, encoding='utf-8')
    print(f"🎨 HTML report generated at {output_path}")


def main():
    """
    # Main script entry point.
    # Parses arguments, orchestrates file scanning, AI analysis, and report generation.
    # Designed for flexible execution in development or CI/CD pipelines.
    """
    parser = argparse.ArgumentParser(description="AI DAG Code Audit using Llama 3.2")
    parser.add_argument("--dags-dir", type=str, default=DEFAULT_S3_DAGS_DIR, help="S3 path containing DAG Python files (e.g. s3://bucket/prefix)")
    parser.add_argument("--output", type=str, default="reports/dag_ai_audit", help="Output file base name (creates .html and .json)")
    parser.add_argument("--max", type=int, default=100, help="Max number of DAG files to analyze")
    args = parser.parse_args()
    
    output_base = Path(args.output)
    html_output_file = output_base.with_suffix('.html')
    json_output_file = output_base.with_suffix('.json')

    print(f"[INFO] Scanning S3 DAGs from: {args.dags_dir}")

    client = OllamaClient()
    dag_paths = list_py_files(args.dags_dir)
    results = []

    # Iterate and analyze DAG files, respecting the --max limit.
    for dag_path in dag_paths[:args.max]:
        print(f"🔍 Analyzing: {dag_path}")
        code = read_file(dag_path)
        file_name = dag_path.split("/")[-1]

        dag_ids_in_file = extract_dag_ids_from_code(code)
        if not dag_ids_in_file:
            print(f"   -> No DAGs found in {file_name}")
            continue

        # Analyze each DAG ID found within the file individually.
        for dag_id in dag_ids_in_file:
            print(f"      -> Analyzing DAG: {dag_id}")
            result = analyze_dag_code(Path(file_name), code, client, dag_id)
            result["filename"] = file_name
            results.append(result)

    # Save final results.
    save_results_as_json(results, str(json_output_file))
    generate_html(results, str(html_output_file))

if __name__ == "__main__":
    main()
