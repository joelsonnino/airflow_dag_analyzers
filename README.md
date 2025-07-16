# 🔬 Airflow DAG Intelligence Dashboard

This project is a comprehensive suite of tools for static and dynamic analysis of Apache Airflow DAGs. It leverages an AI language model (like Llama 3.2) to perform code audits, analyze error logs, and calculate performance statistics. All insights are presented in an interactive web dashboard built with Streamlit.

## ✨ Key Features

-   **AI Code Audit**: Analyzes DAG source code to identify potential issues, bad practices, and security risks.
-   **Log Analysis**: Scans CloudWatch error logs, categorizes them, and provides AI-powered suggestions for resolution.
-   **Stat Reporter**: Calculates performance metrics from task instance logs, including success rates, failure counts, and more.
-   **Intelligent Report Merger**: Aggregates data from all sources and uses AI to generate an executive summary, a health score, and actionable recommendations for each DAG.
-   **Interactive Streamlit Dashboard**: A user-friendly web dashboard to explore, filter, and drill down into the health and performance of all your DAGs.

## 📂 Project Structure

```
.
├── analyzers/              # Core modules for analysis
│   ├── code_analyzer.py    # AI audit for DAG source code
│   ├── dag_utils.py        # Utility functions for DAGs
│   ├── data_reader.py      # Reads files from local or S3
│   ├── log_analyzer.py     # AI-powered error log analysis
│   ├── report_merger_agent.py # Aggregates reports and generates dashboard data
│   └── stat_reporter.py    # Generates stats from run history
├── reports/                # Output directory for generated reports
│   ├── dag_ai_audit.html
│   ├── dag_ai_audit.json
│   ├── dag_stats.html
│   ├── dag_stats.json
│   └── log_analysis.json
├── .gitignore              # Files and directories to be ignored by Git
├── docker-compose.yaml     # Docker configuration (if used)
├── requirements.txt        # Python dependencies
├── streamlit_dashboard.py  # The Streamlit dashboard application
└── README.md               # This file
```

## 🚀 Getting Started

### Prerequisites

-   Python 3.9+
-   Access to an Ollama-compatible AI model (e.g., Llama 3.2)
-   AWS credentials configured for accessing S3 and CloudWatch Logs

### Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/joelsonnino/airflow_dag_analyzers.git
    cd airflow_dag_analyzers
    ```

2.  **Create and activate a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use: venv\Scripts\activate
    ```

3.  **Install the dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## ⚙️ Usage

Ensure your environment is correctly configured with the necessary credentials and endpoints (e.g., AWS credentials, `OLLAMA_HOST` environment variable).

### 1. Run the Analyzers

Execute the individual analysis scripts to generate the raw JSON and HTML reports in the `reports/` directory.

```bash
# Run the code audit (ensure your S3 path is correct)
python -m analyzers.code_analyzer --dags-dir s3://your-dags-bucket/dags/

# Run the statistics reporter on CloudWatch task logs
python -m analyzers.stat_reporter --log-group-prefix your-airflow-environment-

# Run the error log analysis on CloudWatch task logs
python -m analyzers.log_analyzer --log-group "your-airflow-environment-Task"
```

### 2. Generate Dashboard Data

The `report_merger_agent.py` script aggregates all the JSON reports generated in the previous step and runs a final AI analysis to create the data needed for the dashboard.

```bash
# Run the agent to merge reports and apply the final AI analysis
python -m analyzers.report_merger_agent
```

This script will create a self-contained, timestamped HTML dashboard in the `reports/daily_dashboards/` folder.

### 3. Launch the Streamlit Dashboard

Once the analysis is complete, you can launch the interactive dashboard.

```bash
streamlit run streamlit_dashboard.py
```

Open your web browser and navigate to `http://localhost:8501` to view the dashboard.