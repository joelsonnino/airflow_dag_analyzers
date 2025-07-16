import ast
from typing import List, Tuple

def extract_dag_ids_from_code(code: str) -> List[str]:
    """
    Safely parses Python code using AST to find all dag_id declarations.
    """
    dag_ids = []
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                # Handles both DAG(...) and models.DAG(...)
                if (isinstance(func, ast.Name) and func.id == "DAG") or \
                   (isinstance(func, ast.Attribute) and func.attr == "DAG"):
                    # Find the 'dag_id' keyword argument
                    for kw in node.keywords:
                        if kw.arg == "dag_id" and isinstance(kw.value, ast.Str):
                            dag_ids.append(kw.value.s)
    except Exception as e:
        # Avoid crashing on syntax errors in the scanned file
        print(f"  [Warning] Could not parse a file with AST: {e}")
        pass
    return dag_ids

def extract_info_from_log_stream(log_stream_name: str) -> Tuple[str, str, str]:
    """
    Extracts dag_id, task_id, and run_id from an Airflow log stream name.
    Handles formats like:
    - dag_id/task_id/run_id/try.log
    - dag_id=my_dag/task_id=my_task/run_id=.../1.log (common in some setups)
    """
    parts = log_stream_name.split('/')
    if len(parts) < 3:
        return "unknown", "unknown", "unknown"

    # Clean up key=value format if it exists
    dag_id = parts[0].split('=')[-1]
    task_id = parts[1].split('=')[-1]
    run_id = parts[2] # The run_id often contains timestamps and is fine as is

    return dag_id, task_id, run_id