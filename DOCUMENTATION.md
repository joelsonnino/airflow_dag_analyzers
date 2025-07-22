# 🔬 Airflow DAG Intelligence Dashboard - Comprehensive Documentation

## Table of Contents

1.  [Introduction](#1-introduction)
2.  [Purpose and Value Proposition](#2-purpose-and-value-proposition)
3.  [Key Features Explained](#3-key-features-explained)
4.  [System Architecture](#4-system-architecture)
    *   [Data Flow](#41-data-flow)
    *   [Component Breakdown](#42-component-breakdown)
5.  [Setup and Installation](#5-setup-and-installation)
    *   [Prerequisites](#51-prerequisites)
    *   [Installation Steps](#52-installation-steps)
6.  [Configuration](#6-configuration)
    *   [AWS Credentials](#61-aws-credentials)
    *   [Ollama Integration](#62-ollama-integration)
    *   [Log Group and S3 Paths](#63-log-group-and-s3-paths)
7.  [Usage Guide](#7-usage-guide)
    *   [Step 1: Running Individual Analyzers](#71-step-1-running-individual-analyzers)
    *   [Step 2: Generating Dashboard Data](#72-step-2-generating-dashboard-data)
    *   [Step 3: Launching the Streamlit Dashboard](#73-step-3-launching-the-streamlit-dashboard)
8.  [Detailed Component Documentation](#8-detailed-component-documentation)
    *   [`analyzers/data_reader.py`](#analyzersdata_readerpy)
    *   [`analyzers/dag_utils.py`](#analyzersdag_utilspy)
    *   [`analyzers/code_analyzer.py`](#analyzerscode_analyzerpy)
    *   [`analyzers/stat_reporter.py`](#analyzersstat_reporterpy)
    *   [`analyzers/log_analyzer.py`](#analyzerslog_analyzerpy)
    *   [`analyzers/report_merger_agent.py`](#analyzersreport_merger_agentpy)
    *   [`streamlit_dashboard.py`](#streamlit_dashboardpy)
9.  [Output Structure](#9-output-structure)
10. [Extensibility and Customization](#10-extensibility-and-customization)
    *   [Adding New Analysis Types](#adding-new-analysis-types)
    *   [Customizing AI Prompts](#customizing-ai-prompts)
    *   [Integrating Other Data Sources](#integrating-other-data-sources)
    *   [Dashboard Customization](#dashboard-customization)
11. [Troubleshooting](#11-troubleshooting)
12. [Future Enhancements](#12-future-enhancements)

---

## 1. Introduction

The Airflow DAG Intelligence Dashboard is a robust and innovative solution designed to provide deep insights into the health, performance, and code quality of Apache Airflow DAGs. By integrating static code analysis, dynamic log analysis, and performance metric reporting, this project offers a holistic view of your data orchestration pipelines. Its core strength lies in leveraging a local Large Language Model (LLM), such as Llama 3.2 via Ollama, to provide intelligent, actionable recommendations and executive summaries, transforming raw data into business-relevant intelligence.

## 2. Purpose and Value Proposition

In complex data ecosystems, managing the reliability and efficiency of Airflow DAGs is paramount. Manual audits are time-consuming, and scattered logs or metrics make holistic analysis challenging. This dashboard addresses these pain points by:

*   **Proactive Issue Detection**: Identifying potential code vulnerabilities, bad practices, or performance bottlenecks *before* they impact production.
*   **Accelerated Troubleshooting**: Providing AI-powered root cause analysis and suggested fixes for common runtime errors, significantly reducing mean time to recovery (MTTR).
*   **Performance Optimization**: Offering clear statistics on success rates, failures, and execution trends, enabling data engineers to optimize resource utilization and task scheduling.
*   **Centralized Insights**: Consolidating disparate data sources (code, logs, metrics) into a single, interactive dashboard for easy consumption by engineers, operations, and management.
*   **Intelligent Prioritization**: Assigning health scores and priority levels to DAGs based on a comprehensive AI assessment, allowing teams to focus on the most critical areas.

This tool transforms reactive firefighting into proactive pipeline management, enhancing operational efficiency and data product reliability.

## 3. Key Features Explained

*   **AI Code Audit (`analyzers/code_analyzer.py`)**:
    *   **Functionality**: Scans Python source code of Airflow DAGs. It identifies common anti-patterns, security risks (e.g., hardcoded credentials, unencrypted connections), performance inefficiencies (e.g., suboptimal task grouping, lack of `deferrable=True`), and adherence to best practices (e.g., proper error handling, retry mechanisms, XCom usage).
    *   **LLM Role**: An LLM (e.g., Llama 3.2) analyzes the code snippets and generates a summary, lists identified problems, assigns a risk level (LOW, MEDIUM, HIGH), and provides specific suggestions, including potential code fixes.
    *   **Output**: Structured JSON for programmatic access and an HTML report for human-readable review.

*   **Log Analysis (`analyzers/log_analyzer.py`)**:
    *   **Functionality**: Connects to AWS CloudWatch Logs (specifically Airflow Task logs) to fetch recent error events. It extracts critical error lines and their context.
    *   **LLM Role**: The LLM processes these error logs to categorize the error type, determine its severity (HIGH, MEDIUM, LOW), identify the root cause, and propose actionable solutions, including code fixes where applicable.
    *   **Output**: JSON format, ideal for feeding into the dashboard.

*   **Stat Reporter (`analyzers/stat_reporter.py`)**:
    *   **Functionality**: Queries CloudWatch Logs to collect task instance execution events over a specified look-back period. It aggregates these events to calculate vital performance metrics per DAG.
    *   **Metrics Captured**: Success rates, total runs, total failures, last run timestamps, and identification of the most frequently failing tasks.
    *   **Output**: JSON and HTML reports, providing raw statistical data.

*   **Intelligent Report Merger (`analyzers/report_merger_agent.py`)**:
    *   **Functionality**: This is the orchestration layer that brings all individual analysis reports together. It consumes the JSON outputs from the Code Audit, Log Analysis, and Stat Reporter.
    *   **LLM Role**: Performs a *final*, holistic AI analysis on the aggregated data for each DAG. This comprehensive analysis generates:
        *   An `executive_summary` of the DAG's overall health.
        *   A `health_score` (0-100) reflecting its reliability and quality.
        *   A `priority` level (CRITICAL, HIGH, MEDIUM, LOW) for immediate attention.
        *   `key_recommendations` – a consolidated list of actionable steps for improvement.
    *   **Output**: A single, self-contained JSON data structure used directly by the Streamlit dashboard. It also has the capability to generate a standalone HTML dashboard using a template.

*   **Interactive Streamlit Dashboard (`streamlit_dashboard.py`)**:
    *   **Functionality**: A user-friendly web interface built with Streamlit that visualizes the merged and AI-analyzed data.
    *   **Features**:
        *   **Overview Metrics**: High-level summaries (total DAGs, critical issues, average health).
        *   **DAG Health Overview**: A customizable grid of DAG cards, allowing quick prioritization based on health score and priority.
        *   **Detailed DAG View**: Drilling down into individual DAGs reveals specific AI analyses (summary, recommendations), performance metrics, code audit details, and recent error logs.
        *   **Filtering & Searching**: Allows users to filter DAGs by priority, health score, and search by name.
        *   **Export**: Enables downloading detailed reports for individual DAGs in Markdown or JSON format.

## 4. System Architecture

The architecture is designed for modularity, allowing individual components to be run independently or as part of the integrated pipeline.

```
+------------------+     +--------------------+     +-------------------+
| AWS S3 (DAGs)    |     | AWS CloudWatch     |     | LLM (Ollama)      |
|                  |     | (Task Logs)        |     |                   |
+--------+---------+     +----------+---------+     +---------+---------+
         |                        |                             |
         | (Code Files)           | (Log Events)                | (API Requests)
         v                        v                             v
+------------------+     +--------------------+     +-------------------+
| data_reader.py   |     | stat_reporter.py   |     | ollama_client     |
| (Local/S3)       |     | (CloudWatch)       |     | (in various       |
+------------------+     +--------------------+     | analyzers)        |
         |                        |                   +---------+---------+
         | (Python Code)          | (Performance Stats)         |
         v                        v                             |
+------------------+     +--------------------+                 |
| code_analyzer.py |     | log_analyzer.py    |                 |
| (AI Code Audit)  |     | (AI Log Analysis)  |<----------------+
+--------+---------+     +----------+---------+
         |                        |
         | (dag_ai_audit.json)    | (log_analysis.json)
         v                        v
+-------------------------------------------------+
| reports/                                        |
|   ├── dag_ai_audit.json                         |
|   ├── dag_stats.json                            |
|   └── log_analysis.json                         |
+-------------------------------------------------+
         | (Raw JSON Reports)
         v
+-------------------------------------------------+
| analyzers/report_merger_agent.py                |
| (Aggregates Reports, Performs Final AI Analysis)|
+--------+----------------------------------------+
         | (Combined Data JSON)
         v
+-------------------------------------------------+
| streamlit_dashboard.py                          |
| (Interactive Web UI)                            |
+-------------------------------------------------+
```

### 4.1. Data Flow

1.  **Ingestion**:
    *   DAG Python files are read from an S3 bucket (or local directory) by `data_reader.py` and passed to `code_analyzer.py`.
    *   CloudWatch log groups are queried by `stat_reporter.py` and `log_analyzer.py` to retrieve task execution events and error logs.
2.  **Analysis (Individual)**:
    *   `code_analyzer.py` utilizes the LLM (`OllamaClient`) to perform static code audits.
    *   `stat_reporter.py` processes raw log events into structured performance metrics.
    *   `log_analyzer.py` identifies errors and uses the LLM (`OllamaClient`) for root cause analysis and suggested solutions.
3.  **Intermediate Storage**: All individual analysis results are stored as JSON files in the `reports/` directory (`dag_ai_audit.json`, `dag_stats.json`, `log_analysis.json`).
4.  **Aggregation and Final AI Analysis**:
    *   `report_merger_agent.py` reads these intermediate JSON files.
    *   For each DAG, it compiles a comprehensive data object.
    *   It then invokes the LLM (`OllamaClient`) one final time to generate an executive summary, health score, priority, and consolidated recommendations based on all available data.
5.  **Visualization**:
    *   `streamlit_dashboard.py` loads the fully analyzed and merged data (via `report_merger_agent.py`'s `generate_dashboard_data` method).
    *   It renders this data in an interactive web interface, allowing users to explore, filter, and drill down into DAG insights.

### 4.2. Component Breakdown

*   **`analyzers/`**: Contains the core logic for different analysis types.
    *   `code_analyzer.py`: Orchestrates the AI code audit.
    *   `dag_utils.py`: Helper functions for extracting DAG metadata from log streams and code.
    *   `data_reader.py`: Handles file reading from both local paths and S3.
    *   `log_analyzer.py`: Manages CloudWatch log fetching and AI-powered error analysis.
    *   `report_merger_agent.py`: The central orchestrator for merging reports and performing the final AI synthesis.
    *   `stat_reporter.py`: Gathers and processes performance statistics from CloudWatch.
*   **`reports/`**: Default output directory for all generated JSON and HTML reports. Includes a `daily_dashboards/` sub-directory for timestamped, self-contained HTML dashboards.
*   **`.gitignore`**: Standard Git ignore file.
*   **`docker-compose.yaml`**: (If used) Defines the Docker services for the application, likely including Ollama.
*   **`requirements.txt`**: Specifies all Python dependencies.
*   **`streamlit_dashboard.py`**: The Streamlit application responsible for the interactive web dashboard.
*   **`README.md`**: Top-level project overview.

## 5. Setup and Installation

### 5.1. Prerequisites

Before starting, ensure you have the following installed and configured:

1.  **Python**: Version 3.9 or higher.
2.  **Git**: For cloning the repository.
3.  **Ollama**: Install Ollama from [ollama.com](https://ollama.com/).
    *   After installation, pull the required LLM model (e.g., Llama 3.2). For example:
        ```bash
        ollama pull llama3.2
        ```
    *   Ensure Ollama is running and accessible (default: `http://localhost:11434`).
4.  **AWS Credentials**: Configure your AWS CLI or environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `AWS_REGION`) with permissions to:
    *   Read from your S3 bucket containing DAG files.
    *   Read from specified CloudWatch Logs groups.

### 5.2. Installation Steps

1.  **Clone the repository**:
    ```bash
    git clone https://github.com/joelsonnino/airflow_dag_analyzers.git
    cd airflow_dag_analyzers
    ```

2.  **Create and activate a virtual environment (recommended)**:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use: venv\Scripts\activate
    ```

3.  **Install Python dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## 6. Configuration

### 6.1. AWS Credentials

The `boto3` library (used by `data_reader.py`, `stat_reporter.py`, `log_analyzer.py`) automatically picks up AWS credentials from standard locations:

*   Environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`).
*   Shared credential file (`~/.aws/credentials`).
*   AWS CLI configuration file (`~/.aws/config`).
*   IAM roles for EC2 instances.

Ensure the user/role associated with these credentials has:
*   `s3:GetObject` and `s3:ListBucket` permissions on your DAGs S3 bucket and prefix.
*   `logs:FilterLogEvents`, `logs:DescribeLogGroups` permissions on relevant CloudWatch Log Groups.

### 6.2. Ollama Integration

*   **`OLLAMA_HOST` Environment Variable**: By default, the `OllamaClient` attempts to connect to `http://localhost:11434`. If your Ollama server is running on a different host or port, set the `OLLAMA_HOST` environment variable accordingly:
    ```bash
    export OLLAMA_HOST="http://your-ollama-host:port"
    ```
    If running within a Docker container and Ollama is on the host machine, you might need to set it to `http://host.docker.internal:11434` as suggested in `code_analyzer.py`.
*   **Model Selection**: The default LLM model is `llama3.2`. This can be overridden using the `--model` argument when running `code_analyzer.py`, `log_analyzer.py`, or by modifying the `OllamaClient` instantiation in `report_merger_agent.py` or `streamlit_dashboard.py` if needed. Ensure the selected model is pulled in your Ollama instance (`ollama pull <model_name>`).

### 6.3. Log Group and S3 Paths

*   **DAGs S3 Directory (`--dags-dir`)**: Specify the S3 path where your Airflow DAG Python files are stored when running `code_analyzer.py`. Example: `s3://your-airflow-bucket/dags/`.
*   **CloudWatch Log Group Prefix (`--log-group-prefix`)**: Used by `stat_reporter.py` to auto-detect relevant task log groups. Airflow task logs often follow a pattern like `airflow-<env_name>-Task`.
*   **Specific CloudWatch Log Group (`--log-group`)**: Used by `log_analyzer.py` to target a specific CloudWatch log group for error analysis. This should typically be the consolidated task log group for your Airflow environment.

## 7. Usage Guide

This section details the step-by-step process to generate and view the DAG Intelligence Dashboard.

### 7.1. Step 1: Running Individual Analyzers

Execute these scripts sequentially to generate the initial raw JSON reports in the `reports/` directory. Adjust parameters as per your environment.

**a. Run the Code Audit:**
Scans your DAG Python files for best practices, potential issues, and security risks.

```bash
python -m analyzers.code_analyzer --dags-dir s3://your-airflow-dags-bucket/dags/ --output reports/dag_ai_audit --max 50
```
*   `--dags-dir`: The S3 path to your DAGs. Replace `s3://your-airflow-dags-bucket/dags/` with your actual path. Can also be a local directory path.
*   `--output`: Base name for the output JSON and HTML files. Default is `reports/dag_ai_audit`.
*   `--max`: Maximum number of DAG files to analyze (useful for testing or large environments).

**b. Run the Statistics Reporter:**
Collects performance metrics (success rates, failures) from your CloudWatch task logs.

```bash
python -m analyzers.stat_reporter --log-group-prefix your-airflow-environment- --output reports/dag_stats --hours 72
```
*   `--log-group-prefix`: The prefix for your Airflow task log groups in CloudWatch. E.g., if your log groups are `airflow-prod-Task`, `airflow-dev-Task`, use `airflow-`.
*   `--output`: Base name for the output JSON and HTML files. Default is `reports/dag_stats`.
*   `--hours`: Look-back window for log data in hours. Default is 48 hours.

**c. Run the Error Log Analysis:**
Fetches recent errors from CloudWatch and uses AI to provide root cause analysis and solutions.

```bash
python -m analyzers.log_analyzer --log-group your-airflow-environment-Task --output reports/log_analysis --hours 24 --max-errors 100
```
*   `--log-group`: The specific CloudWatch log group containing Airflow task errors. This is typically the `-Task` group for your environment.
*   `--output`: Base name for the output JSON and HTML files. Default is `reports/log_analysis`.
*   `--hours`: Look-back window for error logs in hours.
*   `--max-errors`: Maximum number of individual errors to analyze (AI calls can be resource-intensive).

### 7.2. Step 2: Generating Dashboard Data

This step merges the reports from the previous step and performs the final AI analysis to prepare data for the Streamlit dashboard.

```bash
python -m analyzers.report_merger_agent
```
*   This script will read `reports/dag_ai_audit.json`, `reports/dag_stats.json`, and `reports/log_analysis.json`.
*   It will perform the final AI analysis and consolidate all data into a structure accessible by Streamlit.
*   It also generates a self-contained, timestamped HTML dashboard file in `reports/daily_dashboards/`. This file is static and can be shared.

### 7.3. Step 3: Launching the Streamlit Dashboard

Once the `report_merger_agent.py` has completed, the `streamlit_dashboard.py` can be launched. It will dynamically load the data generated by the merger agent.

```bash
streamlit run streamlit_dashboard.py
```
*   Open your web browser and navigate to the URL provided by Streamlit (typically `http://localhost:8501`).
*   The dashboard will load the latest analyzed data.

## 8. Detailed Component Documentation

### `analyzers/data_reader.py`

This module provides a unified interface for reading Python files from both local file systems and S3 buckets, abstracting away the underlying storage details.

*   **`is_s3_path(path: str) -> bool`**:
    *   Checks if a given path string starts with "s3://".
*   **`parse_s3_path(s3_path: str) -> Tuple[str, str]`**:
    *   Parses an S3 URI (e.g., `s3://bucket-name/prefix/key.py`) into its bucket name and key/prefix components.
*   **`list_py_files(path: str) -> List[str]`**:
    *   Lists all `.py` files under the specified path.
    *   For local paths, it uses `Path.rglob()`.
    *   For S3 paths, it uses `boto3`'s `list_objects_v2` paginator. It also includes an optional in-memory filter to check for "DAG" string to focus on potential DAG files.
*   **`read_file(path: str) -> str`**:
    *   Reads the entire content of a file (local or S3) into a string. Handles decoding with `utf-8` and `errors='ignore'`.
*   **`read_lines(path: str) -> List[str]`**:
    *   Reads a file line by line.

### `analyzers/dag_utils.py`

Contains utility functions for extracting common Airflow metadata from code and log streams.

*   **`extract_dag_ids_from_code(code: str) -> List[str]`**:
    *   Uses Python's `ast` module for safe parsing of DAG Python code.
    *   Identifies `dag_id` arguments in `DAG()` or `models.DAG()` calls.
    *   Returns a list of `dag_id` strings found in the code. Robust against basic syntax errors.
*   **`extract_info_from_log_stream(log_stream_name: str) -> Tuple[str, str, str]`**:
    *   Parses standard Airflow CloudWatch log stream names (e.g., `dag_id/task_id/run_id/try.log` or `dag_id=.../task_id=.../run_id=.../1.log`).
    *   Extracts `dag_id`, `task_id`, and `run_id`. Returns "unknown" for parts that cannot be parsed.

### `analyzers/code_analyzer.py`

This module performs static code analysis on Airflow DAG files using an LLM.

*   **`OllamaClient` class**:
    *   Initializes with an Ollama model (`llama3.2` default) and host URL.
    *   `ask(prompt: str, system_prompt: str) -> dict`: Sends a request to the Ollama API, expecting a JSON response. Includes robust error handling for API calls and JSON parsing.
*   **`analyze_dag_code(file_path: Path, code: str, client: OllamaClient, dag_id: str) -> dict`**:
    *   Constructs a detailed prompt for the LLM, including the DAG's source code and specific instructions for analysis (summary, problems, risk level, suggestions, code fix).
    *   Calls the `OllamaClient` to get the AI analysis.
    *   Ensures the `dag_id` is correctly attributed in the result.
*   **`save_results_as_json(results: List[Dict], output_file: str)`**:
    *   Writes the list of AI audit results to a JSON file.
*   **`generate_html(results: List[dict], output_path: str)`**:
    *   Creates a human-readable HTML report summarizing the code audit findings, including styling for risk levels.

### `analyzers/stat_reporter.py`

Focuses on extracting and summarizing performance statistics from CloudWatch Task logs.

*   **`find_task_log_groups(prefix: str) -> List[str]`**:
    *   Uses `boto3` to discover CloudWatch log groups matching a given prefix and ending with `-Task` (standard Airflow task log convention).
*   **`fetch_cloudwatch_events(log_groups: List[str], start_time: datetime, end_time: datetime, max_events: int) -> List[Dict]`**:
    *   Retrieves log events from specified CloudWatch log groups within a time range.
    *   Uses pagination to fetch a large number of events efficiently.
*   **`parse_events(events: List[Dict]) -> Dict[str, Dict[str, Any]]`**:
    *   Processes raw log events.
    *   Identifies task success/failure markers using regex.
    *   Uses `extract_info_from_log_stream` from `dag_utils` to associate events with DAGs and tasks.
    *   Aggregates statistics such as `Total_Runs`, `Success_Rate`, `Total_Failures`, `Last_Run`, and `Most_Failing_Task`.
*   **`save_stats_as_json(stats_data: dict, output_file: str)`**:
    *   Saves the aggregated statistics to a JSON file.
*   **`generate_html_report(stats_data: dict, output: Path)`**:
    *   Generates a simple HTML table visualization of the performance statistics.

### `analyzers/log_analyzer.py`

Performs AI-powered analysis of error logs from CloudWatch.

*   **`LogError` dataclass**:
    *   Defines the structure for extracted error information (DAG/task name, error line, context, type).
*   **`ErrorAnalysis` dataclass**:
    *   Defines the structure for the AI-generated analysis of an error (category, severity, suggestion, code fix, etc.).
*   **`OllamaClient` class**: (Similar to `code_analyzer.py` but includes availability check).
    *   `is_available() -> bool`: Checks if the Ollama server is running and the specified model is loaded.
    *   `generate(prompt: str, system_prompt: str) -> str`: Sends prompt to Ollama, expecting a text response (which is then parsed as JSON).
*   **`DAGLogAnalyzer` class**:
    *   `extract_errors_from_cloudwatch(...) -> List[LogError]`: Queries CloudWatch for logs matching an "ERROR" filter pattern. Extracts structured `LogError` objects, including log stream name parsing via `dag_utils`.
    *   `_classify_error(error_line: str) -> str`: Categorizes errors based on predefined regex patterns (e.g., `ModuleNotFoundError` -> `IMPORT_ERROR`).
    *   `analyze_error_with_ai(error: LogError) -> ErrorAnalysis`:
        *   Constructs a detailed prompt with error context for the LLM.
        *   Instructs the LLM to provide root cause, solution steps, code fix, and prevention tips in JSON format.
        *   Robustly parses the LLM's response, handling cases where the response isn't perfectly formed JSON.
    *   `analyze_all_errors(errors: List[LogError], max_workers: int) -> List[ErrorAnalysis]`:
        *   Processes multiple `LogError` objects in parallel using `ThreadPoolExecutor` to speed up AI calls.
    *   `generate_summary_report(analyses: List[ErrorAnalysis]) -> str`:
        *   Aggregates statistics from all error analyses (e.g., total errors, high-severity count, errors per category/DAG).
        *   Uses the LLM to generate an executive summary and high-level recommendations based on the aggregated error data.
*   **`save_analyses_as_json(analyses: List[ErrorAnalysis], output_file: str)`**:
    *   Saves the list of `ErrorAnalysis` objects to a JSON file.
*   **`generate_analysis_html_report(...)`**: (Placeholder in provided code, actual implementation would render a detailed HTML report of error analyses).

### `analyzers/report_merger_agent.py`

This is the integration and final intelligence layer of the dashboard.

*   **`_collect_and_merge_data() -> Dict[str, Dict]`**:
    *   Reads `dag_stats.json`, `dag_ai_audit.json`, and `log_analysis.json` using `ReportParser`.
    *   Merges these disparate data sources into a single dictionary, keyed by `dag_id`, where each DAG contains its `stats`, `code_audit`, and `log_errors` raw data.
*   **`_run_ai_final_analysis(all_dag_data: Dict) -> Dict`**:
    *   Iterates through each merged DAG's data.
    *   Constructs a comprehensive prompt including performance stats, code audit findings, and recent error summaries.
    *   Calls the `OllamaClient` to perform the *final* AI analysis, generating the `executive_summary`, `health_score`, `priority`, and `key_recommendations`.
    *   This is the critical step where cross-domain intelligence is generated.
*   **`generate_dashboard_data() -> Dict[str, Dict]`**: **(Primary method for Streamlit)**
    *   This public method orchestrates the data collection and final AI analysis.
    *   It returns the fully processed and enriched dictionary of DAG data, which `streamlit_dashboard.py` consumes directly.
*   **`generate_standalone_dashboard()`**: (Legacy method for standalone HTML)
    *   This method generates a single, self-contained HTML file (using `dashboard_template.html`) that embeds all the AI-analyzed DAG data directly into JavaScript.
    *   The HTML file is timestamped and saved in `reports/daily_dashboards/`, making it easily portable and shareable.

### `streamlit_dashboard.py`

The interactive web application layer built with Streamlit.

*   **`st.set_page_config(...)`**: Configures the Streamlit page layout and appearance.
*   **Custom CSS**: Enhances the visual appeal with custom styling for cards, headers, and priority indicators.
*   **`@st.cache_data load_data()`**:
    *   A cached function that calls `IntelligentReportMerger().generate_dashboard_data()`. This caching prevents re-running the heavy AI analysis every time the Streamlit app updates, significantly improving performance.
*   **`get_priority_config(priority)`**: Maps priority strings (CRITICAL, HIGH, etc.) to emojis, colors, and CSS classes for consistent styling.
*   **`get_health_status(score)`**: Maps health scores to descriptive statuses (Excellent, Good, Warning, Critical) and corresponding colors/classes.
*   **`create_health_gauge(score, title)`**: Generates a Plotly gauge chart for visualizing the health score.
*   **`generate_markdown_report(dag_id, dag_content)`**:
    *   **NEW**: Dynamically creates a comprehensive Markdown report for a selected DAG, suitable for download.
*   **`generate_json_report(dag_content)`**:
    *   **NEW**: Converts the full DAG content dictionary into a pretty-printed JSON string for download.
*   **`display_overview_metrics(all_dags_data)`**: Displays high-level aggregated metrics using Streamlit's `st.metric`.
*   **`display_dag_grid(filtered_dags)`**:
    *   Presents DAGs in an intuitive grid layout with summary information.
    *   Provides "Details" and "Analytics" buttons to navigate to a specific DAG's detailed view.
*   **`display_dag_details(dag_id, dag_content)`**:
    *   Shows a detailed breakdown for a selected DAG, including:
        *   Health gauge, key metrics (Success Rate, Last Run).
        *   AI-generated executive summary and recommendations (expandable).
        *   Tabs for **Performance** (via `display_performance_stats`), **Code Audit** (via `display_code_audit`), **Error Logs** (via `display_error_logs`), and **Trends** (via `display_trends_analysis`).
        *   **NEW**: "Export Report" popover with Markdown and JSON download options.
*   **`display_performance_stats(stats)`**: Renders a DataFrame and bar chart of performance metrics. **Includes a fix to robustly handle mixed data types for `st.dataframe` by converting the 'Value' column to string.**
*   **`display_code_audit(audit)`**: Displays code audit findings, including risk level, summary, problems, and suggested code fixes.
*   **`display_error_logs(logs)`**: Presents a list of recent errors with AI-suggested solutions in expandable sections.
*   **`display_trends_analysis(dag_id, stats)`**: A placeholder for future historical trend visualization.
*   **`create_sidebar()`**: Manages the Streamlit sidebar for filtering (search, priority, health score) and navigation.
*   **`main()`**: The main execution flow of the Streamlit application, handling state management for navigation between overview and detailed DAG views, and applying filters.

## 9. Output Structure

All generated reports are stored within the `reports/` directory:

```
reports/
├── dag_ai_audit.html       # HTML report of AI code audit findings
├── dag_ai_audit.json       # Structured JSON data from AI code audit
├── dag_stats.html          # HTML report of DAG performance statistics
├── dag_stats.json          # Structured JSON data from DAG performance statistics
├── log_analysis.json       # Structured JSON data from AI error log analysis
└── daily_dashboards/
    └── dashboard_YYYY-MM-DD.html # Self-contained HTML dashboard with embedded data (timestamped)
```

The `daily_dashboards/` folder is designed to store historical snapshots of your dashboard data, each as a single HTML file, allowing for easy archiving and distribution of daily insights.

## 10. Extensibility and Customization

The modular design allows for significant extensibility and customization:

### Adding New Analysis Types

*   **New Data Sources**: Implement a new `_read_X_report` method in `ReportParser` for your data source.
*   **New Analyzers**: Create a new Python script (e.g., `analyzers/my_new_analyzer.py`) that outputs JSON in a structured format.
*   **Integration**: Modify `report_merger_agent.py` to include your new JSON report in `_collect_and_merge_data()` and potentially enhance the `_run_ai_final_analysis()` prompt to incorporate these new insights.
*   **Dashboard**: Add new tabs or sections in `streamlit_dashboard.py` to visualize the new data.

### Customizing AI Prompts

*   The LLM prompts are defined within `code_analyzer.py`, `log_analyzer.py`, and `report_merger_agent.py`.
*   You can fine-tune these prompts to:
    *   Request different types of analysis.
    *   Adjust verbosity or tone.
    *   Incorporate specific organizational best practices or security standards into the audit.
    *   Change the output JSON schema (remember to update Python parsing logic accordingly).

### Integrating Other Data Sources

*   **Airflow Metadata Database**: Extend `stat_reporter.py` or create a new analyzer to query the Airflow database directly for task instance details, DAG run durations, etc., for richer historical data beyond CloudWatch logs.
*   **Monitoring Tools**: Integrate with Prometheus, Grafana, or other monitoring systems to pull in CPU/memory usage for tasks, operator-specific metrics, etc.

### Dashboard Customization

*   **UI/UX**: Modify the custom CSS in `streamlit_dashboard.py` to match your organization's branding or preferred aesthetics.
*   **Visualization Types**: Experiment with different Plotly chart types or Streamlit components to visualize data in new ways.
*   **Filtering Logic**: Enhance filter options in the sidebar for more granular control over DAG selection.

## 11. Troubleshooting

*   **`Error: Ollama is not running or model 'llama3.2' is not available.`**:
    *   **Solution**: Ensure Ollama is running (`ollama serve`) and that the `llama3.2` model (or your specified model) has been pulled (`ollama pull llama3.2`). Check `OLLAMA_HOST` environment variable if Ollama is not on `localhost:11434`.
*   **`Connection to Ollama failed.` or `Failed to parse JSON from Ollama.`**:
    *   **Solution**: This usually indicates an issue with the Ollama server or an unexpected response format.
        *   Verify Ollama is running and accessible from the machine running the analyzers.
        *   Check Ollama server logs for errors.
        *   Ensure the model can process the requests within the timeout. Large prompts or complex requests might require more time or resources from the LLM. Increase `timeout` in `OllamaClient` if necessary.
*   **`No DAG data found.` (from `report_merger_agent.py` or `streamlit_dashboard.py`)**:
    *   **Solution**: Ensure the individual analyzer scripts (`code_analyzer.py`, `stat_reporter.py`, `log_analyzer.py`) have been run successfully and generated their respective JSON files in the `reports/` directory. Check file paths and permissions.
*   **`Error parsing JSON from ...`**:
    *   **Solution**: The output JSON file from a previous analyzer might be corrupted or empty. Check the raw file for valid JSON syntax. This can happen if an AI call fails or returns non-JSON text. Re-run the specific analyzer.
*   **AWS Permissions Errors**:
    *   **Solution**: Ensure your AWS credentials have the necessary `s3:GetObject`, `s3:ListBucket`, `logs:FilterLogEvents`, and `logs:DescribeLogGroups` permissions for the target resources.
*   **Empty Dashboard**:
    *   **Solution**: If the dashboard shows no data after running all steps, verify that your S3 DAGs directory and CloudWatch log groups actually contain data and match the specified prefixes/names. Also, check the `reports/` directory for generated `.json` files.
*   **`pyarrow.lib.ArrowTypeError` or similar DataFrame errors in Streamlit**:
    *   **Solution**: This often occurs when a DataFrame column has mixed data types, and Streamlit (or underlying libraries) expects a uniform type. The fix already implemented in `display_performance_stats` (`df['Value'] = df['Value'].astype(str)`) addresses this. If new data types are introduced, ensure they are handled robustly (e.g., explicit type casting before creating DataFrames).

## 12. Future Enhancements

*   **Historical Trends**: Implement true historical data storage (e.g., into a local SQLite DB or external time-series DB) to visualize DAG performance trends over longer periods.
*   **Alerting Integration**: Add functionality to send notifications (e.g., Slack, Email) for critical DAG health changes or new high-priority issues detected.
*   **Advanced Filtering**: Implement more sophisticated filtering options, such as filtering by owner, tag, or specific Airflow versions.
*   **Machine Learning for Anomaly Detection**: Beyond rule-based AI, integrate ML models to detect anomalous behavior in DAG execution times or failure rates.
*   **Cost Analysis**: Incorporate cost metrics (e.g., related to resource consumption or external service calls) into the DAG analysis.
*   **Multi-environment Support**: Enhance the dashboard to easily switch between different Airflow environments.
*   **Interactive Code Viewer**: Integrate a code viewer directly into the dashboard to display the DAG code alongside the audit findings.
*   **Authentication/Authorization**: For production deployments, add user authentication and role-based access control.
*   **Dockerization**: Provide a complete Docker Compose setup that bundles Ollama, the analyzers, and the dashboard for easier deployment.
