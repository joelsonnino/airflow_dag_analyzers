import subprocess
import os
import sys
from pathlib import Path

# --- Environment Configuration ---
# !!! IMPORTANT: Modify these values to match your setup !!!

# S3 path where your Airflow DAG Python files are stored (e.g., s3://your-bucket/dags/)
S3_DAGS_DIR = "s3://buff-analytics-dags/dags/" 

# Prefix for your CloudWatch Log Groups for Airflow tasks (e.g., airflow-prod-, if your log groups are airflow-prod-Task)
LOG_GROUP_PREFIX = "airflow-" 

# Exact name of the CloudWatch Log Group for error log analysis (e.g., airflow-prod-Task)
LOG_GROUP_NAME = "airflow-Airflow-14-12-22-Task" 

# URL of your Ollama server (usually doesn't change if Ollama is local)
OLLAMA_HOST = "http://localhost:11434"

# Llama model to use with Ollama (ensure it's already downloaded with `ollama pull <model_name>`)
OLLAMA_MODEL = "llama3.2"

# Number of hours to look back for stat_reporter
STAT_REPORTER_HOURS = 48

# Number of hours to look back for log_analyzer
LOG_ANALYZER_HOURS = 24

# --- End Configuration ---

def run_command(command, step_name):
    """Executes a command and handles errors, streaming output in real-time."""
    print(f"\n--- Starting: {step_name} ---")
    print(f"Command: {' '.join(command)}")
    try:
        # Key change: Use stdout=sys.stdout and stderr=sys.stderr for real-time streaming
        # This pipes the subprocess's output directly to the parent script's output
        process = subprocess.run(command, check=True, stdout=sys.stdout, stderr=sys.stderr)
        
        # We no longer need to print process.stdout/stderr here, as they were streamed live
        print(f"\n--- Finished: {step_name} - Successfully Completed ---")
        return True
    except subprocess.CalledProcessError as e:
        print(f"\n--- Error: {step_name} - Failed ---")
        print(f"Command '{' '.join(e.cmd)}' returned non-zero exit code {e.returncode}.")
        # Note: e.stdout and e.stderr will be None here because output was streamed.
        # The actual error output should have been visible on the console already.
        return False
    except FileNotFoundError:
        print(f"\n--- Error: {step_name} - Failed ---")
        print(f"The command '{command[0]}' was not found. Ensure 'python' is in your PATH or the virtual environment is activated.")
        return False
    except Exception as e:
        print(f"\n--- Unexpected Error: {step_name} - Failed ---")
        print(f"An unexpected error occurred: {e}")
        return False

def check_ollama_availability(host, model):
    """Checks if Ollama is running and the specified model is available."""
    print(f"🔍 Checking Ollama availability at {host} with model {model}...")
    try:
        import requests
        response = requests.get(f"{host}/api/tags", timeout=10)
        response.raise_for_status() # Raise an exception for HTTP 4xx/5xx status codes
        models_data = response.json().get('models', [])
        if not any(m['name'].startswith(model) for m in models_data):
            print(f"❌ Error: Model '{model}' is not found in Ollama. Download it with 'ollama pull {model}'.")
            return False
        print("✅ Ollama is available and the model is loaded.")
        return True
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection error to Ollama. Ensure Ollama is running at {host}.")
        return False
    except requests.exceptions.Timeout:
        print(f"❌ Timeout connecting to Ollama at {host}. Server might be overloaded or slow.")
        return False
    except Exception as e:
        print(f"❌ Unexpected error during Ollama check: {e}")
        return False

def main():
    print("🚀 Starting the complete Airflow DAG analysis process (Python Orchestrator)...")
    print("--------------------------------------------------------------------------------------")

    # Ensure we are in the project's root directory
    script_dir = Path(__file__).resolve().parent
    os.chdir(script_dir)
    print(f"Changed working directory to: {os.getcwd()}")

    # Adjust PATH to include virtual environment's bin/Scripts if detected
    if os.environ.get("VIRTUAL_ENV"):
        venv_bin_path = Path(os.environ["VIRTUAL_ENV"]) / "bin"
        if sys.platform == "win32":
            venv_bin_path = Path(os.environ["VIRTUAL_ENV"]) / "Scripts"
        os.environ["PATH"] = str(venv_bin_path) + os.pathsep + os.environ["PATH"]
        print(f"PATH updated to include virtual environment: {venv_bin_path}")
    else:
        print("⚠️ Warning: No virtual environment detected. Ensure dependencies are installed globally or activate your virtual environment manually.")

    # Check Ollama availability
    if not check_ollama_availability(OLLAMA_HOST, OLLAMA_MODEL):
        print("Process terminated due to Ollama unavailability.")
        sys.exit(1)

    # Set OLLAMA_HOST environment variable for child processes
    os.environ["OLLAMA_HOST"] = OLLAMA_HOST

    # Commands to execute in sequence
    commands = [
        {
            "name": "Code Analyzer",
            "cmd": [
                sys.executable, "-m", "analyzers.code_analyzer",
                "--dags-dir", S3_DAGS_DIR,
                "--output", "reports/dag_ai_audit"
            ]
        },
        {
            "name": "Stat Reporter",
            "cmd": [
                sys.executable, "-m", "analyzers.stat_reporter",
                "--log-group-prefix", LOG_GROUP_PREFIX,
                "--output", "reports/dag_stats",
                "--hours", str(STAT_REPORTER_HOURS)
            ]
        },
        {
            "name": "Log Analyzer",
            "cmd": [
                sys.executable, "-m", "analyzers.log_analyzer",
                "--log-group", LOG_GROUP_NAME,
                "--output", "reports/log_analysis",
                "--model", OLLAMA_MODEL,
                "--ollama-url", OLLAMA_HOST,
                "--hours", str(LOG_ANALYZER_HOURS)
            ]
        },
        {
            "name": "Report Merger Agent",
            "cmd": [
                sys.executable, "-m", "analyzers.report_merger_agent"
            ]
        }
    ]

    for cmd_info in commands:
        if not run_command(cmd_info["cmd"], cmd_info["name"]):
            print(f"\n❌ Process stopped. {cmd_info['name']} failed.")
            sys.exit(1)

    print("\n--------------------------------------------------------------------------------------")
    print("✅ All analyzers executed successfully!")
    print("JSON and HTML reports have been generated in the 'reports/' folder.")
    print("A standalone HTML dashboard is available in 'reports/daily_dashboards/' folder.")
    print("Now you can launch the Streamlit dashboard with: 'streamlit run streamlit_dashboard.py'")
    print("--------------------------------------------------------------------------------------")

if __name__ == "__main__":
    # Ensure 'requests' is installed for the Ollama check
    try:
        import requests
    except ImportError:
        print("Error: The 'requests' module is not installed. Please run 'pip install requests'.")
        sys.exit(1)
        
    main()