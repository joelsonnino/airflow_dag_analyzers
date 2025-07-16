#!/usr/bin/env python3
"""
Intelligent DAG Report Merger & Standalone HTML Generator
Merges reports, gets AI analysis, and injects the final data into an HTML template
to create a single, portable dashboard file with a unique daily timestamp.
"""

import os
import json
from pathlib import Path
import requests
from collections import defaultdict
from typing import Dict, List, Any, Optional
from datetime import datetime

# --- Configuration ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports"
TEMPLATE_HTML_PATH = PROJECT_ROOT / "dashboard_template.html"

# <<< MODIFIED: Define a directory for the daily reports
DAILY_REPORTS_OUTPUT_DIR = REPORTS_DIR / "daily_dashboards"


# (The OllamaClient and ReportParser classes remain exactly the same)
def read_file(file_path: Path) -> str:
    """A helper function to read a file."""
    try:
        return file_path.read_text(encoding='utf-8')
    except FileNotFoundError:
        print(f"⚠️ Report file not found at {file_path}. Returning empty string.")
        return ""
    except Exception as e:
        print(f"❌ Error reading {file_path}: {e}")
        return ""

class OllamaClient:
    def __init__(self, model: str = "llama3.2", host: Optional[str] = None):
        if host is None:
            host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        self.model = model
        self.host = host
        print(f"🤖 Ollama client configured for model '{self.model}' at {self.host}")

    def ask(self, prompt: str, system_prompt: str) -> Dict:
        try:
            response = requests.post(
                f"{self.host}/api/generate",
                json={
                    "model": self.model, "prompt": prompt, "system": system_prompt,
                    "stream": False, "format": "json", "options": {"temperature": 0.2}
                },
                timeout=180
            )
            response.raise_for_status()
            response_data = response.json()
            json_response_string = response_data.get("response", "{}")
            return json.loads(json_response_string)
        except requests.exceptions.RequestException as e:
            print(f"❌ Connection error with Ollama: {e}")
            return {"error": "Connection to Ollama failed.", "details": str(e)}
        except json.JSONDecodeError as e:
            raw_text = response.json().get("response", "") if 'response' in locals() else "Raw response not available."
            print(f"❌ Failed to parse JSON from Ollama: {e}\n   Raw response: {raw_text[:300]}...")
            return {"error": "Failed to parse AI JSON response.", "raw_text": raw_text}
        except Exception as e:
            print(f"❌ An unexpected error occurred in Ollama client: {e}")
            return {"error": "An unexpected error occurred.", "details": str(e)}

class ReportParser:
    def _read_json(self, file_path: Path) -> Optional[Any]:
        try:
            content = read_file(file_path)
            if not content: return None
            return json.loads(content)
        except json.JSONDecodeError as e:
            print(f"❌ Error parsing JSON from {file_path}: {e}")
            return None
        except Exception as e:
            print(f"❌ Error reading {file_path}: {e}")
            return None

    def parse_stats_report(self, file_path: Path) -> Dict[str, Dict[str, Any]]:
        stats_data = self._read_json(file_path)
        if not isinstance(stats_data, dict):
            print(f"✅ Parsed 0 DAGs from stats report (file empty or invalid).")
            return {}
        print(f"✅ Parsed {len(stats_data)} DAGs from the stats report.")
        return stats_data

    def parse_audit_report(self, file_path: Path) -> Dict[str, Dict[str, Any]]:
        audit_list = self._read_json(file_path)
        if not isinstance(audit_list, list):
            print(f"✅ Parsed 0 DAGs from audit report (file empty or invalid).")
            return {}
        audit_data = {item['dag_id']: item for item in audit_list if item.get('dag_id')}
        print(f"✅ Parsed {len(audit_data)} DAGs from audit report.")
        return audit_data

    def parse_analysis_report(self, file_path: Path) -> Dict[str, List[Dict[str, Any]]]:
        analysis_list = self._read_json(file_path)
        if not isinstance(analysis_list, list):
            print(f"✅ Parsed 0 log analyses (file empty or invalid).")
            return {}
        analysis_data = defaultdict(list)
        for item in analysis_list:
            dag_name = item.get('error', {}).get('dag_name')
            if dag_name:
                analysis_data[dag_name].append(item)
        print(f"✅ Parsed log analyses for {len(analysis_data)} DAGs.")
        return dict(analysis_data)

class IntelligentReportMerger:
    def __init__(self):
        self.client = OllamaClient()
        self.parser = ReportParser()

    def _collect_and_merge_data(self) -> Dict[str, Dict]:
        base_data = self.parser.parse_stats_report(REPORTS_DIR / "dag_stats.json")
        audit_data = self.parser.parse_audit_report(REPORTS_DIR / "dag_ai_audit.json")
        analysis_data = self.parser.parse_analysis_report(REPORTS_DIR / "log_analysis.json")
        
        dag_data = defaultdict(lambda: {"stats": {}, "code_audit": {}, "log_errors": []})
        all_dags = set(base_data.keys()) | set(audit_data.keys()) | set(analysis_data.keys())

        for dag_id in all_dags:
            if dag_id in base_data: dag_data[dag_id]['stats'] = base_data[dag_id]
            if dag_id in audit_data: dag_data[dag_id]['code_audit'] = audit_data[dag_id]
            if dag_id in analysis_data: dag_data[dag_id]['log_errors'].extend(analysis_data[dag_id])
        
        return dict(dag_data)

    def _run_ai_final_analysis(self, all_dag_data: Dict) -> Dict:
        analyzed_dags = {}
        for dag_id, data in all_dag_data.items():
            if dag_id == "unknown": continue
            print(f"  -> AI Analyzing: {dag_id}")
            data_summary = {
                "performance_stats": data.get("stats"),
                "code_audit": data.get("code_audit"),
                "recent_log_errors": [{"severity": e["severity"], "error": e["error"]["error_line"][:200]} for e in data.get("log_errors", [])]
            }
            prompt = f"""
            Analyze the comprehensive data for the Airflow DAG '{dag_id}'.
            Data: {json.dumps(data_summary, indent=2)}
            Provide a final analysis as a valid JSON object with these keys:
            - "executive_summary": A 2-3 sentence overview of the DAG's health, problems, and state.
            - "health_score": An integer score from 0 (broken) to 100 (perfect). Consider success rate, failure count, code risk.
            - "priority": Priority for attention: "CRITICAL", "HIGH", "MEDIUM", or "LOW".
            - "key_recommendations": A list of 2-3 specific, actionable recommendations.
            """
            system_prompt = "You are a Senior Airflow Operations Engineer. Provide a concise, actionable JSON summary for a DAG based on its performance stats, code quality, and runtime errors. Return a valid JSON object only."
            ai_result = self.client.ask(prompt, system_prompt)
            analyzed_dags[dag_id] = {"raw_data": data, "ai_analysis": ai_result}
        return analyzed_dags

    # --- START: THIS IS THE NEW METHOD ---
    def generate_dashboard_data(self) -> Dict[str, Dict]:
        """Merges all data sources and runs the final AI analysis to produce dashboard data."""
        print("🚀 Starting intelligent DAG data generation for dashboard...")
        
        # Step 1: Collect and merge raw data from reports
        dag_data = self._collect_and_merge_data()
        if not dag_data:
            print("❌ No DAG data found. Halting.")
            return {}

        # Step 2: Run the final AI analysis on the merged data
        print(f"📊 Processing {len(dag_data)} DAGs for final AI analysis...")
        analyzed_dags = self._run_ai_final_analysis(dag_data)
        
        print("✅ Dashboard data generated successfully.")
        return analyzed_dags
    # --- END: THIS IS THE NEW METHOD ---

    def generate_standalone_dashboard(self):
        """The main function to generate the final, portable HTML dashboard."""
        print("🚀 Starting intelligent DAG report generation...")
        
        dag_data = self._collect_and_merge_data()
        if not dag_data:
            print("❌ No DAG data found. Halting.")
            return

        print(f"📊 Processing {len(dag_data)} DAGs for final AI analysis...")
        analyzed_dags = self._run_ai_final_analysis(dag_data)

        try:
            template_content = TEMPLATE_HTML_PATH.read_text(encoding='utf-8')
        except FileNotFoundError:
            print(f"❌ ERROR: Template file not found at {TEMPLATE_HTML_PATH}")
            print("Please ensure 'dashboard_template.html' exists in the project root.")
            return

        data_as_json_string = json.dumps(analyzed_dags, indent=2)

        final_html = template_content.replace(
            "//__DASHBOARD_DATA_PLACEHOLDER__", data_as_json_string
        )

        # <<< MODIFIED: Create directory and generate unique filename
        # 1. Ensure the output directory exists
        DAILY_REPORTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        # 2. Create a filename with the current date
        timestamp = datetime.now().strftime("%Y-%m-%d")
        final_filename = f"dashboard_{timestamp}.html"
        final_path = DAILY_REPORTS_OUTPUT_DIR / final_filename

        # 3. Save the final, self-contained HTML file to the new path
        final_path.write_text(final_html, encoding='utf-8')
        
        print("="*50)
        print(f"✅ Success! Standalone dashboard created at: {final_path}")
        print("You can now find this file in the 'reports/daily_dashboards/' folder.")
        print("="*50)